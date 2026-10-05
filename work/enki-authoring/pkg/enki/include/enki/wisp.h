#ifndef EN_WISP_H
#define EN_WISP_H

/*
 * wisp: the PLAN-assembly front end (parser, macro expander, top-level
 * evaluator).  Mirrors the reference PlanAssembler / Repl modules,
 * rebased onto the plan API.
 */

#include <setjmp.h>
#include <stdbool.h>
#include <stddef.h>

#include "axsys/allocator.h"
#include "plan/eval.h"
#include "plan/heap.h"
#include "plan/value.h"

typedef struct er_scheduler er_scheduler; /* enki/actor.h */
typedef struct er_actor er_actor;
typedef struct er_mt_executor er_mt_executor;

typedef struct en_env_entry {
  pl_val key_v;
  pl_val val_v;
  int mac_f;
  struct en_env_entry* next;
} en_env_entry;

typedef struct en_wisp {
  const ax_allocator* loc_a;
  pl_heap* heap;
  pl_thread* t;
  jmp_buf errjmp;
  bool err_f; /* has errjmp been set */
  char* msg_c;
  en_env_entry* env;
  /* rooted scratch stack (registered as a GC root source) */
  pl_val* tmp_v;
  size_t tmp_s, tmp_cap;
  /*
   * Optional actor executor (the reference withNewRts): when set, the
   * guarded evaluations below arm `t` (which must be `self`'s adopted
   * thread) and drive the scheduler, so op-82 coordination effects in
   * top-level code are serviced instead of raising.  NULL keeps the
   * plain host evaluation path.
   */
  er_scheduler* sched;
  er_actor* self;
  /* Optional multithreaded executor for scheduler-driven evaluations. */
  er_mt_executor* exec;
} en_wisp;

en_wisp* en_wisp_new(pl_heap* heap);
void en_wisp_free(en_wisp* w);

pl_val en_wisp_parse(en_wisp* w, char** str);
pl_val en_wisp_macroexpand(en_wisp* w, pl_val v);
pl_val en_wisp_thunk(en_wisp* w, pl_val v);
pl_val en_wisp_eval(en_wisp* w, pl_val v);
char* en_wisp_print(en_wisp* w, pl_val v, size_t* out_s);

/* Environment access (used by the boot driver). */
en_env_entry* en_wisp_getenv(en_wisp* w, pl_val key);
void en_wisp_putenv(en_wisp* w, pl_val key, bool mac_f, pl_val val);

/* Rooted scratch helpers. */
size_t en_root_mark(en_wisp* w);
void en_root_pop(en_wisp* w, size_t mark);
void en_root_push(en_wisp* w, pl_val v);

/* Construction helpers (reserve + root internally). */
pl_val en_app_make(en_wisp* w, pl_val fn, size_t n, const pl_val* args);
pl_val en_bytes_nat(en_wisp* w, const char* b, size_t n);
pl_val en_string_nat(en_wisp* w, const char* s);

/* Guarded evaluation: PLAN errors become wisp failures (longjmp). */
pl_val en_run_whnf(en_wisp* w, pl_val v);
pl_val en_run_nf(en_wisp* w, pl_val v);

[[noreturn]] void en_wisp_fail(en_wisp* w, const char* msg);

#endif
