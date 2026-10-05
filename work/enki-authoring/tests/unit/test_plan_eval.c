#include "test.h"
#include <string.h>

#include "test_plan.h"

/* A lazy thunk whose body expr runs under an empty (1-slot) env. */
static pl_val test_thunk(pl_thread* t, pl_val expr) {
  size_t base = t->vsp;
  pl_vpush(t, expr);
  pl_gc_reserve(t, PL_ENV_CELLS(1) + PL_THUNK_CELLS);
  pl_val env = pl_mk_env(t, 1);
  pl_val out = pl_mk_thunk(t, env, t->vstack[base]);
  t->vsp = base;
  return out;
}

/* A thunk that raises PLAN_EXN(code) when forced: P66 % ("Throw" code). */
static pl_val test_throwing(pl_thread* t, uint64_t code) {
  size_t base = t->vsp;
  pl_val args[1] = {code};
  pl_vpush(t, test_app(t, ax_s5('T', 'h', 'r', 'o', 'w'), 1, args));
  pl_vpush(t, test_app1(t, 0, t->vstack[base])); /* (0 row) literal */
  pl_vpush(t, test_app1(t, 0, test_p66(t)));     /* (0 P66)         */
  pl_val expr = test_app2(t, 0, t->vstack[base + 2], t->vstack[base + 1]);
  t->vsp = base;
  return test_thunk(t, expr);
}

/* A one-element app whose field is a thunk that evaluates to value. */
static pl_val test_app1_thunk_to(pl_thread* t, pl_val value) {
  size_t base = t->vsp;
  pl_vpush(t, test_thunk(t, test_app1(t, 0, value)));
  pl_val out = test_app1(t, 0, t->vstack[base]);
  t->vsp = base;
  return out;
}

static pl_val test_byte_mask(pl_thread* t, const uint8_t* bytes, size_t n) {
  uint8_t mask[32] = {0};
  for (size_t i = 0; i < n; i++)
    mask[bytes[i] / 8u] |= (uint8_t)(1u << (bytes[i] % 8u));
  return pl_nat_from_bytes(t, mask, sizeof(mask));
}

static void test_assert_nat_row3(pl_val value, pl_val a, pl_val b, pl_val c) {
  pl_cell* p = pl_as(PL_TAG_APP, value);
  ASSERT_NOT_NULL(p);
  ASSERT_EQ(pl_app_head(p), 0);
  ASSERT_EQ(pl_app_n(p), 3);
  ASSERT(pl_is_nat(pl_app_args(p)[0]));
  ASSERT(pl_is_nat(pl_app_args(p)[1]));
  ASSERT(pl_is_nat(pl_app_args(p)[2]));
  ASSERT(pl_nat_eq(pl_app_args(p)[0], a));
  ASSERT(pl_nat_eq(pl_app_args(p)[1], b));
  ASSERT(pl_nat_eq(pl_app_args(p)[2], c));
}

static pl_val test_cord_text(pl_thread* t, pl_val text) {
  pl_val fields[2] = {ax_s4('t', 'e', 'x', 't'), text};
  return test_app(t, 0, 2, fields);
}

static pl_val test_cord_slice(pl_thread* t, pl_val source, pl_val offset,
                              pl_val length) {
  pl_val fields[4] = {ax_s5('s', 'l', 'i', 'c', 'e'), source, offset, length};
  return test_app(t, 0, 4, fields);
}

static pl_val test_cord_repeat(pl_thread* t, pl_val byte, pl_val count) {
  pl_val fields[3] = {ax_s6('r', 'e', 'p', 'e', 'a', 't'), byte, count};
  return test_app(t, 0, 3, fields);
}

static pl_val test_cord_cat(pl_thread* t, pl_val left, pl_val right) {
  pl_val fields[3] = {ax_s3('c', 'a', 't'), left, right};
  return test_app(t, 0, 3, fields);
}

static bool growing_enter_hook(pl_thread* t, size_t hbase, uint32_t argc,
                               pl_val* out) {
  (void)hbase;
  (void)argc;
  (void)out;
  /* Larger than test_rt's initial semispace: this collects, grows, and frees
   * both old spaces while the entered unresolved PIN remains stack-rooted. */
  pl_gc_reserve(t, (size_t)1 << 17);
  return false;
}

static void test_expect_no_op66(pl_thread* t, pl_val name, size_t n,
                                const pl_val* args) {
  pl_catch c;
  pl_catch_init(t, &c);
  if (setjmp(c.jb) == 0) {
    (void)test_op66(t, name, n, args);
    FAIL_TEST("expected no primop");
  }
  pl_catch_unwind(t, &c);
  ASSERT_NOT_NULL(t->exn_msg);
  char expected[64];
  (void)snprintf(expected, sizeof(expected), "no primop 66 (argc %zu)", n);
  ASSERT_STR_EQ(t->exn_msg, expected);
}

static bool test_install_self_replacement_raises(pl_thread* t,
                                                 pl_val compiler) {
  pl_val args[1] = {compiler};
  pl_catch c;
  pl_catch_init(t, &c);
  if (setjmp(c.jb) == 0) {
    (void)test_op66(t, ax_s7('I', 'n', 's', 't', 'a', 'l', 'l'), 1, args);
    pl_catch_pop(t, &c);
    return false;
  }
  pl_catch_unwind(t, &c);
  return true;
}

static pl_val test_ice(pl_thread* t, pl_val pin) {
  return test_op66(t, ax_s3('I', 'c', 'e'), 1, &pin);
}

static bool test_ice_raises(pl_thread* t, pl_val value) {
  pl_catch c;
  pl_catch_init(t, &c);
  if (setjmp(c.jb) == 0) {
    (void)test_ice(t, value);
    pl_catch_pop(t, &c);
    return false;
  }
  pl_catch_unwind(t, &c);
  return true;
}

/* ── Application shapes ────────────────────────────────────────────────── */

TEST(apply, under_application_builds_app) {
  test_rt rt = test_rt_new();
  pl_thread* t = rt.t;
  pl_val k = test_law(t, 2, 0, 1); /* K x y = x */
  pl_val r = pl_apply(t, k, 7);
  pl_cell* p = pl_as(PL_TAG_APP, r);
  ASSERT_NOT_NULL(p);
  ASSERT_EQ(pl_arity(r), 1);
  test_rt_free(&rt);
}

TEST(apply, exact_and_over_application) {
  test_rt rt = test_rt_new();
  pl_thread* t = rt.t;
  size_t base = t->vsp;
  pl_vpush(t, test_law(t, 2, 0, 1)); /* K */
  pl_vpush(t, test_law(t, 1, 0, 1)); /* id */
  /* ((K id) 7) 9  ->  id 9  ->  9 */
  pl_val r = pl_apply(t, t->vstack[base], t->vstack[base + 1]);
  pl_vpush(t, r);
  r = pl_apply(t, t->vstack[base + 2], 7);
  pl_vpush(t, r);
  r = pl_apply(t, t->vstack[base + 3], 9);
  ASSERT_EQ(r, 9);
  test_rt_free(&rt);
}

TEST(apply, args_stay_lazy) {
  test_rt rt = test_rt_new();
  pl_thread* t = rt.t;
  pl_catch c;
  pl_catch_init(t, &c);
  if (setjmp(c.jb) != 0)
    FAIL_TEST("unexpected exception");
  size_t base = t->vsp;
  pl_vpush(t, test_law(t, 2, 0, 1)); /* K x y = x */
  pl_vpush(t, test_throwing(t, 7));
  /* K 5 <throw>  ->  5 without forcing the throwing arg */
  pl_val r = pl_apply(t, t->vstack[base], 5);
  pl_vpush(t, r);
  r = pl_apply(t, t->vstack[base + 2], t->vstack[base + 1]);
  ASSERT_EQ(r, 5);
  pl_catch_pop(t, &c);
  test_rt_free(&rt);
}

TEST(apply, slow_bytecode_thunk_applies_unknown_arity) {
  test_rt rt = test_rt_new();
  pl_thread* t = rt.t;
  size_t base = t->vsp;
  pl_vpush(t, test_law(t, 2, 0, 1)); /* K x y = x */
  pl_vpush(t, 5);
  pl_vpush(t, test_throwing(t, 7));
  pl_gc_reserve(t, PL_THKE_CELLS(3));
  pl_val thke = pl_mk_thke(t, PL_BAN_SLOW, 3, &t->vstack[base]);
  t->vsp = base;

  ASSERT_EQ(pl_whnf(t, thke), 5);
  test_rt_free(&rt);
}

TEST(apply, fast_bytecode_thunk_applies_deferred_head) {
  test_rt rt = test_rt_new();
  pl_thread* t = rt.t;
  size_t base = t->vsp;
  pl_vpush(t, test_thunk(t, test_app1(t, 0, test_law(t, 2, 0, 1))));
  pl_vpush(t, 5);
  pl_vpush(t, test_throwing(t, 7));
  pl_gc_reserve(t, PL_THKE_CELLS(3));
  pl_val thke = pl_mk_thke(t, PL_BAN_FAST, 3, &t->vstack[base]);
  t->vsp = base;

  ASSERT_EQ(pl_whnf(t, thke), 5);
  test_rt_free(&rt);
}

TEST(apply, slow_thke_under_applied_builds_flat_app) {
  test_rt rt = test_rt_new();
  pl_thread* t = rt.t;
  size_t base = t->vsp;
  pl_vpush(t, test_law(t, 3, 0, 1)); /* K3 x y z = x */
  pl_vpush(t, 5);
  pl_vpush(t, 6);
  pl_gc_reserve(t, PL_THKE_CELLS(3));
  pl_val thke = pl_mk_thke(t, PL_BAN_SLOW, 3, &t->vstack[base]);
  t->vsp = base;

  pl_val r = pl_whnf(t, thke);
  pl_cell* p = pl_as(PL_TAG_APP, r);
  ASSERT_NOT_NULL(p);
  ASSERT_EQ(pl_app_n(p), 2);
  ASSERT_EQ(pl_arity(r), 1);
  ASSERT_EQ(pl_whnf(t, pl_apply(t, r, 7)), 5);
  test_rt_free(&rt);
}

TEST(apply, slow_thke_under_applied_partial_head_stays_flat) {
  test_rt rt = test_rt_new();
  pl_thread* t = rt.t;
  size_t base = t->vsp;
  pl_val k3 = test_law(t, 3, 0, 1); /* K3 x y z = x */
  pl_vpush(t, k3);
  pl_vpush(t, test_app1(t, t->vstack[base], 5)); /* (K3 5), need 2 */
  pl_vpush(t, 6);
  pl_gc_reserve(t, PL_THKE_CELLS(2));
  pl_val thke = pl_mk_thke(t, PL_BAN_SLOW, 2, &t->vstack[base + 1]);
  t->vsp = base + 1;

  /* the result must extend the spine (flat), not nest an app head */
  pl_val r = pl_whnf(t, thke);
  pl_cell* p = pl_as(PL_TAG_APP, r);
  ASSERT_NOT_NULL(p);
  ASSERT_EQ(pl_app_n(p), 2);
  ASSERT_EQ(pl_app_head(p), t->vstack[base]);
  ASSERT_EQ(pl_whnf(t, pl_apply(t, r, 7)), 5);
  t->vsp = base;
  test_rt_free(&rt);
}

TEST(apply, slow_thke_data_head_extends_row) {
  test_rt rt = test_rt_new();
  pl_thread* t = rt.t;
  size_t base = t->vsp;
  pl_vpush(t, test_app2(t, 0, 7, 8)); /* the row [7 8] */
  pl_vpush(t, 9);
  pl_gc_reserve(t, PL_THKE_CELLS(2));
  pl_val thke = pl_mk_thke(t, PL_BAN_SLOW, 2, &t->vstack[base]);
  t->vsp = base;

  /* snoc onto a row: [7 8 9], still flat and 0-headed */
  pl_val r = pl_whnf(t, thke);
  pl_cell* p = pl_as(PL_TAG_APP, r);
  ASSERT_NOT_NULL(p);
  ASSERT_EQ(pl_app_n(p), 3);
  ASSERT_EQ(pl_app_head(p), 0);
  ASSERT_EQ(pl_app_args(p)[2], 9);
  test_rt_free(&rt);
}

TEST(apply, slow_thke_splices_partial_app_head) {
  test_rt rt = test_rt_new();
  pl_thread* t = rt.t;
  size_t base = t->vsp;
  /* head is already a partial application: (K 5) applied to 9 */
  pl_vpush(t, test_app1(t, test_law(t, 2, 0, 1), 5));
  pl_vpush(t, 9);
  pl_gc_reserve(t, PL_THKE_CELLS(2));
  pl_val thke = pl_mk_thke(t, PL_BAN_SLOW, 2, &t->vstack[base]);
  t->vsp = base;

  ASSERT_EQ(pl_whnf(t, thke), 5);
  test_rt_free(&rt);
}

TEST(apply, enter_hook_growth_refreshes_unresolved_pin_body) {
  test_rt rt = test_rt_new();
  pl_thread* t = rt.t;
  size_t base = t->vsp;
  pl_vpush(t, test_law(t, 1, ax_s4('M', 'o', 'v', 'e'), 1));
  t->vstack[base] = pl_pin(t, t->vstack[base]);

  pl_set_enter_hook(growing_enter_hook);
  pl_val result = pl_apply(t, t->vstack[base], 42);
  pl_set_enter_hook(NULL);

  ASSERT_EQ(result, 42);
  pl_cell* proxy = pl_as(PL_TAG_PIN, t->vstack[base]);
  ASSERT_NOT_NULL(proxy);
  ASSERT(pl_pin_is_proxy(proxy));
  ASSERT_EQ(pl_pin_proxy_target(proxy), 0);
  ASSERT_NOT_NULL(pl_as(PL_TAG_LAW, pl_pin_body(proxy)));
  test_rt_free(&rt);
}

TEST(apply, tailcall_loops_in_constant_frame_space) {
  test_rt rt = test_rt_new();
  pl_thread* t = rt.t;
  size_t base = t->vsp;
  /* loop x = loop x, as fused tail-call bytecode: must run in constant
   * frame space AND stay preemptable (the tail path takes a fuel step) */
  pl_vpush(t, test_law(t, 1, 0, 0));
  t->vstack[base] = pl_pin(t, t->vstack[base]);
  char err[192] = {0};
  ASSERT(pl_store_save_root(rt.store, t->vstack[base], NULL, err, sizeof(err)),
         "%s", err);
  pl_cell* proxy = pl_as(PL_TAG_PIN, t->vstack[base]);
  ASSERT_NOT_NULL(proxy);
  pl_val pin = pl_pin_proxy_target(proxy);
  ASSERT_NEQ(pin, 0); /* static bytecode literals must be non-moving */
  t->vsp = base;
  pl_cell* pp = pl_as(PL_TAG_PIN, pin);
  ASSERT_NOT_NULL(pp);
  static pl_op_t loop_ops[7];
  loop_ops[0] = OP_PUSH_LIT;
  loop_ops[1] = pin;
  loop_ops[2] = OP_PUSH_VAR;
  loop_ops[3] = 1;
  loop_ops[4] = OP_TAILCALL;
  loop_ops[5] = 2;
  loop_ops[6] = PL_BAN_FAST;
  static pl_code loop_code = {loop_ops, 7, 0, 0, 0};
  pl_pin_set_code(pp, &loop_code);

  size_t fcap0 = t->fcap;
  pl_vpush(t, pin);
  pl_vpush(t, 5);
  pl_gc_reserve(t, PL_THKE_CELLS(2));
  pl_val thke = pl_mk_thke(t, PL_BAN_FAST, 2, &t->vstack[base]);
  t->vsp = base;
  pl_thread_start(t, thke);
  for (int i = 0; i < 200; i++)
    ASSERT_EQ(pl_thread_run(t, 10000), PL_RUN_YIELDED);
  /* Fuel checkpoints must not retain unaliased tail continuations until
   * this (possibly infinite) loop returns. Coalesced update roots count,
   * even when the ordinary frame stack stays shallow. */
  ASSERT_EQ(t->fcap, fcap0);
  ASSERT(t->fsp <= t->base_fsp + 3);
  ASSERT_EQ(t->usp, 0);
  pl_gc_collect_now(t);
  ASSERT_LT(pl_gc_live_cells(t->heap), 128);
  pl_pin_set_code(pp, NULL); /* the code is a stack-lifetime fake */
  test_rt_free(&rt);
}

TEST(apply, slow_thke_over_applied_order) {
  test_rt rt = test_rt_new();
  pl_thread* t = rt.t;
  size_t base = t->vsp;
  /* (K K' 5) 6 7 = K' 6 7 = 6: the first excess arg applies first */
  pl_vpush(t, test_law(t, 2, 0, 1)); /* K x y = x */
  pl_vpush(t, test_law(t, 2, 0, 1)); /* K' */
  pl_vpush(t, 5);
  pl_vpush(t, 6);
  pl_vpush(t, 7);
  pl_gc_reserve(t, PL_THKE_CELLS(5));
  pl_val thke = pl_mk_thke(t, PL_BAN_SLOW, 5, &t->vstack[base]);
  t->vsp = base;

  ASSERT_EQ(pl_whnf(t, thke), 6);
  test_rt_free(&rt);
}

/* ── Recursive-let knots ───────────────────────────────────────────────── */

TEST(judge, environment_populates_self_slot) {
  test_rt rt = test_rt_new();
  pl_thread* t = rt.t;
  size_t base = t->vsp;
  pl_vpush(t, test_law(t, 1, 0, 0)); /* f x = f */

  pl_val result = pl_apply(t, t->vstack[base], 9);
  ASSERT_EQ(result, t->vstack[base]);

  t->vsp = base;
  test_rt_free(&rt);
}

/*
 * f x = let b1 = b2; b2 = x in b1
 * body: (1 3 (1 1 2)) with slots [self=0, x=1, b1=2, b2=3].
 * Exercises the backpatched knot: b1's expression references the later
 * bind b2.
 */
TEST(judge, knot_forward_reference) {
  test_rt rt = test_rt_new();
  pl_thread* t = rt.t;
  size_t base = t->vsp;
  pl_vpush(t, test_app2(t, 1, 1, 2));               /* (1 1 2)   */
  pl_vpush(t, test_app2(t, 1, 3, t->vstack[base])); /* (1 3 ...) */
  pl_val f = test_law(t, 1, 0, t->vstack[base + 1]);
  ASSERT_EQ(pl_apply(t, f, 9), 9);
  test_rt_free(&rt);
}

/* f x = let b = b in b  ->  <<loop>> */
TEST(judge, self_referential_bind_raises_loop) {
  test_rt rt = test_rt_new();
  pl_thread* t = rt.t;
  size_t base = t->vsp;
  pl_vpush(t, test_app2(t, 1, 2, 2)); /* (1 2 2) */
  pl_val f = test_law(t, 1, 0, t->vstack[base]);
  pl_vpush(t, f);
  pl_catch c;
  pl_catch_init(t, &c);
  if (setjmp(c.jb) == 0) {
    (void)pl_apply(t, t->vstack[base + 1], 9);
    FAIL_TEST("expected <<loop>>");
  }
  pl_catch_unwind(t, &c);
  ASSERT_NOT_NULL(t->exn_msg);
  ASSERT_STR_EQ(t->exn_msg, "<<loop>>");
  test_rt_free(&rt);
}

/* ── Primop strictness ─────────────────────────────────────────────────── */

TEST(ops, strict_args_force_left_to_right) {
  test_rt rt = test_rt_new();
  pl_thread* t = rt.t;
  size_t base = t->vsp;
  pl_vpush(t, test_throwing(t, 7));
  pl_vpush(t, test_throwing(t, 8));
  pl_catch c;
  pl_catch_init(t, &c);
  if (setjmp(c.jb) == 0) {
    (void)test_op66_2(t, ax_s3('A', 'd', 'd'), t->vstack[base],
                      t->vstack[base + 1]);
    FAIL_TEST("expected PLAN_EXN");
  }
  pl_catch_unwind(t, &c);
  ASSERT_NULL(t->exn_msg);
  ASSERT_EQ(t->exn, 7); /* arg 0 forced first */
  test_rt_free(&rt);
}

TEST(ops, lookup_segregates_opcode_set_and_argc) {
  test_rt rt = test_rt_new();
  pl_thread* t = rt.t;
  pl_val arg1[1] = {0};
  test_expect_no_op66(t, ax_s3('A', 'd', 'd'), 1, arg1);
  test_expect_no_op66(t, ax_s4('R', 'e', 'c', 'v'), 1, arg1);
  test_rt_free(&rt);
}

TEST(ops, install_rejects_compiler_self_replacement) {
  test_rt rt = test_rt_new();
  pl_thread* t = rt.t;
  size_t base = t->vsp;
  pl_vpush(t, pl_pin(t, 42));
  char err[192] = {0};
  ASSERT(pl_store_save_root(rt.store, t->vstack[base], NULL, err, sizeof(err)),
         "%s", err);
  pl_val compiler = t->vstack[base];
  const uint8_t* hash = pl_pin_hash(compiler);

  /* Make the old, unguarded path idempotent so this test fails safely
   * instead of freeing the active machine out from under op_install. */
  memcpy(rt.store->compiler, hash, sizeof(rt.store->compiler));
  rt.store->compiler_f = hash[0] == 0 || memcmp(hash, hash + 1, 31) != 0;
  rt.store->compiler_t = t;

  bool raised = test_install_self_replacement_raises(t, compiler);

  rt.store->compiler_t = NULL;
  rt.store->compiler_f = false;
  memset(rt.store->compiler, 0, sizeof(rt.store->compiler));
  ASSERT(raised, "expected a compiler self-install to raise");
  ASSERT_STR_EQ(t->exn_msg, "Install: compiler cannot replace its own machine");
  test_rt_free(&rt);
}

TEST(ops, untaken_branches_stay_lazy) {
  test_rt rt = test_rt_new();
  pl_thread* t = rt.t;
  size_t base = t->vsp;
  pl_vpush(t, test_throwing(t, 7));
  /* If 0 <throw> 42  ->  42 */
  pl_val args[3] = {0, t->vstack[base], 42};
  ASSERT_EQ(test_op66(t, ax_s2('I', 'f'), 3, args), 42);
  /* And 0 <throw> -> 0; Or 1 <throw> -> 1 */
  ASSERT_EQ(test_op66_2(t, ax_s3('A', 'n', 'd'), 0, t->vstack[base]), 0);
  ASSERT_EQ(test_op66_2(t, ax_s2('O', 'r'), 1, t->vstack[base]), 1);
  test_rt_free(&rt);
}

TEST(ops, elim_case_branches_stay_lazy) {
  test_rt rt = test_rt_new();
  pl_thread* t = rt.t;
  size_t base = t->vsp;
  pl_vpush(t, test_throwing(t, 7));
  /* match _ _ _ z _ 0  ->  z, with every other branch throwing */
  pl_val th = t->vstack[base];
  pl_val args[6] = {th, th, th, 42, th, 0};
  ASSERT_EQ(test_op66(t, ax_s4('E', 'l', 'i', 'm'), 6, args), 42);
  test_rt_free(&rt);
}

TEST(ops, elim_decomposition_hands_out_lazy_args) {
  test_rt rt = test_rt_new();
  pl_thread* t = rt.t;
  size_t base = t->vsp;
  /* scrutinee row (0 1 <throw>): the a-branch gets ini and the (lazy)
   * last element; a const2 law ignores both. */
  pl_vpush(t, test_throwing(t, 7));
  pl_vpush(t, test_app2(t, 0, 1, t->vstack[base]));
  pl_vpush(t, test_app1(t, 0, 99));                    /* (0 99) quote */
  pl_vpush(t, test_law(t, 2, 0, t->vstack[base + 2])); /* const2 -> 99 */
  pl_val th = t->vstack[base];
  pl_val args[6] = {th, th, t->vstack[base + 3], th, th, t->vstack[base + 1]};
  ASSERT_EQ(test_op66(t, ax_s4('E', 'l', 'i', 'm'), 6, args), 99);
  test_rt_free(&rt);
}

TEST(ops, seq_and_force) {
  test_rt rt = test_rt_new();
  pl_thread* t = rt.t;
  /* Seq 1 2 -> 2 */
  ASSERT_EQ(test_op66_2(t, ax_s3('S', 'e', 'q'), 1, 2), 2);
  /* Seq <throw> 2 raises */
  size_t base = t->vsp;
  pl_vpush(t, test_throwing(t, 7));
  pl_catch c;
  pl_catch_init(t, &c);
  if (setjmp(c.jb) == 0) {
    (void)test_op66_2(t, ax_s3('S', 'e', 'q'), t->vstack[base], 2);
    FAIL_TEST("expected PLAN_EXN");
  }
  pl_catch_unwind(t, &c);
  ASSERT_EQ(t->exn, 7);
  test_rt_free(&rt);
}

TEST(ops, force_deep_normalizes_arg) {
  test_rt rt = test_rt_new();
  pl_thread* t = rt.t;
  size_t base = t->vsp;
  pl_vpush(t, test_app1_thunk_to(t, 42));
  pl_val args[1] = {t->vstack[base]};
  pl_val r = test_op66(t, ax_s5('F', 'o', 'r', 'c', 'e'), 1, args);
  pl_cell* p = pl_as(PL_TAG_APP, r);
  ASSERT_NOT_NULL(p);
  ASSERT_EQ(pl_app_args(p)[0], 42);
  ASSERT((pl_hdr_flags(p[0]) & PL_F_NORMAL) != 0);
  test_rt_free(&rt);
}

TEST(ops, pin_keeps_nested_fields_lazy) {
  test_rt rt = test_rt_new();
  pl_thread* t = rt.t;
  size_t base = t->vsp;
  pl_vpush(t, test_app1_thunk_to(t, 42));
  pl_val args[1] = {t->vstack[base]};
  pl_vpush(t, test_op66(t, ax_s3('P', 'i', 'n'), 1, args));

  pl_cell* proxy = pl_as(PL_TAG_PIN, t->vstack[base + 1]);
  ASSERT_NOT_NULL(proxy);
  pl_cell* body = pl_as(PL_TAG_APP, pl_pin_body(proxy));
  ASSERT_NOT_NULL(body);
  ASSERT_EQ(pl_tag(pl_app_args(body)[0]), PL_TAG_DEFER);
  ASSERT_EQ(pl_hdr_flags(proxy[0]) & PL_F_NORMAL, 0);
  test_rt_free(&rt);
}

TEST(ops, deepseq_normalizes_first_and_returns_second_lazily) {
  test_rt rt = test_rt_new();
  pl_thread* t = rt.t;
  size_t base = t->vsp;
  pl_vpush(t, test_app1_thunk_to(t, 42));
  pl_vpush(t, test_throwing(t, 7));
  pl_vpush(t, test_app1(t, 0, t->vstack[base + 1]));
  pl_val r = test_op66_2(t, ax_s7('D', 'e', 'e', 'p', 'S', 'e', 'q'),
                         t->vstack[base], t->vstack[base + 2]);
  ASSERT_EQ(r, t->vstack[base + 2]);
  pl_cell* xp = pl_as(PL_TAG_APP, t->vstack[base]);
  ASSERT_NOT_NULL(xp);
  ASSERT_EQ(pl_app_args(xp)[0], 42);
  ASSERT((pl_hdr_flags(xp[0]) & PL_F_NORMAL) != 0);
  pl_cell* yp = pl_as(PL_TAG_APP, r);
  ASSERT_NOT_NULL(yp);
  ASSERT_EQ(pl_tag(pl_app_args(yp)[0]), PL_TAG_DEFER);
  test_rt_free(&rt);
}

TEST(ops, trace_deep_normalizes_before_showing) {
  test_rt rt = test_rt_new();
  pl_thread* t = rt.t;
  size_t base = t->vsp;
  pl_vpush(t, test_app1_thunk_to(t, 42));
  pl_vpush(t, test_throwing(t, 7));
  pl_vpush(t, test_app1(t, 0, t->vstack[base + 1]));
  pl_val r = test_op66_2(t, ax_s5('T', 'r', 'a', 'c', 'e'), t->vstack[base],
                         t->vstack[base + 2]);
  ASSERT_EQ(r, t->vstack[base + 2]);
  pl_cell* xp = pl_as(PL_TAG_APP, t->vstack[base]);
  ASSERT_NOT_NULL(xp);
  ASSERT_EQ(pl_app_args(xp)[0], 42);
  pl_cell* yp = pl_as(PL_TAG_APP, r);
  ASSERT_NOT_NULL(yp);
  ASSERT_EQ(pl_tag(pl_app_args(yp)[0]), PL_TAG_DEFER);
  test_rt_free(&rt);
}

TEST(ops, try_catches_plan_exn_only) {
  test_rt rt = test_rt_new();
  pl_thread* t = rt.t;
  size_t base = t->vsp;
  /* thrower x = Throw 5 — body: (0 (0 P66) (0 ("Throw" 5))) */
  {
    pl_val row_args[1] = {5};
    pl_vpush(t, test_app(t, ax_s5('T', 'h', 'r', 'o', 'w'), 1, row_args));
    pl_vpush(t, test_app1(t, 0, t->vstack[base]));
    pl_vpush(t, test_app1(t, 0, test_p66(t)));
    pl_vpush(t, test_app2(t, 0, t->vstack[base + 2], t->vstack[base + 1]));
    pl_vpush(t, test_law(t, 1, 0, t->vstack[base + 3]));
  }
  size_t thrower = t->vsp - 1;
  pl_val args[2] = {t->vstack[thrower], 1};
  pl_val r = test_op66(t, ax_s3('T', 'r', 'y'), 2, args);
  pl_cell* p = pl_as(PL_TAG_APP, r);
  ASSERT_NOT_NULL(p);
  ASSERT_EQ(pl_app_head(p), 1); /* Left: (1 exn) */
  ASSERT_EQ(pl_app_args(p)[0], 5);

  /* and the Right case */
  pl_vpush(t, test_law(t, 1, 0, 1)); /* id */
  pl_val args2[2] = {t->vstack[t->vsp - 1], 9};
  r = test_op66(t, ax_s3('T', 'r', 'y'), 2, args2);
  p = pl_as(PL_TAG_APP, r);
  ASSERT_NOT_NULL(p);
  ASSERT_EQ(pl_app_head(p), 0);
  ASSERT_EQ(pl_app_args(p)[0], 9);
  test_rt_free(&rt);
}

TEST(ops, pure_bounds_and_recovers) {
  test_rt rt = test_rt_new();
  pl_thread* t = rt.t;
  pl_vpush(t, test_law(t, 1, 0, 1));
  size_t identity = t->vsp - 1;
  const uint64_t budgets[] = {0, 1, 1000000000};
  for (size_t i = 0; i < 3; i++) {
    pl_val args[3] = {budgets[i], t->vstack[identity], 9};
    pl_val r = test_op66(t, ax_s4('P', 'u', 'r', 'e'), 3, args);
    pl_cell* p = pl_as(PL_TAG_APP, r);
    ASSERT_NOT_NULL(p);
    ASSERT_EQ(pl_app_head(p), i == 0 ? 1 : 0);
    if (i != 0) ASSERT_EQ(pl_app_args(p)[0], 9);
    ASSERT_EQ(t->pure_depth, 0);
  }
  test_rt_free(&rt);
}

TEST(ops, pure_trace_preserves_underlying_exception) {
  test_rt rt = test_rt_new();
  pl_thread* t = rt.t;
  size_t base = t->vsp;
  pl_vpush(t, test_throwing(t, 19));
  pl_val fields[2] = {42, t->vstack[base]};
  base = t->vsp;
  pl_vpush(t, test_app(t, ax_s5('T', 'r', 'a', 'c', 'e'), 2, fields));
  pl_vpush(t, test_app1(t, 0, t->vstack[base]));
  pl_vpush(t, test_app1(t, 0, test_p66(t)));
  pl_vpush(t, test_app2(t, 0, t->vstack[base + 2], t->vstack[base + 1]));
  pl_vpush(t, test_law(t, 1, 0, t->vstack[base + 3]));
  pl_val denied[3] = {10000, t->vstack[base + 4], 0};
  pl_cell* p = pl_as(PL_TAG_APP,
      test_op66(t, ax_s4('P', 'u', 'r', 'e'), 3, denied));
  ASSERT_NOT_NULL(p);
  ASSERT_EQ(pl_app_head(p), 1);
  ASSERT_EQ(pl_app_args(p)[0], 19);
  ASSERT_EQ(t->pure_depth, 0);
  test_rt_free(&rt);
}

TEST(ops, pure_silences_trace_and_normalizes_lazy_results) {
  test_rt rt = test_rt_new();
  pl_thread* t = rt.t;
  size_t base = t->vsp;
  pl_val fields[2] = {42, 7};
  pl_vpush(t, test_app(t, ax_s5('T', 'r', 'a', 'c', 'e'), 2, fields));
  pl_vpush(t, test_app1(t, 0, t->vstack[base]));
  pl_vpush(t, test_app1(t, 0, test_p66(t)));
  pl_vpush(t, test_app2(t, 0, t->vstack[base + 2], t->vstack[base + 1]));
  pl_vpush(t, test_law(t, 1, 0, t->vstack[base + 3]));
  pl_val denied[3] = {10000, t->vstack[base + 4], 0};
  pl_cell* p = pl_as(PL_TAG_APP,
      test_op66(t, ax_s4('P', 'u', 'r', 'e'), 3, denied));
  ASSERT_NOT_NULL(p);
  ASSERT_EQ(pl_app_head(p), 0);
  ASSERT_EQ(pl_app_args(p)[0], 7);
  ASSERT_EQ(t->pure_depth, 0);
  pl_vpush(t, test_law(t, 1, 0, 1));
  pl_vpush(t, test_app1_thunk_to(t, 17));
  pl_val allowed[3] = {10000, t->vstack[t->vsp - 2], t->vstack[t->vsp - 1]};
  p = pl_as(PL_TAG_APP, test_op66(t, ax_s4('P', 'u', 'r', 'e'), 3, allowed));
  ASSERT_NOT_NULL(p);
  ASSERT_EQ(pl_app_head(p), 0);
  pl_cell* result = pl_as(PL_TAG_APP, pl_app_args(p)[0]);
  ASSERT_NOT_NULL(result);
  ASSERT_EQ(pl_resolve(pl_app_args(result)[0]), 17);
  ASSERT_EQ(t->pure_depth, 0);
  test_rt_free(&rt);
}

TEST(ops, try_restores_unwound_thunk_chain) {
  test_rt rt = test_rt_new();
  pl_thread* t = rt.t;
  size_t base = t->vsp;
  enum { DEPTH = 8 };

  /* Model a lazy import/elaboration chain whose innermost thunk throws.
   * Every THKE is blackholed before Try catches the PLAN exception. */
  pl_vpush(t, test_throwing(t, 7));
  for (unsigned i = 0; i < DEPTH; i++) {
    pl_gc_reserve(t, PL_THKE_CELLS(1));
    t->vstack[base] = pl_mk_thke(t, PL_BAN_SLOW, 1, &t->vstack[base]);
  }
  pl_vpush(t, test_law(t, 1, 0, 1)); /* identity forces its argument */

  for (unsigned attempt = 0; attempt < 2; attempt++) {
    pl_val args[2] = {t->vstack[base + 1], t->vstack[base]};
    pl_val r = test_op66(t, ax_s3('T', 'r', 'y'), 2, args);
    pl_cell* p = pl_as(PL_TAG_APP, r);
    ASSERT_NOT_NULL(p);
    ASSERT_EQ(pl_app_head(p), 1);
    ASSERT_EQ(pl_app_args(p)[0], 7);

    pl_val cursor = t->vstack[base];
    for (unsigned i = 0; i < DEPTH; i++) {
      p = pl_as(PL_TAG_DEFER, cursor);
      ASSERT_NOT_NULL(p);
      ASSERT_EQ(pl_hdr_kind(p[0]), PL_K_THKE);
      ASSERT_EQ(pl_hdr_flags(p[0]) & PL_F_HOLE, 0);
      cursor = pl_thke_args(p)[0];
    }
    p = pl_as(PL_TAG_DEFER, cursor);
    ASSERT_NOT_NULL(p);
    ASSERT_EQ(pl_hdr_kind(p[0]), PL_K_THUNK);
  }

  test_rt_free(&rt);
}

TEST(ops, equal_deep_and_pin_identity) {
  test_rt rt = test_rt_new();
  pl_thread* t = rt.t;
  size_t base = t->vsp;
  pl_vpush(t, test_app2(t, 0, 1, 2));
  pl_vpush(t, test_app2(t, 0, 1, 2));
  ASSERT_EQ(test_op66_2(t, ax_s5('E', 'q', 'u', 'a', 'l'), t->vstack[base],
                        t->vstack[base + 1]),
            1);
  /* Pin construction is lazy: equal values get distinct proxies while PLAN
   * equality remains structural until Save gives them canonical hashes. */
  pl_vpush(t, pl_pin(t, t->vstack[base]));
  pl_vpush(t, pl_pin(t, t->vstack[base + 1]));
  ASSERT_NEQ(t->vstack[base + 2], t->vstack[base + 3]);
  ASSERT_EQ(test_op66_2(t, ax_s5('E', 'q', 'u', 'a', 'l'), t->vstack[base + 2],
                        t->vstack[base + 3]),
            1);
  ASSERT_EQ(pl_pin_proxy_target(pl_ptr(t->vstack[base + 2])), 0);
  ASSERT_EQ(pl_pin_proxy_target(pl_ptr(t->vstack[base + 3])), 0);
  ASSERT_NULL(pl_pin_hash(t->vstack[base + 2]));
  ASSERT_NULL(pl_pin_hash(t->vstack[base + 3]));

  /* Save keeps the two public proxies distinct but deduplicates their
   * canonical target.  Equal must chase that target before its identity
   * check, including when only one operand is still the public proxy. */
  char err[192] = {0};
  ASSERT(
      pl_store_save_root(rt.store, t->vstack[base + 2], NULL, err, sizeof(err)),
      "%s", err);
  ASSERT(
      pl_store_save_root(rt.store, t->vstack[base + 3], NULL, err, sizeof(err)),
      "%s", err);
  pl_val canonical = pl_pin_proxy_target(pl_ptr(t->vstack[base + 2]));
  ASSERT_NEQ(canonical, 0);
  ASSERT_EQ(canonical, pl_pin_proxy_target(pl_ptr(t->vstack[base + 3])));
  ASSERT_EQ(test_op66_2(t, ax_s5('E', 'q', 'u', 'a', 'l'), t->vstack[base + 2],
                        t->vstack[base + 3]),
            1);
  ASSERT_EQ(test_op66_2(t, ax_s5('E', 'q', 'u', 'a', 'l'), t->vstack[base + 2],
                        canonical),
            1);
  test_rt_free(&rt);
}

TEST(ops, ice_normalizes_and_persists_without_publishing_root) {
  test_rt rt = test_rt_new();
  pl_thread* t = rt.t;
  size_t base = t->vsp;
  pl_vpush(t, test_app1_thunk_to(t, 42));
  t->vstack[base] = pl_pin(t, t->vstack[base]);
  pl_vpush(t, test_app1(t, 0, t->vstack[base]));
  t->vstack[base + 1] = pl_pin(t, t->vstack[base + 1]);
  ASSERT_NULL(pl_pin_hash(t->vstack[base]));
  uint64_t epoch = t->effect_epoch;
  ASSERT_EQ(test_ice(t, t->vstack[base + 1]), 0);
  ASSERT_EQ(t->effect_epoch, epoch + 1);
  for (size_t i = 0; i < 2; i++) {
    pl_val pin = t->vstack[base + i];
    ASSERT_NOT_NULL(pl_pin_hash(pin));
    ASSERT(rt.store->be.has(rt.store->be.ctx, pl_pin_hash(pin)));
    ASSERT_EQ(pl_store_load(t, pl_pin_hash(pin)),
              pl_pin_proxy_target(pl_ptr(pin)));
  }
  pl_val body = pl_pin_body(pl_ptr(t->vstack[base]));
  ASSERT_EQ(pl_app_args(pl_ptr(body))[0], 42);
  uint8_t root[32];
  ASSERT_FALSE(pl_store_get_root(rt.store, root));

  char err[192] = {0};
  ASSERT(pl_store_save_root(rt.store, t->vstack[base], root, err, sizeof(err)),
         "%s", err);
  pl_val canonical = pl_pin_proxy_target(pl_ptr(t->vstack[base + 1]));
  ASSERT_EQ(test_ice(t, t->vstack[base + 1]), 0);
  ASSERT_EQ(test_ice(t, canonical), 0);
  uint8_t after[32];
  ASSERT(pl_store_get_root(rt.store, after));
  ASSERT_EQ(memcmp(root, after, sizeof(root)), 0);
  ASSERT_EQ(pl_pin_proxy_target(pl_ptr(t->vstack[base + 1])), canonical);
  test_rt_free(&rt);
}

TEST(ops, ice_rejects_nonpins_and_propagates_normalization_errors) {
  test_rt rt = test_rt_new();
  pl_thread* t = rt.t;
  ASSERT(test_ice_raises(t, 42));
  ASSERT_STR_EQ(t->exn_msg, "Ice: expected a pin");
  pl_val wrong_args[2] = {0, 0};
  test_expect_no_op66(t, ax_s3('I', 'c', 'e'), 2, wrong_args);

  size_t base = t->vsp;
  pl_vpush(t, test_throwing(t, 7));
  t->vstack[base] = test_app1(t, 0, t->vstack[base]);
  t->vstack[base] = pl_pin(t, t->vstack[base]);
  for (unsigned attempt = 0; attempt < 2; attempt++) {
    ASSERT(test_ice_raises(t, t->vstack[base]));
    ASSERT_EQ(t->exn, 7);
    ASSERT_NULL(pl_pin_hash(t->vstack[base]));
    ASSERT_EQ(pl_pin_proxy_target(pl_ptr(t->vstack[base])), 0);
  }
  test_rt_free(&rt);
}

TEST(ops, equal_reuses_frozen_pin_in_either_order_and_survives_gc) {
  test_rt rt = test_rt_new();
  pl_thread* t = rt.t;
  size_t base = t->vsp;
  pl_vpush(t, test_law(t, 1, 37, 1));
  t->vstack[base] = pl_pin(t, t->vstack[base]);
  ASSERT_EQ(test_ice(t, t->vstack[base]), 0);
  pl_val canonical = pl_pin_proxy_target(pl_ptr(t->vstack[base]));
  pl_code code = {0};
  pl_pin_set_code(pl_ptr(canonical), &code);
  for (unsigned variant = 0; variant < 4; variant++) {
    pl_vpush(t, test_law(t, 1, 37, 1));
    t->vstack[base + 1] = pl_pin(t, t->vstack[base + 1]);
    pl_val frozen = variant < 2 ? t->vstack[base] : canonical;
    pl_val fresh = t->vstack[base + 1];
    uint64_t epoch = t->effect_epoch;
    ASSERT_EQ(test_op66_2(t, ax_s5('E', 'q', 'u', 'a', 'l'),
                          variant % 2 == 0 ? fresh : frozen,
                          variant % 2 == 0 ? frozen : fresh),
              1);
    ASSERT_EQ(t->effect_epoch, epoch);
    ASSERT_EQ(pl_pin_proxy_target(pl_ptr(t->vstack[base + 1])), canonical);
    pl_gc_collect_now(t);
    pl_cell* proxy = pl_ptr(t->vstack[base + 1]);
    ASSERT_EQ(pl_pin_proxy_target(proxy), canonical);
    ASSERT_EQ(proxy[5], 0);
    ASSERT_EQ(pl_pin_hash(t->vstack[base + 1]), pl_pin_hash(canonical));
    ASSERT_EQ(pl_pin_body(proxy), pl_pin_body(pl_ptr(canonical)));
    ASSERT_EQ(pl_pin_code(proxy), &code);
    t->vsp = base + 1;
  }
  pl_pin_set_code(pl_ptr(canonical), NULL);
  test_rt_free(&rt);
}

TEST(ops, equal_publishes_nested_matches_but_not_unequal_parents) {
  test_rt rt = test_rt_new();
  pl_thread* t = rt.t;
  size_t base = t->vsp;
  pl_vpush(t, pl_pin(t, 7));
  pl_vpush(t, test_app2(t, 0, t->vstack[base], 8));
  t->vstack[base + 1] = pl_pin(t, t->vstack[base + 1]);
  ASSERT_EQ(test_ice(t, t->vstack[base + 1]), 0);
  for (unsigned reverse = 0; reverse < 2; reverse++) {
    pl_vpush(t, pl_pin(t, 7));
    pl_vpush(t, test_app2(t, 0, t->vstack[base + 2], 9));
    t->vstack[base + 3] = pl_pin(t, t->vstack[base + 3]);
    pl_val frozen = t->vstack[base + 1];
    pl_val fresh = t->vstack[base + 3];
    ASSERT_EQ(test_op66_2(t, ax_s5('E', 'q', 'u', 'a', 'l'),
                          reverse != 0 ? frozen : fresh,
                          reverse != 0 ? fresh : frozen),
              0);
    ASSERT_EQ(pl_pin_proxy_target(pl_ptr(t->vstack[base + 2])),
              pl_pin_proxy_target(pl_ptr(t->vstack[base])));
    ASSERT_EQ(pl_pin_proxy_target(pl_ptr(t->vstack[base + 3])), 0);
    ASSERT_NULL(pl_pin_hash(t->vstack[base + 3]));
    t->vsp = base + 2;
  }
  test_rt_free(&rt);
}

TEST(ops, equal_completes_nested_pin_comparisons_beyond_inline_worklist) {
  test_rt rt = test_rt_new();
  pl_thread* t = rt.t;
  size_t base = t->vsp;
  pl_vpush(t, 42);
  pl_vpush(t, 42);
  for (unsigned i = 0; i < 96; i++) {
    t->vstack[base] = test_app1(t, 0, t->vstack[base]);
    t->vstack[base] = pl_pin(t, t->vstack[base]);
    t->vstack[base + 1] = test_app1(t, 0, t->vstack[base + 1]);
    t->vstack[base + 1] = pl_pin(t, t->vstack[base + 1]);
  }
  ASSERT_EQ(test_ice(t, t->vstack[base]), 0);
  ASSERT_EQ(test_op66_2(t, ax_s5('E', 'q', 'u', 'a', 'l'), t->vstack[base],
                        t->vstack[base + 1]),
            1);
  ASSERT_EQ(pl_pin_proxy_target(pl_ptr(t->vstack[base + 1])),
            pl_pin_proxy_target(pl_ptr(t->vstack[base])));
  test_rt_free(&rt);
}

TEST(ops, equal_deep_normalizes_second_arg) {
  test_rt rt = test_rt_new();
  pl_thread* t = rt.t;
  size_t base = t->vsp;
  pl_vpush(t, test_app1_thunk_to(t, 42));
  pl_vpush(t, test_app1_thunk_to(t, 42));
  ASSERT_EQ(test_op66_2(t, ax_s5('E', 'q', 'u', 'a', 'l'), t->vstack[base],
                        t->vstack[base + 1]),
            1);
  test_rt_free(&rt);
}

TEST(ops, row_elements_stay_lazy) {
  test_rt rt = test_rt_new();
  pl_thread* t = rt.t;
  size_t base = t->vsp;
  /* Row 0 1 <stream whose Ix1 tail throws but Ix0 head is 5>:
   * the single element must come out as a lazy Ix0 thunk. */
  pl_vpush(t, test_throwing(t, 7));
  pl_vpush(t, test_app2(t, 0, 5, t->vstack[base])); /* (0 5 <throw>) */
  pl_val args[3] = {0, 1, t->vstack[base + 1]};
  pl_val r = test_op66(t, ax_s3('R', 'o', 'w'), 3, args);
  pl_cell* p = pl_as(PL_TAG_APP, r);
  ASSERT_NOT_NULL(p);
  ASSERT_EQ(pl_app_n(p), 1);
  pl_vpush(t, r);
  /* forcing the element gives Ix0 of the stream = 5 */
  pl_cell* rp = pl_as(PL_TAG_APP, t->vstack[base + 2]);
  ASSERT_NOT_NULL(rp);
  pl_val e = pl_whnf(t, pl_app_args(rp)[0]);
  ASSERT_EQ(e, 5);
  test_rt_free(&rt);
}

TEST(ops, whole_row_slice_reuses_only_exact_result) {
  test_rt rt = test_rt_new();
  pl_thread* t = rt.t;
  size_t base = t->vsp;
  pl_val items[3] = {11, 22, 33};
  pl_vpush(t, test_app(t, 0, 3, items));

  pl_val exact_args[3] = {0, 3, t->vstack[base]};
  pl_val exact = test_op66(t, ax_s5('S', 'l', 'i', 'c', 'e'), 3, exact_args);
  ASSERT_EQ(exact, t->vstack[base]);

  pl_val oversized_args[3] = {0, 99, t->vstack[base]};
  pl_val oversized =
      test_op66(t, ax_s5('S', 'l', 'i', 'c', 'e'), 3, oversized_args);
  ASSERT_EQ(oversized, t->vstack[base]);

  pl_vpush(t, test_app(t, 7, 3, items));
  pl_val rehead_args[3] = {0, 3, t->vstack[base + 1]};
  pl_val reheaded =
      test_op66(t, ax_s5('S', 'l', 'i', 'c', 'e'), 3, rehead_args);
  ASSERT_NEQ(reheaded, t->vstack[base + 1]);
  pl_cell* p = pl_as(PL_TAG_APP, reheaded);
  ASSERT_NOT_NULL(p);
  ASSERT_EQ(pl_app_head(p), 0);
  ASSERT_EQ(pl_app_n(p), 3);

  test_rt_free(&rt);
}

TEST(ops, weld_uses_zero_for_empty_rows) {
  test_rt rt = test_rt_new();
  pl_thread* t = rt.t;
  pl_val weld = ax_s4('W', 'e', 'l', 'd');
  ASSERT_EQ(test_op66_2(t, weld, 0, 0), 0);
  ASSERT_EQ(test_op66_2(t, weld, 7, 9), 0);

  size_t base = t->vsp;
  pl_vpush(t, test_app1(t, 7, 11));
  for (unsigned order = 0; order < 2; order++) {
    pl_val row = t->vstack[base];
    pl_val result = test_op66_2(t, weld, order ? row : 0, order ? 0 : row);
    pl_cell* p = pl_as(PL_TAG_APP, result);
    ASSERT_NOT_NULL(p);
    ASSERT_EQ(pl_app_head(p), 0);
    ASSERT_EQ(pl_app_n(p), 1);
    ASSERT_EQ(pl_app_args(p)[0], 11);
  }
  pl_vpush(t, test_app2(t, 9, 22, 33));
  pl_val result = test_op66_2(t, weld, t->vstack[base], t->vstack[base + 1]);
  test_assert_nat_row3(result, 11, 22, 33);
  test_rt_free(&rt);
}

TEST(ops, app_producers_collapse_head_only_results) {
  test_rt rt = test_rt_new();
  pl_thread* t = rt.t;
  size_t base = t->vsp;
  pl_vpush(t, test_throwing(t, 99));
  pl_vpush(t, test_app1(t, 7, t->vstack[base]));

  /* Empty Row/Rep preserve the head without forcing unused lazy fields. */
  pl_val rep[3] = {7, t->vstack[base], 0};
  ASSERT_EQ(test_op66(t, ax_s3('R', 'e', 'p'), 3, rep), 7);
  pl_val row[3] = {7, 0, t->vstack[base]};
  ASSERT_EQ(test_op66(t, ax_s3('R', 'o', 'w'), 3, row), 7);
  pl_val slice[3] = {0, 0, t->vstack[base + 1]};
  ASSERT_EQ(test_op66(t, ax_s5('S', 'l', 'i', 'c', 'e'), 3, slice), 0);
  pl_val past_end[3] = {1, 10, t->vstack[base + 1]};
  ASSERT_EQ(test_op66(t, ax_s5('S', 'l', 'i', 'c', 'e'), 3, past_end), 0);
  pl_val app = t->vstack[base + 1];
  ASSERT_EQ(test_op66(t, ax_s4('I', 'n', 'i', 't'), 1, &app), 7);
  ASSERT_EQ(test_op66_2(t, ax_s4('C', 'o', 'u', 'p'), 7, 0), 7);
  pl_val up[3] = {0, t->vstack[base], 0};
  ASSERT_EQ(test_op66(t, ax_s2('U', 'p'), 3, up), 0);
  pl_val up_uniq[3] = {0, t->vstack[base], 0};
  ASSERT_EQ(test_op66(t, ax_s6('U', 'p', 'U', 'n', 'i', 'q'), 3, up_uniq), 0);

  /* Elim decomposes the shortest lawful app into head and lazy argument. */
  pl_val elim[6] = {0, 0, 0, 0, 0, t->vstack[base + 1]};
  pl_cell* result =
      pl_as(PL_TAG_APP, test_op66(t, ax_s4('E', 'l', 'i', 'm'), 6, elim));
  ASSERT_NOT_NULL(result);
  ASSERT_EQ(pl_app_head(result), 0);
  ASSERT_EQ(pl_app_n(result), 2);
  ASSERT_EQ(pl_app_args(result)[0], 7);
  ASSERT_EQ(pl_app_args(result)[1], t->vstack[base]);
  test_rt_free(&rt);
}

TEST(ops, scan8_handles_both_polarities_and_stops_at_rejected_byte) {
  test_rt rt = test_rt_new();
  pl_thread* t = rt.t;
  size_t base = t->vsp;
  static const uint8_t source[] = {'a', 'a', 'a', 'b'};
  static const uint8_t klass[] = {'a'};
  pl_vpush(t, pl_nat_from_bytes(t, source, sizeof(source)));
  pl_vpush(t, test_byte_mask(t, klass, sizeof(klass)));

  pl_val inside_args[4] = {
      t->vstack[base],
      0,
      t->vstack[base + 1],
      1,
  };
  pl_val inside = test_op66(t, ax_s5('s', 'c', 'a', 'n', '8'), 4, inside_args);
  test_assert_nat_row3(inside, 3, 0, 3);

  pl_val outside_args[4] = {
      t->vstack[base],
      3,
      t->vstack[base + 1],
      0,
  };
  pl_val outside =
      test_op66(t, ax_s5('s', 'c', 'a', 'n', '8'), 4, outside_args);
  test_assert_nat_row3(outside, 4, 0, 1);
  test_rt_free(&rt);
}

TEST(ops, scan8_counts_lf_and_tracks_column_from_nonzero_start) {
  test_rt rt = test_rt_new();
  pl_thread* t = rt.t;
  size_t base = t->vsp;
  static const uint8_t source[] = {'x', 'x',  'a', '\n', 'b',
                                   'c', '\n', 'z', '!'};
  uint8_t all_bytes[32];
  memset(all_bytes, 0xff, sizeof(all_bytes));
  pl_vpush(t, pl_nat_from_bytes(t, source, sizeof(source)));
  pl_vpush(t, pl_nat_from_bytes(t, all_bytes, sizeof(all_bytes)));

  pl_val args[4] = {
      t->vstack[base],
      2,
      t->vstack[base + 1],
      42,
  };
  pl_val out = test_op66(t, ax_s5('s', 'c', 'a', 'n', '8'), 4, args);
  test_assert_nat_row3(out, 9, 2, 2);
  test_rt_free(&rt);
}

TEST(ops, scan8_preserves_eof_and_past_end_start) {
  test_rt rt = test_rt_new();
  pl_thread* t = rt.t;
  size_t base = t->vsp;
  static const uint8_t source[] = {'a', 'b', 'c'};
  pl_vpush(t, pl_nat_from_bytes(t, source, sizeof(source)));

  pl_val eof_args[4] = {t->vstack[base], 3, 0, 0};
  pl_val eof = test_op66(t, ax_s5('s', 'c', 'a', 'n', '8'), 4, eof_args);
  test_assert_nat_row3(eof, 3, 0, 0);

  uint8_t large_start_bytes[9] = {0};
  large_start_bytes[8] = 1;
  pl_vpush(t,
           pl_nat_from_bytes(t, large_start_bytes, sizeof(large_start_bytes)));
  pl_val past_args[4] = {t->vstack[base], t->vstack[base + 1], 0, 0};
  pl_val past = test_op66(t, ax_s5('s', 'c', 'a', 'n', '8'), 4, past_args);
  test_assert_nat_row3(past, t->vstack[base + 1], 0, 0);

  pl_val empty_args[4] = {0, 0, 0, 1};
  pl_val empty = test_op66(t, ax_s5('s', 'c', 'a', 'n', '8'), 4, empty_args);
  test_assert_nat_row3(empty, 0, 0, 0);
  test_rt_free(&rt);
}

TEST(ops, scan8_uses_all_256_mask_bits) {
  test_rt rt = test_rt_new();
  pl_thread* t = rt.t;
  size_t base = t->vsp;
  static const uint8_t source[] = {0xff, 'x'};
  static const uint8_t klass[] = {0xff};
  pl_vpush(t, pl_nat_from_bytes(t, source, sizeof(source)));
  pl_vpush(t, test_byte_mask(t, klass, sizeof(klass)));
  pl_val args[4] = {
      t->vstack[base],
      0,
      t->vstack[base + 1],
      1,
  };
  pl_val out = test_op66(t, ax_s5('s', 'c', 'a', 'n', '8'), 4, args);
  test_assert_nat_row3(out, 1, 0, 1);
  test_rt_free(&rt);
}

TEST(ops, strtree_text_returns_its_string) {
  test_rt rt = test_rt_new();
  pl_thread* t = rt.t;
  size_t base = t->vsp;
  static const uint8_t hello[] = {'h', 'e', 'l', 'l', 'o'};
  pl_vpush(t, pl_nat_from_bytes(t, hello, sizeof(hello)));
  pl_vpush(t, test_cord_text(t, t->vstack[base]));

  pl_val args[1] = {t->vstack[base + 1]};
  pl_val out = test_op66(t, ax_s7('S', 't', 'r', 'T', 'r', 'e', 'e'), 1, args);
  ASSERT(pl_nat_eq(out, t->vstack[base]));
  test_rt_free(&rt);
}

TEST(ops, strtree_materializes_all_constructors_and_shared_subtrees) {
  test_rt rt = test_rt_new();
  pl_thread* t = rt.t;
  size_t base = t->vsp;
  static const uint8_t hello[] = {'h', 'e', 'l', 'l', 'o'};
  static const uint8_t source[] = {'s', 'o', 'u', 'r', 'c', 'e'};
  static const uint8_t expected[] = {
      'h', 'e', 'l', 'l', 'o', 'o', 'u', 'r', '!', '!', 'h', 'e', 'l', 'l', 'o',
  };
  pl_vpush(t, pl_nat_from_bytes(t, hello, sizeof(hello)));
  pl_vpush(t, pl_nat_from_bytes(t, source, sizeof(source)));
  pl_vpush(t, test_cord_text(t, t->vstack[base]));
  pl_vpush(t, test_cord_slice(t, t->vstack[base + 1], 1, 3));
  pl_vpush(t, test_cord_repeat(t, '!', 2));
  pl_vpush(t, test_cord_cat(t, t->vstack[base + 2], t->vstack[base + 3]));
  pl_vpush(t, test_cord_cat(t, t->vstack[base + 4], t->vstack[base + 2]));
  pl_vpush(t, test_cord_cat(t, t->vstack[base + 5], t->vstack[base + 6]));

  pl_val args[1] = {t->vstack[base + 7]};
  pl_val out = test_op66(t, ax_s7('S', 't', 'r', 'T', 'r', 'e', 'e'), 1, args);
  ASSERT_EQ(pl_nat_byte_len(out), sizeof(expected));
  for (size_t i = 0; i < sizeof(expected); i++)
    ASSERT_EQ(pl_nat_byte_at(out, i), expected[i]);
  test_rt_free(&rt);
}

TEST(ops, strtree_traversal_is_stack_safe) {
  test_rt rt = test_rt_new();
  pl_thread* t = rt.t;
  size_t base = t->vsp;
  pl_vpush(t, test_cord_repeat(t, 'x', 1));
  pl_vpush(t, t->vstack[base]);
  for (size_t i = 0; i < 4096; i++) {
    pl_val next = test_cord_cat(t, t->vstack[base + 1], t->vstack[base]);
    t->vstack[base + 1] = next;
  }

  pl_val args[1] = {t->vstack[base + 1]};
  pl_val out = test_op66(t, ax_s7('S', 't', 'r', 'T', 'r', 'e', 'e'), 1, args);
  ASSERT_EQ(pl_nat_byte_len(out), 4097);
  ASSERT_EQ(pl_nat_byte_at(out, 0), 'x');
  ASSERT_EQ(pl_nat_byte_at(out, 4096), 'x');
  test_rt_free(&rt);
}

TEST(ops, strtree_rejects_malformed_nodes_and_wrong_arity) {
  test_rt rt = test_rt_new();
  pl_thread* t = rt.t;
  size_t base = t->vsp;
  pl_vpush(t, test_app1(t, 0, 0));
  pl_vpush(t, test_cord_text(t, t->vstack[base]));
  pl_val args[1] = {t->vstack[base + 1]};
  ASSERT_EQ(test_op66(t, ax_s7('S', 't', 'r', 'T', 'r', 'e', 'e'), 1, args), 0);

  pl_val bad_fields[2] = {ax_s3('b', 'a', 'd'), 0};
  pl_vpush(t, test_app(t, 0, 2, bad_fields));
  pl_val bad_args[1] = {t->vstack[base + 2]};
  ASSERT_EQ(test_op66(t, ax_s7('S', 't', 'r', 'T', 'r', 'e', 'e'), 1, bad_args),
            0);

  pl_val old_fields[1] = {0};
  pl_vpush(t, test_app(t, ax_s4('t', 'e', 'x', 't'), 1, old_fields));
  pl_val old_args[1] = {t->vstack[base + 3]};
  ASSERT_EQ(test_op66(t, ax_s7('S', 't', 'r', 'T', 'r', 'e', 'e'), 1, old_args),
            0);

  pl_val wrong_args[2] = {0, 0};
  test_expect_no_op66(t, ax_s7('S', 't', 'r', 'T', 'r', 'e', 'e'), 2,
                      wrong_args);
  pl_val scan_args[3] = {0, 0, 0};
  test_expect_no_op66(t, ax_s5('s', 'c', 'a', 'n', '8'), 3, scan_args);
  test_rt_free(&rt);
}

TEST(ops, law_op_adds_one_to_arity) {
  test_rt rt = test_rt_new();
  pl_thread* t = rt.t;
  /* op0: (P0 % (1 a m b)) makes L (a+1) m b */
  size_t base = t->vsp;
  pl_vpush(t, 0);
  pl_val p0 = pl_pin(t, t->vstack[base]);
  pl_vpush(t, p0);
  pl_val row_args[3] = {1, 0, 1};
  pl_vpush(t, test_app(t, 1, 3, row_args)); /* (1 1 0 1) */
  pl_val r = pl_apply(t, t->vstack[base + 1], t->vstack[base + 2]);
  pl_cell* lp = pl_as(PL_TAG_LAW, r);
  ASSERT_NOT_NULL(lp);
  ASSERT_EQ(pl_law_arity(lp), 2); /* nat a + 1 */
  test_rt_free(&rt);
}

/* ── nf ────────────────────────────────────────────────────────────────── */

TEST(nf, deep_normalization_snaps_thunks) {
  test_rt rt = test_rt_new();
  pl_thread* t = rt.t;
  size_t base = t->vsp;
  /* row of one thunk that evaluates to 42 */
  pl_vpush(t, test_thunk(t, test_app1(t, 0, 42)));
  pl_vpush(t, test_app1(t, 0, t->vstack[base]));
  pl_val r = pl_nf(t, t->vstack[base + 1]);
  pl_cell* p = pl_as(PL_TAG_APP, r);
  ASSERT_NOT_NULL(p);
  ASSERT_EQ(pl_app_args(p)[0], 42); /* snapped, no IND left */
  ASSERT((pl_hdr_flags(p[0]) & PL_F_NORMAL) != 0);
  test_rt_free(&rt);
}

/* ── S2 opcodes: FORCE / PUSH_SLOT / BR / JMP / CALL / NOUPD ─────────── */

/* Make a saved law pin with arity and set its code; returns the pin
 * rooted at the current vsp (caller owns the slot). */
/* Distinct `name`s keep otherwise-identical laws from interning to the
 * same canonical pin (and silently sharing one code slot). */
static pl_val test_code_pin_named(test_rt* rt, uint64_t arity, uint64_t name,
                                  pl_code* code) {
  pl_thread* t = rt->t;
  size_t base = t->vsp;
  pl_vpush(t, test_law(t, arity, name, 0));
  t->vstack[base] = pl_pin(t, t->vstack[base]);
  char err[192] = {0};
  ASSERT(pl_store_save_root(rt->store, t->vstack[base], NULL, err, sizeof(err)),
         "%s", err);
  pl_cell* proxy = pl_as(PL_TAG_PIN, t->vstack[base]);
  ASSERT_NOT_NULL(proxy);
  pl_val pin = pl_pin_proxy_target(proxy);
  ASSERT_NEQ(pin, 0);
  t->vstack[base] = pin;
  pl_pin_set_code(pl_as(PL_TAG_PIN, pin), code);
  return pin;
}

static pl_val test_code_pin(test_rt* rt, uint64_t arity, pl_code* code) {
  return test_code_pin_named(rt, arity, 0, code);
}

static pl_val test_run_call1(pl_thread* t, pl_val pin, pl_val arg) {
  size_t base = t->vsp;
  pl_vpush(t, pin);
  pl_vpush(t, arg);
  pl_gc_reserve(t, PL_THKE_CELLS(2));
  pl_val thke = pl_mk_thke(t, PL_BAN_FAST, 2, &t->vstack[base]);
  t->vsp = base;
  pl_thread_start(t, thke);
  pl_run_status s;
  while ((s = pl_thread_run(t, 100000)) == PL_RUN_YIELDED)
    ;
  ASSERT_EQ(s, PL_RUN_DONE);
  return t->result;
}

TEST(exec, force_delivers_whnf_result) {
  test_rt rt = test_rt_new();
  pl_thread* t = rt.t;
  size_t base = t->vsp;
  static pl_op_t ops[4] = {OP_PUSH_VAR, 1, OP_FORCE, OP_RET};
  static pl_code code = {ops, 4, 0, 0, 0};
  pl_val pin = test_code_pin(&rt, 1, &code);
  (void)pin;
  pl_vpush(t, test_thunk(t, 42)); /* lazy arg, forced by OP_FORCE */
  pl_val r = test_run_call1(t, t->vstack[base], t->vstack[base + 1]);
  ASSERT_EQ(r, 42);
  /* already-WHNF operand passes through unchanged */
  r = test_run_call1(t, t->vstack[base], 7);
  ASSERT_EQ(r, 7);
  pl_pin_set_code(pl_as(PL_TAG_PIN, t->vstack[base]), NULL);
  test_rt_free(&rt);
}

TEST(exec, push_slot_duplicates_operand) {
  test_rt rt = test_rt_new();
  pl_thread* t = rt.t;
  size_t base = t->vsp;
  static pl_op_t ops[8] = {OP_PUSH_VAR, 1,         OP_FORCE, OP_PUSH_SLOT,
                           0,           OP_MK_APP, 1,        OP_RET};
  static pl_code code = {ops, 8, 0, 0, 0};
  test_code_pin(&rt, 1, &code);
  pl_val r = test_run_call1(t, t->vstack[base], 42);
  pl_cell* p = pl_as(PL_TAG_APP, r);
  ASSERT_NOT_NULL(p);
  ASSERT_EQ(pl_app_head(p), 42);
  ASSERT_EQ(pl_app_n(p), 1);
  ASSERT_EQ(pl_app_args(p)[0], 42);
  pl_pin_set_code(pl_as(PL_TAG_PIN, t->vstack[base]), NULL);
  test_rt_free(&rt);
}

TEST(exec, br_selects_arm_and_bounds) {
  test_rt rt = test_rt_new();
  pl_thread* t = rt.t;
  size_t base = t->vsp;
  static pl_op_t ops[13] = {OP_PUSH_VAR, 1,  OP_FORCE,    OP_BR, 2,
                            7,           10, OP_PUSH_LIT, 10,    OP_RET,
                            OP_PUSH_LIT, 20, OP_RET};
  static pl_code code = {ops, 13, 0, 0, 0};
  test_code_pin(&rt, 1, &code);
  ASSERT_EQ(test_run_call1(t, t->vstack[base], 0), 10);
  ASSERT_EQ(test_run_call1(t, t->vstack[base], 1), 20);
  /* out-of-range scrutinee raises */
  size_t mark = t->vsp;
  pl_vpush(t, t->vstack[base]);
  pl_vpush(t, 2);
  pl_gc_reserve(t, PL_THKE_CELLS(2));
  pl_val thke = pl_mk_thke(t, PL_BAN_FAST, 2, &t->vstack[mark]);
  t->vsp = mark;
  pl_thread_start(t, thke);
  pl_run_status s;
  while ((s = pl_thread_run(t, 100000)) == PL_RUN_YIELDED)
    ;
  ASSERT_EQ(s, PL_RUN_EXN);
  pl_pin_set_code(pl_as(PL_TAG_PIN, t->vstack[base]), NULL);
  test_rt_free(&rt);
}

TEST(exec, jmp_loop_stays_preemptable) {
  test_rt rt = test_rt_new();
  pl_thread* t = rt.t;
  size_t base = t->vsp;
  static pl_op_t ops[3] = {OP_JMP, 0, OP_RET};
  static pl_code code = {ops, 3, 0, 0, 0};
  test_code_pin(&rt, 1, &code);
  size_t fcap0 = t->fcap;
  pl_vpush(t, t->vstack[base]);
  pl_vpush(t, 5);
  pl_gc_reserve(t, PL_THKE_CELLS(2));
  pl_val thke = pl_mk_thke(t, PL_BAN_FAST, 2, &t->vstack[base + 1]);
  t->vsp = base + 1;
  pl_thread_start(t, thke);
  for (int i = 0; i < 50; i++)
    ASSERT_EQ(pl_thread_run(t, 10000), PL_RUN_YIELDED);
  ASSERT_EQ(t->fcap, fcap0); /* the loop runs in constant frame space */
  pl_pin_set_code(pl_as(PL_TAG_PIN, t->vstack[base]), NULL);
  test_rt_free(&rt);
}

TEST(exec, update_chain_coalesces_and_survives_gc) {
  test_rt rt = test_rt_new();
  pl_thread* t = rt.t;
  size_t base = t->vsp;
  enum { DEPTH = 6000 };

  pl_vpush(t, 7);
  for (unsigned i = 0; i < DEPTH; i++) {
    pl_gc_reserve(t, PL_THKE_CELLS(1));
    t->vstack[base] = pl_mk_thke(t, PL_BAN_SLOW, 1, &t->vstack[base]);
  }

  pl_thread_start(t, t->vstack[base]);
  ASSERT_EQ(pl_thread_run(t, DEPTH / 2), PL_RUN_YIELDED);
  ASSERT_EQ(t->fsp, 1);
  ASSERT_EQ(t->fstack[0].kind, PL_F_UPD);
  ASSERT_EQ(t->fstack[0].argc, t->usp + 1);
  ASSERT(t->usp > 1000);
  ASSERT_EQ(t->fcap, 4096); /* the generic frame stack never grew */

  /* The compact target suffix is an independent GC root source. */
  pl_gc_collect_now(t);
  pl_run_status s;
  while ((s = pl_thread_run(t, 100000)) == PL_RUN_YIELDED)
    ;
  ASSERT_EQ(s, PL_RUN_DONE);
  ASSERT_EQ(pl_thread_result(t), 7);
  ASSERT_EQ(t->fsp, 0);
  ASSERT_EQ(t->usp, 0);
  ASSERT_EQ(pl_hdr_kind(pl_ptr(t->vstack[base])[0]), PL_K_IND);

  test_rt_free(&rt);
}

static void test_update_chain_reachability(bool shared) {
  test_rt rt = test_rt_new();
  pl_thread* t = rt.t;
  size_t base = t->vsp;
  enum { DEPTH = 6000 };
  pl_vpush(t, 7);
  pl_vpush(t, 0);
  for (unsigned i = 0; i < DEPTH; i++) {
    pl_gc_reserve(t, PL_THKE_CELLS(1));
    t->vstack[base] = pl_mk_thke(t, PL_BAN_SLOW, 1, &t->vstack[base]);
    if (shared && i == 5000)
      t->vstack[base + 1] = t->vstack[base];
  }
  pl_val chain = t->vstack[base];
  t->vstack[base] = 0; /* the caller does not retain the outer computation */
  pl_thread_start(t, chain);
  ASSERT_EQ(pl_thread_run(t, DEPTH / 2), PL_RUN_YIELDED);
  size_t before = t->usp;
  ASSERT(before > 1000);
  pl_gc_collect_now(t);
  if (shared) {
    ASSERT(t->usp > 1000); /* the shared middle and its inner targets survive */
    ASSERT(t->usp < before);
  } else {
    ASSERT_EQ(t->usp, 0); /* bookkeeping alone must not retain old work */
  }
  pl_run_status status;
  while ((status = pl_thread_run(t, 100000)) == PL_RUN_YIELDED)
    ;
  ASSERT_EQ(status, PL_RUN_DONE);
  ASSERT_EQ(pl_thread_result(t), 7);
  ASSERT_EQ(t->usp, 0);
  if (shared)
    ASSERT_EQ(pl_whnf(t, t->vstack[base + 1]), 7);
  test_rt_free(&rt);
}

TEST(exec, unreachable_update_targets_do_not_retain_tail_history) {
  test_update_chain_reachability(false);
}

TEST(exec, shared_update_targets_keep_call_by_need_results) {
  test_update_chain_reachability(true);
}

TEST(exec, runtime_error_restores_unwound_thke) {
  test_rt rt = test_rt_new();
  pl_thread* t = rt.t;
  size_t base = t->vsp;

  pl_vpush(t, 0);
  pl_gc_reserve(t, PL_THKE_CELLS(0));
  t->vstack[base] = pl_mk_thke(t, PL_BAN_SLOW, 0, &t->vstack[base]);

  for (unsigned attempt = 0; attempt < 2; attempt++) {
    pl_thread_start(t, t->vstack[base]);
    pl_run_status s;
    while ((s = pl_thread_run(t, 1000)) == PL_RUN_YIELDED)
      ;
    ASSERT_EQ(s, PL_RUN_EXN);
    ASSERT_STR_EQ(t->exn_msg, "bad empty bytecode thunk");
    pl_cell* p = pl_as(PL_TAG_DEFER, t->vstack[base]);
    ASSERT_NOT_NULL(p);
    ASSERT_EQ(pl_hdr_kind(p[0]), PL_K_THKE);
    ASSERT_EQ(pl_hdr_flags(p[0]) & PL_F_HOLE, 0);
  }

  test_rt_free(&rt);
}

TEST(exec, call_local_block_returns_forced) {
  test_rt rt = test_rt_new();
  pl_thread* t = rt.t;
  size_t base = t->vsp;
  /* main: [0, arg] -> call sub(arg) -> [0, arg'] -> row [arg']
   * sub (at 10): force its stack argument and return it */
  static pl_op_t ops[14] = {OP_PUSH_LIT,  0, OP_PUSH_VAR, 1,     OP_CALL,
                            10,           1, OP_MK_APP,   1,     OP_RET,
                            OP_PUSH_SLOT, 0, OP_FORCE,    OP_RET};
  static pl_code code = {ops, 14, 0, 0, 0};
  test_code_pin(&rt, 1, &code);
  pl_vpush(t, test_thunk(t, 42));
  pl_val r = test_run_call1(t, t->vstack[base], t->vstack[base + 1]);
  pl_cell* p = pl_as(PL_TAG_APP, r);
  ASSERT_NOT_NULL(p);
  ASSERT_EQ(pl_app_head(p), 0);
  ASSERT_EQ(pl_app_n(p), 1);
  ASSERT_EQ(pl_app_args(p)[0], 42);
  pl_pin_set_code(pl_as(PL_TAG_PIN, t->vstack[base]), NULL);
  test_rt_free(&rt);
}

TEST(exec, noupd_thke_reevaluates) {
  test_rt rt = test_rt_new();
  pl_thread* t = rt.t;
  size_t base = t->vsp;
  /* the code allocates a fresh row [x] on every execution */
  static pl_op_t ops[7] = {OP_PUSH_LIT, 0, OP_PUSH_VAR, 1,
                           OP_MK_APP,   1, OP_RET};
  static pl_code code = {ops, 7, 0, 0, 0};
  test_code_pin(&rt, 1, &code);
  pl_vpush(t, t->vstack[base]);
  pl_vpush(t, 7);
  pl_gc_reserve(t, 2 * PL_THKE_CELLS(2));
  PL_GC_FORBID(t);
  pl_val no_upd =
      pl_mk_thke(t, PL_BAN_FAST | PL_BAN_NOUPD, 2, &t->vstack[base + 1]);
  pl_val upd = pl_mk_thke(t, PL_BAN_FAST, 2, &t->vstack[base + 1]);
  PL_GC_ALLOW(t);
  t->vsp = base + 1;
  pl_vpush(t, no_upd);
  pl_vpush(t, upd);
  for (int round = 0; round < 2; round++) {
    /* a NOUPD thke survives forcing un-updated, and re-evaluates */
    pl_thread_start(t, t->vstack[base + 1]);
    pl_run_status s;
    while ((s = pl_thread_run(t, 100000)) == PL_RUN_YIELDED)
      ;
    ASSERT_EQ(s, PL_RUN_DONE);
    pl_cell* rp = pl_as(PL_TAG_APP, t->result);
    ASSERT_NOT_NULL(rp);
    ASSERT_EQ(pl_app_args(rp)[0], 7);
    ASSERT_EQ(pl_hdr_kind(*pl_ptr(t->vstack[base + 1])), PL_K_THKE);
  }
  /* the updateable control is overwritten by its first force */
  pl_thread_start(t, t->vstack[base + 2]);
  pl_run_status s;
  while ((s = pl_thread_run(t, 100000)) == PL_RUN_YIELDED)
    ;
  ASSERT_EQ(s, PL_RUN_DONE);
  ASSERT_NEQ(pl_hdr_kind(*pl_ptr(t->vstack[base + 2])), PL_K_THKE);
  pl_pin_set_code(pl_as(PL_TAG_PIN, t->vstack[base]), NULL);
  test_rt_free(&rt);
}

TEST(exec, ingest_validates_targets_and_guards_fusion) {
  test_rt rt = test_rt_new();
  pl_thread* t = rt.t;
  size_t base = t->vsp;
  /* BR arm 1 targets the RET behind a MK_THK: decode must NOT fuse.
   * Keep a copy of the scrutinee so both arms have a value to return. */
  pl_val guarded[13] = {OP_PUSH_VAR, 1, OP_FORCE, OP_PUSH_SLOT, 0, OP_BR,
                        2,           9, 12,       OP_MK_THK,    1, PL_BAN_SLOW,
                        OP_RET};
  pl_vpush(t, test_app(t, 0, 13, guarded));
  pl_code* c = pl_bytecode_from_val(t->vstack[base]);
  ASSERT_NOT_NULL(c);
  ASSERT_EQ(c->ops[9], OP_MK_THK);
  pl_bytecode_free(c);
  /* same program, arm 1 rejoining arm 0 instead: the MK_THK fuses */
  pl_val fused[13] = {OP_PUSH_VAR, 1, OP_FORCE, OP_PUSH_SLOT, 0, OP_BR,
                      2,           9, 9,        OP_MK_THK,    1, PL_BAN_SLOW,
                      OP_RET};
  pl_vpush(t, test_app(t, 0, 13, fused));
  c = pl_bytecode_from_val(t->vstack[base + 1]);
  ASSERT_NOT_NULL(c);
  ASSERT_EQ(c->ops[9], OP_TAILCALL);
  pl_bytecode_free(c);
  /* a target into an operand slot fails the decode */
  pl_val bad[6] = {OP_JMP, 4, OP_RET, OP_PUSH_LIT, 9, OP_RET};
  pl_vpush(t, test_app(t, 0, 6, bad));
  ASSERT_EQ(pl_bytecode_from_val(t->vstack[base + 2]), NULL);
  /* a target out of range fails the decode */
  pl_val oob[3] = {OP_JMP, 99, OP_RET};
  pl_vpush(t, test_app(t, 0, 3, oob));
  ASSERT_EQ(pl_bytecode_from_val(t->vstack[base + 3]), NULL);
  test_rt_free(&rt);
}

/* Apply the pinned code at vstack[base] to arg through a FAST thunk carrying
 * the given strictness hint; the result is left in t->result. */
static pl_run_status test_run_hinted(pl_thread* t, size_t base, pl_val arg,
                                     pl_op_t hint) {
  size_t mark = t->vsp;
  pl_vpush(t, t->vstack[base]);
  pl_vpush(t, arg);
  pl_gc_reserve(t, PL_THKE_CELLS(2));
  pl_val thke =
      pl_mk_thke(t, (pl_bane)(PL_BAN_FAST | (hint << 8)), 2, &t->vstack[mark]);
  t->vsp = mark;
  pl_thread_start(t, thke);
  pl_run_status s;
  while ((s = pl_thread_run(t, 100000)) == PL_RUN_YIELDED)
    ;
  return s;
}

/* A law compiled with a checked prologue has two entries.  judge takes the
 * fast one exactly when every strict argument already is a value, whatever
 * the caller's hint says: a hint never bypasses the check, and a value never
 * pays the prologue.  The fast block here deliberately differs from the
 * prologue so the entry taken shows in the result. */
TEST(exec, strict_entry_taken_when_arguments_are_values) {
  test_rt rt = test_rt_new();
  pl_thread* t = rt.t;
  size_t base = t->vsp;
  /* prologue: slot 0 = the forced argument; fast entry: slot 0 = 100 */
  pl_val row[] = {OP_PUSH_VAR, 1,           OP_FORCE, OP_JMP,       9, OP_ENTRY,
                  1,           OP_PUSH_LIT, 100,      OP_PUSH_SLOT, 0, OP_RET};
  pl_code* c = pl_bytecode_from_val(test_app(t, 0, 12, row));
  ASSERT_NOT_NULL(c);
  ASSERT_EQ(c->strict_mask, 1);
  ASSERT_EQ(c->strict_entry, 7);
  test_code_pin(&rt, 1, c); /* base */
  for (pl_op_t hint = 0; hint < 3; hint++) {
    /* a value takes the fast entry, hinted, unhinted or mis-hinted */
    ASSERT_EQ(test_run_hinted(t, base, 7, hint), PL_RUN_DONE);
    ASSERT_EQ(t->result, 100);
    /* an evaluated thunk is an indirection to a value: fast entry too */
    pl_vpush(t, test_thunk(t, 7));
    ASSERT_EQ(pl_whnf(t, t->vstack[base + 1]), 7);
    ASSERT_EQ(test_run_hinted(t, base, t->vstack[base + 1], hint), PL_RUN_DONE);
    ASSERT_EQ(t->result, 100);
    t->vsp = base + 1;
    /* an unevaluated thunk takes the checked entry, which forces it */
    pl_vpush(t, test_thunk(t, 7));
    ASSERT_EQ(test_run_hinted(t, base, t->vstack[base + 1], hint), PL_RUN_DONE);
    ASSERT_EQ(t->result, 7);
    t->vsp = base + 1;
    /* ...so a raising thunk raises even under a matching hint */
    pl_vpush(t, test_throwing(t, 77));
    ASSERT_EQ(test_run_hinted(t, base, t->vstack[base + 1], hint), PL_RUN_EXN);
    t->vsp = base + 1;
  }
  pl_pin_set_code(pl_as(PL_TAG_PIN, t->vstack[base]), NULL);
  pl_bytecode_free(c);
  test_rt_free(&rt);
}

/* ── Direct call opcodes: CALL_KNOWN / CALL_FAST / CALL_SLOW ─────────── */

TEST(exec, call_known_runs_resolved_primop_direct) {
  test_rt rt = test_rt_new();
  pl_thread* t = rt.t;
  size_t base = t->vsp;
  /* decode resolves (opset 66, "Add", 2); law computes arg + 1 */
  pl_vpush(t, pl_pin(t, 66));
  {
    pl_val row[10] = {OP_PUSH_VAR,
                      1,
                      OP_FORCE,
                      OP_PUSH_LIT,
                      1,
                      OP_CALL_KNOWN,
                      2,
                      t->vstack[base],
                      UINT64_C(0x646441) /* "Add" */,
                      OP_RET};
    pl_vpush(t, test_app(t, 0, 10, row));
  }
  pl_code* c = pl_bytecode_from_val(t->vstack[base + 1]);
  ASSERT_NOT_NULL(c);
  t->vsp = base;
  pl_val pin = test_code_pin(&rt, 1, c);
  ASSERT_EQ(test_run_call1(t, pin, 41), 42);
  /* Ready operands can still allocate in the primitive body (and collect
   * under GC stress); their value-stack slots must remain roots. */
  ASSERT_EQ(pl_nat_u64_clamp(test_run_call1(t, t->vstack[base], PL_NAT63_MAX)),
            UINT64_C(1) << 63);
  /* a lazy arg is forced by the op's own strict-arg driver */
  pl_vpush(t, test_thunk(t, 6));
  ASSERT_EQ(test_run_call1(t, t->vstack[base], t->vstack[base + 1]), 7);
  pl_pin_set_code(pl_as(PL_TAG_PIN, t->vstack[base]), NULL);
  pl_bytecode_free(c);
  test_rt_free(&rt);
}

TEST(exec, call_known_ice_deep_normalizes_before_persisting) {
  test_rt rt = test_rt_new();
  pl_thread* t = rt.t;
  size_t base = t->vsp;
  pl_vpush(t, pl_pin(t, 66));
  pl_val row[7] = {
      OP_PUSH_VAR,          1,     OP_CALL_KNOWN, 1, t->vstack[base],
      ax_s3('I', 'c', 'e'), OP_RET};
  pl_vpush(t, test_app(t, 0, 7, row));
  pl_code* code = pl_bytecode_from_val(t->vstack[base + 1]);
  ASSERT_NOT_NULL(code);
  t->vsp = base;
  test_code_pin(&rt, 1, code);
  pl_vpush(t, test_app1_thunk_to(t, 42));
  t->vstack[base + 1] = pl_pin(t, t->vstack[base + 1]);
  ASSERT_EQ(test_run_call1(t, t->vstack[base], t->vstack[base + 1]), 0);
  ASSERT_NOT_NULL(pl_pin_hash(t->vstack[base + 1]));
  pl_val body = pl_pin_body(pl_ptr(t->vstack[base + 1]));
  ASSERT_EQ(pl_app_args(pl_ptr(body))[0], 42);
  pl_pin_set_code(pl_ptr(t->vstack[base]), NULL);
  pl_bytecode_free(code);
  test_rt_free(&rt);
}

/* CALL_KNOWN must retain the same argument safepoints when no forcing is
 * needed, and materialize a rooted continuation when a later argument is
 * deferred. Collect at every yield to exercise that continuation's roots. */
TEST(exec, call_known_argument_checkpoints_survive_gc) {
  for (unsigned fuel = 2; fuel <= 64; fuel *= 32) {
    for (unsigned lazy = 0; lazy < 3; lazy++) {
      test_rt rt = test_rt_new();
      pl_thread* t = rt.t;
      size_t base = t->vsp;
      pl_vpush(t, pl_pin(t, 66));
      pl_val row[9] = {OP_PUSH_VAR,   1, OP_PUSH_VAR,     2,
                       OP_CALL_KNOWN, 2, t->vstack[base], ax_s3('A', 'd', 'd'),
                       OP_RET};
      pl_vpush(t, test_app(t, 0, 9, row));
      pl_code* code = pl_bytecode_from_val(t->vstack[base + 1]);
      ASSERT_NOT_NULL(code);
      t->vsp = base;
      test_code_pin(&rt, 2, code);
      pl_vpush(t, lazy == 1 ? test_thunk(t, 40) : 40);
      pl_vpush(t, lazy == 2 ? test_thunk(t, 2) : 2);
      pl_gc_reserve(t, PL_THKE_CELLS(3));
      pl_val call = pl_mk_thke(t, PL_BAN_FAST, 3, &t->vstack[base]);
      t->vsp = base + 1; /* retain the pin for clearing its borrowed code */
      size_t vsp0 = t->vsp, fsp0 = t->fsp;
      pl_thread_start(t, call);
      unsigned yields = 0;
      pl_run_status status;
      while ((status = pl_thread_run(t, fuel)) == PL_RUN_YIELDED) {
        ASSERT_LT(++yields, 32);
        pl_gc_collect_now(t);
      }
      ASSERT_EQ(status, PL_RUN_DONE);
      ASSERT_EQ(pl_thread_result(t), 42);
      if (fuel == 64)
        ASSERT_EQ(yields, 0);
      else if (lazy == 0)
        ASSERT_EQ(yields, 4); /* entry, two args, op result, bytecode return */
      ASSERT_EQ(t->vsp, vsp0);
      ASSERT_EQ(t->fsp, fsp0);
      pl_pin_set_code(pl_as(PL_TAG_PIN, t->vstack[base]), NULL);
      pl_bytecode_free(code);
      test_rt_free(&rt);
    }
  }
}

/* Try reads the name slot a direct CALL_KNOWN inserts (its exception arm
 * restores vsp to ab - 1 and delivers (1 exn) there): both arms must land
 * at the call's own stack slot with the stacks balanced. */
TEST(exec, call_known_try_delivers_both_arms_in_place) {
  test_rt rt = test_rt_new();
  pl_thread* t = rt.t;
  size_t base = t->vsp;
  pl_vpush(t, pl_pin(t, 66));
  pl_val row[9] = {OP_PUSH_VAR,   1, OP_PUSH_VAR,     2,
                   OP_CALL_KNOWN, 2, t->vstack[base], ax_s3('T', 'r', 'y'),
                   OP_RET};
  pl_vpush(t, test_app(t, 0, 9, row));
  pl_code* code = pl_bytecode_from_val(t->vstack[base + 1]);
  ASSERT_NOT_NULL(code);
  t->vsp = base;
  test_code_pin(&rt, 2, code);
  for (unsigned arm = 0; arm < 2; arm++) {
    size_t vsp0 = t->vsp, fsp0 = t->fsp;
    pl_vpush(t, test_law(t, 1, 0, 1)); /* identity: forces its argument */
    pl_vpush(t, arm ? test_throwing(t, 7) : 42);
    pl_gc_reserve(t, PL_THKE_CELLS(3));
    pl_val call = pl_mk_thke(t, PL_BAN_FAST, 3, &t->vstack[base]);
    t->vsp = base + 1;
    pl_thread_start(t, call);
    pl_run_status status;
    unsigned yields = 0;
    while ((status = pl_thread_run(t, 3)) == PL_RUN_YIELDED) {
      ASSERT_LT(++yields, 64);
      pl_gc_collect_now(t);
    }
    ASSERT_EQ(status, PL_RUN_DONE);
    pl_cell* p = pl_as(PL_TAG_APP, pl_thread_result(t));
    ASSERT_NOT_NULL(p);
    ASSERT_EQ(pl_app_head(p), arm ? 1 : 0);
    ASSERT_EQ(pl_app_args(p)[0], arm ? 7 : 42);
    ASSERT_EQ(t->vsp, vsp0);
    ASSERT_EQ(t->fsp, fsp0);
  }
  pl_pin_set_code(pl_as(PL_TAG_PIN, t->vstack[base]), NULL);
  pl_bytecode_free(code);
  test_rt_free(&rt);
}

/* Decode raw instruction vectors through the same validation as installed
 * compiler output. The caller roots any embedded values while constructing. */
static pl_code* test_decode_ops(pl_thread* t, size_t n, const pl_val* ops) {
  pl_val row = test_app(t, 0, (uint32_t)n, ops);
  return pl_bytecode_from_val(row);
}

TEST(exec, decode_rejects_head_only_apps) {
  test_rt rt = test_rt_new();
  /* There is a head on the operand stack: this is invalid arity, not
   * stack underflow. Counts must also fit the header before narrowing. */
  const pl_val counts[] = {0, UINT32_MAX - 1ULL, UINT32_MAX,
                           (UINT64_C(1) << 32) + 1, PL_NAT63_MAX};
  for (size_t i = 0; i < sizeof(counts) / sizeof(counts[0]); i++) {
    pl_val ops[] = {OP_PUSH_LIT, 7, OP_MK_APP, counts[i], OP_RET};
    pl_code* code = test_decode_ops(rt.t, 5, ops);
    bool rejected = code == NULL;
    pl_bytecode_free(code);
    ASSERT(rejected, "invalid MK_APP count %llu",
           (unsigned long long)counts[i]);
  }
  test_rt_free(&rt);
}

TEST(exec, decode_rejects_operand_stack_underflow) {
  test_rt rt = test_rt_new();
  struct {
    size_t n;
    pl_val ops[12];
  } cases[] = {
      {3, {OP_MK_APP, 1, OP_RET}},
      {5, {OP_PUSH_LIT, 0, OP_MK_APP, 1, OP_RET}},
      {5, {OP_MK_THK, 1, PL_BAN_SLOW, OP_FORCE, OP_RET}},
      {4, {OP_MK_THK, 1, PL_BAN_SLOW, OP_RET}},
      {2, {OP_FORCE, OP_RET}},
      {4, {OP_CALL_FAST, 1, 0, OP_RET}},
      {3, {OP_CALL_SLOW, 1, OP_RET}},
      {5, {OP_CALL_KNOWN, 1, 0, ax_s3('I', 'n', 'c'), OP_RET}},
      {5, {OP_CALL, 4, 1, OP_RET, OP_RET}},
      {5, {OP_CALL, 4, 0, OP_RET, OP_RET}},
      {4, {OP_BR, 1, 3, OP_RET}},
      {1, {OP_RET}},
      /* A nonempty caller can still enter an underflowing local block. */
      {9, {OP_PUSH_LIT, 0, OP_CALL, 6, 1, OP_RET, OP_MK_APP, 1, OP_RET}},
      /* Visit the bad branch even though the other arm has a valid result. */
      {12,
       {OP_PUSH_LIT, 0, OP_BR, 2, 6, 9, OP_PUSH_LIT, 7, OP_RET, OP_MK_APP, 1,
        OP_RET}},
      /* Counts must be checked before narrowing them to the modeled depth. */
      {3, {OP_MK_APP, PL_NAT63_MAX, OP_RET}},
      {5, {OP_MK_THK, PL_NAT63_MAX, PL_BAN_SLOW, OP_FORCE, OP_RET}},
      {4, {OP_CALL_FAST, PL_NAT63_MAX, 0, OP_RET}},
      {3, {OP_CALL_SLOW, PL_NAT63_MAX, OP_RET}},
      {5, {OP_CALL, 4, PL_NAT63_MAX, OP_RET, OP_RET}},
  };
  for (size_t i = 0; i < sizeof(cases) / sizeof(cases[0]); i++) {
    /* Construct heap operands just before test_decode_ops roots them. */
    if (cases[i].ops[0] == OP_CALL_KNOWN)
      cases[i].ops[2] = test_p66(rt.t);
    pl_code* c = test_decode_ops(rt.t, cases[i].n, cases[i].ops);
    bool rejected = c == NULL;
    pl_bytecode_free(c);
    ASSERT(rejected, "underflow case %zu", i);
  }
  test_rt_free(&rt);
}

TEST(exec, eager_skips_unreachable_operand_stack_underflow) {
  test_rt rt = test_rt_new();
  pl_val ops[] = {OP_JMP,      5, OP_MK_APP, 1,     OP_RET,
                  OP_PUSH_LIT, 7, OP_FORCE,  OP_RET};
  pl_code* c = test_decode_ops(rt.t, 9, ops);
  ASSERT_NOT_NULL(c);
  ASSERT_EQ(c->ops[2], OP_MK_APP);
  ASSERT_EQ(c->ops[7], OP_FORCE_READY);
  ASSERT_EQ(c->ops[8], OP_RET_READY);
  pl_bytecode_free(c);
  test_rt_free(&rt);
}

/* The P5 shape of (Add 1 (Add (f (Sub n 1)) (f (Sub n 2)))): every
 * subexpression is a thunk in its own operand slot, copied into its
 * consumer's argument group, and the compiler builds Add's second argument
 * before its first.  Ingest enters the Add thunk and the first-forced call
 * eagerly; the second call must stay a thunk (it would otherwise run before
 * the first), and the Sub thunks feed a law whose strictness is unknown. */
TEST(exec, eager_enters_thunks_forced_by_strict_consumers) {
  test_rt rt = test_rt_new();
  pl_thread* t = rt.t;
  size_t base = t->vsp;
  pl_vpush(t, pl_pin(t, 66)); /* re-read per row: decodes may collect */
  const pl_val sub = ax_s3('S', 'u', 'b'), add = ax_s3('A', 'd', 'd');
  pl_val row[] = {
      OP_PUSH_VAR,     1,   OP_FORCE, /* 0 */
      OP_PUSH_SLOT,    0,   OP_PUSH_LIT,  2, OP_MK_THK, 2, PL_BAN_PRIM_KNOWN,
      t->vstack[base], sub,                                             /* 3 */
      OP_PUSH_VAR,     2,   OP_PUSH_SLOT, 1, OP_MK_THK, 2, PL_BAN_FAST, /* 12 */
      OP_PUSH_SLOT,    0,   OP_PUSH_LIT,  1, OP_MK_THK, 2, PL_BAN_PRIM_KNOWN,
      t->vstack[base], sub,                                             /* 19 */
      OP_PUSH_VAR,     2,   OP_PUSH_SLOT, 3, OP_MK_THK, 2, PL_BAN_FAST, /* 28 */
      OP_PUSH_SLOT,    4,   OP_PUSH_SLOT, 2, OP_MK_THK, 2, PL_BAN_PRIM_KNOWN,
      t->vstack[base], add, /* 35 */
      OP_PUSH_LIT,     1,   OP_PUSH_SLOT, 5, OP_MK_THK, 2, PL_BAN_PRIM_KNOWN,
      t->vstack[base], add, /* 44 */
      OP_RET};              /* 53 */
  pl_code* c = test_decode_ops(t, sizeof row / sizeof row[0], row);
  ASSERT_NOT_NULL(c);
  ASSERT_EQ(c->ops[48], OP_TAIL_ADD);  /* fused tail, forces slot 5 */
  ASSERT_EQ(c->ops[39], OP_ADD);       /* slot 5's thunk: entered eagerly */
  ASSERT_EQ(c->ops[43], OP_NOP);       /* the shorter call leaves filler */
  ASSERT_EQ(c->ops[32], OP_CALL_FAST); /* Add's first argument: eager */
  ASSERT_EQ(c->ops[33], 1);
  ASSERT_EQ(c->ops[34], 0);
  ASSERT_EQ(c->ops[16], OP_MK_THK); /* second argument, built first: lazy */
  ASSERT_EQ(c->ops[7], OP_MK_THK);  /* law arguments: strictness unknown */
  ASSERT_EQ(c->ops[23], OP_MK_THK);
  t->vsp = base;
  test_code_pin(&rt, 2, c);
  for (unsigned lazy = 0; lazy < 2; lazy++) {
    size_t vsp0 = t->vsp, fsp0 = t->fsp;
    pl_vpush(t, lazy ? test_thunk(t, 10) : 10);
    pl_vpush(t, test_law(t, 1, 0, 1)); /* f = identity */
    pl_gc_reserve(t, PL_THKE_CELLS(3));
    pl_val call = pl_mk_thke(t, PL_BAN_FAST, 3, &t->vstack[base]);
    t->vsp = base + 1;
    pl_thread_start(t, call);
    pl_run_status status;
    unsigned yields = 0;
    while ((status = pl_thread_run(t, 3)) == PL_RUN_YIELDED) {
      ASSERT_LT(++yields, 128);
      pl_gc_collect_now(t);
    }
    ASSERT_EQ(status, PL_RUN_DONE);
    ASSERT_EQ(pl_thread_result(t), 18); /* 1 + (10 - 1) + (10 - 2) */
    ASSERT_EQ(t->vsp, vsp0);
    ASSERT_EQ(t->fsp, fsp0);
  }
  pl_pin_set_code(pl_as(PL_TAG_PIN, t->vstack[base]), NULL);
  pl_bytecode_free(c);
  test_rt_free(&rt);
}

/* An evaluation between a thunk's construction and its force pins the
 * thunk: entering it early would reorder it with that evaluation. */
TEST(exec, eager_stops_at_intervening_evaluation) {
  test_rt rt = test_rt_new();
  pl_thread* t = rt.t;
  size_t base = t->vsp;
  pl_vpush(t, pl_pin(t, 66));
  const pl_val inc = ax_s3('I', 'n', 'c');
  pl_val barrier[] = {
      OP_PUSH_VAR,     1,   OP_MK_THK,   1,     PL_BAN_PRIM_KNOWN,
      t->vstack[base], inc, OP_PUSH_VAR, 2,     OP_FORCE,
      OP_PUSH_SLOT,    0,   OP_FORCE,    OP_RET};
  pl_code* c = test_decode_ops(t, 14, barrier);
  ASSERT_NOT_NULL(c);
  ASSERT_EQ(c->ops[2], OP_MK_THK);
  pl_bytecode_free(c);
  pl_val direct[] = {OP_PUSH_VAR,     1,   OP_MK_THK,    1, PL_BAN_PRIM_KNOWN,
                     t->vstack[base], inc, OP_PUSH_SLOT, 0, OP_FORCE,
                     OP_RET};
  c = test_decode_ops(t, 11, direct);
  ASSERT_NOT_NULL(c);
  ASSERT_EQ(c->ops[2], OP_CALL_KNOWN);
  ASSERT_EQ(c->ops[6], OP_NOP);
  t->vsp = base;
  pl_val pin = test_code_pin(&rt, 1, c);
  ASSERT_EQ(test_run_call1(t, pin, 41), 42);
  pl_vpush(t, test_thunk(t, 41));
  ASSERT_EQ(test_run_call1(t, t->vstack[base], t->vstack[base + 1]), 42);
  pl_pin_set_code(pl_as(PL_TAG_PIN, t->vstack[base]), NULL);
  pl_bytecode_free(c);
  test_rt_free(&rt);
}

/* A MK_THK of a total nat primop computes when its operands are already
 * direct nats (looking through indirections) and allocates a thunk
 * otherwise: unevaluated operands, and results that leave nat63. */
TEST(exec, mk_thk_computes_total_primops_on_direct_nats) {
  test_rt rt = test_rt_new();
  pl_thread* t = rt.t;
  size_t base = t->vsp;
  pl_vpush(t, pl_pin(t, 66)); /* base: re-read per row, decodes collect */
  for (unsigned op = 0; op < 2; op++) {
    pl_val row[] = {OP_PUSH_LIT,
                    0,
                    OP_PUSH_VAR,
                    1,
                    OP_PUSH_LIT,
                    1,
                    OP_MK_THK,
                    2,
                    PL_BAN_PRIM_KNOWN,
                    t->vstack[base],
                    op ? ax_s3('A', 'd', 'd') : ax_s3('S', 'u', 'b'),
                    OP_MK_APP,
                    1,
                    OP_RET};
    pl_code* c = test_decode_ops(t, 14, row);
    ASSERT_NOT_NULL(c);
    ASSERT_EQ(c->ops[6], OP_MK_THK); /* MK_APP is not a strict consumer */
    size_t cp = t->vsp;              /* the code pin's own rooted slot */
    pl_vpush(t, test_code_pin(&rt, 1, c));
    size_t top = t->vsp;
    /* direct nat operand: the slot holds the value, no thunk exists */
    pl_cell* app = pl_as(PL_TAG_APP, test_run_call1(t, t->vstack[cp], 5));
    ASSERT_NOT_NULL(app);
    ASSERT_EQ(pl_app_args(app)[0], op ? 6 : 4);
    /* an indirection to a nat is looked through */
    pl_vpush(t, test_thunk(t, 5));
    ASSERT_EQ(pl_whnf(t, t->vstack[top]), 5);
    app = pl_as(PL_TAG_APP, test_run_call1(t, t->vstack[cp], t->vstack[top]));
    ASSERT_NOT_NULL(app);
    ASSERT_EQ(pl_app_args(app)[0], op ? 6 : 4);
    t->vsp = top;
    /* an unevaluated operand keeps the thunk, which still computes */
    pl_vpush(t, test_thunk(t, 5));
    app = pl_as(PL_TAG_APP, test_run_call1(t, t->vstack[cp], t->vstack[top]));
    ASSERT_NOT_NULL(app);
    pl_vpush(t, pl_app_args(app)[0]);
    ASSERT_EQ(pl_tag(t->vstack[top + 1]), PL_TAG_DEFER);
    ASSERT_EQ(pl_whnf(t, t->vstack[top + 1]), op ? 6 : 4);
    t->vsp = top;
    if (op) {
      /* a result outside nat63 keeps the thunk too */
      app = pl_as(PL_TAG_APP, test_run_call1(t, t->vstack[cp], PL_NAT63_MAX));
      ASSERT_NOT_NULL(app);
      pl_vpush(t, pl_app_args(app)[0]);
      ASSERT_EQ(pl_tag(t->vstack[top]), PL_TAG_DEFER);
      ASSERT_EQ(pl_nat_u64_clamp(pl_whnf(t, t->vstack[top])), UINT64_C(1)
                                                                  << 63);
      t->vsp = top;
    }
    pl_pin_set_code(pl_as(PL_TAG_PIN, t->vstack[cp]), NULL);
    pl_bytecode_free(c);
    t->vsp = base + 1;
  }
  test_rt_free(&rt);
}

/* g(n) = if n == 0 then 42 else g(Dec n), with a checked prologue on n.
 * The recursive call is a saturated self-call, so under the law's own mask
 * it forces its argument first thing: the Dec thunk feeding it is entered
 * eagerly, in both the tail and the non-tail form.  A lazy self-call thunk
 * is not a consumer and keeps its argument thunk. */
TEST(exec, eager_self_call_arguments_under_own_strict_mask) {
  test_rt rt = test_rt_new();
  pl_thread* t = rt.t;
  size_t base = t->vsp;
  pl_vpush(t, pl_pin(t, 66)); /* base: re-read per row, decodes collect */
  const pl_val nil = ax_s3('N', 'i', 'l'), dec = ax_s3('D', 'e', 'c');
  for (unsigned tail = 0; tail < 2; tail++) {
    pl_val row[] = {OP_PUSH_VAR,
                    1,
                    OP_FORCE,
                    OP_JMP,
                    9,
                    OP_ENTRY,
                    1,
                    OP_PUSH_VAR,
                    1, /* 0 */
                    OP_PUSH_SLOT,
                    0,
                    OP_CALL_KNOWN,
                    1,
                    t->vstack[base],
                    nil, /* 9 */
                    OP_PUSH_SLOT,
                    1,
                    OP_BR,
                    2,
                    21,
                    34, /* 15 */
                    OP_PUSH_VAR,
                    0,
                    OP_PUSH_SLOT,
                    0, /* 21 */
                    OP_MK_THK,
                    1,
                    PL_BAN_PRIM_KNOWN,
                    t->vstack[base],
                    dec, /* 25 */
                    tail ? OP_MK_THK : OP_CALL_FAST,
                    tail ? 2 : 1,
                    tail ? PL_BAN_FAST : 0, /* 30 */
                    OP_RET,                 /* 33 */
                    OP_PUSH_LIT,
                    42,
                    OP_RET}; /* 34 */
    pl_code* c = test_decode_ops(t, sizeof row / sizeof row[0], row);
    ASSERT_NOT_NULL(c);
    ASSERT_EQ(c->ops[11], OP_CALL_READY); /* n is a value on both entries */
    ASSERT_EQ(c->ops[25], OP_CALL_READY); /* Dec n: eager, and n is a value */
    ASSERT_EQ(c->ops[29], OP_NOP);
    ASSERT_EQ(c->ops[30], tail ? OP_TAILCALL : OP_CALL_FAST);
    size_t cp = t->vsp;
    pl_vpush(t, test_code_pin(&rt, 1, c));
    for (unsigned lazy = 0; lazy < 2; lazy++) {
      size_t vsp0 = t->vsp, fsp0 = t->fsp;
      pl_vpush(t, t->vstack[cp]);
      pl_vpush(t, lazy ? test_thunk(t, 5) : 5);
      pl_gc_reserve(t, PL_THKE_CELLS(2));
      pl_val call = pl_mk_thke(t, PL_BAN_FAST, 2, &t->vstack[vsp0]);
      t->vsp = vsp0;
      pl_thread_start(t, call);
      pl_run_status status;
      unsigned yields = 0;
      while ((status = pl_thread_run(t, 3)) == PL_RUN_YIELDED) {
        ASSERT_LT(++yields, 256);
        pl_gc_collect_now(t);
      }
      ASSERT_EQ(status, PL_RUN_DONE);
      ASSERT_EQ(pl_thread_result(t), 42);
      ASSERT_EQ(t->vsp, vsp0);
      ASSERT_EQ(t->fsp, fsp0);
    }
    pl_pin_set_code(pl_as(PL_TAG_PIN, t->vstack[cp]), NULL);
    pl_bytecode_free(c);
    t->vsp = base + 1;
  }
  /* a lazy self-call thunk (consumed by MK_APP) keeps its argument thunk */
  pl_val lazy_row[] = {OP_PUSH_VAR,
                       1,
                       OP_FORCE,
                       OP_JMP,
                       9,
                       OP_ENTRY,
                       1,
                       OP_PUSH_VAR,
                       1, /* 0 */
                       OP_PUSH_LIT,
                       0,
                       OP_PUSH_VAR,
                       0,
                       OP_PUSH_SLOT,
                       0, /* 9 */
                       OP_MK_THK,
                       1,
                       PL_BAN_PRIM_KNOWN,
                       t->vstack[base],
                       dec, /* 15 */
                       OP_MK_THK,
                       2,
                       PL_BAN_FAST,
                       OP_MK_APP,
                       1,
                       OP_RET}; /* 20 */
  pl_code* c =
      test_decode_ops(t, sizeof lazy_row / sizeof lazy_row[0], lazy_row);
  ASSERT_NOT_NULL(c);
  ASSERT_EQ(c->ops[15], OP_MK_THK);
  ASSERT_EQ(c->ops[20], OP_MK_THK);
  pl_bytecode_free(c);
  test_rt_free(&rt);
}

/* A saturated call to another law whose installed code has a checked
 * prologue enters that prologue, which forces the callee's strict arguments
 * first: with the callee's pin as the call's literal head, ingest reads the
 * installed mask and enters the argument thunks eagerly.  Without installed
 * code, or when the arity does not match, the thunks stay. */
TEST(exec, eager_callee_arguments_under_installed_strict_mask) {
  test_rt rt = test_rt_new();
  pl_thread* t = rt.t;
  size_t base = t->vsp;
  pl_vpush(t, pl_pin(t, 66)); /* base: re-read per row, decodes collect */
  const pl_val inc = ax_s3('I', 'n', 'c'), add = ax_s3('A', 'd', 'd');
  /* callee h(x) = Inc x, strict in x, compiled with a checked prologue */
  pl_val hrow[] = {OP_PUSH_VAR, 1,
                   OP_FORCE,    OP_JMP,
                   9,           OP_ENTRY,
                   1,           OP_PUSH_VAR,
                   1,           OP_PUSH_SLOT,
                   0,           OP_CALL_KNOWN,
                   1,           t->vstack[base],
                   inc,         OP_RET};
  pl_code* hc = test_decode_ops(t, 16, hrow);
  ASSERT_NOT_NULL(hc);
  ASSERT_EQ(hc->strict_mask, 1);
  size_t hp = t->vsp; /* the helper leaves the canonical pin here */
  test_code_pin_named(&rt, 1, ax_s1('h'), hc);
  /* caller f(n) = h(Add n 1): the Add thunk feeds h's strict argument */
  pl_val frow[] = {OP_PUSH_VAR,
                   1,
                   OP_FORCE,
                   OP_PUSH_LIT,
                   t->vstack[hp],
                   OP_PUSH_SLOT,
                   0,
                   OP_PUSH_LIT,
                   1,
                   OP_MK_THK,
                   2,
                   PL_BAN_PRIM_KNOWN,
                   t->vstack[base],
                   add,
                   OP_CALL_FAST,
                   1,
                   0,
                   OP_RET};
  pl_code* fc = test_decode_ops(t, 18, frow);
  ASSERT_NOT_NULL(fc);
  ASSERT_EQ(fc->ops[9], OP_ADD); /* entered eagerly (then specialised) */
  ASSERT_EQ(fc->ops[13], OP_NOP);
  ASSERT_EQ(fc->ops[14], OP_CALL_FAST);
  size_t fp = t->vsp;
  test_code_pin_named(&rt, 1, ax_s1('f'), fc);
  ASSERT_EQ(test_run_call1(t, t->vstack[fp], 5), 7);
  size_t arg = t->vsp;
  pl_vpush(t, test_thunk(t, 5));
  ASSERT_EQ(test_run_call1(t, t->vstack[fp], t->vstack[arg]), 7);
  t->vsp = arg;
  /* a callee with matching arity but no installed code: unknown, stays */
  pl_pin_set_code(pl_as(PL_TAG_PIN, t->vstack[hp]), NULL);
  pl_val frow2[] = {OP_PUSH_VAR,
                    1,
                    OP_FORCE,
                    OP_PUSH_LIT,
                    t->vstack[hp],
                    OP_PUSH_SLOT,
                    0,
                    OP_PUSH_LIT,
                    1,
                    OP_MK_THK,
                    2,
                    PL_BAN_PRIM_KNOWN,
                    t->vstack[base],
                    add,
                    OP_CALL_FAST,
                    1,
                    0,
                    OP_RET};
  pl_code* fc2 = test_decode_ops(t, 18, frow2);
  ASSERT_NOT_NULL(fc2);
  ASSERT_EQ(fc2->ops[9], OP_MK_THK);
  pl_bytecode_free(fc2);
  /* a callee of arity 2 called with one argument is not saturated: stays */
  pl_val grow[] = {OP_PUSH_VAR, 1,
                   OP_FORCE,    OP_JMP,
                   9,           OP_ENTRY,
                   1,           OP_PUSH_VAR,
                   1,           OP_PUSH_SLOT,
                   0,           OP_CALL_KNOWN,
                   1,           t->vstack[base],
                   inc,         OP_RET};
  pl_code* gc = test_decode_ops(t, 16, grow);
  ASSERT_NOT_NULL(gc);
  size_t gp = t->vsp;
  test_code_pin_named(&rt, 2, ax_s1('g'), gc);
  pl_val frow3[] = {OP_PUSH_VAR,
                    1,
                    OP_FORCE,
                    OP_PUSH_LIT,
                    t->vstack[gp],
                    OP_PUSH_SLOT,
                    0,
                    OP_PUSH_LIT,
                    1,
                    OP_MK_THK,
                    2,
                    PL_BAN_PRIM_KNOWN,
                    t->vstack[base],
                    add,
                    OP_CALL_FAST,
                    1,
                    0,
                    OP_RET};
  pl_code* fc3 = test_decode_ops(t, 18, frow3);
  ASSERT_NOT_NULL(fc3);
  ASSERT_EQ(fc3->ops[9], OP_MK_THK);
  pl_bytecode_free(fc3);
  pl_pin_set_code(pl_as(PL_TAG_PIN, t->vstack[gp]), NULL);
  pl_pin_set_code(pl_as(PL_TAG_PIN, t->vstack[fp]), NULL);
  pl_bytecode_free(gc);
  pl_bytecode_free(fc);
  pl_bytecode_free(hc);
  test_rt_free(&rt);
}

/* Row projections and inspections are total O(1) field reads: a MK_THK of
 * one whose strict operands are already values runs the body instead of
 * allocating — the element itself, evaluated or not, stands in for the
 * projection thunk.  An unevaluated row keeps the thunk. */
TEST(exec, mk_thk_projects_evaluated_rows_without_allocating) {
  test_rt rt = test_rt_new();
  pl_thread* t = rt.t;
  size_t base = t->vsp;
  pl_vpush(t, pl_pin(t, 66)); /* base: re-read per row, decodes collect */
  const pl_val names[3] = {ax_s3('I', 'x', '1'), ax_s2('I', 'x'),
                           ax_s2('S', 'z')};
  for (unsigned op = 0; op < 3; op++) {
    /* g(r) = (0 (Ix1 r)) / (0 (Ix 5 r)) / (0 (Sz r)) */
    pl_val one[] = {OP_PUSH_LIT,
                    0,
                    OP_PUSH_VAR,
                    1,
                    OP_MK_THK,
                    1,
                    PL_BAN_PRIM_KNOWN,
                    t->vstack[base],
                    names[op],
                    OP_MK_APP,
                    1,
                    OP_RET};
    pl_val two[] = {OP_PUSH_LIT,
                    0,
                    OP_PUSH_LIT,
                    5,
                    OP_PUSH_VAR,
                    1,
                    OP_MK_THK,
                    2,
                    PL_BAN_PRIM_KNOWN,
                    t->vstack[base],
                    names[op],
                    OP_MK_APP,
                    1,
                    OP_RET};
    pl_code* c =
        op == 1 ? test_decode_ops(t, 14, two) : test_decode_ops(t, 12, one);
    ASSERT_NOT_NULL(c);
    ASSERT_NEQ(c->ops[op == 1 ? 10 : 8], 0); /* a speculation code was set */
    size_t cp = t->vsp;
    test_code_pin(&rt, 1, c);
    /* an evaluated row holding an evaluated and an unevaluated element */
    size_t rp = t->vsp;
    pl_vpush(t, test_thunk(t, 20));
    pl_val elts[3] = {10, t->vstack[rp], 30};
    pl_vpush(t, test_app(t, 0, 3, elts));
    pl_cell* app =
        pl_as(PL_TAG_APP, test_run_call1(t, t->vstack[cp], t->vstack[rp + 1]));
    ASSERT_NOT_NULL(app);
    pl_val got = pl_app_args(app)[0];
    if (op == 0)
      ASSERT_EQ(got, t->vstack[rp]); /* the element thunk itself */
    if (op == 1)
      ASSERT_EQ(got, 0); /* out of range */
    if (op == 2)
      ASSERT_EQ(got, 3);
    /* an unevaluated row keeps the projection thunk, which still computes */
    size_t k = t->vsp;
    pl_vpush(t, test_thunk(t, t->vstack[rp + 1]));
    app = pl_as(PL_TAG_APP, test_run_call1(t, t->vstack[cp], t->vstack[k]));
    ASSERT_NOT_NULL(app);
    pl_vpush(t, pl_app_args(app)[0]);
    ASSERT_EQ(pl_tag(t->vstack[k + 1]), PL_TAG_DEFER);
    ASSERT_EQ(pl_whnf(t, t->vstack[k + 1]), op == 0 ? 20 : op == 1 ? 0 : 3);
    pl_pin_set_code(pl_as(PL_TAG_PIN, t->vstack[cp]), NULL);
    pl_bytecode_free(c);
    t->vsp = base + 1;
  }
  test_rt_free(&rt);
}

TEST(exec, readiness_meets_branches_and_loop_backedges) {
  test_rt rt = test_rt_new();
  pl_val branches[] = {OP_PUSH_LIT, 0,  OP_BR,    2,     6,           10,
                       OP_PUSH_LIT, 7,  OP_JMP,   14,    OP_PUSH_VAR, 1,
                       OP_JMP,      14, OP_FORCE, OP_RET};
  pl_code* c = test_decode_ops(rt.t, 16, branches);
  ASSERT_NOT_NULL(c);
  ASSERT_EQ(c->ops[14], OP_FORCE); /* one predecessor is unknown */
  ASSERT_EQ(c->ops[15], OP_RET_READY);
  pl_bytecode_free(c);
  branches[10] = OP_PUSH_LIT;
  c = test_decode_ops(rt.t, 16, branches);
  ASSERT_NOT_NULL(c);
  ASSERT_EQ(c->ops[14], OP_FORCE_READY); /* both predecessors ready */
  pl_bytecode_free(c);
  pl_val loop[] = {OP_PUSH_LIT, 7,      OP_FORCE, OP_PUSH_LIT, 0, OP_BR,     2,
                   9,           10,     OP_RET,   OP_PUSH_VAR, 1, OP_MK_THK, 2,
                   PL_BAN_SLOW, OP_JMP, 2,        OP_RET};
  c = test_decode_ops(rt.t, 18, loop);
  ASSERT_NOT_NULL(c);
  ASSERT_EQ(c->ops[2], OP_FORCE); /* backedge supplies a thunk */
  pl_bytecode_free(c);
  test_rt_free(&rt);
}

TEST(exec, readiness_tracks_values_not_forced_aliases) {
  test_rt rt = test_rt_new();
  pl_val ops[] = {OP_PUSH_VAR,  1, OP_FORCE, OP_PUSH_VAR, 1, OP_FORCE,
                  OP_PUSH_SLOT, 0, OP_FORCE, OP_RET};
  pl_code* c = test_decode_ops(rt.t, 10, ops);
  ASSERT_NOT_NULL(c);
  ASSERT_EQ(c->ops[2], OP_FORCE);
  ASSERT_EQ(c->ops[5], OP_FORCE); /* original slot may contain an IND */
  ASSERT_EQ(c->ops[8], OP_FORCE_READY);
  ASSERT_EQ(c->ops[9], OP_RET_READY);
  pl_bytecode_free(c);
  pl_val calls[] = {OP_PUSH_LIT, 7,      OP_CALL,  7,     1,
                    OP_FORCE,    OP_RET, OP_FORCE, OP_RET};
  c = test_decode_ops(rt.t, 9, calls);
  ASSERT_NOT_NULL(c);
  ASSERT_EQ(c->ops[5], OP_FORCE_READY); /* call result is WHNF */
  ASSERT_EQ(c->ops[7], OP_FORCE);       /* callee arguments are conservative */
  pl_bytecode_free(c);
  test_rt_free(&rt);
}

TEST(exec, readiness_knows_strict_args_at_fast_entries_and_limits) {
  test_rt rt = test_rt_new();
  pl_val entry[] = {OP_PUSH_VAR, 1, OP_FORCE, OP_JMP, 9, OP_ENTRY, 1,
                    OP_PUSH_VAR, 1, OP_FORCE, OP_RET};
  pl_code* c = test_decode_ops(rt.t, 11, entry);
  ASSERT_NOT_NULL(c);
  ASSERT_EQ(c->strict_entry, 7);
  /* judge verifies the strict args before taking the fast entry, so its
   * push of var 1 is a value on both paths into pc 9 */
  ASSERT_EQ(c->ops[9], OP_FORCE_READY);
  pl_bytecode_free(c);
  pl_val other[] = {OP_PUSH_VAR, 1, OP_FORCE, OP_JMP, 9, OP_ENTRY, 1,
                    OP_PUSH_VAR, 2, OP_FORCE, OP_RET};
  c = test_decode_ops(rt.t, 11, other);
  ASSERT_NOT_NULL(c);
  ASSERT_EQ(c->ops[9], OP_FORCE); /* var 2 is not in the mask: unknown */
  pl_bytecode_free(c);
  pl_val wide[516];
  for (size_t i = 0; i < 257; i++) {
    wide[i * 2] = OP_PUSH_LIT;
    wide[i * 2 + 1] = 0;
  }
  wide[514] = OP_FORCE;
  wide[515] = OP_RET;
  c = test_decode_ops(rt.t, 516, wide);
  ASSERT_NOT_NULL(c);
  ASSERT_EQ(c->ops[514], OP_FORCE); /* above the tracked stack limit */
  ASSERT_EQ(c->ops[515], OP_RET);
  pl_bytecode_free(c);
  test_rt_free(&rt);
}

TEST(exec, ready_call_preserves_lazy_branches_and_forces_its_result) {
  test_rt rt = test_rt_new();
  pl_thread* t = rt.t;
  size_t base = t->vsp;
  pl_vpush(t, pl_pin(t, 66));
  pl_val ops[] = {OP_PUSH_LIT,     1,
                  OP_PUSH_VAR,     1,
                  OP_PUSH_VAR,     2,
                  OP_CALL_KNOWN,   3,
                  t->vstack[base], ax_s2('I', 'f'),
                  OP_RET};
  pl_code* c = test_decode_ops(t, 11, ops);
  ASSERT_NOT_NULL(c);
  ASSERT_EQ(c->ops[6], OP_CALL_READY); /* only the condition is strict */
  ASSERT_EQ(c->ops[10], OP_RET_READY);
  t->vsp = base;
  test_code_pin(&rt, 2, c);
  pl_vpush(t, test_thunk(t, 7));
  pl_vpush(t, test_throwing(t, 99));
  pl_gc_reserve(t, PL_THKE_CELLS(3));
  pl_val call = pl_mk_thke(t, PL_BAN_FAST, 3, &t->vstack[base]);
  t->vsp = base + 1;
  pl_thread_start(t, call);
  pl_run_status status;
  unsigned yields = 0;
  while ((status = pl_thread_run(t, 3)) == PL_RUN_YIELDED) {
    ASSERT_LT(++yields, 64);
    pl_gc_collect_now(t);
  }
  ASSERT_EQ(status, PL_RUN_DONE);
  ASSERT_EQ(pl_thread_result(t), 7);
  pl_pin_set_code(pl_as(PL_TAG_PIN, t->vstack[base]), NULL);
  pl_bytecode_free(c);
  test_rt_free(&rt);
}

TEST(exec, ready_entries_match_generic_checkpoints) {
  for (unsigned tail = 0; tail < 2; tail++) {
    for (unsigned fuel = 2; fuel <= 9; fuel++) {
      unsigned reference_yields = 0;
      for (unsigned fast = 0; fast < 2; fast++) {
        test_rt rt = test_rt_new();
        pl_thread* t = rt.t;
        size_t base = t->vsp;
        pl_vpush(t, pl_pin(t, 66));
        /* Mul uses the general ready-argument entry, not numeric Add/Sub/Cmp.
         * Force a lazy input, then copy its actual WHNF result from a slot. */
        pl_val ops[] = {OP_PUSH_VAR,
                        1,
                        OP_FORCE,
                        OP_PUSH_SLOT,
                        0,
                        OP_FORCE,
                        OP_PUSH_LIT,
                        6,
                        OP_CALL_KNOWN,
                        2,
                        t->vstack[base],
                        ax_s3('M', 'u', 'l'),
                        OP_FORCE,
                        OP_RET};
        pl_val tailops[] = {OP_PUSH_VAR,
                            1,
                            OP_FORCE,
                            OP_PUSH_SLOT,
                            0,
                            OP_FORCE,
                            OP_PUSH_LIT,
                            6,
                            OP_MK_THK,
                            2,
                            PL_BAN_PRIM_KNOWN,
                            t->vstack[base],
                            ax_s3('M', 'u', 'l'),
                            OP_RET};
        pl_code* c = test_decode_ops(t, 14, tail ? tailops : ops);
        ASSERT_NOT_NULL(c);
        ASSERT_EQ(c->ops[5], OP_FORCE_READY);
        ASSERT_EQ(c->ops[8], tail ? OP_TAIL_READY : OP_CALL_READY);
        if (!fast) {
          c->ops[5] = OP_FORCE;
          c->ops[8] = tail ? OP_TAILCALL : OP_CALL_KNOWN;
          if (!tail) {
            c->ops[12] = OP_FORCE;
            c->ops[13] = OP_RET;
          }
        }
        t->vsp = base;
        test_code_pin(&rt, 1, c);
        pl_vpush(t, test_thunk(t, 7));
        pl_gc_reserve(t, PL_THKE_CELLS(2));
        pl_val call = pl_mk_thke(t, PL_BAN_FAST, 2, &t->vstack[base]);
        t->vsp = base + 1;
        size_t fsp = t->fsp;
        pl_thread_start(t, call);
        unsigned yields = 0;
        pl_run_status status;
        while ((status = pl_thread_run(t, fuel)) == PL_RUN_YIELDED) {
          ASSERT_LT(++yields, 64);
          pl_gc_collect_now(t);
        }
        ASSERT_EQ(status, PL_RUN_DONE);
        ASSERT_EQ(pl_thread_result(t), 42);
        ASSERT_EQ(t->vsp, base + 1);
        ASSERT_EQ(t->fsp, fsp);
        if (fast)
          ASSERT_EQ(yields, reference_yields);
        else
          reference_yields = yields;
        pl_pin_set_code(pl_as(PL_TAG_PIN, t->vstack[base]), NULL);
        pl_bytecode_free(c);
        test_rt_free(&rt);
      }
    }
  }
}

TEST(exec, numeric_opcodes_are_ingest_only) {
  test_rt rt = test_rt_new();
  for (pl_op_t op = OP_ADD; op <= OP_NOP; op++) {
    pl_val row[] = {op, 2, 0, 0, OP_RET};
    pl_val val = test_app(rt.t, 0, 5, row);
    ASSERT_EQ(pl_bytecode_from_val(val), NULL);
  }
  test_rt_free(&rt);
}

/* Compare specialised execution with the same decoded call forced through
 * the generic handler, including every small fuel quantum and GC at yields. */
TEST(exec, numeric_exec_matches_generic) {
  const pl_val names[] = {ax_s3('A', 'd', 'd'), ax_s3('S', 'u', 'b'),
                          ax_s3('C', 'm', 'p')};
  const pl_op_t specialised[] = {OP_ADD,      OP_SUB,      OP_CMP,
                                 OP_TAIL_ADD, OP_TAIL_SUB, OP_TAIL_CMP};
  for (unsigned op = 0; op < 6; op++) {
    for (unsigned input = 0; input < 11; input++) {
      for (unsigned fuel = 2; fuel <= 9; fuel++) {
        unsigned reference_yields = 0;
        uint64_t reference_result = 0;
        for (unsigned fast = 0; fast < 2; fast++) {
          test_rt rt = test_rt_new();
          pl_thread* t = rt.t;
          size_t base = t->vsp;
          pl_vpush(t, pl_pin(t, 66));
          pl_val row[10] = {
              OP_PUSH_VAR,   1,     OP_PUSH_VAR,     2,
              OP_CALL_KNOWN, 2,     t->vstack[base], names[op % 3],
              OP_RET,        OP_RET};
          if (op >= 3) {
            row[4] = OP_MK_THK;
            row[6] = PL_BAN_PRIM_KNOWN;
            row[7] = t->vstack[base];
            row[8] = names[op % 3];
          }
          pl_vpush(t, test_app(t, 0, op >= 3 ? 10 : 9, row));
          pl_code* code = pl_bytecode_from_val(t->vstack[base + 1]);
          ASSERT_NOT_NULL(code);
          ASSERT_EQ(code->ops[4], specialised[op]);
          /* Exercise both environment-backed and stack-backed exec frames. */
          if (input & 1u)
            code->max_var = UINT32_MAX;
          if (!fast)
            code->ops[4] = op >= 3 ? OP_TAILCALL : OP_CALL_KNOWN;
          t->vsp = base;
          test_code_pin(&rt, 2, code);
          /* greater, less, equal, overflow, bignat, lazy first/second,
           * and a WHNF non-nat (coerced to zero). */
          pl_vpush(t, input == 1   ? 1
                      : input == 2 ? 2
                      : input == 3 ? PL_NAT63_MAX
                                   : 40);
          pl_vpush(t, 2);
          pl_val replacement;
          if (input == 4) {
            replacement = pl_mk_nat_u64(t, UINT64_C(1) << 63);
            t->vstack[base + 1] = replacement;
          }
          if (input == 5) {
            replacement = test_thunk(t, 40);
            t->vstack[base + 1] = replacement;
          }
          if (input == 6) {
            replacement = test_thunk(t, 2);
            t->vstack[base + 2] = replacement;
          }
          if (input == 7) {
            replacement = pl_pin(t, 123);
            t->vstack[base + 1] = replacement;
          }
          if (input == 8 || input == 9) {
            replacement = pl_mk_nat_u64(t, UINT64_C(1) << 63);
            t->vstack[base + 2] = replacement;
            if (input == 8)
              t->vstack[base + 1] = replacement;
          }
          if (input == 10) {
            t->vstack[base + 1] = PL_NAT63_MAX;
            t->vstack[base + 2] = PL_NAT63_MAX;
          }
          pl_gc_reserve(t, PL_THKE_CELLS(3));
          pl_val call = pl_mk_thke(t, PL_BAN_FAST, 3, &t->vstack[base]);
          t->vsp = base + 1;
          size_t fsp = t->fsp;
          pl_thread_start(t, call);
          unsigned yields = 0;
          pl_run_status status;
          while ((status = pl_thread_run(t, fuel)) == PL_RUN_YIELDED) {
            ASSERT_LT(++yields, 64);
            pl_gc_collect_now(t);
          }
          ASSERT_EQ(status, PL_RUN_DONE);
          uint64_t result = pl_nat_u64_clamp(pl_thread_result(t));
          if (!fast) {
            reference_yields = yields;
            reference_result = result;
          } else {
            ASSERT_EQ(result, reference_result);
            ASSERT_EQ(yields, reference_yields);
          }
          ASSERT_EQ(t->vsp, base + 1);
          ASSERT_EQ(t->fsp, fsp);
          pl_pin_set_code(pl_as(PL_TAG_PIN, t->vstack[base]), NULL);
          pl_bytecode_free(code);
          test_rt_free(&rt);
        }
      }
    }
  }
}

TEST(exec, call_fast_enters_law_direct) {
  test_rt rt = test_rt_new();
  pl_thread* t = rt.t;
  size_t base = t->vsp;
  /* callee: force and return its argument */
  static pl_op_t id_ops[4] = {OP_PUSH_VAR, 1, OP_FORCE, OP_RET};
  static pl_code id_code = {id_ops, 4, 0, 0, 0};
  pl_val callee = test_code_pin_named(&rt, 1, 111, &id_code);
  /* caller: direct call of the callee on its (lazy) argument */
  pl_op_t caller_ops[8] = {OP_PUSH_LIT,  callee, OP_PUSH_VAR, 1,
                           OP_CALL_FAST, 1,      0,           OP_RET};
  pl_code caller_code = {caller_ops, 8, 0, 0, 0};
  test_code_pin(&rt, 1, &caller_code);
  ASSERT_EQ(test_run_call1(t, t->vstack[base + 1], 42), 42);
  pl_vpush(t, test_thunk(t, 9));
  ASSERT_EQ(test_run_call1(t, t->vstack[base + 1], t->vstack[base + 2]), 9);
  pl_pin_set_code(pl_as(PL_TAG_PIN, t->vstack[base]), NULL);
  pl_pin_set_code(pl_as(PL_TAG_PIN, t->vstack[base + 1]), NULL);
  test_rt_free(&rt);
}

TEST(exec, call_fast_arity_mismatch_degrades_to_apply) {
  test_rt rt = test_rt_new();
  pl_thread* t = rt.t;
  size_t base = t->vsp;
  /* head: an arity-2 law pin (its code never runs — the direct call
   * supplies one arg, so verification rejects it and the generic
   * apply path yields the WHNF partial application) */
  static pl_op_t id_ops[4] = {OP_PUSH_VAR, 1, OP_FORCE, OP_RET};
  static pl_code id_code = {id_ops, 4, 0, 0, 0};
  pl_val head2 = test_code_pin(&rt, 2, &id_code);
  pl_op_t caller_ops[8] = {OP_PUSH_LIT,  head2, OP_PUSH_VAR, 1,
                           OP_CALL_FAST, 1,     0,           OP_RET};
  pl_code caller_code = {caller_ops, 8, 0, 0, 0};
  test_code_pin(&rt, 1, &caller_code);
  pl_val r = test_run_call1(t, t->vstack[base + 1], 42);
  pl_cell* p = pl_as(PL_TAG_APP, r);
  ASSERT_NOT_NULL(p);
  ASSERT_EQ(pl_app_n(p), 1);
  ASSERT_EQ(pl_app_args(p)[0], 42);
  pl_pin_set_code(pl_as(PL_TAG_PIN, t->vstack[base]), NULL);
  pl_pin_set_code(pl_as(PL_TAG_PIN, t->vstack[base + 1]), NULL);
  test_rt_free(&rt);
}

TEST(exec, call_slow_forces_head_then_applies) {
  test_rt rt = test_rt_new();
  pl_thread* t = rt.t;
  size_t base = t->vsp;
  static pl_op_t id_ops[4] = {OP_PUSH_VAR, 1, OP_FORCE, OP_RET};
  static pl_code id_code = {id_ops, 4, 0, 0, 0};
  pl_val callee = test_code_pin_named(&rt, 1, 222, &id_code);
  (void)callee;
  /* caller: head is a lazy thunk (forced by the slow path) */
  pl_op_t caller_ops[7] = {OP_PUSH_VAR,  1, OP_PUSH_LIT, 9,
                           OP_CALL_SLOW, 1, OP_RET};
  pl_code caller_code = {caller_ops, 7, 0, 0, 0};
  test_code_pin(&rt, 1, &caller_code);
  pl_vpush(t, test_thunk(t, t->vstack[base]));
  ASSERT_EQ(test_run_call1(t, t->vstack[base + 1], t->vstack[base + 2]), 9);
  pl_pin_set_code(pl_as(PL_TAG_PIN, t->vstack[base]), NULL);
  pl_pin_set_code(pl_as(PL_TAG_PIN, t->vstack[base + 1]), NULL);
  test_rt_free(&rt);
}

/* ── op 66 Memo (doc/sigoflaw-memo-spec.md) ────────────────────────────── */

/* Pin v and persist it so the pin carries a content hash. */
static pl_val test_saved_pin(test_rt* rt, pl_val v) {
  pl_thread* t = rt->t;
  size_t base = t->vsp;
  pl_vpush(t, v);
  t->vstack[base] = pl_pin(t, t->vstack[base]);
  char err[192] = {0};
  ASSERT(pl_store_save_root(rt->store, t->vstack[base], NULL, err, sizeof(err)),
         "%s", err);
  pl_val pin = t->vstack[base];
  t->vsp = base;
  return pin;
}

static pl_val test_memo(pl_thread* t, pl_val f, pl_val x) {
  return test_op66_2(t, ax_s4('M', 'e', 'm', 'o'), f, x);
}

TEST(memo, unpinned_args_apply_without_caching) {
  test_rt rt = test_rt_new();
  pl_thread* t = rt.t;
  size_t base = t->vsp;
  uint64_t rec0;
  uint64_t rec1;
  pl_memo_stats(NULL, NULL, &rec0);
  /* raw (unpinned) law: (Memo f 7) is exactly (f 7), never recorded */
  pl_vpush(t, test_law(t, 1, ax_s4('m', 'm', '_', 'a'), test_app1(t, 0, 42)));
  ASSERT_EQ(test_memo(t, t->vstack[base], 7), 42);
  pl_memo_stats(NULL, NULL, &rec1);
  ASSERT_EQ(rec0, rec1);
  test_rt_free(&rt);
}

TEST(memo, pinned_nat_result_is_recorded_and_served) {
  test_rt rt = test_rt_new();
  pl_thread* t = rt.t;
  size_t base = t->vsp;
  pl_vpush(t, test_law(t, 1, ax_s4('m', 'm', '_', 'b'), test_app1(t, 0, 42)));
  t->vstack[base] = test_saved_pin(&rt, t->vstack[base]);
  pl_vpush(t, test_saved_pin(&rt, ax_s4('m', 'm', 'x', 'b')));
  ASSERT_EQ(test_memo(t, t->vstack[base], t->vstack[base + 1]), 42);
  uint64_t got = 0;
  ASSERT(pl_memo_probe(pl_pin_hash(t->vstack[base]),
                       pl_pin_hash(t->vstack[base + 1]), &got));
  ASSERT_EQ(got, 42);
  test_rt_free(&rt);
}

TEST(memo, cached_value_is_served_without_reevaluation) {
  test_rt rt = test_rt_new();
  pl_thread* t = rt.t;
  size_t base = t->vsp;
  /* plant a sentinel for a never-evaluated pair: a probe hit must be
   * served verbatim, proving the serve path short-circuits the apply */
  pl_vpush(t, test_law(t, 1, ax_s4('m', 'm', '_', 'c'), test_app1(t, 0, 42)));
  t->vstack[base] = test_saved_pin(&rt, t->vstack[base]);
  pl_vpush(t, test_saved_pin(&rt, ax_s4('m', 'm', 'x', 'c')));
  pl_memo_record(pl_pin_hash(t->vstack[base]), pl_pin_hash(t->vstack[base + 1]),
                 99);
  ASSERT_EQ(test_memo(t, t->vstack[base], t->vstack[base + 1]), 99);
  test_rt_free(&rt);
}

TEST(memo, effectful_evaluation_is_never_recorded) {
  test_rt rt = test_rt_new();
  pl_thread* t = rt.t;
  size_t base = t->vsp;
  /* f's body runs (Trace 1 5): the effect-epoch bump must block the
   * record even though the result (5) is a cacheable nat63 */
  pl_val trace_args[2] = {1, 5};
  pl_vpush(t, test_app(t, ax_s5('T', 'r', 'a', 'c', 'e'), 2, trace_args));
  pl_vpush(t, test_app1(t, 0, t->vstack[base])); /* (0 row) literal */
  pl_vpush(t, test_app1(t, 0, test_p66(t)));     /* (0 P66) literal */
  pl_vpush(t, test_app2(t, 0, t->vstack[base + 2], t->vstack[base + 1]));
  pl_vpush(t, test_law(t, 1, ax_s4('m', 'm', '_', 'd'), t->vstack[base + 3]));
  t->vstack[base] = test_saved_pin(&rt, t->vstack[base + 4]);
  t->vsp = base + 1;
  pl_vpush(t, test_saved_pin(&rt, ax_s4('m', 'm', 'x', 'd')));
  ASSERT_EQ(test_memo(t, t->vstack[base], t->vstack[base + 1]), 5);
  uint64_t got = 0;
  ASSERT(!pl_memo_probe(pl_pin_hash(t->vstack[base]),
                        pl_pin_hash(t->vstack[base + 1]), &got));
  test_rt_free(&rt);
}

TEST(memo, non_nat_result_evaluates_but_never_caches) {
  test_rt rt = test_rt_new();
  pl_thread* t = rt.t;
  size_t base = t->vsp;
  /* identity law: (f x) is the x pin itself — not a nat63, so the
   * application runs uncached and nothing is recorded */
  pl_vpush(t, test_law(t, 1, ax_s4('m', 'm', '_', 'e'), 1));
  t->vstack[base] = test_saved_pin(&rt, t->vstack[base]);
  pl_vpush(t,
           test_saved_pin(&rt, test_law(t, 2, ax_s4('m', 'm', 'x', 'e'), 1)));
  pl_val r = test_memo(t, t->vstack[base], t->vstack[base + 1]);
  ASSERT(!pl_is_nat63(r));
  ASSERT_NOT_NULL(pl_as(PL_TAG_PIN, r));
  ASSERT(memcmp(pl_pin_hash(r), pl_pin_hash(t->vstack[base + 1]), 32) == 0);
  uint64_t got = 0;
  ASSERT(!pl_memo_probe(pl_pin_hash(t->vstack[base]),
                        pl_pin_hash(t->vstack[base + 1]), &got));
  test_rt_free(&rt);
}

TEST(memo, ice_persistence_is_never_cached) {
  test_rt rt = test_rt_new();
  pl_thread* t = rt.t;
  size_t base = t->vsp;
  /* f x = P66 (Ice x), assembled from law-body application expressions. */
  pl_vpush(t, test_app1(t, 0, ax_s3('I', 'c', 'e')));
  pl_vpush(t, test_app2(t, 0, t->vstack[base], 1));
  pl_vpush(t, test_app1(t, 0, test_p66(t)));
  pl_vpush(t, test_app2(t, 0, t->vstack[base + 2], t->vstack[base + 1]));
  pl_vpush(t, test_law(t, 1, ax_s6('m', 'm', '_', 'i', 'c', 'e'),
                       t->vstack[base + 3]));
  t->vstack[base] = test_saved_pin(&rt, t->vstack[base + 4]);
  t->vsp = base + 1;
  pl_vpush(t, test_saved_pin(&rt, ax_s6('m', 'm', 'x', 'i', 'c', 'e')));
  for (unsigned attempt = 0; attempt < 2; attempt++) {
    uint64_t epoch = t->effect_epoch;
    ASSERT_EQ(test_memo(t, t->vstack[base], t->vstack[base + 1]), 0);
    ASSERT_EQ(t->effect_epoch, epoch + 1);
    uint64_t got = 0;
    ASSERT_FALSE(pl_memo_probe(pl_pin_hash(t->vstack[base]),
                               pl_pin_hash(t->vstack[base + 1]), &got));
  }
  test_rt_free(&rt);
}

TEST(ops, equal_survives_very_deep_structures) {
  test_rt rt = test_rt_new();
  pl_thread* t = rt.t;
  size_t base = t->vsp;
  /* two structurally-equal 200k-deep app chains (distinct cells): the
   * old recursive pl_eq_deep overflowed the C stack near ~80k.  Under
   * GC_STRESS every reserve copies the growing chains (quadratic, never
   * finishes at 200k), so that build only checks the rooting at 2k. */
#ifdef PL_GC_STRESS
  enum { DEPTH = 2000 };
#else
  enum { DEPTH = 200000 };
#endif
  pl_vpush(t, 7);
  pl_vpush(t, 7);
  pl_vpush(t, 8);
  for (int i = 0; i < DEPTH; i++) {
    t->vstack[base] = test_app1(t, 0, t->vstack[base]);
    t->vstack[base + 1] = test_app1(t, 0, t->vstack[base + 1]);
    t->vstack[base + 2] = test_app1(t, 0, t->vstack[base + 2]);
  }
  ASSERT_EQ(test_op66_2(t, ax_s5('E', 'q', 'u', 'a', 'l'), t->vstack[base],
                        t->vstack[base + 1]),
            1);
  /* same shape, different leaf */
  ASSERT_EQ(test_op66_2(t, ax_s5('E', 'q', 'u', 'a', 'l'), t->vstack[base],
                        t->vstack[base + 2]),
            0);
  test_rt_free(&rt);
}
