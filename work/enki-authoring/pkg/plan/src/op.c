#include <setjmp.h>
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>
#include <sys/stat.h>
#include <unistd.h>

#include "axsys/allocator.h"
#include "axsys/assume.h"
#include "axsys/base58.h"
#include "axsys/util.h"
#include "internal.h"
#include "plan/build.h"
#include "plan/canon.h"
#include "plan/debug.h"
#include "plan/value.h"
#include "plan/nat.h"
#include "plan/store.h"
#include "store_internal.h"
#include "native_wire.h"

/*
 * Primops, normative semantics from the Haskell reference (Plan.hs).
 * op 0:  core PLAN ops (pin / law / case).
 * op 66: named extended ops.
 * op 82: rplan I/O (rplan.c) — RPLAN-mode gated.  Console/file/socket
 *        ops run inline; the actor ops are coordination effects that
 *        suspend the thread for an executor to service.
 * op 83: staging area for provisional primops whose PLAN-level semantics
 *        are not yet settled.  Includes local primitives and executor effects.
 */

#define ARG(i) (t->vstack[ab + (i)])

/* ── Small helpers ─────────────────────────────────────────────────────── */

/* Equal compares identity after both evaluator indirections and published
 * PIN-proxy indirections.  Save deliberately preserves the public proxy
 * values while making equal proxies point at one canonical store PIN; chase
 * that target here so those values still take Equal's pointer fast path. */
static pl_val pl_eq_resolve_pin(pl_val v) {
  pl_val target = pl_pin_proxy_target(pl_ptr(v));
  return target != 0 ? target : v;
}

/* ── op 0 / shared bodies ──────────────────────────────────────────────── */

static pl_val op_pin(pl_thread* t, size_t ab) {
  return pl_pin(t, ARG(0));
}

static pl_val op_law(pl_thread* t, size_t ab) {
  uint64_t arity = pl_nat_u64_clamp(pl_nat_coerce(ARG(0)));
  ax_assume(arity < PL_NAT63_MAX, "law arity out of range");
  arity += 1; /* reference: L (nat a + 1) m b */
  pl_gc_reserve(t, PL_LAW_CELLS);
  PL_GC_FORBID(t);
  pl_val r = pl_mk_law(t, arity, ARG(1), ARG(2));
  PL_GC_ALLOW(t);
  return r;
}

/* match p l a z m o — strict only in the scrutinee o. */
static pl_val op_elim(pl_thread* t, size_t ab) {
  pl_val o = ARG(5);
  if (pl_is_nat(o)) {
    if (o == 0)
      return ARG(3);
    pl_val om1 = pl_nat_dec(t, &ARG(5));
    pl_push_apply(t, om1);
    return ARG(4);
  }
  switch (pl_tag(o)) {
  case PL_TAG_PIN:
    pl_push_apply(t, pl_pin_body(pl_ptr(o)));
    return ARG(0);
  case PL_TAG_LAW: {
    pl_cell* lp = pl_ptr(o);
    uint64_t a = pl_law_arity(lp);
    ax_assume(a <= PL_NAT63_MAX, "law arity out of range");
    pl_push_apply(t, pl_law_body(lp));
    pl_push_apply(t, pl_law_name(lp));
    pl_push_apply(t, a);
    return ARG(1);
  }
  case PL_TAG_APP: {
    pl_cell* p = pl_ptr(o);
    uint32_t n = pl_app_n(p);
    pl_val ini, last;
    if (n == 1) {
      ini = pl_app_head(p);
      last = pl_app_args(p)[0];
    } else {
      pl_gc_reserve(t, PL_APP_CELLS(n - 1));
      PL_GC_FORBID(t);
      ini = pl_mk_app_take(t, ARG(5), n - 1);
      PL_GC_ALLOW(t);
      last = pl_app_args(pl_ptr(ARG(5)))[n - 1];
    }
    pl_push_apply(t, last);
    pl_push_apply(t, ini);
    return ARG(2);
  }
  default:
    ax_abort("match: bad scrutinee tag");
  }
}

/* ── Arithmetic / bit ops ──────────────────────────────────────────────── */

#define COERCE(i) (ARG(i) = pl_nat_coerce(ARG(i)))

static pl_val op_inc(pl_thread* t, size_t ab) {
  COERCE(0);
  return pl_nat_inc(t, &ARG(0));
}
static pl_val op_dec(pl_thread* t, size_t ab) {
  COERCE(0);
  return pl_nat_dec(t, &ARG(0));
}
static pl_val op_add(pl_thread* t, size_t ab) {
  COERCE(0);
  COERCE(1);
  return pl_nat_add(t, &ARG(0), &ARG(1));
}
static pl_val op_sub(pl_thread* t, size_t ab) {
  COERCE(0);
  COERCE(1);
  return pl_nat_sub(t, &ARG(0), &ARG(1));
}
static pl_val op_mul(pl_thread* t, size_t ab) {
  COERCE(0);
  COERCE(1);
  return pl_nat_mul(t, &ARG(0), &ARG(1));
}
static pl_val op_div(pl_thread* t, size_t ab) {
  COERCE(0);
  COERCE(1);
  return pl_nat_div(t, &ARG(0), &ARG(1));
}
static pl_val op_mod(pl_thread* t, size_t ab) {
  COERCE(0);
  COERCE(1);
  return pl_nat_mod(t, &ARG(0), &ARG(1));
}
static pl_val op_rsh(pl_thread* t, size_t ab) {
  COERCE(0);
  COERCE(1);
  return pl_nat_rsh(t, &ARG(0), &ARG(1));
}
static pl_val op_lsh(pl_thread* t, size_t ab) {
  COERCE(0);
  COERCE(1);
  return pl_nat_lsh(t, &ARG(0), &ARG(1));
}
static pl_val op_bex(pl_thread* t, size_t ab) {
  COERCE(0);
  return pl_nat_bex(t, &ARG(0));
}
static pl_val op_test(pl_thread* t, size_t ab) {
  COERCE(0);
  COERCE(1);
  return pl_nat_test_bit(ARG(0), ARG(1)) ? 1 : 0;
}
static pl_val op_set(pl_thread* t, size_t ab) {
  COERCE(0);
  COERCE(1);
  return pl_nat_set_bit(t, &ARG(0), &ARG(1));
}
static pl_val op_clear(pl_thread* t, size_t ab) {
  COERCE(0);
  COERCE(1);
  return pl_nat_clear_bit(t, &ARG(0), &ARG(1));
}
static pl_val op_nib(pl_thread* t, size_t ab) {
  COERCE(0);
  COERCE(1);
  uint64_t i = pl_nat_u64_clamp(ARG(0));
  uint8_t byte = pl_nat_byte_at(ARG(1), i / 2);
  return (byte >> (4 * (i % 2))) & 0xF;
}
static pl_val op_load8(pl_thread* t, size_t ab) {
  COERCE(0);
  COERCE(1);
  return pl_nat_byte_at(ARG(1), pl_nat_u64_clamp(ARG(0)));
}

static pl_val op_loadvar(pl_thread* t, size_t ab) {
  COERCE(0);
  COERCE(1);
  COERCE(2);
  return pl_nat_load_var(t, &ARG(0), &ARG(1), &ARG(2));
}

static pl_val op_store8(pl_thread* t, size_t ab) {
  COERCE(0);
  COERCE(1);
  COERCE(2);
  return pl_nat_store_byte(t, &ARG(0), &ARG(1), &ARG(2));
}
static pl_val op_trunc(pl_thread* t, size_t ab) {
  COERCE(0);
  COERCE(1);
  return pl_nat_trunc(t, &ARG(0), &ARG(1));
}
static pl_val op_trunc_k(pl_thread* t, size_t ab, uint64_t w) {
  COERCE(0);
  pl_val width = w;
  return pl_nat_trunc(t, &width, &ARG(0));
}
static pl_val op_trunc8(pl_thread* t, size_t ab) {
  return op_trunc_k(t, ab, 8);
}
static pl_val op_trunc16(pl_thread* t, size_t ab) {
  return op_trunc_k(t, ab, 16);
}
static pl_val op_trunc32(pl_thread* t, size_t ab) {
  return op_trunc_k(t, ab, 32);
}
static pl_val op_trunc64(pl_thread* t, size_t ab) {
  return op_trunc_k(t, ab, 64);
}
static pl_val op_bits(pl_thread* t, size_t ab) {
  COERCE(0);
  AX_UNUSED(t);
  return pl_nat_bit_len(ARG(0));
}
static pl_val op_bytes(pl_thread* t, size_t ab) {
  COERCE(0);
  AX_UNUSED(t);
  return pl_nat_byte_len(ARG(0));
}

/* ── Byte scanning / cord trees ───────────────────────────────────────── */

/* scan8 src start class-mask polarity */
static pl_val op_scan8(pl_thread* t, size_t ab) {
  COERCE(0);
  COERCE(1);
  COERCE(2);
  COERCE(3);

  size_t src_len = pl_nat_byte_len(ARG(0));
  uint64_t start = pl_nat_u64_clamp(ARG(1));
  bool polarity = ARG(3) != 0;
  size_t end = 0;
  size_t newlines = 0;
  size_t final_column = 0;
  bool preserve_start = start >= (uint64_t)src_len;

  if (!preserve_start) {
    /* Hoist the 256-bit class mask and the source limbs out of the loop:
     * nothing below allocates, so the limb pointer stays valid.  Bytes are
     * little-endian within limbs, so byte i lives in limb i/8. */
    uint64_t cls[4];
    for (size_t k = 0; k < 4; k++)
      cls[k] = pl_nat_limb_at(ARG(2), k);
    uint64_t src_word = ARG(0);
    const uint64_t* limbs =
        pl_is_nat63(ARG(0)) ? &src_word : pl_nat_limb_ptr(pl_ptr(ARG(0)));
    end = (size_t)start;
    while (end < src_len) {
      uint8_t byte = (uint8_t)(limbs[end / 8] >> ((end % 8) * 8));
      bool in_class = ((cls[byte / 64u] >> (byte % 64u)) & 1u) != 0;
      if (in_class != polarity)
        break;
      end++;
      if (byte == '\n') {
        newlines++;
        final_column = 0;
      } else {
        final_column++;
      }
    }
  }

  pl_gc_reserve(t, PL_APP_CELLS(3));
  PL_GC_FORBID(t);
  pl_val fields[3] = {
      preserve_start ? ARG(1) : pl_mk_nat_u64(t, (uint64_t)end),
      pl_mk_nat_u64(t, (uint64_t)newlines),
      pl_mk_nat_u64(t, (uint64_t)final_column),
  };
  pl_val out = pl_mk_app_from(t, 0, 3, fields);
  PL_GC_ALLOW(t);
  return out;
}

typedef struct strtree_stack {
  pl_val* items;
  size_t len;
  size_t cap;
} strtree_stack;

typedef struct strtree_bytes {
  uint8_t* items;
  size_t len;
  size_t cap;
} strtree_bytes;

#define STRTREE_MAX_BYTES ((((size_t)1 << 20) - 1) * sizeof(uint64_t))

static void* strtree_grow(void* mem, size_t* cap, size_t need,
                          size_t item_size) {
  if (need <= *cap)
    return mem;
  size_t next = *cap == 0 ? 16 : *cap;
  while (next < need) {
    if (next > SIZE_MAX / 2) {
      next = need;
      break;
    }
    next *= 2;
  }
  if (next > SIZE_MAX / item_size)
    return NULL;
  void* grown = realloc(mem, next * item_size);
  if (grown == NULL)
    return NULL;
  *cap = next;
  return grown;
}

static bool strtree_push(strtree_stack* stack, pl_val value) {
  void* grown = strtree_grow(stack->items, &stack->cap, stack->len + 1,
                             sizeof(*stack->items));
  if (grown == NULL)
    return false;
  stack->items = grown;
  stack->items[stack->len++] = value;
  return true;
}

static bool strtree_nat_size(pl_val value, size_t* out) {
  if (pl_nat_limb_len(value) > 1)
    return false;
  uint64_t n = pl_nat_limb_at(value, 0);
  if (n > SIZE_MAX)
    return false;
  *out = (size_t)n;
  return true;
}

static bool strtree_reserve_bytes(strtree_bytes* bytes, size_t add) {
  if (add == 0)
    return true;
  if (add > STRTREE_MAX_BYTES - bytes->len)
    return false;
  void* grown = strtree_grow(bytes->items, &bytes->cap, bytes->len + add,
                             sizeof(*bytes->items));
  if (grown == NULL)
    return false;
  bytes->items = grown;
  return true;
}

/*
 * StrTree traverses an already-deep-normal CordTree.  The host stack and
 * byte accumulator cannot be invalidated by GC; the only PLAN allocation
 * happens after traversal, when no CordTree pointers remain in the host stack.
 */
static pl_val op_strtree(pl_thread* t, size_t ab) {
  const pl_val text_tag = ax_s4('t', 'e', 'x', 't');
  const pl_val slice_tag = ax_s5('s', 'l', 'i', 'c', 'e');
  const pl_val repeat_tag = ax_s6('r', 'e', 'p', 'e', 'a', 't');
  const pl_val cat_tag = ax_s3('c', 'a', 't');
  strtree_stack stack = {0};
  strtree_bytes bytes = {0};

  if (!strtree_push(&stack, ARG(0)))
    goto allocation_failed;

  while (stack.len != 0) {
    pl_val node = stack.items[--stack.len];
    pl_cell* app = pl_as(PL_TAG_APP, node);
    if (app == NULL)
      goto malformed;
    uint32_t row_n = pl_app_n(app);
    if (pl_app_head(app) != 0 || row_n == 0)
      goto malformed;
    pl_val* fields = pl_app_args(app);
    pl_val tag = fields[0];
    fields++;
    uint32_t n = row_n - 1;
    if (n == 1 && tag == text_tag) {
      if (!pl_is_nat(fields[0]))
        goto malformed;
      size_t text_len = pl_nat_byte_len(fields[0]);
      if (!strtree_reserve_bytes(&bytes, text_len))
        goto output_too_large_or_allocation_failed;
      for (size_t i = 0; i < text_len; i++)
        bytes.items[bytes.len + i] = pl_nat_byte_at(fields[0], i);
      bytes.len += text_len;
    } else if (n == 3 && tag == slice_tag) {
      if (!pl_is_nat(fields[0]) || !pl_is_nat(fields[1]) ||
          !pl_is_nat(fields[2]))
        goto malformed;
      size_t slice_len;
      if (!strtree_nat_size(fields[2], &slice_len) ||
          !strtree_reserve_bytes(&bytes, slice_len))
        goto output_too_large_or_allocation_failed;
      size_t offset;
      size_t source_len = pl_nat_byte_len(fields[0]);
      size_t available = 0;
      if (strtree_nat_size(fields[1], &offset) && offset < source_len)
        available = source_len - offset;
      if (available > slice_len)
        available = slice_len;
      for (size_t i = 0; i < available; i++)
        bytes.items[bytes.len + i] = pl_nat_byte_at(fields[0], offset + i);
      if (slice_len != available)
        memset(bytes.items + bytes.len + available, 0, slice_len - available);
      bytes.len += slice_len;
    } else if (n == 2 && tag == repeat_tag) {
      if (!pl_is_nat(fields[0]) || !pl_is_nat(fields[1]))
        goto malformed;
      size_t count;
      if (!strtree_nat_size(fields[1], &count) ||
          !strtree_reserve_bytes(&bytes, count))
        goto output_too_large_or_allocation_failed;
      if (count != 0)
        memset(bytes.items + bytes.len, pl_nat_byte_at(fields[0], 0), count);
      bytes.len += count;
    } else if (n == 2 && tag == cat_tag) {
      if (!strtree_push(&stack, fields[1]) || !strtree_push(&stack, fields[0]))
        goto allocation_failed;
    } else {
      goto malformed;
    }
  }

  free(stack.items);
  pl_val out = pl_nat_from_bytes(t, bytes.items, bytes.len);
  free(bytes.items);
  return out;

malformed:
  free(stack.items);
  free(bytes.items);
  return 0;

allocation_failed:
  free(stack.items);
  free(bytes.items);
  pl_raise_msg(t, "StrTree: temporary allocation failed");

output_too_large_or_allocation_failed:
  free(stack.items);
  free(bytes.items);
  pl_raise_msg(t, "StrTree: output too large or temporary allocation failed");
}

/* ── Comparisons ───────────────────────────────────────────────────────── */

static int nat_cmp_args(pl_thread* t, size_t ab) {
  COERCE(0);
  COERCE(1);
  return pl_nat_cmp(ARG(0), ARG(1));
}
static pl_val op_eq(pl_thread* t, size_t ab) {
  return nat_cmp_args(t, ab) == 0 ? 1 : 0;
}
static pl_val op_ne(pl_thread* t, size_t ab) {
  return nat_cmp_args(t, ab) != 0 ? 1 : 0;
}
static pl_val op_lt(pl_thread* t, size_t ab) {
  return nat_cmp_args(t, ab) < 0 ? 1 : 0;
}
static pl_val op_le(pl_thread* t, size_t ab) {
  return nat_cmp_args(t, ab) <= 0 ? 1 : 0;
}
static pl_val op_gt(pl_thread* t, size_t ab) {
  return nat_cmp_args(t, ab) > 0 ? 1 : 0;
}
static pl_val op_ge(pl_thread* t, size_t ab) {
  return nat_cmp_args(t, ab) >= 0 ? 1 : 0;
}
static pl_val op_cmp(pl_thread* t, size_t ab) {
  int c = nat_cmp_args(t, ab);
  return c < 0 ? 0 : (c == 0 ? 1 : 2);
}

/* ── Booleans / branches (laziness boundaries) ─────────────────────────── */

static pl_val op_nil(pl_thread* t, size_t ab) {
  AX_UNUSED(t);
  return ARG(0) == 0 ? 1 : 0;
}
static pl_val op_truth(pl_thread* t, size_t ab) {
  AX_UNUSED(t);
  return ARG(0) == 0 ? 0 : 1;
}
static pl_val op_or(pl_thread* t, size_t ab) {
  AX_UNUSED(t);
  return ARG(0) == 0 ? ARG(1) : ARG(0);
}
static pl_val op_and(pl_thread* t, size_t ab) {
  AX_UNUSED(t);
  return ARG(0) == 0 ? 0 : ARG(1);
}
static pl_val op_nor(pl_thread* t, size_t ab) {
  if (ARG(0) != 0)
    return 0;
  /* conditional strictness through a frame: the machine forces y
   * at depth 0 and the F_NIL frame maps it to planNil y */
  pl_frame* fr = pl_fpush(t);
  fr->kind = PL_F_NIL;
  return ARG(1);
}
static pl_val op_if(pl_thread* t, size_t ab) {
  AX_UNUSED(t);
  return ARG(0) != 0 ? ARG(1) : ARG(2);
}
static pl_val op_ifz(pl_thread* t, size_t ab) {
  AX_UNUSED(t);
  return ARG(0) == 0 ? ARG(1) : ARG(2);
}

/* CaseK x b0 .. b(K-2) fb — strict ONLY in the scrutinee. */
static pl_val op_case_k(pl_thread* t, size_t ab, uint32_t argc) {
  AX_UNUSED(t);
  pl_val x = ARG(0);
  if (pl_is_nat63(x) && x < argc - 2)
    return ARG(1 + x);
  return ARG(argc - 1);
}
#define DEF_CASE(K, ARGC)                                                      \
  static pl_val op_case##K(pl_thread* t, size_t ab) {                          \
    return op_case_k(t, ab, ARGC);                                             \
  }
DEF_CASE(2, 3)
DEF_CASE(3, 4)
DEF_CASE(4, 5)
DEF_CASE(5, 6)
DEF_CASE(6, 7)
DEF_CASE(7, 8)
DEF_CASE(8, 9)
DEF_CASE(9, 10)
DEF_CASE(10, 11)
DEF_CASE(11, 12)
DEF_CASE(12, 13)
DEF_CASE(13, 14)
DEF_CASE(14, 15)
DEF_CASE(15, 16)
DEF_CASE(16, 17)

/* Case ix cs f */
static pl_val op_case(pl_thread* t, size_t ab) {
  AX_UNUSED(t);
  pl_cell* cp = pl_as(PL_TAG_APP, ARG(1));
  if (cp != NULL && pl_is_nat63(ARG(0)) && ARG(0) < pl_app_n(cp))
    return pl_app_args(cp)[ARG(0)];
  return ARG(2);
}

/* ── Inspection ────────────────────────────────────────────────────────── */

static pl_val op_type(pl_thread* t, size_t ab) {
  AX_UNUSED(t);
  pl_val x = ARG(0);
  if (pl_is_nat(x))
    return 0;
  switch (pl_tag(x)) {
  case PL_TAG_PIN:
    return 1;
  case PL_TAG_LAW:
    return 2;
  case PL_TAG_APP:
    return 3;
  default:
    return 0;
  }
}
static pl_val op_is_pin(pl_thread* t, size_t ab) {
  AX_UNUSED(t);
  return pl_as(PL_TAG_PIN, ARG(0)) != NULL ? 1 : 0;
}
static pl_val op_is_law(pl_thread* t, size_t ab) {
  AX_UNUSED(t);
  return pl_as(PL_TAG_LAW, ARG(0)) != NULL ? 1 : 0;
}
static pl_val op_is_app(pl_thread* t, size_t ab) {
  AX_UNUSED(t);
  return pl_as(PL_TAG_APP, ARG(0)) != NULL ? 1 : 0;
}
static pl_val op_is_nat(pl_thread* t, size_t ab) {
  AX_UNUSED(t);
  return pl_is_nat(ARG(0)) ? 1 : 0;
}
static pl_val op_nat(pl_thread* t, size_t ab) {
  AX_UNUSED(t);
  return pl_nat_coerce(ARG(0));
}
static pl_val op_arity(pl_thread* t, size_t ab) {
  AX_UNUSED(t);
  pl_cell* lp = pl_as(PL_TAG_LAW, ARG(0));
  return lp != NULL ? pl_law_arity(lp) : 0;
}
static pl_val op_name(pl_thread* t, size_t ab) {
  AX_UNUSED(t);
  pl_cell* lp = pl_as(PL_TAG_LAW, ARG(0));
  return lp != NULL ? pl_law_name(lp) : 0;
}
static pl_val op_body(pl_thread* t, size_t ab) {
  AX_UNUSED(t);
  pl_cell* lp = pl_as(PL_TAG_LAW, ARG(0));
  return lp != NULL ? pl_law_body(lp) : 0;
}
static pl_val op_unpin(pl_thread* t, size_t ab) {
  AX_UNUSED(t);
  pl_cell* pp = pl_as(PL_TAG_PIN, ARG(0));
  return pp != NULL ? pl_pin_body(pp) : 0;
}

/* ── Rows ──────────────────────────────────────────────────────────────── */

static pl_val op_sz(pl_thread* t, size_t ab) {
  AX_UNUSED(t);
  pl_cell* p = pl_as(PL_TAG_APP, ARG(0));
  return p != NULL ? pl_app_n(p) : 0;
}
static pl_val op_hd(pl_thread* t, size_t ab) {
  AX_UNUSED(t);
  pl_cell* p = pl_as(PL_TAG_APP, ARG(0));
  return p != NULL ? pl_app_head(p) : ARG(0);
}
static pl_val op_last(pl_thread* t, size_t ab) {
  AX_UNUSED(t);
  pl_cell* p = pl_as(PL_TAG_APP, ARG(0));
  return p != NULL ? pl_app_args(p)[pl_app_n(p) - 1] : 0;
}
static pl_val op_init(pl_thread* t, size_t ab) {
  pl_cell* p = pl_as(PL_TAG_APP, ARG(0));
  if (p == NULL)
    return 0;
  uint32_t n = pl_app_n(p);
  if (n == 1)
    return pl_app_head(p);
  pl_gc_reserve(t, PL_APP_CELLS(n - 1));
  PL_GC_FORBID(t);
  pl_val r = pl_mk_app_take(t, ARG(0), n - 1);
  PL_GC_ALLOW(t);
  return r;
}
static pl_val op_ix(pl_thread* t, size_t ab) {
  AX_UNUSED(t);
  COERCE(0);
  pl_cell* p = pl_as(PL_TAG_APP, ARG(1));
  uint64_t i = pl_nat_u64_clamp(ARG(0));
  if (p != NULL && i < pl_app_n(p))
    return pl_app_args(p)[i];
  return 0;
}
static pl_val op_ix_k(pl_thread* t, size_t ab, uint64_t i) {
  AX_UNUSED(t);
  pl_cell* p = pl_as(PL_TAG_APP, ARG(0));
  if (p == NULL)
    return 0;
  if (i == 0)
    return pl_app_args(p)[0];
  return i < pl_app_n(p) ? pl_app_args(p)[i] : 0;
}
#define DEF_IX(K)                                                              \
  static pl_val op_ix##K(pl_thread* t, size_t ab) {                            \
    return op_ix_k(t, ab, K);                                                  \
  }
DEF_IX(0)
DEF_IX(1)
DEF_IX(2)
DEF_IX(3)
DEF_IX(4)
DEF_IX(5)
DEF_IX(6)
DEF_IX(7)

/* planUp: functional update of slot i; v stays lazy. */
static pl_val op_up(pl_thread* t, size_t ab) {
  COERCE(0);
  pl_cell* p = pl_as(PL_TAG_APP, ARG(2));
  uint64_t i = pl_nat_u64_clamp(ARG(0));
  if (p == NULL || i >= pl_app_n(p))
    return ARG(2);
  uint32_t n = pl_app_n(p);
  pl_gc_reserve(t, PL_APP_CELLS(n));
  PL_GC_FORBID(t);
  pl_cell* sp = pl_ptr(ARG(2));
  pl_val r = pl_mk_app_from(t, pl_app_head(sp), n, pl_app_args(sp));
  pl_app_args(pl_ptr(r))[i] = ARG(1);
  PL_GC_ALLOW(t);
  return r;
}

/* planSlice o n v — note the result head is N 0. */
static pl_val op_slice(pl_thread* t, size_t ab) {
  COERCE(0);
  COERCE(1);
  pl_cell* p = pl_as(PL_TAG_APP, ARG(2));
  if (p == NULL)
    return 0;
  uint64_t o = pl_nat_u64_clamp(ARG(0));
  uint64_t n = pl_nat_u64_clamp(ARG(1));
  uint64_t sz = pl_app_n(p);
  if (o > sz)
    return 0;
  uint64_t rsz = sz - o < n ? sz - o : n;
  if (rsz == 0)
    return 0;
  /* Slice resets the result head to 0.  A complete slice of a row that
   * already has that head is therefore the exact result. */
  if (o == 0 && rsz == sz && pl_app_head(p) == 0)
    return ARG(2);
  pl_gc_reserve(t, PL_APP_CELLS(rsz));
  PL_GC_FORBID(t);
  pl_val r =
      pl_mk_app_from(t, 0, (uint32_t)rsz, pl_app_args(pl_ptr(ARG(2))) + o);
  PL_GC_ALLOW(t);
  return r;
}

/* planWeld x y — concatenate rows under head 0; an empty result is 0. */
static pl_val op_weld(pl_thread* t, size_t ab) {
  pl_cell* xp = pl_as(PL_TAG_APP, ARG(0));
  pl_cell* yp = pl_as(PL_TAG_APP, ARG(1));
  uint32_t nx = xp ? pl_app_n(xp) : 0;
  uint32_t ny = yp ? pl_app_n(yp) : 0;
  if (nx == 0 && ny == 0)
    return 0;
  pl_gc_reserve(t, PL_APP_CELLS(nx + ny));
  PL_GC_FORBID(t);
  pl_cell* p = pl_bump(t, PL_APP_CELLS(nx + ny));
  pl_cache_stat_alloc(t, PL_K_APP, PL_APP_CELLS(nx + ny));
  p[0] = pl_hdr_make(PL_K_APP, 0, 0, PL_APP_CELLS(nx + ny));
  p[1] = 0;
  xp = pl_as(PL_TAG_APP, ARG(0));
  yp = pl_as(PL_TAG_APP, ARG(1));
  if (nx)
    memcpy(p + 2, pl_app_args(xp), nx * sizeof(pl_val));
  if (ny)
    memcpy(p + 2 + nx, pl_app_args(yp), ny * sizeof(pl_val));
  PL_GC_ALLOW(t);
  return pl_make(PL_TAG_APP, p);
}

/* planRep hd item sz — item replicated unforced. */
static pl_val op_rep(pl_thread* t, size_t ab) {
  COERCE(0);
  COERCE(2);
  uint64_t n = pl_nat_u64_clamp(ARG(2));
  if (n == 0)
    return ARG(0);
  ax_assume(n < (1u << 24), "Rep size too large");
  pl_gc_reserve(t, PL_APP_CELLS(n));
  PL_GC_FORBID(t);
  pl_cell* p = pl_bump(t, PL_APP_CELLS(n));
  pl_cache_stat_alloc(t, PL_K_APP, PL_APP_CELLS(n));
  p[0] = pl_hdr_make(PL_K_APP, 0, 0, PL_APP_CELLS(n));
  p[1] = ARG(0);
  for (uint64_t i = 0; i < n; i++)
    p[2 + i] = ARG(1);
  PL_GC_ALLOW(t);
  return pl_make(PL_TAG_APP, p);
}

/*
 * planRow hd sz xs — elements stay LAZY: element k is the unforced
 * `Ix0 (Ix1^k xs)`.  Encoded with the store-resident ix0/ix1 law-body
 * expressions over tiny shared envs (see pl_store_ix?_expr).
 */
static pl_val op_row(pl_thread* t, size_t ab) {
  COERCE(0);
  COERCE(1);
  uint64_t n = pl_nat_u64_clamp(ARG(1));
  if (n == 0)
    return ARG(0);
  ax_assume(n < (1u << 22), "Row size too large");
  pl_store* s = pl_heap_store(t->heap);
  ax_assume(s != NULL, "Row requires a store");
  size_t per = PL_ENV_CELLS(2) + 2 * PL_THUNK_CELLS;
  pl_gc_reserve(t, n * per + PL_APP_CELLS(n));
  pl_val ix0e = pl_store_ix0_expr(s);
  pl_val ix1e = pl_store_ix1_expr(s);
  PL_GC_FORBID(t);
  pl_cell* p = pl_bump(t, PL_APP_CELLS(n));
  pl_cache_stat_alloc(t, PL_K_APP, PL_APP_CELLS(n));
  p[0] = pl_hdr_make(PL_K_APP, 0, 0, PL_APP_CELLS(n));
  p[1] = ARG(0);
  pl_val prefix = ARG(2);
  for (uint64_t k = 0; k < n; k++) {
    pl_val env = pl_mk_env(t, 2);
    pl_env_slots(pl_ptr(env))[1] = prefix;
    p[2 + k] = pl_mk_thunk(t, env, ix0e);
    if (k + 1 < n)
      prefix = pl_mk_thunk(t, env, ix1e);
  }
  PL_GC_ALLOW(t);
  return pl_make(PL_TAG_APP, p);
}

/* planCoup hd x */
static pl_val op_coup(pl_thread* t, size_t ab) {
  pl_cell* xp = pl_as(PL_TAG_APP, ARG(1));
  if (xp == NULL)
    return ARG(0);
  uint32_t n = pl_app_n(xp);
  if (pl_arity(ARG(0)) > n) {
    pl_gc_reserve(t, PL_APP_CELLS(n));
    PL_GC_FORBID(t);
    xp = pl_ptr(ARG(1));
    pl_val r = pl_mk_app_from(t, ARG(0), n, pl_app_args(xp));
    PL_GC_ALLOW(t);
    return r;
  }
  /* apple (hd : args): fold the applications through the machine */
  for (uint32_t i = n; i > 0; i--)
    pl_push_apply(t, pl_app_args(xp)[i - 1]);
  return ARG(0);
}

/* ── Forcing / sequencing ──────────────────────────────────────────────── */

static pl_val op_seq(pl_thread* t, size_t ab) {
  AX_UNUSED(t);
  return ARG(1);
}
static pl_val op_seq2(pl_thread* t, size_t ab) {
  AX_UNUSED(t);
  return ARG(2);
}
static pl_val op_seq3(pl_thread* t, size_t ab) {
  AX_UNUSED(t);
  return ARG(3);
}
static pl_val op_sap(pl_thread* t, size_t ab) {
  pl_push_apply(t, ARG(1));
  return ARG(0);
}
static pl_val op_sap2(pl_thread* t, size_t ab) {
  pl_push_apply(t, ARG(2));
  pl_push_apply(t, ARG(1));
  return ARG(0);
}
static pl_val op_force(pl_thread* t, size_t ab) {
  pl_push_nf(t);
  return ARG(0);
}
static pl_val op_deepseq(pl_thread* t, size_t ab) {
  pl_push_seq(t, ARG(1));
  pl_push_nf(t);
  return ARG(0);
}

/* ── Exceptions ────────────────────────────────────────────────────────── */

static pl_val op_throw(pl_thread* t, size_t ab) {
  pl_raise(t, ARG(0)); /* arg 0 already deeply forced (deep flag) */
}

/*
 * Frame-based Try: push the F_TRY
 * barrier, then drive force (f % x) through the machine itself.  The
 * success/exception wrapping lives in the trampoline (F_TRY return
 * case, pl_run_caught), so suspension, fuel yields, and blocking
 * coordination effects all work beneath a Try.
 */
static pl_val op_try(pl_thread* t, size_t ab) {
  pl_frame* fr = pl_fpush(t);
  fr->kind = PL_F_TRY;
  fr->argbase = (uint32_t)(ab - 1); /* vsp to restore on exn delivery */
  fr->profile_mark = t->profile_next_generation;
  pl_push_nf(t);
  pl_push_apply(t, ARG(1));
  return ARG(0);
}

/* Pure limit f x returns Try's result shape after deep normalization.
 * The frame survives yields and unwinds; nested calls share the outer budget. */
static pl_val op_pure(pl_thread* t, size_t ab) {
  uint64_t limit = pl_nat_u64_clamp(pl_nat_coerce(ARG(0)));
  if (limit > UINT64_C(1000000000)) limit = UINT64_C(1000000000);
  pl_frame* fr = pl_fpush(t);
  fr->kind = PL_F_PURE;
  fr->argbase = (uint32_t)(ab - 1);
  fr->profile_mark = t->profile_next_generation;
  fr->k = t->pure_depth;
  /* Preserve the outer budget beyond this nested call's allowance. The
   * nested computation charges its actual consumption, not its full limit. */
  fr->argc = t->pure_depth != 0 && t->pure_remaining > limit
      ? (uint32_t)(t->pure_remaining - limit) : 0;
  if (t->pure_depth == 0 || limit < t->pure_remaining)
    t->pure_remaining = limit;
  t->pure_depth++;
  if (getenv("PLAN_PURE_STATS") != NULL)
    fprintf(stderr, "[pure] enter depth=%u allowance=%llu requested=%llu\n",
            t->pure_depth, (unsigned long long)t->pure_remaining,
            (unsigned long long)limit);
  pl_push_nf(t);
  pl_push_apply(t, ARG(2));
  return ARG(1);
}

/*
 * (Memo f x) ≡ (f x), unconditionally — the identity on application
 * (spec: doc/sigoflaw-memo-spec.md).  When both args are canonical
 * hashed pins the runtime may serve the pair from the machine-global
 * nat cache: probe here, and on a miss run the application beneath an
 * F_MEMO barrier — ret_memo records the result only if it is a nat63
 * and the thread's effect epoch never moved (caching may skip work,
 * never effects).  Purity of f is the caller's contract; anything
 * uncacheable — raw laws, unsaved pins, non-nat results — simply
 * evaluates as a plain application.
 */
static pl_val op_memo(pl_thread* t, size_t ab) {
  pl_val f = pl_resolve(ARG(0));
  pl_val x = pl_resolve(ARG(1));
  const uint8_t* fh = pl_as(PL_TAG_PIN, f) != NULL ? pl_pin_hash(f) : NULL;
  const uint8_t* xh = pl_as(PL_TAG_PIN, x) != NULL ? pl_pin_hash(x) : NULL;
  if (fh != NULL && xh != NULL) {
    uint64_t cached;
    if (pl_memo_probe(fh, xh, &cached))
      return (pl_val)cached;
    pl_frame* fr = pl_fpush(t);
    fr->kind = PL_F_MEMO;
    fr->a = f;
    fr->b = x;
    fr->epoch = t->effect_epoch;
  }
  pl_push_apply(t, x);
  return f;
}

/* ── Misc ──────────────────────────────────────────────────────────────── */

static pl_val op_trace(pl_thread* t, size_t ab) {
  t->effect_epoch++; /* observable output: never cached across (F_MEMO) */
  /* arg 0 deep via mask: the reference shows the value deeply */
  char* s = pl_show_val(ax_allocator_system(), ARG(0), NULL);
  fprintf(stderr, "%s\n", s);
  ax_free(ax_allocator_system(), s);
  return ARG(1);
}

/*
 * Structural equality over already-normal values, driven by an
 * explicit worklist instead of C recursion: op-66 Equal runs on
 * arbitrarily deep data (the compiler compares whole IR trees for its
 * fixed point), so graph depth must never translate into C stack
 * depth.  The worklist holds bare pl_vals with no GC protection —
 * legal only because nothing here allocates on the PLAN heap; both roots
 * stay live on the caller's vstack.
 */
typedef struct {
  pl_val a, b;
  bool publish; /* after a successful body comparison: proxy a -> canonical b */
} pl_eq_pair;

typedef struct {
  pl_eq_pair* items;
  size_t n, cap;
  pl_eq_pair inline_buf[64];
} pl_eq_stack;

static void pl_eq_push(pl_eq_stack* s, pl_val a, pl_val b) {
  if (s->n == s->cap) {
    size_t cap2 = s->cap * 2;
    if (s->items == s->inline_buf) {
      pl_eq_pair* grown = malloc(cap2 * sizeof(pl_eq_pair));
      ax_assume(grown != NULL, "oom");
      memcpy(grown, s->items, s->n * sizeof(pl_eq_pair));
      s->items = grown;
    } else {
      s->items = realloc(s->items, cap2 * sizeof(pl_eq_pair));
      ax_assume(s->items != NULL, "oom");
    }
    s->cap = cap2;
  }
  s->items[s->n++] = (pl_eq_pair){.a = a, .b = b};
}

static void pl_eq_publish(pl_store* store, pl_val proxy, pl_val target) {
  target = pl_eq_resolve_pin(target);
  if (store == NULL || !pl_store_owns(store, target))
    return;
  /* Serialize with Save/Ice and other Equal publications.  Another thread
   * may already have resolved a shared store proxy while we compared it. */
  pl_store_save_lock(store);
  pl_cell* p = pl_ptr(proxy);
  if (pl_pin_is_proxy(p) && pl_pin_proxy_target(p) == 0)
    pl_pin_set_target(p, target);
  pl_store_save_unlock(store);
}

static bool pl_eq_deep(pl_store* store, pl_val a0, pl_val b0) {
  pl_eq_stack s;
  s.items = s.inline_buf;
  s.n = 0;
  s.cap = sizeof(s.inline_buf) / sizeof(s.inline_buf[0]);
  pl_eq_push(&s, a0, b0);
  bool eq = true;
  while (eq && s.n > 0) {
    pl_eq_pair p = s.items[--s.n];
    if (p.publish) {
      pl_eq_publish(store, p.a, p.b);
      continue;
    }
    pl_val a = pl_resolve(p.a);
    pl_val b = pl_resolve(p.b);
    if (a == b)
      continue;
    if (pl_is_nat(a) && pl_is_nat(b)) {
      eq = pl_nat_eq(a, b);
      continue;
    }
    if (pl_is_nat63(a) || pl_is_nat63(b) || pl_tag(a) != pl_tag(b)) {
      eq = false;
      continue;
    }
    switch (pl_tag(a)) {
    case PL_TAG_PIN: {
      a = pl_eq_resolve_pin(a);
      b = pl_eq_resolve_pin(b);
      if (a == b)
        break;
      const uint8_t* ah = pl_pin_hash(a);
      const uint8_t* bh = pl_pin_hash(b);
      if (ah != NULL && bh != NULL)
        eq = memcmp(ah, bh, 32) == 0;
      else {
        if ((ah != NULL) != (bh != NULL)) {
          /* LIFO completion marker: publish only after the entire body has
           * compared equal, including any nested PINs. */
          pl_eq_push(&s, ah == NULL ? a : b, ah != NULL ? a : b);
          s.items[s.n - 1].publish = true;
        }
        pl_eq_push(&s, pl_pin_body(pl_ptr(a)), pl_pin_body(pl_ptr(b)));
      }
      break;
    }
    case PL_TAG_LAW: {
      pl_cell *pa = pl_ptr(a), *pb = pl_ptr(b);
      if (pl_law_arity(pa) != pl_law_arity(pb)) {
        eq = false;
        break;
      }
      pl_eq_push(&s, pl_law_body(pa), pl_law_body(pb));
      pl_eq_push(&s, pl_law_name(pa), pl_law_name(pb));
      break;
    }
    case PL_TAG_APP: {
      pl_cell *pa = pl_ptr(a), *pb = pl_ptr(b);
      uint32_t n = pl_app_n(pa);
      if (n != pl_app_n(pb)) {
        eq = false;
        break;
      }
      for (uint32_t i = n; i > 0; i--)
        pl_eq_push(&s, pl_app_args(pa)[i - 1], pl_app_args(pb)[i - 1]);
      pl_eq_push(&s, pl_app_head(pa), pl_app_head(pb));
      break;
    }
    default:
      eq = false;
      break;
    }
  }
  if (s.items != s.inline_buf)
    free(s.items);
  return eq;
}

static pl_val op_equal(pl_thread* t, size_t ab) {
  /* both args deep via mask */
  return pl_eq_deep(pl_heap_store(t->heap), ARG(0), ARG(1)) ? 1 : 0;
}

static pl_val op_install(pl_thread* t, size_t ab) {
  pl_val a = pl_resolve(ARG(0));
  pl_cell* p = pl_as(PL_TAG_PIN, a);
  if (!p) {
    fprintf(stderr, "compiler not pin, ignoring\n");
    return 0;
  }
  const uint8_t* hash = pl_pin_hash(a);
  if (hash == NULL)
    pl_raise_msg(t, "Install: compiler PIN must be saved first");
  pl_store* s = pl_heap_store(t->heap);
  pl_store_lock(s);
  bool replacing_self = t == s->compiler_t;
  pl_store_unlock(s);
  if (replacing_self)
    pl_raise_msg(t, "Install: compiler cannot replace its own machine");
  (void)pl_store_put_compiler(s, hash);
  return 1;
}

static pl_val op_compile(pl_thread* t, size_t ab) {
  pl_val a = pl_resolve(ARG(0));
  pl_cell* p = pl_as(PL_TAG_PIN, a);
  if (!p) {
    fprintf(stderr, "no pin, failing compile\n");
    return 0;
  }
  const uint8_t* hash = pl_pin_hash(a);
  if (hash == NULL)
    pl_raise_msg(t, "Compile: PIN must be saved first");
  pl_store_put_code(pl_heap_store(t->heap), hash);

  return 1;
}

/*
 * savePinOnly: write snap/<base58>.plan for the pin and (depth-first)
 * its sub-pins, skipping files that already exist; the file content is
 * the canonical text whose SHA-256 is the pin hash, so any PLAN
 * assembler can resume from the snapshot directory.
 */
static void save_pin_only(pl_thread* t, pl_val pin) {
  pl_cell* p = pl_ptr(pin);
  char b58[AX_BASE58_CAP(32)];
  ax_base58(pl_pin_hash(pin), 32, b58);
  char path[AX_BASE58_CAP(32) + 16];
  (void)snprintf(path, sizeof(path), "snap/%s.plan", b58);
  if (access(path, F_OK) == 0)
    return;

  uint32_t np = pl_pin_npins(p);
  for (uint32_t i = 0; i < np; i++)
    save_pin_only(t, pl_pin_subpins(p)[i]);

  size_t n;
  char* text = pl_canonize(ax_allocator_system(), pin, &n);
  FILE* f = fopen(path, "wb");
  if (f == NULL) {
    ax_free(ax_allocator_system(), text);
    pl_raise_msg(t, "Save: cannot write snapshot file");
  }
  size_t wrote = fwrite(text, 1, n, f);
  ax_free(ax_allocator_system(), text);
  if (fclose(f) != 0 || wrote != n)
    pl_raise_msg(t, "Save: short write");
}

static pl_val op_ice(pl_thread* t, size_t ab) {
  t->effect_epoch++; /* persistence effect: never cached across (F_MEMO) */
  if (pl_as(PL_TAG_PIN, ARG(0)) == NULL)
    pl_raise_msg(t, "Ice: expected a pin");
  char err[192] = {0};
  if (!pl_store_save_pin(pl_heap_store(t->heap), ARG(0), NULL, err,
                         sizeof(err)))
    pl_raise_msgf(t, "Ice: %s", err[0] != '\0' ? err : "store failure");
  return 0;
}

static pl_val op_save(pl_thread* t, size_t ab) {
  t->effect_epoch++; /* persistence effect: never cached across (F_MEMO) */
  pl_cell* pp = pl_as(PL_TAG_PIN, ARG(0));
  if (pp == NULL)
    pl_raise_msg(t, "Save: expected a pin");
  pl_store* store = pl_heap_store(t->heap);
  char err[192] = {0};
  if (!pl_store_save_root(store, ARG(0), NULL, err, sizeof(err)))
    pl_raise_msgf(t, "Save: %s", err[0] != '\0' ? err : "store failure");
  if (store->format == PL_STORE_FORMAT_SILO_V1) {
    return 0;
  }

  (void)mkdir("./snap", 0777); /* EEXIST is fine */
  save_pin_only(t, ARG(0));

  char b58[AX_BASE58_CAP(32)];
  ax_base58(pl_pin_hash(ARG(0)), 32, b58);
  FILE* f = fopen("snap/root.plan", "a");
  if (f == NULL)
    pl_raise_msg(t, "Save: cannot append snap/root.plan");
  fprintf(f, "@%s\n", b58);
  if (fclose(f) != 0)
    pl_raise_msg(t, "Save: short write");
  return 0;
}

static pl_val op_load(pl_thread* t, size_t ab) {
  AX_UNUSED(ab);
  pl_raise_msg(t, "load ./snap/root.plan"); /* loadSnapshot, verbatim */
}

/* ── The table ─────────────────────────────────────────────────────────── */

#define M2(a, b) ax_s2(a, b)
#define OP66(name, argc, mask, deep, body)                                     \
  {66, name, NULL, argc, mask, deep, false, false, body}
#define OP82(name, argc, mask, body)                                           \
  {82, 0, name, argc, mask, 0, true, false, body}
/* coordination effects: the machine blocks instead of executing;
 * deep is the initiation-time payload normalization */
#define OP82C(name, argc, mask, deep, body)                                    \
  {82, 0, name, argc, mask, deep, true, true, body}
/* Evaluator-local op 83 entries: no host-effect worker affinity. */
#define OP83_LOCAL(name, argc, mask, body)                                     \
  {83, 0, name, argc, mask, 0, false, false, body}
#define OP83_LOCAL_DEEP(name, argc, mask, deep, body)                          \
  {83, 0, name, argc, mask, deep, false, false, body}
/* Coordination effects are serviced in pkg/enki. */
#define OP83C(name, argc, mask, deep, body)                                    \
  {83, 0, name, argc, mask, deep, true, true, body}

const pl_opdesc pl_ops[] = {
    /* op 0: core PLAN */
    {0, 0, NULL, 1, 0b1, 0, false, false, op_pin},
    {0, 1, NULL, 3, 0b111, 0, false, false, op_law},
    {0, 2, NULL, 6, 0b100000, 0, false, false, op_elim},

    OP66(ax_s3('P', 'i', 'n'), 1, 0b1, 0, op_pin),
    OP66(ax_s3('L', 'a', 'w'), 3, 0b111, 0, op_law),
    OP66(ax_s4('E', 'l', 'i', 'm'), 6, 0b100000, 0, op_elim),

    OP66(ax_s3('I', 'n', 'c'), 1, 0b1, 0, op_inc),
    OP66(ax_s3('D', 'e', 'c'), 1, 0b1, 0, op_dec),
    OP66(ax_s3('A', 'd', 'd'), 2, 0b11, 0, op_add),
    OP66(ax_s3('S', 'u', 'b'), 2, 0b11, 0, op_sub),
    OP66(ax_s3('M', 'u', 'l'), 2, 0b11, 0, op_mul),
    OP66(ax_s3('D', 'i', 'v'), 2, 0b11, 0, op_div),
    OP66(ax_s3('M', 'o', 'd'), 2, 0b11, 0, op_mod),
    OP66(ax_s3('R', 's', 'h'), 2, 0b11, 0, op_rsh),
    OP66(ax_s3('L', 's', 'h'), 2, 0b11, 0, op_lsh),

    OP66(ax_s5('C', 'a', 's', 'e', '2'), 3, 0b1, 0, op_case2),
    OP66(ax_s5('C', 'a', 's', 'e', '3'), 4, 0b1, 0, op_case3),
    OP66(ax_s5('C', 'a', 's', 'e', '4'), 5, 0b1, 0, op_case4),
    OP66(ax_s5('C', 'a', 's', 'e', '5'), 6, 0b1, 0, op_case5),
    OP66(ax_s5('C', 'a', 's', 'e', '6'), 7, 0b1, 0, op_case6),
    OP66(ax_s5('C', 'a', 's', 'e', '7'), 8, 0b1, 0, op_case7),
    OP66(ax_s5('C', 'a', 's', 'e', '8'), 9, 0b1, 0, op_case8),
    OP66(ax_s5('C', 'a', 's', 'e', '9'), 10, 0b1, 0, op_case9),
    OP66(ax_s6('C', 'a', 's', 'e', '1', '0'), 11, 0b1, 0, op_case10),
    OP66(ax_s6('C', 'a', 's', 'e', '1', '1'), 12, 0b1, 0, op_case11),
    OP66(ax_s6('C', 'a', 's', 'e', '1', '2'), 13, 0b1, 0, op_case12),
    OP66(ax_s6('C', 'a', 's', 'e', '1', '3'), 14, 0b1, 0, op_case13),
    OP66(ax_s6('C', 'a', 's', 'e', '1', '4'), 15, 0b1, 0, op_case14),
    OP66(ax_s6('C', 'a', 's', 'e', '1', '5'), 16, 0b1, 0, op_case15),
    OP66(ax_s6('C', 'a', 's', 'e', '1', '6'), 17, 0b1, 0, op_case16),
    OP66(ax_s4('C', 'a', 's', 'e'), 3, 0b11, 0, op_case),

    OP66(ax_s4('T', 'e', 's', 't'), 2, 0b11, 0, op_test),
    OP66(ax_s3('N', 'i', 'b'), 2, 0b11, 0, op_nib),
    OP66(ax_s5('L', 'o', 'a', 'd', '8'), 2, 0b11, 0, op_load8),
    OP66(ax_s7('L', 'o', 'a', 'd', 'V', 'a', 'r'), 3, 0b111, 0, op_loadvar),
    OP66(ax_s6('S', 't', 'o', 'r', 'e', '8'), 3, 0b111, 0, op_store8),
    OP66(ax_s3('S', 'e', 't'), 2, 0b11, 0, op_set),
    OP66(ax_s5('C', 'l', 'e', 'a', 'r'), 2, 0b11, 0, op_clear),
    OP66(ax_s3('B', 'e', 'x'), 1, 0b1, 0, op_bex),
    OP66(ax_s6('T', 'r', 'u', 'n', 'c', '8'), 1, 0b1, 0, op_trunc8),
    OP66(ax_s7('T', 'r', 'u', 'n', 'c', '1', '6'), 1, 0b1, 0, op_trunc16),
    OP66(ax_s7('T', 'r', 'u', 'n', 'c', '3', '2'), 1, 0b1, 0, op_trunc32),
    OP66(ax_s7('T', 'r', 'u', 'n', 'c', '6', '4'), 1, 0b1, 0, op_trunc64),
    OP66(ax_s5('T', 'r', 'u', 'n', 'c'), 2, 0b11, 0, op_trunc),
    OP66(ax_s4('B', 'i', 't', 's'), 1, 0b1, 0, op_bits),
    OP66(ax_s5('B', 'y', 't', 'e', 's'), 1, 0b1, 0, op_bytes),

    OP66(ax_s5('U', 'n', 'p', 'i', 'n'), 1, 0b1, 0, op_unpin),
    OP66(ax_s3('S', 'e', 'q'), 2, 0b01, 0, op_seq),
    OP66(ax_s4('S', 'e', 'q', '2'), 3, 0b011, 0, op_seq2),
    OP66(ax_s4('S', 'e', 'q', '3'), 4, 0b0111, 0, op_seq3),
    OP66(ax_s3('S', 'a', 'p'), 2, 0b10, 0, op_sap),
    OP66(ax_s4('S', 'a', 'p', '2'), 3, 0b110, 0, op_sap2),
    OP66(ax_s4('T', 'y', 'p', 'e'), 1, 0b1, 0, op_type),
    OP66(ax_s5('I', 's', 'P', 'i', 'n'), 1, 0b1, 0, op_is_pin),
    OP66(ax_s5('I', 's', 'L', 'a', 'w'), 1, 0b1, 0, op_is_law),
    OP66(ax_s5('I', 's', 'A', 'p', 'p'), 1, 0b1, 0, op_is_app),
    OP66(ax_s5('I', 's', 'N', 'a', 't'), 1, 0b1, 0, op_is_nat),
    OP66(ax_s3('N', 'a', 't'), 1, 0b1, 0, op_nat),
    OP66(ax_s5('A', 'r', 'i', 't', 'y'), 1, 0b1, 0, op_arity),
    OP66(ax_s4('N', 'a', 'm', 'e'), 1, 0b1, 0, op_name),
    OP66(ax_s4('B', 'o', 'd', 'y'), 1, 0b1, 0, op_body),

    OP66(ax_s3('R', 'o', 'w'), 3, 0b011, 0, op_row),
    OP66(ax_s3('R', 'e', 'p'), 3, 0b101, 0, op_rep),
    OP66(ax_s5('S', 'l', 'i', 'c', 'e'), 3, 0b111, 0, op_slice),
    OP66(ax_s4('W', 'e', 'l', 'd'), 2, 0b11, 0, op_weld),
    OP66(ax_s5('F', 'o', 'r', 'c', 'e'), 1, 0, 0, op_force),
    OP66(ax_s7('D', 'e', 'e', 'p', 'S', 'e', 'q'), 2, 0, 0, op_deepseq),
    OP66(ax_s2('U', 'p'), 3, 0b101, 0, op_up),
    OP66(ax_s6('U', 'p', 'U', 'n', 'i', 'q'), 3, 0b101, 0, op_up),
    OP66(ax_s4('C', 'o', 'u', 'p'), 2, 0b11, 0, op_coup),
    OP66(ax_s3('T', 'r', 'y'), 2, 0, 0, op_try),
    OP66(ax_s5('T', 'h', 'r', 'o', 'w'), 1, 0b1, 0b1, op_throw),
    OP66(ax_s2('H', 'd'), 1, 0b1, 0, op_hd),
    OP66(ax_s2('I', 'x'), 2, 0b11, 0, op_ix),
    OP66(ax_s3('I', 'x', '0'), 1, 0b1, 0, op_ix0),
    OP66(ax_s3('I', 'x', '1'), 1, 0b1, 0, op_ix1),
    OP66(ax_s3('I', 'x', '2'), 1, 0b1, 0, op_ix2),
    OP66(ax_s3('I', 'x', '3'), 1, 0b1, 0, op_ix3),
    OP66(ax_s3('I', 'x', '4'), 1, 0b1, 0, op_ix4),
    OP66(ax_s3('I', 'x', '5'), 1, 0b1, 0, op_ix5),
    OP66(ax_s3('I', 'x', '6'), 1, 0b1, 0, op_ix6),
    OP66(ax_s3('I', 'x', '7'), 1, 0b1, 0, op_ix7),
    OP66(ax_s4('S', 'a', 'v', 'e'), 1, 0b1, 0b1, op_save),
    OP66(ax_s4('L', 'o', 'a', 'd'), 1, 0b1, 0, op_load),
    OP66(ax_s5('T', 'r', 'a', 'c', 'e'), 2, 0, 0b1, op_trace),
    OP66(ax_s3('N', 'i', 'l'), 1, 0b1, 0, op_nil),
    OP66(ax_s5('T', 'r', 'u', 't', 'h'), 1, 0b1, 0, op_truth),
    OP66(ax_s2('O', 'r'), 2, 0b01, 0, op_or),
    OP66(ax_s3('N', 'o', 'r'), 2, 0b01, 0, op_nor),
    OP66(ax_s3('A', 'n', 'd'), 2, 0b01, 0, op_and),
    OP66(ax_s2('I', 'f'), 3, 0b001, 0, op_if),
    OP66(ax_s3('I', 'f', 'z'), 3, 0b001, 0, op_ifz),
    OP66(ax_s2('E', 'q'), 2, 0b11, 0, op_eq),
    OP66(ax_s2('N', 'e'), 2, 0b11, 0, op_ne),
    OP66(ax_s2('L', 't'), 2, 0b11, 0, op_lt),
    OP66(ax_s2('L', 'e'), 2, 0b11, 0, op_le),
    OP66(ax_s2('G', 't'), 2, 0b11, 0, op_gt),
    OP66(ax_s2('G', 'e'), 2, 0b11, 0, op_ge),
    OP66(ax_s3('C', 'm', 'p'), 2, 0b11, 0, op_cmp),
    OP66(ax_s2('S', 'z'), 1, 0b1, 0, op_sz),
    OP66(ax_s4('L', 'a', 's', 't'), 1, 0b1, 0, op_last),
    OP66(ax_s4('I', 'n', 'i', 't'), 1, 0b1, 0, op_init),
    OP66(ax_s5('E', 'q', 'u', 'a', 'l'), 2, 0b11, 0b11, op_equal),
    OP66(ax_s7('I', 'n', 's', 't', 'a', 'l', 'l'), 1, 0b1, 0b1, op_install),
    OP66(ax_s7('C', 'o', 'm', 'p', 'i', 'l', 'e'), 1, 0b1, 0b1, op_compile),

    /* op 82: rplan I/O (mode-gated in eval.c) */
    OP82("Input", 1, 0b1, pl_op82_input),
    OP82("Output", 1, 0b1, pl_op82_output),
    OP82("Warn", 1, 0b1, pl_op82_warn),
    OP82("ReadFile", 1, 0b1, pl_op82_read_file),
    OP82("WriteFile", 2, 0b11, pl_op82_write_file),
    OP82("Print", 1, 0b1, pl_op82_print),
    OP82("Stamp", 1, 0b1, pl_op82_stamp),
    OP82("Now", 1, 0, pl_op82_now),
    OP82("CloseFd", 1, 0b1, pl_op82_closefd),
    OP82("Listen", 1, 0b1, pl_op82_listen),
    OP82("Accept", 1, 0b1, pl_op82_accept),
    OP82("Read", 2, 0b11, pl_op82_read),
    OP82("Write", 2, 0b11, pl_op82_write),
    /* payloads deep-normalize at initiation: forcing — and any
     * effects within it — runs as the sender's own execution, before
     * the request parks; the service pins already-normal values */
    OP82C("Spawn", 1, 0, 0b1, pl_op82_spawn),
    OP82C("Send", 2, 0b1, 0b10, pl_op82_send),
    OP82C("SendCaps", 3, 0b1, 0b110, pl_op82_send_caps),
    OP82C("Recv", 1, 0b1, 0, pl_op82_recv),
    OP82C("CloseHandle", 1, 0b1, 0, pl_op82_close_handle),
    OP82("Connect", 3, 0b111, pl_op82_connect),

    /* op 83: provisional primops; their PLAN-level semantics are deliberately
     * not yet committed.  Coordination operations are executor-serviced and
     * mode-gated like op 82; profiling operations stay evaluator-local.
     * ReadFolder returns an arbitrary row, so it cannot use op 82's nat-only
     * direct-effect replay seam.  Fetch args deep-normalize at initiation: the
     * request/config rows are consumed from C at service time, and effects
     * inside them run as the caller's own execution before the request parks.
     */
    OP83C("ReadFolder", 1, 0b1, 0, pl_op83_read_folder),
    OP83C("Fetch", 2, 0b11, 0b11, pl_op83_fetch),
    /* provisional: a blocking sleep, serviced synchronously in pkg/enki.
     * Sleep remains index 126. */
    OP83C("Sleep", 1, 0b1, 0, pl_op83_sleep),
    OP83_LOCAL("ZoneStart", 1, 0b1, pl_op83_zone_start),
    OP83_LOCAL("ZoneEnd", 1, 0b1, pl_op83_zone_end),

    /* op 66 additions are appended to preserve every established index. */
    OP66(ax_s5('s', 'c', 'a', 'n', '8'), 4, 0b1111, 0, op_scan8),
    OP66(ax_s7('S', 't', 'r', 'T', 'r', 'e', 'e'), 1, 0b1, 0b1, op_strtree),

    /* Reaver exposes these provisional string operations through splan. */
    OP83_LOCAL_DEEP("scan8", 4, 0b1111, 0, op_scan8),
    OP83_LOCAL_DEEP("StrTree", 1, 0b1, 0b1, op_strtree),

    /* Memo stays index 133. */
    OP66(ax_s4('M', 'e', 'm', 'o'), 2, 0b11, 0, op_memo),

    /* Deterministic crypto; append to preserve established indices. */
    OP83_LOCAL("Blake3", 1, 0b1, pl_op83_blake3),
    OP83_LOCAL("Sha256", 1, 0b1, pl_op83_sha256),
    OP83_LOCAL("Ed25519PublicKey", 1, 0b1, pl_op83_ed25519_public_key),
    OP83_LOCAL("Ed25519Sign", 2, 0b11, pl_op83_ed25519_sign),
    OP83_LOCAL("Ed25519Verify", 3, 0b111, pl_op83_ed25519_verify),
    OP83_LOCAL("Blake3Keyed", 2, 0b11, pl_op83_blake3_keyed),
    OP83_LOCAL("HmacSha256", 2, 0b11, pl_op83_hmac_sha256),

    OP66(ax_s3('I', 'c', 'e'), 1, 0b1, 0b1, op_ice),
    OP66(ax_s4('P', 'u', 'r', 'e'), 3, 0b001, 0, op_pure),
    OP83_LOCAL_DEEP("NativePack", 2, 0b11, 0b11, pl_native_pack),
    OP83_LOCAL_DEEP("NativeUnpack", 2, 0b11, 0b01, pl_native_unpack),
};

const size_t pl_nops = sizeof(pl_ops) / sizeof(pl_ops[0]);

typedef struct pl_opbucket {
  const uint16_t* ix;
  size_t n;
} pl_opbucket;

#define PL_IX_BUCKET(a) ((pl_opbucket){(a), sizeof(a) / sizeof((a)[0])})

static const uint16_t pl_op0_argc1[] = {0};
static const uint16_t pl_op0_argc3[] = {1};
static const uint16_t pl_op0_argc6[] = {2};

static const uint16_t pl_op66_argc1[] = {
    3,  6,  7,  38, 39, 40, 41, 42, 44,  45,  46,  52,  53,  54,
    55, 56, 57, 58, 59, 60, 65, 71, 72,  74,  75,  76,  77,  78,
    79, 80, 81, 82, 83, 85, 86, 99, 100, 101, 103, 104, 130, 141};
static const uint16_t pl_op66_argc2[] = {
    8,  9,  10, 11, 12, 13, 14, 31, 32, 33, 36, 37, 43, 47, 50,  64, 66,
    69, 70, 73, 84, 87, 88, 89, 92, 93, 94, 95, 96, 97, 98, 102, 133};
static const uint16_t pl_op66_argc3[] = {4,  15, 30, 34, 35, 48, 51,
                                         61, 62, 63, 67, 68, 90, 91, 142};
static const uint16_t pl_op66_argc4[] = {16, 49, 129};
static const uint16_t pl_op66_argc5[] = {17};
static const uint16_t pl_op66_argc6[] = {5, 18};
static const uint16_t pl_op66_argc7[] = {19};
static const uint16_t pl_op66_argc8[] = {20};
static const uint16_t pl_op66_argc9[] = {21};
static const uint16_t pl_op66_argc10[] = {22};
static const uint16_t pl_op66_argc11[] = {23};
static const uint16_t pl_op66_argc12[] = {24};
static const uint16_t pl_op66_argc13[] = {25};
static const uint16_t pl_op66_argc14[] = {26};
static const uint16_t pl_op66_argc15[] = {27};
static const uint16_t pl_op66_argc16[] = {28};
static const uint16_t pl_op66_argc17[] = {29};

static const uint16_t pl_op82_argc1[] = {105, 106, 107, 108, 110, 111, 112,
                                         113, 114, 115, 118, 121, 122};
static const uint16_t pl_op82_argc2[] = {109, 116, 117, 119};
static const uint16_t pl_op82_argc3[] = {120, 123};

static const uint16_t pl_op83_argc1[] = {124, 126, 127, 128,
                                         132, 134, 135, 136};
static const uint16_t pl_op83_argc2[] = {125, 137, 139, 140, 143, 144};
static const uint16_t pl_op83_argc3[] = {138};
static const uint16_t pl_op83_argc4[] = {131};

static pl_opbucket pl_op_lookup_bucket(uint64_t opset, uint32_t argc) {
  switch (opset) {
  case 0:
    switch (argc) {
    case 1:
      return PL_IX_BUCKET(pl_op0_argc1);
    case 3:
      return PL_IX_BUCKET(pl_op0_argc3);
    case 6:
      return PL_IX_BUCKET(pl_op0_argc6);
    }
    break;
  case 66:
    switch (argc) {
    case 1:
      return PL_IX_BUCKET(pl_op66_argc1);
    case 2:
      return PL_IX_BUCKET(pl_op66_argc2);
    case 3:
      return PL_IX_BUCKET(pl_op66_argc3);
    case 4:
      return PL_IX_BUCKET(pl_op66_argc4);
    case 5:
      return PL_IX_BUCKET(pl_op66_argc5);
    case 6:
      return PL_IX_BUCKET(pl_op66_argc6);
    case 7:
      return PL_IX_BUCKET(pl_op66_argc7);
    case 8:
      return PL_IX_BUCKET(pl_op66_argc8);
    case 9:
      return PL_IX_BUCKET(pl_op66_argc9);
    case 10:
      return PL_IX_BUCKET(pl_op66_argc10);
    case 11:
      return PL_IX_BUCKET(pl_op66_argc11);
    case 12:
      return PL_IX_BUCKET(pl_op66_argc12);
    case 13:
      return PL_IX_BUCKET(pl_op66_argc13);
    case 14:
      return PL_IX_BUCKET(pl_op66_argc14);
    case 15:
      return PL_IX_BUCKET(pl_op66_argc15);
    case 16:
      return PL_IX_BUCKET(pl_op66_argc16);
    case 17:
      return PL_IX_BUCKET(pl_op66_argc17);
    }
    break;
  case 82:
    switch (argc) {
    case 1:
      return PL_IX_BUCKET(pl_op82_argc1);
    case 2:
      return PL_IX_BUCKET(pl_op82_argc2);
    case 3:
      return PL_IX_BUCKET(pl_op82_argc3);
    }
    break;
  case 83:
    switch (argc) {
    case 1:
      return PL_IX_BUCKET(pl_op83_argc1);
    case 2:
      return PL_IX_BUCKET(pl_op83_argc2);
    case 3:
      return PL_IX_BUCKET(pl_op83_argc3);
    case 4:
      return PL_IX_BUCKET(pl_op83_argc4);
    }
    break;
  }
  return (pl_opbucket){NULL, 0};
}

static bool nat_name_eq(pl_val v, const char* s) {
  if (!pl_is_nat(v))
    return false;
  size_t n = strlen(s);
  if (pl_nat_byte_len(v) != n)
    return false;
  for (size_t i = 0; i < n; i++) {
    if (pl_nat_byte_at(v, i) != (uint8_t)s[i])
      return false;
  }
  return true;
}

int pl_op_lookup(uint64_t opset, pl_val name, uint32_t argc) {
  pl_opbucket b = pl_op_lookup_bucket(opset, argc);
  for (size_t j = 0; j < b.n; j++) {
    size_t i = b.ix[j];
    const pl_opdesc* d = &pl_ops[i];
    // ax_assume(d->opset == opset && d->argc == argc,
    // "primop lookup bucket mismatch");
    if (d->name_c != NULL ? nat_name_eq(name, d->name_c)
                          : (pl_is_nat63(name) && d->name == name))
      return (int)i;
  }
  return -1;
}
