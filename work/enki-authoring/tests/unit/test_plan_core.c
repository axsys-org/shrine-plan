#include "test.h"
#include <string.h>

#include "axsys/ds.h"
#include "../../pkg/plan/src/store_internal.h"
#include "test_plan.h"

/* ── Value representation ──────────────────────────────────────────────── */

TEST(value, tagged_pointer_address_views) {
  pl_cell cells[2] = {UINT64_C(0x123456789abcdef0), 0};
  pl_val v = pl_make(PL_TAG_APP, cells);

  ASSERT_EQ(pl_addr(v), (uintptr_t)cells);
  ASSERT_EQ(pl_ptr(v)[0], cells[0]);
#if AX_USE_TBI
  ASSERT_EQ((uintptr_t)pl_ptr(v), (uintptr_t)v);
#else
  ASSERT_EQ((uintptr_t)pl_ptr(v), (uintptr_t)cells);
#endif
}

TEST(value, direct_nat_boundary) {
  test_rt rt = test_rt_new();
  pl_thread* t = rt.t;

  pl_gc_reserve(t, PL_NAT_CELLS(1));
  pl_val small = pl_mk_nat_u64(t, PL_NAT63_MAX);
  ASSERT(pl_is_nat63(small));

  pl_gc_reserve(t, PL_NAT_CELLS(1));
  pl_val big = pl_mk_nat_u64(t, PL_NAT63_MAX + 1);
  ASSERT(!pl_is_nat63(big));
  ASSERT_EQ(pl_tag(big), PL_TAG_NAT);
  ASSERT(pl_is_whnf(big));
  ASSERT_EQ(pl_nat_u64_clamp(big), PL_NAT63_MAX + 1);

  test_rt_free(&rt);
}

TEST(value, nat_trim_canonicalizes) {
  test_rt rt = test_rt_new();
  pl_thread* t = rt.t;

  pl_gc_reserve(t, PL_NAT_CELLS(3));
  uint64_t* limbs;
  pl_val v = pl_mk_nat_limbs(t, 3, &limbs);
  limbs[0] = 42;
  limbs[1] = 0;
  limbs[2] = 0;
  v = pl_nat_trim(v);
  ASSERT_EQ(v, 42); /* trims to a direct nat */

  test_rt_free(&rt);
}

TEST(value, app_need_cache) {
  test_rt rt = test_rt_new();
  pl_thread* t = rt.t;

  pl_val law = test_law(t, 3, 0, 1);
  ASSERT_EQ(pl_arity(law), 3);
  pl_val a1 = test_app1(t, law, 7);
  ASSERT_EQ(pl_arity(a1), 2);

  pl_vpush(t, a1);
  pl_gc_reserve(t, PL_APP_CELLS(2));
  pl_val a2 = pl_mk_app_snoc(t, pl_vpop(t), 8);
  ASSERT_EQ(pl_arity(a2), 1);

  /* inert app: nat head has arity 0 */
  pl_val row = test_app2(t, 0, 1, 2);
  ASSERT_EQ(pl_arity(row), 0);

  test_rt_free(&rt);
}

TEST(value, env_constructor_zeroes_slots) {
  test_rt rt = test_rt_new();
  pl_thread* t = rt.t;

  pl_gc_reserve(t, PL_ENV_CELLS(4));
  pl_val env = pl_mk_env(t, 4);
  pl_cell* p = pl_as(PL_TAG_ENV, env);
  ASSERT_NOT_NULL(p);
  for (uint32_t i = 0; i < 4; i++)
    ASSERT_EQ(pl_env_slots(p)[i], 0);

  test_rt_free(&rt);
}

/* ── Nat arithmetic ────────────────────────────────────────────────────── */

TEST(nat, add_carries_across_boundary) {
  test_rt rt = test_rt_new();
  pl_thread* t = rt.t;

  size_t a = t->vsp;
  pl_vpush(t, PL_NAT63_MAX);
  pl_vpush(t, 1);
  pl_val sum = pl_nat_add(t, &t->vstack[a], &t->vstack[a + 1]);
  ASSERT(!pl_is_nat63(sum));
  ASSERT_EQ(pl_nat_u64_clamp(sum), UINT64_C(1) << 63);

  /* and back below the boundary via sub */
  t->vsp = a;
  pl_vpush(t, sum);
  pl_vpush(t, 1);
  pl_val back = pl_nat_sub(t, &t->vstack[a], &t->vstack[a + 1]);
  ASSERT(pl_is_nat63(back));
  ASSERT_EQ(back, PL_NAT63_MAX);

  test_rt_free(&rt);
}

TEST(nat, sub_floors_at_zero) {
  test_rt rt = test_rt_new();
  pl_thread* t = rt.t;
  size_t a = t->vsp;
  pl_vpush(t, 3);
  pl_vpush(t, 5);
  ASSERT_EQ(pl_nat_sub(t, &t->vstack[a], &t->vstack[a + 1]), 0);
  test_rt_free(&rt);
}

TEST(nat, mul_two_limbs) {
  test_rt rt = test_rt_new();
  pl_thread* t = rt.t;
  size_t a = t->vsp;
  pl_vpush(t, UINT64_C(0xffffffffffffffff) >> 1);
  pl_vpush(t, 16);
  pl_val p = pl_nat_mul(t, &t->vstack[a], &t->vstack[a + 1]);
  ASSERT(!pl_is_nat63(p));
  ASSERT_EQ(pl_nat_limb_at(p, 0), UINT64_C(0xfffffffffffffff0));
  ASSERT_EQ(pl_nat_limb_at(p, 1), 7);
  test_rt_free(&rt);
}

TEST(nat, divmod_bignum) {
  test_rt rt = test_rt_new();
  pl_thread* t = rt.t;
  size_t a = t->vsp;
  /* (2^64 + 5) / 3 and mod */
  pl_vpush(t, 0);
  pl_vpush(t, 3);
  pl_gc_reserve(t, PL_NAT_CELLS(2));
  uint64_t* limbs;
  pl_val big = pl_mk_nat_limbs(t, 2, &limbs);
  limbs[0] = 5;
  limbs[1] = 1;
  t->vstack[a] = pl_nat_trim(big);
  pl_val q = pl_nat_div(t, &t->vstack[a], &t->vstack[a + 1]);
  pl_vpush(t, q);
  pl_val m = pl_nat_mod(t, &t->vstack[a], &t->vstack[a + 1]);
  /* 2^64+5 = 18446744073709551621 = 3*6148914691236517207 + 0 */
  ASSERT_EQ(pl_nat_u64_clamp(t->vstack[a + 2]), UINT64_C(6148914691236517207));
  ASSERT_EQ(m, 0);
  test_rt_free(&rt);
}

/* LoadVar reference (Plan.hs op 66): (a >> 8*off) mod 2^(8*width) */
TEST(nat, load_var_small_subject) {
  test_rt rt = test_rt_new();
  pl_thread* t = rt.t;
  size_t a = t->vsp;
  pl_vpush(t, 1);        /* off */
  pl_vpush(t, 2);        /* width */
  pl_vpush(t, 0xCCBBAA); /* subject */
  ASSERT_EQ(
      pl_nat_load_var(t, &t->vstack[a], &t->vstack[a + 1], &t->vstack[a + 2]),
      0xCCBB);

  /* width >= 8 bytes covers the whole value */
  t->vstack[a] = 0;
  t->vstack[a + 1] = 8;
  t->vstack[a + 2] = 5;
  ASSERT_EQ(
      pl_nat_load_var(t, &t->vstack[a], &t->vstack[a + 1], &t->vstack[a + 2]),
      5);

  /* offset past a small nat reads zero (shift count would exceed 63) */
  t->vstack[a] = 8;
  t->vstack[a + 1] = 1;
  t->vstack[a + 2] = 0x1234;
  ASSERT_EQ(
      pl_nat_load_var(t, &t->vstack[a], &t->vstack[a + 1], &t->vstack[a + 2]),
      0);

  test_rt_free(&rt);
}

TEST(nat, load_var_big_subject) {
  test_rt rt = test_rt_new();
  pl_thread* t = rt.t;
  size_t a = t->vsp;
  pl_vpush(t, 0); /* off */
  pl_vpush(t, 0); /* width */
  pl_vpush(t, 0); /* subject */
  pl_gc_reserve(t, PL_NAT_CELLS(2));
  uint64_t* limbs;
  pl_val big = pl_mk_nat_limbs(t, 2, &limbs);
  limbs[0] = UINT64_C(0x1122334455667788);
  limbs[1] = UINT64_C(0x99AABBCCDDEEFF00);
  t->vstack[a + 2] = pl_nat_trim(big);

  /* unaligned read across the limb boundary: bytes 7..8 = {0x11, 0x00} */
  t->vstack[a] = 7;
  t->vstack[a + 1] = 2;
  ASSERT_EQ(
      pl_nat_load_var(t, &t->vstack[a], &t->vstack[a + 1], &t->vstack[a + 2]),
      0x11);

  /* aligned full-limb read */
  t->vstack[a] = 8;
  t->vstack[a + 1] = 8;
  pl_val r =
      pl_nat_load_var(t, &t->vstack[a], &t->vstack[a + 1], &t->vstack[a + 2]);
  ASSERT(!pl_is_nat63(r));
  ASSERT_EQ(pl_nat_limb_at(r, 0), UINT64_C(0x99AABBCCDDEEFF00));
  ASSERT_EQ(pl_nat_limb_at(r, 1), 0);

  /* read extending past the end: missing bytes are zero, result canonical */
  t->vstack[a] = 12;
  t->vstack[a + 1] = 8;
  r = pl_nat_load_var(t, &t->vstack[a], &t->vstack[a + 1], &t->vstack[a + 2]);
  ASSERT(pl_is_nat63(r)); /* trimmed: no garbage in the high limbs */
  ASSERT_EQ(r, 0x99AABBCC);

  /* wide window over the whole value returns it unchanged */
  t->vstack[a] = 0;
  t->vstack[a + 1] = 32;
  r = pl_nat_load_var(t, &t->vstack[a], &t->vstack[a + 1], &t->vstack[a + 2]);
  ASSERT_EQ(pl_nat_limb_at(r, 0), UINT64_C(0x1122334455667788));
  ASSERT_EQ(pl_nat_limb_at(r, 1), UINT64_C(0x99AABBCCDDEEFF00));

  /* offset at/past the end reads zero, even for huge offsets */
  t->vstack[a] = 16;
  t->vstack[a + 1] = 4;
  ASSERT_EQ(
      pl_nat_load_var(t, &t->vstack[a], &t->vstack[a + 1], &t->vstack[a + 2]),
      0);
  t->vstack[a] = UINT64_C(1) << 40;
  t->vstack[a + 1] = 8;
  ASSERT_EQ(
      pl_nat_load_var(t, &t->vstack[a], &t->vstack[a + 1], &t->vstack[a + 2]),
      0);

  test_rt_free(&rt);
}

TEST(nat, from_decimal_roundtrip) {
  test_rt rt = test_rt_new();
  pl_thread* t = rt.t;
  const char* dec = "340282366920938463463374607431768211456"; /* 2^128 */
  bool ok = false;
  pl_val v = pl_nat_from_decimal(t, dec, strlen(dec), &ok);
  ASSERT(ok);
  ASSERT_EQ(pl_nat_bit_len(v), 129);
  ASSERT_EQ(pl_nat_limb_at(v, 2), 1);
  test_rt_free(&rt);
}

/* ── Heap / collector ──────────────────────────────────────────────────── */

static pl_val test_pin_proxy(pl_thread* t, pl_val body) {
  size_t base = t->vsp;
  pl_vpush(t, body);
  pl_gc_reserve(t, PL_PIN_CELLS(0));
  PL_GC_FORBID(t);
  pl_cell* p = pl_bump(t, PL_PIN_CELLS(0));
  p[0] =
      pl_hdr_make(PL_K_PIN, PL_F_NORMAL | PL_F_PIN_PROXY, 0, PL_PIN_CELLS(0));
  memset(p + 1, 0, 4 * sizeof(pl_cell));
  p[5] = t->vstack[base];
  __atomic_store_n(&p[6], 0, __ATOMIC_RELAXED);
  pl_val proxy = pl_make(PL_TAG_PIN, p);
  PL_GC_ALLOW(t);
  t->vsp = base;
  return proxy;
}

#ifndef PL_GC_STRESS
TEST(gc, dense_live_heap_keeps_allocation_headroom) {
  test_rt rt = test_rt_new();
  pl_thread* t = rt.t;
  size_t capacity = pl_gc_headroom(t);
  size_t live = capacity - 32;
  uint32_t count = (uint32_t)(live - PL_APP_CELLS(0));
  pl_val* args = calloc(count, sizeof(*args));
  ASSERT_NOT_NULL(args);
  args[count - 1] = 17;
  pl_vpush(t, test_app(t, 0, count, args));
  free(args);
  pl_gc_reserve(t, 32);
  (void)pl_bump(t, 32); /* unreachable garbage fills the old space */

  /* A one-cell allocation fits after collection. It must still gain
   * proportional headroom, rather than copying the whole live graph
   * again for every 32 subsequent cells of garbage. */
  pl_gc_reserve(t, 1);
  ASSERT(pl_gc_headroom(t) >= live / 2);
  pl_cell* row = pl_as(PL_TAG_APP, t->vstack[t->vsp - 1]);
  ASSERT_EQ(pl_app_n(row), count);
  ASSERT_EQ(pl_app_args(row)[count - 1], 17);

  t->vsp = 0;
  pl_gc_trim(t);
  ASSERT(pl_gc_headroom(t) <= 8192);
  test_rt_free(&rt);
}

TEST(gc, pressure_collection_is_amortized) {
  test_rt rt = test_rt_new();
  pl_thread* t = rt.t;

  ASSERT_FALSE(pl_gc_collect_if_pressure(t, 8));

  pl_gc_reserve(t, 8);
  (void)pl_bump(t, 8); /* unreachable allocation */
  ASSERT_FALSE(pl_gc_collect_if_pressure(t, 9));
  ASSERT(pl_gc_collect_if_pressure(t, 8));
  ASSERT_EQ(pl_gc_live_cells(rt.heap), 0);

  /* Once there is a live set, require at least that much new allocation
   * before copying it again, even when the caller supplies a tiny floor. */
  pl_val args[14] = {0};
  pl_val row = test_app(t, 0, 14, args); /* 16 cells */
  pl_vpush(t, row);
  pl_gc_collect_now(t);
  ASSERT_EQ(pl_gc_live_cells(rt.heap), 16);

  pl_gc_reserve(t, 15);
  (void)pl_bump(t, 15);
  ASSERT_FALSE(pl_gc_collect_if_pressure(t, 1));
  pl_gc_reserve(t, 1);
  (void)pl_bump(t, 1);
  ASSERT(pl_gc_collect_if_pressure(t, 1));

  pl_cell* p = pl_as(PL_TAG_APP, t->vstack[t->vsp - 1]);
  ASSERT_NOT_NULL(p);
  ASSERT_EQ(pl_app_n(p), 14);
  ASSERT_EQ(pl_gc_live_cells(rt.heap), 16);

  test_rt_free(&rt);
}
#endif

TEST(gc, values_survive_collection) {
  test_rt rt = test_rt_new();
  pl_thread* t = rt.t;

  pl_val row = test_app2(t, 0, 17, PL_NAT63_MAX);
  pl_vpush(t, row);
  size_t slot = t->vsp - 1;

  /* churn enough garbage to force several collections */
  for (int i = 0; i < 100000; i++) {
    pl_gc_reserve(t, PL_APP_CELLS(2));
    pl_val args[2] = {1, 2};
    (void)pl_mk_app_from(t, 0, 2, args);
  }
  pl_gc_collect_now(t);

  pl_val moved = t->vstack[slot];
  pl_cell* p = pl_as(PL_TAG_APP, moved);
  ASSERT_NOT_NULL(p);
  ASSERT_EQ(pl_app_n(p), 2);
  ASSERT_EQ(pl_app_args(p)[0], 17);
  ASSERT_EQ(pl_app_args(p)[1], (pl_val)PL_NAT63_MAX);

  test_rt_free(&rt);
}

TEST(gc, unresolved_pin_proxy_keeps_its_moving_body) {
  test_rt rt = test_rt_new();
  pl_thread* t = rt.t;

  size_t base = t->vsp;
  pl_vpush(t, test_app2(t, 0, 17, 23));
  t->vstack[base] = test_pin_proxy(t, t->vstack[base]);
  pl_val before = t->vstack[base];
  ASSERT(pl_pin_is_proxy(pl_ptr(before)));
  ASSERT_EQ(pl_pin_proxy_target(pl_ptr(before)), 0);

  pl_gc_collect_now(t);

  pl_val after = t->vstack[base];
  ASSERT_NEQ(after, before);
  pl_cell* proxy = pl_as(PL_TAG_PIN, after);
  ASSERT_NOT_NULL(proxy);
  ASSERT(pl_pin_is_proxy(proxy));
  ASSERT_EQ(pl_pin_proxy_target(proxy), 0);
  pl_cell* body = pl_as(PL_TAG_APP, pl_pin_body(proxy));
  ASSERT_NOT_NULL(body);
  ASSERT_EQ(pl_app_args(body)[0], 17);
  ASSERT_EQ(pl_app_args(body)[1], 23);
  ASSERT_EQ(pl_gc_live_cells(rt.heap), PL_PIN_CELLS(0) + PL_APP_CELLS(2));

  test_rt_free(&rt);
}

TEST(gc, public_pin_needs_no_store) {
  pl_heap* h = pl_heap_new(4096, NULL);
  pl_thread* t = pl_thread_new(h);

  size_t base = t->vsp;
  pl_vpush(t, test_app2(t, 0, 17, 23));
  t->vstack[base] = pl_pin(t, t->vstack[base]);

  pl_cell* proxy = pl_as(PL_TAG_PIN, t->vstack[base]);
  ASSERT_NOT_NULL(proxy);
  ASSERT(pl_pin_is_proxy(proxy));
  ASSERT_EQ(pl_pin_proxy_target(proxy), 0);
  ASSERT_NULL(pl_pin_hash(t->vstack[base]));

  pl_gc_collect_now(t);
  proxy = pl_as(PL_TAG_PIN, t->vstack[base]);
  ASSERT_NOT_NULL(proxy);
  pl_cell* body = pl_as(PL_TAG_APP, pl_pin_body(proxy));
  ASSERT_NOT_NULL(body);
  ASSERT_EQ(pl_app_args(body)[0], 17);
  ASSERT_EQ(pl_app_args(body)[1], 23);

  pl_thread_free(t);
  pl_heap_free(h);
}

TEST(gc, dropped_unsaved_pins_do_not_reach_the_store) {
  test_rt rt = test_rt_new();
  pl_thread* t = rt.t;
  size_t arena_before = pl_store_mark(rt.store);
  ptrdiff_t pins_before = ax_arrlen(rt.store->pins);
  ptrdiff_t intern_before = ax_hmlen(rt.store->intern);

  for (uint64_t i = 0; i < 10000; i++)
    (void)pl_pin(t, i);
  pl_gc_collect_now(t);

  ASSERT_EQ(pl_gc_live_cells(rt.heap), 0);
  ASSERT_EQ(pl_store_mark(rt.store), arena_before);
  ASSERT_EQ(ax_arrlen(rt.store->pins), pins_before);
  ASSERT_EQ(ax_hmlen(rt.store->intern), intern_before);
  test_rt_free(&rt);
}

TEST(gc, resolved_pin_proxy_retains_only_its_canonical_target) {
  test_rt rt = test_rt_new();
  pl_thread* t = rt.t;
  uint8_t hash[32] = {1};
  pl_val canonical = pl_store_mk_pin(rt.store, hash, 99, 0, NULL);
  pl_cell* canonical_p = pl_ptr(canonical);

  size_t base = t->vsp;
  pl_vpush(t, test_app2(t, 0, 17, 23));
  t->vstack[base] = test_pin_proxy(t, t->vstack[base]);
  pl_cell* proxy = pl_ptr(t->vstack[base]);
  pl_pin_set_target(proxy, canonical);

  pl_code code = {0};
  pl_pin_set_code(canonical_p, &code);
  ASSERT_EQ(pl_pin_body(proxy), 99);
  ASSERT_EQ(pl_pin_code(proxy), &code);
  ASSERT_EQ(pl_pin_hash_bytes(proxy), pl_pin_hash_bytes(canonical_p));
  ASSERT_EQ(pl_pin_subpins(proxy), pl_pin_subpins(canonical_p));

  pl_gc_collect_now(t);

  proxy = pl_ptr(t->vstack[base]);
  ASSERT(pl_pin_is_proxy(proxy));
  ASSERT_EQ(pl_pin_proxy_target(proxy), canonical);
  ASSERT_EQ(proxy[5], 0); /* obsolete moving body is no longer an edge */
  ASSERT_EQ(pl_pin_body(proxy), 99);
  ASSERT_EQ(pl_pin_code(proxy), &code);
  ASSERT_EQ(pl_gc_live_cells(rt.heap), PL_PIN_CELLS(0));

  pl_pin_set_code(canonical_p, NULL);
  test_rt_free(&rt);
}

TEST(gc, store_values_are_terminal) {
  test_rt rt = test_rt_new();
  pl_thread* t = rt.t;

  uint8_t hash[32] = {1};
  pl_val pin = pl_store_mk_pin(rt.store, hash, 42, 0, NULL);
  size_t base = t->vsp;
  pl_vpush(t, pin);
  ASSERT(pl_store_owns(rt.store, pin));

  pl_gc_collect_now(t);
  /* the pin val must be unchanged (non-moving store region) */
  ASSERT_EQ(t->vstack[base], pin);

  test_rt_free(&rt);
}

TEST(gc, ind_short_circuit_on_evacuation) {
  test_rt rt = test_rt_new();
  pl_thread* t = rt.t;

  /* a thunk that evaluates to 42: expr = (0 42) over an empty env */
  size_t base = t->vsp;
  pl_vpush(t, test_app1(t, 0, 42));
  pl_gc_reserve(t, PL_ENV_CELLS(1) + PL_THUNK_CELLS);
  pl_val env = pl_mk_env(t, 1);
  pl_val thunk = pl_mk_thunk(t, env, t->vstack[base]);
  t->vsp = base;
  pl_vpush(t, thunk);

  ASSERT_EQ(pl_whnf(t, t->vstack[base]), 42);
  /* slot now holds an IND; collection should snap it to the target */
  ASSERT_EQ(pl_tag(t->vstack[base]), PL_TAG_DEFER);
  pl_gc_collect_now(t);
  ASSERT_EQ(t->vstack[base], 42);

  test_rt_free(&rt);
}

TEST(gc, bytecode_thunk_scans_args) {
  test_rt rt = test_rt_new();
  pl_thread* t = rt.t;

  size_t base = t->vsp;
  pl_vpush(t, test_law(t, 1, 0, 1));
  pl_vpush(t, test_app2(t, 0, 11, 12));

  pl_gc_reserve(t, PL_THKE_CELLS(2));
  pl_val thke = pl_mk_thke(t, PL_BAN_SLOW, 2, &t->vstack[base]);
  t->vsp = base;
  pl_vpush(t, thke);

  pl_gc_collect_now(t);

  pl_cell* p = pl_ptr(t->vstack[base]);
  ASSERT_EQ(pl_hdr_kind(p[0]), PL_K_THKE);
  ASSERT_EQ(pl_hdr_cells(p[0]), PL_THKE_CELLS(2));
  ASSERT_EQ(pl_thke_bane(p), PL_BAN_SLOW);

  pl_val* args = pl_thke_args(p);
  ASSERT_EQ(pl_kind_of(args[0]), PL_K_LAW);
  pl_cell* ap = pl_as(PL_TAG_APP, args[1]);
  ASSERT_NOT_NULL(ap);
  ASSERT_EQ(pl_app_args(ap)[0], 11);
  ASSERT_EQ(pl_app_args(ap)[1], 12);

  test_rt_free(&rt);
}

TEST(value, show_big_nat_decimal_owns_its_digits) {
  test_rt rt = test_rt_new();
  pl_thread* t = rt.t;

  /* A non-printable two-limb nat forces pl_show_nat's GMP decimal path.
   * The digits must be copied into the builder: ax_sb defers, so a
   * referenced-then-freed digit buffer reads freed memory at build time
   * (rendered as stable-length garbage that varies run to run). */
  pl_gc_reserve(t, PL_NAT_CELLS(2));
  uint64_t* limbs;
  pl_val v = pl_mk_nat_limbs(t, 2, &limbs);
  limbs[0] = 0;
  limbs[1] = 1; /* 2^64 */
  v = pl_nat_trim(v);

  char* s = pl_show(ax_allocator_system(), v, NULL);
  ASSERT_STR_EQ(s, "18446744073709551616");
  ax_free(ax_allocator_system(), s);

  test_rt_free(&rt);
}
