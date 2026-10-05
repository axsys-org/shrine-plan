#include "plan/bytecode.h"
#include "stdio.h"
#include "inttypes.h"
#include "stdlib.h"
#include <string.h>

#include "internal.h"
#include "plan/nat.h"

/*
 * Decode a compiled code row into an executable pl_code.
 *
 * The walk below is the single validation point for compiled programs:
 * exec trusts the decoded stream (its checks are debug-only), so every
 * opcode, operand count, and bane is verified here, and a malformed
 * program fails the decode — the law simply stays interpreted.
 *
 * It is also where PL_BAN_PRIM_KNOWN thunks get their primop resolved:
 * the compiler emits the opset pin and the op-name nat as two inline
 * operands after the bane (a pure shape check on its side); we resolve
 * (opset, name, argc) through pl_op_lookup once and overwrite the pin
 * operand with the pl_ops index in this malloc'd copy.  The pinned
 * canonical row keeps the symbolic form, so content addressing and
 * snapshots are unaffected.
 */

/* These opcodes exist only in the validated, private decoded stream. */
static pl_op numeric_opcode(uint32_t idx, bool tail) {
  const pl_opdesc* d = &pl_ops[idx];
  if (d->opset == 66 && d->argc == 2) {
    if (d->name == ax_s3('A', 'd', 'd'))
      return tail ? OP_TAIL_ADD : OP_ADD;
    if (d->name == ax_s3('S', 'u', 'b'))
      return tail ? OP_TAIL_SUB : OP_SUB;
    if (d->name == ax_s3('C', 'm', 'p'))
      return tail ? OP_TAIL_CMP : OP_CMP;
  }
  return tail ? OP_TAILCALL : OP_CALL_KNOWN;
}

/* Which total O(1) nat primops a MK_THK KNOWN may compute instead of
 * allocating when its arguments turn out to be direct nats (see x_mk_thk).
 * Anything that can raise (Div/Mod), allocate (Lsh/Bex/Init) or is lazy in
 * an operand (And/Or/If) is deliberately absent.  PL_SPEC_BODY marks the
 * total field reads whose own body runs once the operands are values. */
static pl_spec spec_code(uint32_t idx) {
  const pl_opdesc* d = &pl_ops[idx];
  if (d->opset != 66)
    return PL_SPEC_NONE;
  if (d->argc == 2) {
    if (d->name == ax_s3('A', 'd', 'd'))
      return PL_SPEC_ADD;
    if (d->name == ax_s3('S', 'u', 'b'))
      return PL_SPEC_SUB;
    if (d->name == ax_s3('M', 'u', 'l'))
      return PL_SPEC_MUL;
    if (d->name == ax_s2('E', 'q'))
      return PL_SPEC_EQ;
    if (d->name == ax_s2('N', 'e'))
      return PL_SPEC_NE;
    if (d->name == ax_s2('L', 't'))
      return PL_SPEC_LT;
    if (d->name == ax_s2('L', 'e'))
      return PL_SPEC_LE;
    if (d->name == ax_s2('G', 't'))
      return PL_SPEC_GT;
    if (d->name == ax_s2('G', 'e'))
      return PL_SPEC_GE;
    if (d->name == ax_s3('C', 'm', 'p'))
      return PL_SPEC_CMP;
    if (d->name == ax_s2('I', 'x'))
      return PL_SPEC_BODY;
  } else if (d->argc == 1) {
    if (d->name == ax_s3('I', 'n', 'c'))
      return PL_SPEC_INC;
    if (d->name == ax_s3('D', 'e', 'c'))
      return PL_SPEC_DEC;
    if (d->name == ax_s3('N', 'i', 'l'))
      return PL_SPEC_NIL;
    if (d->name == ax_s5('T', 'r', 'u', 't', 'h'))
      return PL_SPEC_TRUTH;
    /* projections and inspections: pure field reads, nothing to raise or
     * allocate (Init, which rebuilds a row, is deliberately absent) */
    if (d->name == ax_s2('H', 'd') || d->name == ax_s2('S', 'z') ||
        d->name == ax_s4('L', 'a', 's', 't') ||
        d->name == ax_s4('T', 'y', 'p', 'e') ||
        d->name == ax_s3('N', 'a', 't') ||
        d->name == ax_s4('N', 'a', 'm', 'e') ||
        d->name == ax_s4('B', 'o', 'd', 'y') ||
        d->name == ax_s5('I', 's', 'P', 'i', 'n') ||
        d->name == ax_s5('I', 's', 'L', 'a', 'w') ||
        d->name == ax_s5('I', 's', 'A', 'p', 'p') ||
        d->name == ax_s5('I', 's', 'N', 'a', 't'))
      return PL_SPEC_BODY;
    for (char k = '0'; k <= '7'; k++)
      if (d->name == ax_s3('I', 'x', k))
        return PL_SPEC_BODY;
  }
  return PL_SPEC_NONE;
}

/* Readiness is a property of a value-stack slot, not of an expression that
 * once evaluated it: another reference can still contain an IND. Meet facts
 * at control-flow joins. Local calls get independent unknown argument slots;
 * all evaluated calls return WHNF. Compiler hints are never trusted; the
 * strict arguments ARE known WHNF at strict_entry because judge verifies them
 * before taking that entry (pl_strict_entry). Limits only disable
 * optimisation. */
enum { READY_SLOTS = 256, READY_WORDS = READY_SLOTS / 64 };
typedef struct {
  int depth; /* -1 unseen; -2 unknown or inconsistent stack shape */
  uint64_t bits[READY_WORDS];
  uint64_t vars; /* bit v: env var v holds a value (seeded at strict_entry) */
} ready_state;

static bool ready_get(const ready_state* s, size_t k) {
  return s->depth >= 0 && k < (size_t)s->depth &&
         ((s->bits[k / 64] >> (k % 64)) & 1u);
}

static void ready_push(ready_state* s, bool known) {
  if (s->depth < 0)
    return;
  if (s->depth == READY_SLOTS) {
    s->depth = -2;
    return;
  }
  unsigned k = (unsigned)s->depth++;
  uint64_t bit = UINT64_C(1) << (k % 64);
  s->bits[k / 64] = (s->bits[k / 64] & ~bit) | (known ? bit : 0);
}

static bool ready_pop(ready_state* s, pl_op_t n) {
  if (s->depth < 0)
    return true; /* an unknown shape cannot prove an underflow */
  if (n > (pl_op_t)s->depth)
    return false;
  s->depth -= (int)n;
  /* Dead stack slots must not participate in the fixed point. */
  unsigned word = (unsigned)s->depth / 64;
  unsigned bit = (unsigned)s->depth % 64;
  if (word < READY_WORDS)
    s->bits[word++] &= (UINT64_C(1) << bit) - 1;
  while (word < READY_WORDS)
    s->bits[word++] = 0;
  return true;
}

static bool ready_merge(ready_state* dst, ready_state src) {
  if (src.depth < 0) {
    src.depth = -2;
    memset(src.bits, 0, sizeof(src.bits));
    src.vars = 0;
  }
  if (dst->depth == -1) {
    *dst = src;
    return true;
  }
  if (dst->depth == -2)
    return false;
  if (src.depth != dst->depth) {
    dst->depth = -2;
    memset(dst->bits, 0, sizeof(dst->bits));
    dst->vars = 0;
    return true;
  }
  bool changed = false;
  for (unsigned k = 0; k < READY_WORDS; k++) {
    uint64_t meet = dst->bits[k] & src.bits[k];
    changed |= meet != dst->bits[k];
    dst->bits[k] = meet;
  }
  uint64_t vmeet = dst->vars & src.vars;
  changed |= vmeet != dst->vars;
  dst->vars = vmeet;
  return changed;
}

static bool ready_args(const ready_state* s, pl_op_t argc, uint32_t idx) {
  if (s->depth < 0 || argc > (pl_op_t)s->depth)
    return false;
  uint32_t mask = pl_ops[idx].strict_mask;
  for (unsigned k = 0; k < 32; k++)
    if ((mask & (UINT32_C(1) << k)) &&
        (k >= argc || !ready_get(s, (size_t)s->depth - (size_t)argc + k)))
      return false;
  return true;
}

typedef enum {
  READY_OK,
  READY_INCOMPLETE,
  READY_UNDERFLOW,
} ready_result;

/* Worklist fixed point over every pc; states[pc] receives the stack shape
 * and known-WHNF slots on entry to pc. Limits only disable rewriting;
 * a provable underflow rejects the decode instead of becoming unknown. */
static ready_result ready_analyse(pl_code* c, ready_state* states) {
  size_t n = c->nops;
  ready_result result = READY_INCOMPLETE;
  size_t* queue = calloc(n, sizeof(*queue));
  bool* queued = calloc(n, sizeof(*queued));
  if (!queue || !queued)
    goto done;
  for (size_t i = 0; i < n; i++)
    states[i].depth = -1;
  size_t head = 0, tail = 0, count = 0, visits = 0;
#define POP(n)                                                                 \
  do {                                                                         \
    if (!ready_pop(&s, (n))) {                                                 \
      result = READY_UNDERFLOW;                                                \
      goto done;                                                               \
    }                                                                          \
  } while (0)
#define FLOW(pc, state)                                                        \
  do {                                                                         \
    size_t target_ = (size_t)(pc);                                             \
    if (target_ < n && ready_merge(&states[target_], (state)) &&               \
        !queued[target_]) {                                                    \
      queue[tail] = target_;                                                   \
      tail = (tail + 1) % n;                                                   \
      count++;                                                                 \
      queued[target_] = true;                                                  \
    }                                                                          \
  } while (0)
  ready_state empty = {.depth = 0};
  FLOW(0, empty);
  if (c->strict_entry) {
    /* judge reaches this entry only after verifying that every strict
     * argument is a value (mask bit i-1 = arg i = var i) */
    ready_state fast = {.depth = 0, .vars = c->strict_mask << 1};
    FLOW(c->strict_entry, fast);
  }
  while (count) {
    if (++visits > n * 512)
      goto done; /* never publish a partial fixed point */
    size_t pc = queue[head];
    head = (head + 1) % n;
    count--;
    queued[pc] = false;
    ready_state s = states[pc];
    size_t next = pc + 1;
    pl_op_t* o = &c->ops[next];
    switch (c->ops[pc]) {
    case OP_PUSH_VAR:
      ready_push(&s, o[0] < 64 && ((s.vars >> o[0]) & 1u) != 0);
      next++;
      break;
    case OP_PUSH_LIT:
      ready_push(&s, pl_is_whnf(o[0]));
      next++;
      break;
    case OP_PUSH_SLOT: {
      bool known = ready_get(&s, (size_t)o[0]);
      ready_push(&s, known);
      next++;
      break;
    }
    case OP_FORCE:
      POP(1);
      ready_push(&s, true);
      break;
    case OP_INTERP:
      ready_push(&s, true);
      next++;
      break;
    case OP_MK_APP:
      POP(o[0] < READY_SLOTS ? o[0] + 1 : READY_SLOTS + 1);
      ready_push(&s, true);
      next++;
      break;
    case OP_MK_THK:
      POP(o[0]);
      ready_push(&s, false);
      next += (o[1] & PL_BAN_MASK) == PL_BAN_PRIM_KNOWN ? 4 : 2;
      break;
    case OP_CALL: {
      ready_state args = {.depth = o[1] <= READY_SLOTS ? (int)o[1] : -2};
      FLOW(o[0], args);
      POP(o[1]);
      ready_push(&s, true);
      next += 2;
      break;
    }
    case OP_CALL_FAST:
      POP(o[0] < READY_SLOTS ? o[0] + 1 : READY_SLOTS + 1);
      ready_push(&s, true);
      next += 2;
      break;
    case OP_CALL_SLOW:
      POP(o[0] < READY_SLOTS ? o[0] + 1 : READY_SLOTS + 1);
      ready_push(&s, true);
      next++;
      break;
    case OP_CALL_KNOWN:
    case OP_ADD:
    case OP_SUB:
    case OP_CMP:
      POP(o[0]);
      ready_push(&s, true);
      next += 3;
      break;
    case OP_ENTRY:
      next++;
      break;
    case OP_NOP:
      break;
    case OP_JMP:
      FLOW(o[0], s);
      continue;
    case OP_BR:
      POP(1);
      for (size_t k = 0; k < (size_t)o[0]; k++)
        FLOW(o[k + 1], s);
      continue;
    case OP_RET:
      POP(1);
      continue;
    case OP_TAILCALL:
    case OP_TAIL_ADD:
    case OP_TAIL_SUB:
    case OP_TAIL_CMP:
      POP(o[0]);
      continue;
    default:
      goto done;
    }
    FLOW(next, s);
  }
#undef FLOW
#undef POP
  result = READY_OK;
done:
  free(queue);
  free(queued);
  return result;
}

/* Rewrite only after every predecessor has contributed its facts. */
static void ready_rewrite(pl_code* c, const ready_state* states) {
  for (size_t pc = 0; pc < c->nops; pc++) {
    const ready_state* s = &states[pc];
    if (s->depth < 0)
      continue;
    pl_op_t* o = &c->ops[pc + 1];
    switch (c->ops[pc]) {
    case OP_FORCE:
      if (s->depth && ready_get(s, (size_t)s->depth - 1))
        c->ops[pc] = OP_FORCE_READY;
      break;
    case OP_RET:
      if (s->depth && ready_get(s, (size_t)s->depth - 1))
        c->ops[pc] = OP_RET_READY;
      break;
    case OP_CALL_KNOWN:
      if (ready_args(s, o[0], (uint32_t)o[1]))
        c->ops[pc] = OP_CALL_READY;
      break;
    case OP_TAILCALL:
      if ((o[1] & PL_BAN_MASK) == PL_BAN_PRIM_KNOWN &&
          ready_args(s, o[0], (uint32_t)o[2]))
        c->ops[pc] = OP_TAIL_READY;
      break;
    default:
      break;
    }
  }
}

/* ── Eager entry of thunks the block forces immediately ─────────────── */
/*
 * The slot-model compiler builds every subexpression as a thunk in its own
 * operand slot and later copies the slot into the argument group of the
 * consumer.  When that consumer is a primop strict in that position (or a
 * FORCE), the thunk is entered on the very next evaluation step, so its
 * allocation, blackhole and update are pure overhead.  Rewrite such a MK_THK
 * into the direct call the consumer would have performed, but only where
 * that is observably identical:
 *   - producer and consumer sit in one straight-line block (no jump target
 *     or control transfer between them), so the force is certain;
 *   - every instruction between them is a push or a construction, so no
 *     other evaluation happens in between;
 *   - every strict argument the consumer forces before this one is already
 *     a value, or is itself made eager at an earlier pc, so the evaluation
 *     order stays exactly the order op_args would have used.
 * The thunk's evaluation then moves to a point with no intervening
 * evaluation, exceptions and effects included.  A converted call is itself
 * a strict consumer, so the pass iterates to a fixed point.
 */
typedef struct {
  int32_t src;      /* slot this entry copies (PUSH_SLOT), or -1 */
  int32_t producer; /* pc of a convertible MK_THK that filled it, or -1 */
  int32_t eval_pc;  /* pc of the converted call that computes it, or -1 */
  uint32_t var1;    /* 1 + env var index for a PUSH_VAR value, else 0 */
  pl_val lit;       /* the literal a PUSH_LIT pushed (see has_lit) */
  bool has_lit;
  bool whnf; /* known to hold a value at this point of the block */
} eager_slot;

static bool eager_consume(pl_code* c, eager_slot* slots, size_t base,
                          uint32_t argc, uint32_t mask, int32_t* last_impure);

/* The strict mask a saturated call through this head slot enters under: for
 * a self-reference (var 0; FAST is the compiler's exact-arity claim, and a
 * law knows its own arity) this law's own mask; for a literal pinned law the
 * mask of the code installed on that pin at decode time, when the call
 * passes exactly its arity.  Either prologue forces those arguments first
 * thing on entry, so under that mask the call is a strict consumer.  A mask
 * is a strictness fact about the law, valid whichever tier's code ends up
 * running; a callee whose code lands later is simply not seen.  Published
 * code objects live as long as the store, so the peek cannot dangle. */
static uint64_t eager_callee_mask(const pl_code* c, const eager_slot* head,
                                  size_t nargs) {
  if (head->var1 == 1)
    return c->strict_mask;
  if (!head->has_lit)
    return 0;
  pl_cell* p = pl_as(PL_TAG_PIN, head->lit);
  if (p == NULL)
    return 0;
  pl_val body = pl_pin_body(p);
  if (pl_is_nat63(body) || pl_tag(body) != PL_TAG_LAW ||
      pl_law_arity(pl_ptr(body)) != nargs)
    return 0;
  const pl_code* callee = pl_pin_code(p);
  return callee != NULL ? callee->strict_mask : 0;
}

/* A saturated call whose callee mask is known forces the strict arguments in
 * order on entry: consume them like a primop's.  Bits naming arguments the
 * call lacks void the mask. */
static bool eager_call_consume(pl_code* c, eager_slot* slots, int depth,
                               size_t nargs, int32_t* last_impure) {
  if (nargs + 1 > (size_t)depth)
    return false;
  uint64_t mask =
      eager_callee_mask(c, &slots[(size_t)depth - nargs - 1], nargs);
  if (mask == 0 || (nargs < 64 && (mask >> nargs) != 0))
    return false;
  return eager_consume(c, slots, (size_t)depth - nargs, (uint32_t)nargs,
                       (uint32_t)mask, last_impure);
}

static bool eager_apply(pl_code* c, size_t p) {
  pl_op_t* o = &c->ops[p + 1];
  if (c->ops[p] != OP_MK_THK)
    return false;
  pl_op_t argc = o[0];
  switch (o[1] & PL_BAN_MASK) {
  case PL_BAN_FAST:
    if (argc < 2)
      return false; /* a bare head is just forced; leave it */
    c->ops[p] = OP_CALL_FAST;
    o[0] = argc - 1;
    o[1] = o[1] >> 8; /* the strict-entry hint travels with the call */
    return true;
  case PL_BAN_SLOW:
    if (argc < 2)
      return false;
    c->ops[p] = OP_CALL_FAST; /* verified law: judge; anything else: apply */
    o[0] = argc - 1;
    o[1] = 0;
    return true;
  case PL_BAN_PRIM_KNOWN:
    c->ops[p] = OP_CALL_KNOWN; /* [argc, idx, spec] + filler */
    o[1] = o[2];
    o[2] = o[3];
    o[3] = OP_NOP;
    return true;
  default:
    return false; /* PRIM: unresolved [oppin, arg] row form */
  }
}

/* The consumer at the current pc forces its strict arguments [base, base +
 * argc) in ascending order.  Make each one's producer eager while the order
 * argument holds; the first argument that stays a thunk ends the run. */
static bool eager_consume(pl_code* c, eager_slot* slots, size_t base,
                          uint32_t argc, uint32_t mask, int32_t* last_impure) {
  bool changed = false;
  for (uint32_t k = 0; k < argc && k < 32; k++) {
    if (((mask >> k) & 1u) == 0)
      continue;
    eager_slot* e = &slots[base + k];
    eager_slot* src = e->src >= 0 ? &slots[e->src] : e;
    if (src->whnf)
      continue;
    int32_t p = src->producer;
    if (p < 0 || *last_impure >= p)
      break;
    bool ordered = true;
    for (uint32_t j = 0; ordered && j < k; j++) {
      if (((mask >> j) & 1u) == 0)
        continue;
      eager_slot* ej = &slots[base + j];
      eager_slot* sj = ej->src >= 0 ? &slots[ej->src] : ej;
      ordered = sj->whnf && sj->eval_pc < p;
    }
    if (!ordered || !eager_apply(c, (size_t)p))
      break;
    src->producer = -1;
    src->whnf = true;
    src->eval_pc = p;
    if (p > *last_impure)
      *last_impure = p;
    changed = true;
  }
  return changed;
}

static bool eager_rewrite(pl_code* c, const ready_state* states,
                          const uint8_t* is_target) {
  size_t n = c->nops;
  eager_slot slots[READY_SLOTS];
  bool changed = false, live = false, block_start = true;
  int depth = 0;
  int32_t last_impure = -1;
#define EPUSH(...)                                                             \
  do {                                                                         \
    if (!live)                                                                 \
      break;                                                                   \
    if (depth >= READY_SLOTS)                                                  \
      live = false;                                                            \
    else {                                                                     \
      slots[depth] = (eager_slot){__VA_ARGS__};                                \
      depth++;                                                                 \
    }                                                                          \
  } while (0)
#define EPOP(k)                                                                \
  do {                                                                         \
    if (!live)                                                                 \
      break;                                                                   \
    if ((pl_op_t)(k) > (pl_op_t)depth)                                         \
      live = false;                                                            \
    else                                                                       \
      depth -= (int)(k);                                                       \
  } while (0)
  const eager_slot unknown = {.src = -1, .producer = -1, .eval_pc = -1};
  for (size_t pc = 0; pc < n;) {
    if (block_start || is_target[pc]) {
      const ready_state* s = &states[pc];
      live = s->depth >= 0 && s->depth <= READY_SLOTS;
      depth = live ? s->depth : 0;
      for (int i = 0; live && i < depth; i++) {
        slots[i] = unknown;
        slots[i].whnf = ready_get(s, (size_t)i);
      }
      last_impure = -1;
      block_start = false;
    }
    pl_op_t op = c->ops[pc];
    pl_op_t* o = &c->ops[pc + 1];
    size_t next = pc + 1;
    switch (op) {
    case OP_PUSH_VAR: {
      bool known = live && o[0] < 64 && ((states[pc].vars >> o[0]) & 1u) != 0;
      EPUSH(.src = -1, .producer = -1, .eval_pc = -1,
            .var1 = o[0] < UINT32_MAX ? (uint32_t)o[0] + 1 : 0, .whnf = known);
      next++;
      break;
    }
    case OP_PUSH_LIT:
      EPUSH(.src = -1, .producer = -1, .eval_pc = -1, .lit = o[0],
            .has_lit = true, .whnf = pl_is_whnf(o[0]));
      next++;
      break;
    case OP_PUSH_SLOT: {
      if (live && o[0] < (pl_op_t)depth) {
        int32_t s = slots[o[0]].src >= 0 ? slots[o[0]].src : (int32_t)o[0];
        EPUSH(.src = s, .producer = -1, .eval_pc = -1, .var1 = slots[o[0]].var1,
              .lit = slots[o[0]].lit, .has_lit = slots[o[0]].has_lit);
      } else {
        live = false;
      }
      next++;
      break;
    }
    case OP_MK_THK: {
      pl_op_t bane = o[1] & PL_BAN_MASK;
      EPOP(o[0]);
      EPUSH(.src = -1, .producer = (int32_t)pc, .eval_pc = -1);
      next += bane == PL_BAN_PRIM_KNOWN ? 4 : 2;
      break;
    }
    case OP_MK_APP:
      EPOP(o[0] + 1);
      EPUSH(.src = -1, .producer = -1, .eval_pc = -1, .whnf = true);
      next++;
      break;
    case OP_NOP:
      break;
    case OP_ENTRY:
      next++;
      break;
    case OP_FORCE:
      if (live && depth >= 1)
        changed |=
            eager_consume(c, slots, (size_t)depth - 1, 1, 1, &last_impure);
      EPOP(1);
      EPUSH(.src = -1, .producer = -1, .eval_pc = -1, .whnf = true);
      last_impure = (int32_t)pc;
      break;
    case OP_CALL_KNOWN:
      if (live && o[0] <= (pl_op_t)depth)
        changed |= eager_consume(c, slots, (size_t)depth - (size_t)o[0],
                                 (uint32_t)o[0], pl_ops[o[1]].strict_mask,
                                 &last_impure);
      EPOP(o[0]);
      EPUSH(.src = -1, .producer = -1, .eval_pc = -1, .whnf = true);
      last_impure = (int32_t)pc;
      next += 3;
      break;
    case OP_CALL_FAST:
      if (live)
        changed |=
            eager_call_consume(c, slots, depth, (size_t)o[0], &last_impure);
      EPOP(o[0] + 1);
      EPUSH(.src = -1, .producer = -1, .eval_pc = -1, .whnf = true);
      last_impure = (int32_t)pc;
      next += 2;
      break;
    case OP_CALL_SLOW:
      EPOP(o[0] + 1);
      EPUSH(.src = -1, .producer = -1, .eval_pc = -1, .whnf = true);
      last_impure = (int32_t)pc;
      next++;
      break;
    case OP_CALL:
      EPOP(o[1]);
      EPUSH(.src = -1, .producer = -1, .eval_pc = -1, .whnf = true);
      last_impure = (int32_t)pc;
      next += 2;
      break;
    case OP_INTERP:
      EPUSH(.src = -1, .producer = -1, .eval_pc = -1, .whnf = true);
      last_impure = (int32_t)pc;
      next++;
      break;
    case OP_TAILCALL: {
      pl_op_t bane = o[1] & PL_BAN_MASK;
      if (bane == PL_BAN_PRIM_KNOWN && live && o[0] <= (pl_op_t)depth)
        changed |= eager_consume(c, slots, (size_t)depth - (size_t)o[0],
                                 (uint32_t)o[0], pl_ops[o[2]].strict_mask,
                                 &last_impure);
      else if (bane == PL_BAN_FAST && live && o[0] >= 2)
        changed |=
            eager_call_consume(c, slots, depth, (size_t)o[0] - 1, &last_impure);
      next += bane == PL_BAN_PRIM_KNOWN ? 4 : 2;
      block_start = true;
      break;
    }
    case OP_BR:
      next += 1 + (size_t)o[0];
      block_start = true;
      break;
    case OP_JMP:
      next++;
      block_start = true;
      break;
    case OP_RET:
      block_start = true;
      break;
    default:
      return changed; /* specialised opcodes never reach this pass */
    }
    pc = next;
  }
#undef EPUSH
#undef EPOP
  return changed;
}

/* Resolved numeric calls get their inline opcodes, keeping operand widths
 * and the op index for the generic fallback. */
static void numeric_specialise(pl_code* c) {
  size_t n = c->nops;
  for (size_t i = 0; i < n;) {
    pl_op_t op = c->ops[i];
    pl_op_t* o = &c->ops[i + 1];
    switch (op) {
    case OP_CALL_KNOWN:
      c->ops[i] = numeric_opcode((uint32_t)o[1], false);
      i += 4;
      break;
    case OP_TAILCALL:
      if ((o[1] & PL_BAN_MASK) == PL_BAN_PRIM_KNOWN) {
        c->ops[i] = numeric_opcode((uint32_t)o[2], true);
        i += 5;
      } else {
        i += 3;
      }
      break;
    case OP_MK_THK:
      i += (o[1] & PL_BAN_MASK) == PL_BAN_PRIM_KNOWN ? 5 : 3;
      break;
    case OP_BR:
      i += 2 + (size_t)o[0];
      break;
    case OP_CALL:
    case OP_CALL_FAST:
      i += 3;
      break;
    case OP_PUSH_VAR:
    case OP_PUSH_LIT:
    case OP_MK_APP:
    case OP_INTERP:
    case OP_PUSH_SLOT:
    case OP_JMP:
    case OP_ENTRY:
    case OP_CALL_SLOW:
      i += 2;
      break;
    default:
      i += 1;
      break;
    }
  }
}

/* The private-stream rewrites, in dependency order: eager entries first
 * (they create new strict consumers, so iterate), numeric specialisation on
 * the resulting calls, readiness variants on the final shape. Return false
 * on a provable stack underflow so the law stays interpreted. */
static bool bytecode_optimise(pl_code* c, const uint8_t* is_target) {
  size_t n = c->nops;
  if (n == 0 || n > 16384)
    return true;
  ready_state* states = calloc(n, sizeof(*states));
  if (states == NULL)
    return true;
  ready_result result = READY_INCOMPLETE;
  for (unsigned round = 0; round < 64; round++) {
    result = ready_analyse(c, states);
    if (result != READY_OK)
      goto done;
    if (!eager_rewrite(c, states, is_target))
      break;
  }
  numeric_specialise(c);
  result = ready_analyse(c, states);
  if (result == READY_OK)
    ready_rewrite(c, states);
done:
  free(states);
  return result != READY_UNDERFLOW;
}

/* PL_DUMP_BYTECODE=1: print every decoded program (final, post-rewrite
 * form) to stderr — the only way to see what a compiler tier actually
 * emitted once the row is behind a pin. */
static void dump_op_name(FILE* f, uint32_t idx) {
  const pl_opdesc* d = &pl_ops[idx];
  if (d->name_c != NULL) {
    fprintf(f, "%s", d->name_c);
  } else if (d->opset == 66) {
    char nm[9] = {0};
    memcpy(nm, &d->name, 8);
    fprintf(f, "%s", nm);
  } else {
    fprintf(f, "op%llu/%llu", (unsigned long long)d->opset,
            (unsigned long long)d->name);
  }
}

static void dump_val(FILE* f, pl_val v) {
  if (pl_is_nat63(v))
    fprintf(f, "%llu", (unsigned long long)v);
  else
    fprintf(f, "<tag%llx>", (unsigned long long)pl_tag(v));
}

static void bytecode_dump(const pl_code* c) {
  static const char* const names[PL_OP_COUNT] = {
      [OP_PUSH_VAR] = "PUSH_VAR",
      [OP_PUSH_LIT] = "PUSH_LIT",
      [OP_MK_THK] = "MK_THK",
      [OP_FORCE] = "FORCE",
      [OP_CALL] = "CALL",
      [OP_TAILCALL] = "TAILCALL",
      [OP_INTERP] = "INTERP",
      [OP_RET] = "RET",
      [OP_MK_APP] = "MK_APP",
      [OP_PUSH_SLOT] = "PUSH_SLOT",
      [OP_BR] = "BR",
      [OP_JMP] = "JMP",
      [OP_ENTRY] = "ENTRY",
      [OP_CALL_KNOWN] = "CALL_KNOWN",
      [OP_CALL_FAST] = "CALL_FAST",
      [OP_CALL_SLOW] = "CALL_SLOW",
      [OP_ADD] = "ADD",
      [OP_SUB] = "SUB",
      [OP_CMP] = "CMP",
      [OP_TAIL_ADD] = "TAIL_ADD",
      [OP_TAIL_SUB] = "TAIL_SUB",
      [OP_TAIL_CMP] = "TAIL_CMP",
      [OP_FORCE_READY] = "FORCE_READY",
      [OP_RET_READY] = "RET_READY",
      [OP_CALL_READY] = "CALL_READY",
      [OP_TAIL_READY] = "TAIL_READY",
      [OP_NOP] = "NOP",
  };
  FILE* f = stderr;
  fprintf(f, "--- bytecode %zu ops, strict_mask 0x%llx entry %u max_var %u\n",
          c->nops, (unsigned long long)c->strict_mask, c->strict_entry,
          c->max_var);
  size_t i = 0;
  while (i < c->nops) {
    pl_op_t op = c->ops[i];
    const pl_op_t* o = &c->ops[i + 1];
    fprintf(f, "%4zu  %s", i, op < PL_OP_COUNT && names[op] ? names[op] : "?");
    size_t w = 0;
    switch (op) {
    case OP_PUSH_VAR:
    case OP_PUSH_SLOT:
    case OP_MK_APP:
    case OP_JMP:
    case OP_INTERP:
    case OP_ENTRY:
    case OP_CALL_SLOW:
      fprintf(f, " %llu", (unsigned long long)o[0]);
      w = 1;
      break;
    case OP_PUSH_LIT:
      fprintf(f, " ");
      dump_val(f, o[0]);
      w = 1;
      break;
    case OP_CALL:
    case OP_CALL_FAST:
      fprintf(f, " %llu %llu", (unsigned long long)o[0],
              (unsigned long long)o[1]);
      w = 2;
      break;
    case OP_CALL_KNOWN:
    case OP_CALL_READY:
    case OP_ADD:
    case OP_SUB:
    case OP_CMP:
      fprintf(f, " %llu ", (unsigned long long)o[0]);
      dump_op_name(f, (uint32_t)o[1]);
      w = 3;
      break;
    case OP_MK_THK:
    case OP_TAILCALL:
    case OP_TAIL_READY:
    case OP_TAIL_ADD:
    case OP_TAIL_SUB:
    case OP_TAIL_CMP: {
      pl_op_t bane = o[1] & PL_BAN_MASK;
      static const char* const bn[] = {"?", "FAST", "SLOW", "PRIM", "KNOWN"};
      fprintf(f, " %llu %s%s", (unsigned long long)o[0],
              bane <= 4 ? bn[bane] : "?",
              (o[1] & PL_BAN_NOUPD) ? "|NOUPD" : "");
      if (o[1] >> 8)
        fprintf(f, " hint=0x%llx", (unsigned long long)(o[1] >> 8));
      if (bane == PL_BAN_PRIM_KNOWN) {
        fprintf(f, " ");
        dump_op_name(f, (uint32_t)o[2]);
        w = 4;
      } else
        w = 2;
      break;
    }
    case OP_BR:
      fprintf(f, " %llu:", (unsigned long long)o[0]);
      for (size_t k = 0; k < o[0]; k++)
        fprintf(f, " %llu", (unsigned long long)o[1 + k]);
      w = 1 + (size_t)o[0];
      break;
    default:
      w = 0;
      break;
    }
    fprintf(f, "\n");
    i += 1 + w;
  }
}

/** mallocs (and leaks) */
pl_code* pl_bytecode_from_val(pl_val val) {
  /* PL_NO_BYTECODE=1: refuse every decode, so the whole system runs
   * interpreted — the differential-testing ground truth */
  static int no_bytecode = -1;
  if (no_bytecode < 0)
    no_bytecode = getenv("PL_NO_BYTECODE") != NULL;
  if (no_bytecode)
    return NULL;

  char* msg = NULL;
  uint8_t* starts = NULL; /* pass-1 scratch, freed on every exit */
  pl_code* out = calloc(1, sizeof(pl_code));
  pl_cell* a = pl_as(PL_TAG_APP, val);
#define FAIL(m)                                                                \
  {                                                                            \
    msg = m;                                                                   \
    goto failed;                                                               \
  }
  if (a == NULL)
    FAIL("no app inside pin")
  out->nops = pl_app_n(a);
  out->ops = calloc(out->nops, sizeof(pl_op_t));
  pl_val* args = pl_app_args(a);
  for (size_t i = 0; i < out->nops; i++)
    out->ops[i] = args[i];

  pl_op_t* ops = out->ops;
  size_t n = out->nops;
  size_t i = 0;
  pl_op_t last_op = PL_OP_COUNT;
  /* pass 1: validate opcodes/operands, record instruction starts, and
   * mark jump targets; pass 2 checks every target lands on a start;
   * pass 3 fuses MK_THK+RET (skipped when the RET is a jump target). */
  starts = calloc(n, 2); /* [0..n): is-start, [n..2n): is-target */
  uint8_t* is_target = starts == NULL ? NULL : starts + n;
  if (starts == NULL)
    FAIL("oom")
#define MARK_TARGET(tgt)                                                       \
  {                                                                            \
    if ((pl_val)(tgt) >= n || !pl_is_nat63((pl_val)(tgt)))                     \
      FAIL("jump target out of range")                                         \
    is_target[(size_t)(tgt)] = 1;                                              \
  }
  while (i < n) {
    starts[i] = 1;
    pl_op_t op = ops[i++];
    last_op = op;
    switch (op) {
    case OP_PUSH_VAR:
      if (i + 1 > n)
        FAIL("truncated operand")
      if (pl_is_nat63((pl_val)ops[i]) && ops[i] > out->max_var &&
          out->max_var != UINT32_MAX)
        out->max_var = (uint32_t)(ops[i] < UINT32_MAX ? ops[i] : UINT32_MAX);
      i += 1;
      break;
    case OP_INTERP:
      out->max_var = UINT32_MAX; /* expr operands read env vars */
      if (i + 1 > n)
        FAIL("truncated operand")
      i += 1;
      break;
    case OP_PUSH_LIT:
    case OP_PUSH_SLOT:
      if (i + 1 > n)
        FAIL("truncated operand")
      i += 1;
      break;
    case OP_MK_APP:
      if (i + 1 > n)
        FAIL("truncated operand")
      if (!pl_is_nat63((pl_val)ops[i]) || ops[i] == 0 ||
          ops[i] > UINT32_MAX - 2u)
        FAIL("bad app argument count")
      i += 1;
      break;
    case OP_RET:
    case OP_FORCE:
      break;
    case OP_ENTRY:
      if (i + 1 > n)
        FAIL("truncated operand")
      if (out->strict_entry != 0 || !pl_is_nat63((pl_val)ops[i]) || ops[i] == 0)
        FAIL("bad strict entry")
      out->strict_mask = ops[i];
      out->strict_entry = (uint32_t)(i + 1);
      i += 1;
      break;
    case OP_JMP:
      if (i + 1 > n)
        FAIL("truncated operand")
      MARK_TARGET(ops[i])
      i += 1;
      break;
    case OP_CALL:
      if (i + 2 > n)
        FAIL("truncated operand")
      MARK_TARGET(ops[i])
      i += 2;
      break;
    case OP_CALL_SLOW:
      if (i + 1 > n)
        FAIL("truncated operand")
      if (ops[i] == 0 || !pl_is_nat63((pl_val)ops[i]))
        FAIL("bad call argc")
      i += 1;
      break;
    case OP_CALL_FAST:
      if (i + 2 > n)
        FAIL("truncated operand")
      if (ops[i] == 0 || !pl_is_nat63((pl_val)ops[i]) ||
          !pl_is_nat63((pl_val)ops[i + 1]))
        FAIL("bad call argc")
      i += 2;
      break;
    case OP_CALL_KNOWN: {
      /* +argc +oppin +name: resolve (opset, name, argc) exactly as the
       * MK_THK KNOWN path does, rewriting the operands to the pl_ops
       * index; an op this runtime doesn't implement fails the decode
       * silently (the law stays interpreted). */
      if (i + 3 > n)
        FAIL("truncated operand")
      pl_op_t cargc = ops[i];
      if (cargc == 0 || !pl_is_nat63((pl_val)cargc))
        FAIL("bad call argc")
      pl_cell* cpin = pl_as(PL_TAG_PIN, (pl_val)ops[i + 1]);
      pl_val cname = (pl_val)ops[i + 2];
      if (cpin == NULL || !pl_is_nat(pl_pin_body(cpin)))
        FAIL("bad known-primop opset")
      uint64_t copset = pl_nat_u64_clamp(pl_pin_body(cpin));
      int cidx = pl_op_lookup(copset, cname, (uint32_t)cargc);
      if (cidx < 0)
        goto failed;
      ops[i + 1] = (pl_op_t)cidx;
      ops[i + 2] = 0;
      i += 3;
      break;
    }
    case OP_BR: {
      if (i + 1 > n)
        FAIL("truncated operand")
      pl_op_t arms = ops[i];
      if (arms == 0 || !pl_is_nat63((pl_val)arms) || i + 1 + arms > n)
        FAIL("bad branch arm count")
      for (size_t arm = 0; arm < arms; arm++)
        MARK_TARGET(ops[i + 1 + arm])
      i += 1 + arms;
      break;
    }
    case OP_MK_THK: {
      if (i + 2 > n)
        FAIL("truncated operand")
      pl_op_t argc = ops[i];
      pl_op_t bane = ops[i + 1] & PL_BAN_MASK;
      pl_op_t hint = ops[i + 1] >> 8;
      if (ops[i + 1] & ~(pl_op_t)(PL_BAN_MASK | PL_BAN_NOUPD) & (pl_op_t)0xff)
        FAIL("bad bane")
      if (hint != 0 && (bane != PL_BAN_FAST || !pl_is_nat63((pl_val)hint)))
        FAIL("bad strict hint")
      i += 2;
      if (bane == PL_BAN_PRIM_KNOWN) {
        if (i + 2 > n)
          FAIL("truncated operand")
        pl_cell* pin = pl_as(PL_TAG_PIN, (pl_val)ops[i]);
        pl_val name = (pl_val)ops[i + 1];
        if (pin == NULL || !pl_is_nat(pl_pin_body(pin)))
          FAIL("bad known-primop opset")
        uint64_t opset = pl_nat_u64_clamp(pl_pin_body(pin));
        int idx = pl_op_lookup(opset, name, (uint32_t)argc);
        if (idx < 0) {
          /* an op this runtime doesn't implement (wrappers are declared
           * speculatively): stay interpreted, silently — the interp
           * raises "no primop" if the wrapper is ever actually called */
          goto failed;
        }
        ops[i] = (pl_op_t)idx;
        ops[i + 1] = spec_code((uint32_t)idx);
        i += 2;
      } else if (bane != PL_BAN_FAST && bane != PL_BAN_SLOW &&
                 bane != PL_BAN_PRIM) {
        FAIL("bad bane")
      }
      break;
    }
    default:
      FAIL("bad opcode")
    }
  }
#undef MARK_TARGET
  /* exec must never run off the end: the last instruction is a RET
   * (possibly the unreachable one behind a fused TAILCALL) */
  if (last_op != OP_RET)
    FAIL("bad program end")
  for (size_t j = 0; j < n; j++)
    if (is_target[j] && !starts[j])
      FAIL("jump target inside an instruction")
  /* pass 3: a thunk RETurned immediately is forced immediately — fuse
   * into a direct tail entry (the trailing RET becomes unreachable).
   * Never fuse when something jumps to that RET: it must stay live.
   * The remaining rewrites (eager entries, numeric specialisation,
   * readiness) follow in bytecode_optimise; canonical rows stay unchanged. */
  i = 0;
  while (i < n) {
    size_t opslot = i;
    pl_op_t op = ops[i++];
    switch (op) {
    case OP_PUSH_VAR:
    case OP_PUSH_LIT:
    case OP_MK_APP:
    case OP_INTERP:
    case OP_PUSH_SLOT:
    case OP_JMP:
    case OP_ENTRY:
      i += 1;
      break;
    case OP_CALL:
    case OP_CALL_FAST:
      i += 2;
      break;
    case OP_CALL_SLOW:
      i += 1;
      break;
    case OP_CALL_KNOWN:
      i += 3;
      break;
    case OP_BR:
      i += 1 + (size_t)ops[i];
      break;
    case OP_MK_THK:
      i += (ops[i + 1] & PL_BAN_MASK) == PL_BAN_PRIM_KNOWN ? 4 : 2;
      if (i < n && ops[i] == OP_RET && !is_target[i])
        ops[opslot] = OP_TAILCALL;
      break;
    default:
      break;
    }
  }
  if (!bytecode_optimise(out, is_target)) {
    FAIL("operand stack underflow")
  }
  {
    static int dump = -1;
    if (dump < 0)
      dump = getenv("PL_DUMP_BYTECODE") != NULL;
    if (dump)
      bytecode_dump(out);
  }
  free(starts);
  return out;

failed:
  free(starts);
  if (out->ops != NULL)
    free(out->ops);
  free(out);
  if (msg != NULL)
    fprintf(stderr, "Failed to decode bytecode: %s\r\n", msg);
  return NULL;
}

void pl_bytecode_free(pl_code* code) {
  if (code == NULL)
    return;
  free(code->ops);
  free(code);
}
