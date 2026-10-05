#include "plan/build.h"

#include <string.h>

#include "axsys/assume.h"
#include "plan/nat.h"

/* gcc -O3's inliner chains the pl_as-returned-NULL fact into
 * pl_arity's APP case and reports an impossible null dereference
 * (APP-tagged vals always carry an address); clang and lower -O
 * levels are clean. */
#if defined(__GNUC__) && !defined(__clang__)
#pragma GCC diagnostic ignored "-Wnull-dereference"
#endif

/* ── Nats ──────────────────────────────────────────────────────────────── */

pl_val pl_mk_nat_u64(pl_thread* t, uint64_t n) {
  if (n <= PL_NAT63_MAX)
    return n;
  pl_cell* p = pl_bump(t, PL_NAT_CELLS(1));
  pl_cache_stat_alloc(t, PL_K_NAT, PL_NAT_CELLS(1));
  p[0] = pl_hdr_make(PL_K_NAT, PL_F_NORMAL, 1, PL_NAT_CELLS(1));
  p[1] = n;
  return pl_make(PL_TAG_NAT, p);
}

pl_val pl_mk_nat_limbs(pl_thread* t, size_t limbs, uint64_t** out) {
  ax_assume(limbs >= 1 && limbs < (1u << 20), "nat limb count out of range");
  pl_cell* p = pl_bump(t, PL_NAT_CELLS(limbs));
  pl_cache_stat_alloc(t, PL_K_NAT, PL_NAT_CELLS(limbs));
  p[0] =
      pl_hdr_make(PL_K_NAT, PL_F_NORMAL, (uint32_t)limbs, PL_NAT_CELLS(limbs));
  *out = (uint64_t*)(p + 1);
  return pl_make(PL_TAG_NAT, p);
}

pl_val pl_nat_trim(pl_val v) {
  if (pl_is_nat63(v))
    return v;
  pl_cell* p = pl_ptr(v);
  ax_assume(pl_hdr_kind(p[0]) == PL_K_NAT, "trim of non-nat");
  uint32_t used = pl_nat_limbs(p);
  uint64_t* limb = pl_nat_limb_ptr(p);
  while (used > 0 && limb[used - 1] == 0)
    used--;
  if (used == 0)
    return 0;
  if (used == 1 && limb[0] <= PL_NAT63_MAX)
    return limb[0];
  p[0] = pl_hdr_make(PL_K_NAT, PL_F_NORMAL, used, pl_hdr_cells(p[0]));
  return v;
}

/* ── Arity (WHNF inputs only; never forces) ────────────────────────────── */

uint64_t pl_arity(pl_val v) {
  if (pl_is_nat63(v))
    return 0;
  switch (pl_tag(v)) {
  case PL_TAG_NAT:
    return 0;
  case PL_TAG_LAW:
    return pl_law_arity(pl_ptr(v));
  case PL_TAG_PIN: {
    pl_val body = pl_pin_body(pl_ptr(v));
    if (!pl_is_nat63(body) && pl_tag(body) == PL_TAG_LAW)
      return pl_law_arity(pl_ptr(body));
    return 1; /* pinned nat: 1; pinned app/pin: 1, error at exec */
  }
  case PL_TAG_APP:
    return pl_app_need(pl_ptr(v));
  default:
    ax_abort("pl_arity on a non-WHNF value (tag 0x%llx)",
             (unsigned long long)pl_tag(v));
  }
}

static uint32_t pl_need_after(pl_val head, uint64_t n_args) {
  uint64_t a = pl_arity(head);
  if (a == 0 || a <= n_args)
    return 0;
  uint64_t need = a - n_args;
  ax_assume(need < (1u << 20), "app need exceeds meta width");
  return (uint32_t)need;
}

/* ── APPs ──────────────────────────────────────────────────────────────── */

pl_val pl_mk_app_from(pl_thread* t, pl_val head, uint32_t n,
                      const pl_val* args) {
  ax_assume(n >= 1, "empty app");
  pl_cell* p = pl_bump(t, PL_APP_CELLS(n));
  pl_cache_stat_alloc(t, PL_K_APP, PL_APP_CELLS(n));
  p[0] = pl_hdr_make(PL_K_APP, 0, pl_need_after(head, n), PL_APP_CELLS(n));
  p[1] = head;
  memcpy(p + 2, args, n * sizeof(pl_val));
  return pl_make(PL_TAG_APP, p);
}

pl_val pl_mk_app_cat(pl_thread* t, pl_val f, uint32_t m, const pl_val* args) {
  ax_assume(m >= 1, "empty cat");
  pl_cell* fp = pl_as(PL_TAG_APP, f);
  if (fp == NULL)
    return pl_mk_app_from(t, f, m, args);
  uint32_t n = pl_app_n(fp);
  pl_cell* p = pl_bump(t, PL_APP_CELLS(n + m));
  pl_cache_stat_alloc(t, PL_K_APP, PL_APP_CELLS(n + m));
  p[0] = pl_hdr_make(PL_K_APP, 0, pl_need_after(pl_app_head(fp), n + m),
                     PL_APP_CELLS(n + m));
  p[1] = fp[1];
  memcpy(p + 2, fp + 2, n * sizeof(pl_val));
  memcpy(p + 2 + n, args, m * sizeof(pl_val));
  return pl_make(PL_TAG_APP, p);
}

pl_val pl_mk_app_snoc(pl_thread* t, pl_val f, pl_val x) {
  pl_cell* fp = pl_as(PL_TAG_APP, f);
  if (fp != NULL) {
    uint32_t n = pl_app_n(fp);
    uint32_t need = pl_app_need(fp);
    pl_cell* p = pl_bump(t, PL_APP_CELLS(n + 1));
    pl_cache_stat_alloc(t, PL_K_APP, PL_APP_CELLS(n + 1));
    p[0] =
        pl_hdr_make(PL_K_APP, 0, need == 0 ? 0 : need - 1, PL_APP_CELLS(n + 1));
    p[1] = fp[1];
    memcpy(p + 2, fp + 2, n * sizeof(pl_val));
    p[2 + n] = x;
    return pl_make(PL_TAG_APP, p);
  }
  pl_cell* p = pl_bump(t, PL_APP_CELLS(1));
  pl_cache_stat_alloc(t, PL_K_APP, PL_APP_CELLS(1));
  p[0] = pl_hdr_make(PL_K_APP, 0, pl_need_after(f, 1), PL_APP_CELLS(1));
  p[1] = f;
  p[2] = x;
  return pl_make(PL_TAG_APP, p);
}

pl_val pl_mk_app_take(pl_thread* t, pl_val app, uint32_t n) {
  pl_cell* ap = pl_as(PL_TAG_APP, app);
  ax_assume(ap != NULL && n >= 1 && n < pl_app_n(ap), "bad app take");
  pl_cell* p = pl_bump(t, PL_APP_CELLS(n));
  pl_cache_stat_alloc(t, PL_K_APP, PL_APP_CELLS(n));
  p[0] = pl_hdr_make(PL_K_APP, 0, pl_need_after(pl_app_head(ap), n),
                     PL_APP_CELLS(n));
  p[1] = ap[1];
  memcpy(p + 2, ap + 2, n * sizeof(pl_val));
  return pl_make(PL_TAG_APP, p);
}

/* ── Laws / envs / thunks ──────────────────────────────────────────────── */

pl_val pl_mk_law(pl_thread* t, uint64_t arity, pl_val name, pl_val body) {
  pl_cell* p = pl_bump(t, PL_LAW_CELLS);
  pl_cache_stat_alloc(t, PL_K_LAW, PL_LAW_CELLS);
  p[0] = pl_hdr_make(PL_K_LAW, 0, 0, PL_LAW_CELLS);
  p[1] = arity;
  p[2] = name;
  p[3] = body;
  return pl_make(PL_TAG_LAW, p);
}

pl_val pl_mk_env_uninit(pl_thread* t, uint32_t nslots) {
  pl_cell* p = pl_bump(t, PL_ENV_CELLS(nslots));
  pl_cache_stat_alloc(t, PL_K_ENV, PL_ENV_CELLS(nslots));
  p[0] = pl_hdr_make(PL_K_ENV, 0, 0, PL_ENV_CELLS(nslots));
  return pl_make(PL_TAG_ENV, p);
}

pl_val pl_mk_env(pl_thread* t, uint32_t nslots) {
  pl_val env = pl_mk_env_uninit(t, nslots);
  memset(pl_env_slots(pl_ptr(env)), 0, nslots * sizeof(pl_cell));
  return env;
}

pl_val pl_mk_thunk(pl_thread* t, pl_val env, pl_val expr) {
  pl_cell* p = pl_bump(t, PL_THUNK_CELLS);
  pl_cache_stat_alloc(t, PL_K_THUNK, PL_THUNK_CELLS);
  p[0] = pl_hdr_make(PL_K_THUNK, 0, 0, PL_THUNK_CELLS);
  p[1] = env;
  p[2] = expr;
  return pl_make(PL_TAG_DEFER, p);
}

pl_val pl_mk_thke(pl_thread* t, uint64_t bane, uint32_t nargs, pl_val* args) {
  uint32_t size = PL_THKE_CELLS(nargs);
  pl_cell* p = pl_bump(t, PL_THKE_CELLS(nargs));
  pl_cache_stat_alloc(t, PL_K_THKE, size);
  p[0] = pl_hdr_make(PL_K_THKE, 0, 0, size);
  p[1] = bane;
  memcpy(p + 2, args, sizeof(pl_val) * nargs);
  return pl_make(PL_TAG_DEFER, p);
}

pl_val pl_mk_thke_known(pl_thread* t, uint32_t idx, uint32_t nargs,
                        pl_val* args) {
  uint32_t size = PL_THKE_CELLS(nargs + 1);
  pl_cell* p = pl_bump(t, size);
  pl_cache_stat_alloc(t, PL_K_THKE, size);
  p[0] = pl_hdr_make(PL_K_THKE, 0, 0, size);
  p[1] = PL_BAN_PRIM_KNOWN;
  p[2] = idx; /* the ingest-resolved pl_ops index, a nat63 */
  memcpy(p + 3, args, sizeof(pl_val) * nargs);
  return pl_make(PL_TAG_DEFER, p);
}

/* ── Mutation sites ───────────────────────────────────────────────── */

void pl_thunk_update(pl_thread* t, pl_val thunk_or_bh, pl_val result) {
  (void)t;
  pl_cell* p = pl_ptr(thunk_or_bh);
  pl_kind k = pl_hdr_kind(p[0]);
  ax_assume(k == PL_K_THUNK || k == PL_K_BH, "thunk_update on kind %d", (int)k);
  /* keep the original cell count so the collector copies correctly */
  p[0] = pl_hdr_make(PL_K_IND, 0, 0, pl_hdr_cells(p[0]));
  p[1] = result;
}

void pl_thke_update(pl_thread* t, pl_val thke, pl_val result) {
  (void)t;
  (void)thke;
  pl_cell* p = pl_ptr(thke);
  pl_kind k = pl_hdr_kind(p[0]);
  ax_assume(k == PL_K_THKE, "thunk_update on kind %d", (int)k);
  /* keep the original cell count so the collector copies correctly */
  p[0] = pl_hdr_make(PL_K_IND, 0, 0, pl_hdr_cells(p[0]));
  p[1] = result;
}

void pl_nf_writeback(pl_val parent, uint32_t field, pl_val child) {
  pl_cell* p = pl_ptr(parent);
  switch (pl_hdr_kind(p[0])) {
  case PL_K_APP:
    p[1 + field] = child;
    return;
  case PL_K_LAW:
    p[2 + field] = child;
    return;
  case PL_K_PIN:
    ax_assume(pl_pin_is_proxy(p) && pl_pin_proxy_target(p) == 0 && field == 0,
              "nf_writeback on a resolved or canonical PIN");
    p[5] = child;
    return;
  default:
    ax_abort("nf_writeback on kind %d", (int)pl_hdr_kind(p[0]));
  }
}

uint32_t pl_nf_nfields(pl_val v) {
  if (pl_is_nat63(v))
    return 0;
  switch (pl_tag(v)) {
  case PL_TAG_APP:
    return pl_app_n(pl_ptr(v)) + 1;
  case PL_TAG_LAW:
    return 2;
  case PL_TAG_PIN:
    return 1;
  default:
    return 0;
  }
}

pl_val pl_nf_field(pl_val v, uint32_t i) {
  pl_cell* p = pl_ptr(v);
  switch (pl_tag(v)) {
  case PL_TAG_APP:
    return (pl_val)p[1 + i];
  case PL_TAG_LAW:
    return (pl_val)p[2 + i];
  case PL_TAG_PIN:
    ax_assume(pl_pin_is_proxy(p) && pl_pin_proxy_target(p) == 0 && i == 0,
              "pl_nf_field on a resolved or canonical PIN");
    return (pl_val)p[5];
  default:
    ax_abort("pl_nf_field on tag 0x%llx", (unsigned long long)pl_tag(v));
  }
}
