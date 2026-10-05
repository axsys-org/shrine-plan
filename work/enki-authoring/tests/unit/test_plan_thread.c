#include "test.h"

#include "test_plan.h"

/*
 * Suspension core: pl_thread_start / pl_thread_run /
 * pl_thread_deposit.  A suspended thread is a complete continuation in
 * the thread's stacks plus the resume slots; these tests exercise the
 * yield/resume protocol, exception unwinding to the entry watermarks,
 * GC of a suspended thread, and yield-point determinism.
 *
 * APP cells are WHNF by construction, so redexes are driven through
 * lazy thunks whose body code runs under an empty (1-slot) env, as in
 * test_plan_eval.c.
 */

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

/* A thunk computing ((K (K 7 8)) 9) -> 7, K x y = x.  Body code:
 * (0 (0 (0 K) (0 (0 (0 K) 7) 8)) 9); nats are literals (maxArg 0). */
static pl_val test_k_thunk(pl_thread* t) {
  size_t base = t->vsp;
  pl_vpush(t, test_app1(t, 0, test_law(t, 2, 0, 1))); /* (0 K)       */
  pl_vpush(t, test_app2(t, 0, t->vstack[base], 7));   /* (0 K' 7)    */
  pl_vpush(t, test_app2(t, 0, t->vstack[base + 1], 8));
  pl_vpush(t, test_app2(t, 0, t->vstack[base], t->vstack[base + 2]));
  pl_val expr = test_app2(t, 0, t->vstack[base + 3], 9);
  t->vsp = base;
  return test_thunk(t, expr);
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

TEST(thread, run_to_done_with_ample_fuel) {
  test_rt rt = test_rt_new();
  pl_thread* t = rt.t;
  pl_thread_start(t, test_k_thunk(t));
  ASSERT_EQ(pl_thread_run(t, 1u << 20), PL_RUN_DONE);
  ASSERT_EQ(pl_thread_result(t), 7);
  test_rt_free(&rt);
}

TEST(thread, yields_on_fuel_and_resumes_to_same_result) {
  test_rt rt = test_rt_new();
  pl_thread* t = rt.t;
  size_t vsp0 = t->vsp, fsp0 = t->fsp;
  pl_thread_start(t, test_k_thunk(t));
  int quanta = 0;
  pl_run_status s;
  do {
    s = pl_thread_run(t, 2); /* exactly one machine step per quantum */
    quanta++;
    ASSERT_LT(quanta, 1 << 20, "runaway resume loop");
  } while (s == PL_RUN_YIELDED);
  ASSERT_EQ(s, PL_RUN_DONE);
  ASSERT_EQ(pl_thread_result(t), 7);
  ASSERT_GT(quanta, 1, "expected at least one yield");
  /* completion restores the entry watermarks */
  ASSERT_EQ(t->vsp, vsp0);
  ASSERT_EQ(t->fsp, fsp0);
  test_rt_free(&rt);
}

TEST(thread, yield_points_are_deterministic) {
  test_rt rt = test_rt_new();
  pl_thread* t = rt.t;
  int counts[2];
  for (int i = 0; i < 2; i++) {
    pl_thread_start(t, test_k_thunk(t));
    int quanta = 0;
    while (pl_thread_run(t, 2) == PL_RUN_YIELDED)
      quanta++;
    ASSERT_EQ(t->status, PL_RUN_DONE);
    ASSERT_EQ(pl_thread_result(t), 7);
    counts[i] = quanta;
  }
  ASSERT_EQ(counts[0], counts[1]);
  test_rt_free(&rt);
}

TEST(thread, exception_unwinds_to_watermarks) {
  test_rt rt = test_rt_new();
  pl_thread* t = rt.t;
  size_t vsp0 = t->vsp, fsp0 = t->fsp;
  pl_thread_start(t, test_throwing(t, 7));
  pl_run_status s;
  do
    s = pl_thread_run(t, 2);
  while (s == PL_RUN_YIELDED);
  ASSERT_EQ(s, PL_RUN_EXN);
  ASSERT_NULL(t->exn_msg);
  ASSERT_EQ(t->exn, 7);
  ASSERT_EQ(t->vsp, vsp0);
  ASSERT_EQ(t->fsp, fsp0);
  /* the thread object remains usable for a fresh run */
  pl_thread_start(t, test_k_thunk(t));
  ASSERT_EQ(pl_thread_run(t, 1u << 20), PL_RUN_DONE);
  ASSERT_EQ(pl_thread_result(t), 7);
  test_rt_free(&rt);
}

TEST(thread, suspended_continuation_survives_gc) {
  test_rt rt = test_rt_new();
  pl_thread* t = rt.t;
  pl_thread_start(t, test_k_thunk(t));
  pl_run_status s;
  do {
    pl_gc_collect_now(t); /* moves everything the continuation roots */
    s = pl_thread_run(t, 2);
  } while (s == PL_RUN_YIELDED);
  ASSERT_EQ(s, PL_RUN_DONE);
  ASSERT_EQ(pl_thread_result(t), 7);
  test_rt_free(&rt);
}

TEST(thread, start_nf_normalizes_deeply) {
  test_rt rt = test_rt_new();
  pl_thread* t = rt.t;
  size_t base = t->vsp;
  /* (K <thunk -> 7>): under-applied, so already WHNF; nf forces the
   * lazy field and the result row carries the nat */
  pl_vpush(t, test_law(t, 2, 0, 1));
  pl_vpush(t, test_k_thunk(t));
  pl_val v = test_app1(t, t->vstack[base], t->vstack[base + 1]);
  t->vsp = base;
  pl_thread_start_nf(t, v);
  pl_run_status s;
  do
    s = pl_thread_run(t, 2);
  while (s == PL_RUN_YIELDED);
  ASSERT_EQ(s, PL_RUN_DONE);
  pl_val r = pl_thread_result(t);
  pl_cell* p = pl_as(PL_TAG_APP, r);
  ASSERT_NOT_NULL(p);
  ASSERT_EQ(pl_whnf(t, pl_app_args(p)[0]), 7);
  test_rt_free(&rt);
}

TEST(thread, deposit_resumes_with_response) {
  test_rt rt = test_rt_new();
  pl_thread* t = rt.t;
  /* Simulate a blocked effect at thread top level: the deposited
   * response is RETURNed to the (empty) frame stack and becomes the
   * result.  Real BLOCKED producers arrive with op 82. */
  pl_thread_start(t, 0);
  t->status = PL_RUN_BLOCKED;
  t->blocked_on = 42;
  pl_thread_deposit(t, 9);
  ASSERT_EQ(t->blocked_on, 0);
  ASSERT_EQ(pl_thread_run(t, 1u << 10), PL_RUN_DONE);
  ASSERT_EQ(pl_thread_result(t), 9);
  test_rt_free(&rt);
}

/* Memo (op 66) under suspension: the F_MEMO barrier must survive fuel
 * yields mid-application and still record on completion. */
TEST(thread, memo_barrier_survives_fuel_yields) {
  test_rt rt = test_rt_new();
  pl_thread* t = rt.t;
  size_t base = t->vsp;
  /* f: arity-1 law computing ((K 42) 8) -> 42 through real steps */
  pl_vpush(t, test_app1(t, 0, test_law(t, 2, 0, 1)));   /* (0 K)  */
  pl_vpush(t, test_app2(t, 0, t->vstack[base], 42));    /* (0 K' 42) */
  pl_vpush(t, test_app2(t, 0, t->vstack[base + 1], 8)); /* body   */
  pl_vpush(t, test_law(t, 1, ax_s4('m', 'm', 't', 'f'), t->vstack[base + 2]));
  t->vstack[base] = pl_pin(t, t->vstack[base + 3]);
  char err[192] = {0};
  ASSERT(pl_store_save_root(rt.store, t->vstack[base], NULL, err, sizeof(err)),
         "%s", err);
  t->vsp = base + 1;
  pl_vpush(t, pl_pin(t, ax_s4('m', 'm', 't', 'x')));
  ASSERT(
      pl_store_save_root(rt.store, t->vstack[base + 1], NULL, err, sizeof(err)),
      "%s", err);
  /* thunk body: (0 (0 P66) (0 ("Memo" f x))) */
  pl_val margs[2] = {t->vstack[base], t->vstack[base + 1]};
  pl_vpush(t, test_app(t, ax_s4('M', 'e', 'm', 'o'), 2, margs));
  pl_vpush(t, test_app1(t, 0, t->vstack[base + 2]));
  pl_vpush(t, test_app1(t, 0, test_p66(t)));
  pl_vpush(t, test_app2(t, 0, t->vstack[base + 4], t->vstack[base + 3]));
  pl_vpush(t, test_thunk(t, t->vstack[base + 5]));
  pl_thread_start(t, t->vstack[base + 6]);
  int quanta = 0;
  pl_run_status s;
  do {
    s = pl_thread_run(t, 2);
    quanta++;
    ASSERT_LT(quanta, 1 << 20, "runaway resume loop");
  } while (s == PL_RUN_YIELDED);
  ASSERT_EQ(s, PL_RUN_DONE);
  ASSERT_EQ(pl_thread_result(t), 42);
  ASSERT_GT(quanta, 1, "expected at least one yield under the barrier");
  uint64_t got = 0;
  ASSERT(pl_memo_probe(pl_pin_hash(t->vstack[base]),
                       pl_pin_hash(t->vstack[base + 1]), &got));
  ASSERT_EQ(got, 42);
  test_rt_free(&rt);
}

TEST(thread, starting_a_run_releases_the_previous_result) {
  for (unsigned reuse = 0; reuse < 2; reuse++) {
    test_rt rt = test_rt_new();
    pl_thread* t = rt.t;
    pl_thread_start(t, test_app1(t, 0, 42));
    ASSERT_EQ(pl_thread_run(t, 64), PL_RUN_DONE);
    pl_gc_collect_now(t);
    ASSERT_EQ(pl_gc_live_cells(rt.heap), PL_APP_CELLS(1));
    pl_val input = reuse ? pl_thread_result(t) : 7;
    pl_thread_start(t, input);
    pl_gc_collect_now(t);
    ASSERT_EQ(pl_gc_live_cells(rt.heap), reuse ? PL_APP_CELLS(1) : 0);
    ASSERT_EQ(pl_thread_run(t, 64), PL_RUN_DONE);
    if (reuse) {
      pl_cell* app = pl_as(PL_TAG_APP, pl_thread_result(t));
      ASSERT_NOT_NULL(app);
      ASSERT_EQ(pl_app_args(app)[0], 42);
    } else {
      ASSERT_EQ(pl_thread_result(t), 7);
    }
    test_rt_free(&rt);
  }
}

static bool nested_result_preserved, nested_result_released;
static bool nested_result_hook(pl_thread* t, uint32_t op, size_t argbase,
                               pl_val* out) {
  (void)op;
  (void)argbase;
  pl_gc_collect_now(t);
  size_t before = pl_gc_live_cells(t->heap);
  size_t base = t->vsp;
  pl_val value = pl_whnf(t, test_app1(t, 0, 42));
  pl_vpush(t, value);
  pl_gc_collect_now(t);
  pl_cell* app = pl_as(PL_TAG_APP, t->vstack[base]);
  nested_result_preserved = app != NULL && pl_app_args(app)[0] == 42;
  t->vsp = base;
  pl_gc_collect_now(t);
  nested_result_released =
      t->result == 0 && pl_gc_live_cells(t->heap) <= before;
  *out = 9;
  return true;
}

TEST(thread, nested_c_entry_does_not_retain_its_scratch_result) {
  test_rt rt = test_rt_new();
  pl_thread* t = rt.t;
  size_t base = t->vsp;
  pl_vpush(t, pl_pin(t, 82));
  pl_vpush(t, test_app1(t, ax_s3('N', 'o', 'w'), 0));
  pl_gc_reserve(t, PL_THKE_CELLS(2));
  pl_val call = pl_mk_thke(t, PL_BAN_SLOW, 2, &t->vstack[base]);
  t->vsp = base;
  nested_result_preserved = nested_result_released = false;
  t->rplan_f = true;
  pl_set_io_hook(nested_result_hook);
  pl_thread_start(t, call);
  pl_run_status status;
  do {
    status = pl_thread_run(t, 2);
    if (status == PL_RUN_YIELDED)
      pl_gc_collect_now(t);
  } while (status == PL_RUN_YIELDED);
  pl_set_io_hook(NULL);
  ASSERT_EQ(status, PL_RUN_DONE);
  ASSERT_EQ(pl_thread_result(t), 9);
  ASSERT(nested_result_preserved);
  ASSERT(nested_result_released);
  test_rt_free(&rt);
}

TEST(thread, outermost_c_entry_keeps_its_return_value_rooted) {
  test_rt rt = test_rt_new();
  (void)pl_whnf(rt.t, test_app1(rt.t, 0, 42));
  pl_gc_collect_now(rt.t);
  ASSERT_EQ(pl_gc_live_cells(rt.heap), PL_APP_CELLS(1));
  pl_cell* app = pl_as(PL_TAG_APP, rt.t->result);
  ASSERT_NOT_NULL(app);
  ASSERT_EQ(pl_app_args(app)[0], 42);
  test_rt_free(&rt);
}
