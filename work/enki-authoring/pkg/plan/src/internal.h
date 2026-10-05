#ifndef PL_INTERNAL_H
#define PL_INTERNAL_H

/* Private plan-layer declarations shared between eval.c, op.c, pin.c. */

#include "plan/build.h"
#include "plan/eval.h"
#include "plan/heap.h"
#include "plan/value.h"

/*
 * Primop descriptor.  Strictness is data: strict_mask bit i forces
 * arg i to WHNF (low to high) before the body runs; deep_mask bit i
 * additionally deep-normalizes arg i — through the machine at depth 0,
 * so effects inside the normalization suspend and block correctly
 * (coordination ops use this to force payloads before the request
 * parks).  Bodies address their args as value-stack slots
 * t->vstack[ab + i]: slots survive reserves (the collector rewrites them
 * in place) and remain valid across nested machine runs, which may grow
 * the stack.  Bodies may push F_APPLY/F_SEQ/F_NF frames and return a
 * value that the machine continues to evaluate.
 *
 * host_effect marks operations that may enter embedder-controlled work;
 * the evaluator calls rplan_effect_f before their bodies begin.  Profiling
 * operations remain ordinary evaluator work even though they share op set 83.
 *
 * coord marks a coordination effect: the body only validates the forced
 * args and returns the request spine [name, args…]; the machine parks
 * it in t->blocked_on and suspends with PL_RUN_BLOCKED instead of
 * evaluating the body's result.  The name slot sits at vstack[ab - 1].
 */
typedef struct pl_opdesc {
  uint64_t opset;     /* 0, 66, 82 or 83 */
  uint64_t name;      /* op0: subop number; op66: name mote */
  const char* name_c; /* non-NULL: match the name nat against this string
                         (op-82 names can exceed the 7-byte mote width) */
  uint8_t argc;
  uint32_t strict_mask;
  uint32_t deep_mask;
  bool host_effect;
  bool coord;
  pl_val (*body)(pl_thread* t, size_t ab);
} pl_opdesc;

extern const pl_opdesc pl_ops[];
extern const size_t pl_nops;

/* Cheap eagerness: total O(1) nat primops whose arguments are already
 * direct nats compute to the same value whenever they are forced, so a
 * MK_THK KNOWN of one of these computes instead of allocating.  The
 * decoder stores the code in the thunk instruction's spare operand. */
typedef enum pl_spec {
  PL_SPEC_NONE = 0,
  PL_SPEC_ADD,
  PL_SPEC_SUB,
  PL_SPEC_MUL,
  PL_SPEC_INC,
  PL_SPEC_DEC,
  PL_SPEC_EQ,
  PL_SPEC_NE,
  PL_SPEC_LT,
  PL_SPEC_LE,
  PL_SPEC_GT,
  PL_SPEC_GE,
  PL_SPEC_CMP,
  PL_SPEC_NIL,
  PL_SPEC_TRUTH,
  /* Run the op's own body: for total, allocation-free O(1) field reads
   * (row projections and value inspections) whose strict operands are
   * already values.  The body may hand back an unevaluated element; that
   * element then stands in for the projection thunk. */
  PL_SPEC_BODY,
} pl_spec;

/* Returns descriptor index, or -1 if there is no matching primop. */
int pl_op_lookup(uint64_t opset, pl_val name, uint32_t argc);

/* op 82 (rplan) bodies, in rplan.c; arg conventions as pl_opdesc. */
pl_val pl_op82_input(pl_thread* t, size_t ab);
pl_val pl_op82_output(pl_thread* t, size_t ab);
pl_val pl_op82_warn(pl_thread* t, size_t ab);
pl_val pl_op82_read_file(pl_thread* t, size_t ab);
pl_val pl_op82_write_file(pl_thread* t, size_t ab);
pl_val pl_op82_print(pl_thread* t, size_t ab);
pl_val pl_op82_stamp(pl_thread* t, size_t ab);
pl_val pl_op82_now(pl_thread* t, size_t ab);
pl_val pl_op82_closefd(pl_thread* t, size_t ab);
pl_val pl_op82_listen(pl_thread* t, size_t ab);
pl_val pl_op82_accept(pl_thread* t, size_t ab);
pl_val pl_op82_connect(pl_thread* t, size_t ab);
pl_val pl_op82_read(pl_thread* t, size_t ab);
pl_val pl_op82_write(pl_thread* t, size_t ab);

/* op 82 coordination effects: validate + build the request spine. */
pl_val pl_op82_spawn(pl_thread* t, size_t ab);
pl_val pl_op82_send(pl_thread* t, size_t ab);
pl_val pl_op82_send_caps(pl_thread* t, size_t ab);
pl_val pl_op82_recv(pl_thread* t, size_t ab);
pl_val pl_op82_close_handle(pl_thread* t, size_t ab);

/* op 83 (provisional staging area) coordination effects; serviced in pkg/enki.
 */
pl_val pl_op83_read_folder(pl_thread* t, size_t ab);
pl_val pl_op83_fetch(pl_thread* t, size_t ab);
pl_val pl_op83_sleep(pl_thread* t, size_t ab);
pl_val pl_op83_blake3(pl_thread* t, size_t ab);
pl_val pl_op83_sha256(pl_thread* t, size_t ab);
pl_val pl_op83_blake3_keyed(pl_thread* t, size_t ab);
pl_val pl_op83_hmac_sha256(pl_thread* t, size_t ab);
pl_val pl_op83_ed25519_public_key(pl_thread* t, size_t ab);
pl_val pl_op83_ed25519_sign(pl_thread* t, size_t ab);
pl_val pl_op83_ed25519_verify(pl_thread* t, size_t ab);
/* op 83 direct profiling controls, implemented beside evaluator profiling. */
pl_val pl_op83_zone_start(pl_thread* t, size_t ab);
pl_val pl_op83_zone_end(pl_thread* t, size_t ab);

/* Close and release all explicit profiler state before a thread is freed. */
void pl_profile_thread_free(pl_thread* t);
/* Logical Chrome Trace lane active while pl_thread_run drives this native
 * thread, or zero for direct host-side evaluation. */
uint64_t pl_profile_current_lane(void);

/* Frame-push helpers usable from op bodies. */
static inline void pl_push_apply(pl_thread* t, pl_val x) {
  pl_frame* f = pl_fpush(t);
  f->kind = PL_F_APPLY;
  f->b = x;
}

static inline void pl_push_seq(pl_thread* t, pl_val y) {
  pl_frame* f = pl_fpush(t);
  f->kind = PL_F_SEQ;
  f->b = y;
}

static inline void pl_push_nf(pl_thread* t) {
  pl_frame* f = pl_fpush(t);
  f->kind = PL_F_NF;
}

/* Dynamic raise: message formatted into a per-thread static buffer. */
[[noreturn]] void pl_raise_msgf(pl_thread* t, const char* fmt, ...);

/* Is v deeply normal already? (terminal kinds or NORMAL flag) */
static inline bool pl_is_normal(pl_val v) {
  if (pl_is_nat63(v))
    return true;
  switch (pl_tag(v)) {
  case PL_TAG_NAT:
    return true;
  case PL_TAG_PIN:
    return (pl_hdr_flags(pl_pin_resolved(pl_ptr(v))[0]) & PL_F_NORMAL) != 0;
  case PL_TAG_APP:
  case PL_TAG_LAW:
    return (pl_hdr_flags(*pl_ptr(v)) & PL_F_NORMAL) != 0;
  default:
    return false;
  }
}

#endif
