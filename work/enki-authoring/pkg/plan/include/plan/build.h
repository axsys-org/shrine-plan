#ifndef PL_BUILD_H
#define PL_BUILD_H

/*
 * Value construction.  Every constructor here is bump-only (I2): the
 * caller MUST have reserved headroom with pl_gc_reserve, using the
 * PL_*_CELLS size macros from plan/value.h, before calling.
 */

#include "plan/heap.h"
#include "plan/value.h"

/* Direct nat if < 2^63, else a boxed single-limb nat (2 cells). */
pl_val pl_mk_nat_u64(pl_thread* t, uint64_t n);

/* Allocate a boxed nat with `limbs` limbs; caller fills *out, then
 * canonicalizes with pl_nat_trim (which may return a direct nat). */
pl_val pl_mk_nat_limbs(pl_thread* t, size_t limbs, uint64_t** out);
pl_val pl_nat_trim(pl_val v);

/* APP construction. Counts exclude the head and must be positive; callers
 * collapse head-only results to the head. The head must be WHNF (arity is
 * consulted, never forced). */
pl_val pl_mk_app_snoc(pl_thread* t, pl_val f, pl_val x);
/* Flat append of m args to f (as m chained snocs, one allocation).
 * Caller reserves PL_APP_CELLS((f is APP ? pl_app_n(f) : 0) + m). */
pl_val pl_mk_app_cat(pl_thread* t, pl_val f, uint32_t m, const pl_val* args);
pl_val pl_mk_app_take(pl_thread* t, pl_val app, uint32_t n);
pl_val pl_mk_app_from(pl_thread* t, pl_val head, uint32_t n,
                      const pl_val* args);

pl_val pl_mk_law(pl_thread* t, uint64_t arity, pl_val name, pl_val body);
pl_val pl_mk_env(pl_thread* t, uint32_t nslots); /* slots zeroed to nat 0 */
/* Allocation-only ENV constructor.  The caller must overwrite every slot in
 * a no-collect window before publishing the value or allowing a collection. */
pl_val pl_mk_env_uninit(pl_thread* t, uint32_t nslots);
pl_val pl_mk_thunk(pl_thread* t, pl_val env, pl_val expr);
pl_val pl_mk_thke(pl_thread* t, uint64_t bane, uint32_t nargs, pl_val* args);
/* PL_BAN_PRIM_KNOWN thke: args[0] = the ingest-resolved pl_ops index. */
pl_val pl_mk_thke_known(pl_thread* t, uint32_t idx, uint32_t nargs,
                        pl_val* args);

/* Arity of a WHNF value (never forces). */
uint64_t pl_arity(pl_val v);

/* ── The only three mutation sites ──────── */

void pl_thke_update(pl_thread* t, pl_val thke, pl_val result);
/* Overwrite a THUNK or BLACKHOLE in place as K_IND -> result. */
void pl_thunk_update(pl_thread* t, pl_val thunk_or_bh, pl_val result);

/* Snap a normalized child into pointer field `field` of `parent`. */
void pl_nf_writeback(pl_val parent, uint32_t field, pl_val child);

/* Pointer-field map used by nf and the collector: number of pointer
 * fields of a WHNF object and access to field i (APP: head+args;
 * LAW: name+body; unresolved PIN: body; others: none). */
uint32_t pl_nf_nfields(pl_val v);
pl_val pl_nf_field(pl_val v, uint32_t i);

#endif
