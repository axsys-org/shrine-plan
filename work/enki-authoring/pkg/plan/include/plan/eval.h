#ifndef PL_EVAL_H
#define PL_EVAL_H

/*
 * The reduction machine: an explicit-frame EVAL/RETURN loop over the
 * thread's frame stack.  No unbounded C recursion, no C-stack scanning.
 * The naive JUDGE/KAL path implemented here is the executable reference
 * semantics; enki may install an enter hook for jets / compiled code.
 */

#include "plan/heap.h"
#include "plan/value.h"

/* Force to weak head normal form. */
pl_val pl_whnf(pl_thread* t, pl_val v);

/* The reference `%`: forces f (to decide arity); x stays lazy.  A
 * saturated application is executed to WHNF. */
pl_val pl_apply(pl_thread* t, pl_val f, pl_val x);

/* Deep normalization (the reference rnf). */
pl_val pl_nf(pl_thread* t, pl_val v);

/* ── Suspension ────────────────────────────────────────────────────────── */

/*
 * A green thread is not a saved C stack: the complete continuation lives
 * in the thread's value/frame stacks plus the resume slots.  Suspension
 * is returning from pl_thread_run; resumption is calling it again.
 *
 * Fuel is the only yield trigger: one decrement per machine step at
 * the EVAL position, deterministic for identical state and fuel.  Yields
 * fire only at depth-0 safepoints; inside C-entry regions (re-entrant
 * evaluator calls, op bodies, jets) the request is deferred and fires at
 * the first depth-0 step.
 */

typedef enum {
  PL_RUN_DONE = 0, /* normal completion; value in t->result */
  PL_RUN_EXN,      /* PLAN exception; t->exn / t->exn_msg, stacks unwound */
  PL_RUN_YIELDED,  /* fuel exhausted; resume with pl_thread_run */
  PL_RUN_BLOCKED,  /* awaiting an effect response (t->blocked_on);
                      deposit one with pl_thread_deposit, then run */
} pl_run_status;

typedef enum {
  PL_RES_EVAL = 0, /* re-enter the machine EVALing t->resume_val */
  PL_RES_RETURN,   /* re-enter RETURNing t->resume_val to the top frame */
  PL_RES_RUN,      /* re-enter compiled code at the top F_EXEC frame's
                      saved offset (BR/JMP back-edge and CALL yields) */
} pl_resume_kind;

/*
 * Arm a thread to evaluate v (to WHNF) from the current stack position.
 * Records the entry watermarks: an uncaught exception unwinds to
 * them, and the run completes when the frame stack returns to base.
 */
void pl_thread_start(pl_thread* t, pl_val v);
/* As pl_thread_start, but drive a deep normalization of v. */
void pl_thread_start_nf(pl_thread* t, pl_val v);
/* Arm a deep normalization of (f x) — the actor boot shape, the
 * reference `force (fn % N 0)`. */
void pl_thread_start_call_nf(pl_thread* t, pl_val f, pl_val x);

/*
 * Run until done, exception, or fuel exhaustion.  The only public
 * execution entry for suspendable threads.  Resumes per
 * t->resume_kind; must not be re-entered from evaluator C code.
 */
pl_run_status pl_thread_run(pl_thread* t, uint64_t fuel);

/* Abandon a stopped PL_RUN_BLOCKED computation and unwind its stacks and
 * run-local profiling zones to the entry watermarks.  The thread remains
 * blocked and must be re-armed with pl_thread_start before it can run again. */
void pl_thread_abandon(pl_thread* t);

/* Deposit an effect response into a PL_RUN_BLOCKED thread: the
 * machine resumes by RETURNing the response (a WHNF) to the pending
 * frame.  Coordination ops (op 82 Spawn/Send/SendCaps/Recv/CloseHandle)
 * are the PL_RUN_BLOCKED producers; the parked request is the spine
 * [OpName, args…] with strict args already forced. */
void pl_thread_deposit(pl_thread* t, pl_val response);

/* Result of a completed run; valid until the next pl_thread_start or the
 * next outermost host entry (pl_whnf/pl_apply/pl_nf) on this thread. */
pl_val pl_thread_result(pl_thread* t);

/* The parked effect request of a PL_RUN_BLOCKED thread. */
pl_val pl_thread_request(pl_thread* t);

/* ── Direct-effect interception (the record/replay seam) ───────────────── */

/*
 * When set, the machine consults the hook instead of the handler for
 * every direct (non-coordination) op-82 effect.  Return true with *out
 * filled to substitute a result (replay: no syscall happens); return
 * false to run the real handler.  A live-logging hook performs the
 * effect itself via pl_io_run and records the result.  The hook runs
 * inside the op's C-entry region; out must be WHNF.
 */
typedef bool (*pl_io_hook)(pl_thread* t, uint32_t op, size_t argbase,
                           pl_val* out);
void pl_set_io_hook(pl_io_hook hook);

/* Run the real handler of direct op `op` (hooks only). */
pl_val pl_io_run(pl_thread* t, uint32_t op, size_t argbase);
/* Stable identity for the log: the op's name and arg count. */
const char* pl_io_name(uint32_t op);
uint32_t pl_io_argc(uint32_t op);

/* ── Errors ────────────────────────────────────────────────────────────── */

/* Raise PLAN_EXN carrying a PLAN value (catchable by Try). */
[[noreturn]] void pl_raise(pl_thread* t, pl_val v);
/* Raise a runtime error with a static message (NOT catchable by Try). */
[[noreturn]] void pl_raise_msg(pl_thread* t, const char* msg);

/*
 * Handler protocol.  Usage:
 *
 *   pl_catch c;
 *   pl_catch_init(t, &c);
 *   if (setjmp(c.jb) == 0) {
 *     ... protected region ...
 *     pl_catch_pop(t, &c);
 *   } else {
 *     pl_catch_unwind(t, &c);   // resets stacks to the saved watermarks
 *     ... t->exn / t->exn_msg ...
 *   }
 */
typedef struct pl_catch {
  jmp_buf jb;
  jmp_buf* prev;
  size_t vsp, fsp;
  uint32_t centry;       /* centry_depth watermark; restored on unwind */
  uint64_t profile_mark; /* ZoneStart generation watermark */
} pl_catch;

void pl_catch_init(pl_thread* t, pl_catch* c);
void pl_catch_pop(pl_thread* t, pl_catch* c);
void pl_catch_unwind(pl_thread* t, pl_catch* c);

/* ── enki hook seam: jets / compiled code ──────────────────────────────── */

/*
 * Consulted by ENTER before the naive JUDGE/KAL path runs a law.  The
 * saturated call is parked on the value stack: vstack[hbase] is the head
 * (law or pinned law) and vstack[hbase+1 .. hbase+argc] are the
 * arguments.  A hook that handles the call writes the (possibly lazy)
 * result to *out and returns true; the machine then continues by
 * evaluating *out.  NULL hook (the default) means the naive path.
 */
typedef bool (*pl_enter_hook)(pl_thread* t, size_t hbase, uint32_t argc,
                              pl_val* out);
void pl_set_enter_hook(pl_enter_hook hook);

#endif
