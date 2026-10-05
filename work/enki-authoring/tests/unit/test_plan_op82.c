#include "test.h"

#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <sys/stat.h>
#include <time.h>
#include <unistd.h>

#include "test_plan.h"

/*
 * op 82 coordination effects: Spawn/Send/SendCaps/
 * Recv/CloseHandle validate their forced args, park the request spine
 * [OpName, args…] in t->blocked_on, and suspend with PL_RUN_BLOCKED.
 * The host services the request and resumes with pl_thread_deposit; the
 * response arrives as the op's value.  Direct ops (Input/Output/…) are
 * unaffected and keep running inline as op bodies.
 *
 * Redexes are driven through lazy thunks with KAL body code, as in
 * test_plan_thread.c: in a 1-slot-env body, (0 f x) is application and
 * (0 v) is a literal.
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

/* The pin of nat 82, the rplan I/O op set. */
static pl_val test_p82(pl_thread* t) {
  size_t base = t->vsp;
  pl_vpush(t, 82);
  pl_val pin = pl_pin(t, t->vstack[base]);
  t->vsp = base;
  return pin;
}

/* A thunk forcing (P82 % (name args…)): body (0 (0 P82) (0 row)). */
static pl_val test_op82_thunk(pl_thread* t, pl_val name, size_t n,
                              const pl_val* args) {
  size_t base = t->vsp;
  pl_vpush(t, test_app(t, name, n, args));
  pl_vpush(t, test_app1(t, 0, t->vstack[base])); /* (0 row) */
  pl_vpush(t, test_app1(t, 0, test_p82(t)));     /* (0 P82) */
  pl_val expr = test_app2(t, 0, t->vstack[base + 2], t->vstack[base + 1]);
  t->vsp = base;
  return test_thunk(t, expr);
}

/* Run until the thread leaves the runnable set, one machine step per
 * quantum, so every test also exercises yield/resume interleaving. */
static pl_run_status test_run(pl_thread* t) {
  pl_run_status s;
  int quanta = 0;
  do {
    s = pl_thread_run(t, 2);
    ASSERT_LT(++quanta, 1 << 20, "runaway resume loop");
  } while (s == PL_RUN_YIELDED);
  return s;
}

static pl_val test_op82_write_file(pl_thread* t, const char* path,
                                   const uint8_t* bytes, size_t n) {
  size_t base = t->vsp;
  pl_vpush(t, pl_nat_from_bytes(t, (const uint8_t*)"WriteFile", 9));
  pl_vpush(t, pl_nat_from_bytes(t, (const uint8_t*)path, strlen(path)));
  pl_vpush(t, pl_nat_from_bytes(t, bytes, n));
  pl_val args[2] = {t->vstack[base + 1], t->vstack[base + 2]};
  pl_thread_start(t, test_op82_thunk(t, t->vstack[base], 2, args));
  ASSERT_EQ(test_run(t), PL_RUN_DONE);
  pl_val result = pl_thread_result(t);
  t->vsp = base;
  return result;
}

static bool test_file_eq(const char* path, const char* expected) {
  FILE* f = fopen(path, "rb");
  ASSERT_NOT_NULL(f, "failed to open `%s`", path);
  for (size_t i = 0; expected[i] != '\0'; i++)
    if (fgetc(f) != (unsigned char)expected[i]) {
      fclose(f);
      return false;
    }
  int ch = fgetc(f);
  fclose(f);
  return ch == EOF;
}

TEST(op82, recv_blocks_then_deposit_resumes) {
  test_rt rt = test_rt_new();
  pl_thread* t = rt.t;
  t->rplan_f = true;
  size_t vsp0 = t->vsp, fsp0 = t->fsp;
  pl_val args[1] = {0};
  pl_thread_start(t, test_op82_thunk(t, ax_s4('R', 'e', 'c', 'v'), 1, args));
  ASSERT_EQ(test_run(t), PL_RUN_BLOCKED);

  pl_cell* p = pl_as(PL_TAG_APP, pl_thread_request(t));
  ASSERT_NOT_NULL(p);
  ASSERT_EQ(pl_app_head(p), ax_s4('R', 'e', 'c', 'v'));
  ASSERT_EQ(pl_app_n(p), 1);
  ASSERT_EQ(pl_app_args(p)[0], 0);

  pl_thread_deposit(t, 42);
  ASSERT_EQ(t->blocked_on, 0);
  ASSERT_EQ(test_run(t), PL_RUN_DONE);
  ASSERT_EQ(pl_thread_result(t), 42);
  ASSERT_EQ(t->vsp, vsp0);
  ASSERT_EQ(t->fsp, fsp0);
  test_rt_free(&rt);
}

TEST(op82, response_feeds_pending_frames) {
  test_rt rt = test_rt_new();
  pl_thread* t = rt.t;
  t->rplan_f = true;
  /* (P66 % (Add 5 <thunk -> (P82 % (Recv 0))>)): the Recv blocks while
   * forcing Add's strict arg; the deposit RETURNs through the recv
   * thunk's F_UPDATE into the F_OPARG driver. */
  size_t base = t->vsp;
  pl_val rargs[1] = {0};
  pl_vpush(t, test_op82_thunk(t, ax_s4('R', 'e', 'c', 'v'), 1, rargs));
  pl_val aargs[2] = {5, t->vstack[base]};
  pl_vpush(t, test_app(t, ax_s3('A', 'd', 'd'), 2, aargs));
  pl_vpush(t, test_app1(t, 0, t->vstack[base + 1])); /* (0 addrow) */
  pl_vpush(t, test_app1(t, 0, test_p66(t)));         /* (0 P66)    */
  pl_val expr = test_app2(t, 0, t->vstack[base + 3], t->vstack[base + 2]);
  t->vsp = base;
  pl_thread_start(t, test_thunk(t, expr));

  ASSERT_EQ(test_run(t), PL_RUN_BLOCKED);
  pl_thread_deposit(t, 4);
  ASSERT_EQ(test_run(t), PL_RUN_DONE);
  ASSERT_EQ(pl_thread_result(t), 9);
  test_rt_free(&rt);
}

TEST(op82, send_normalizes_payload_at_initiation) {
  test_rt rt = test_rt_new();
  pl_thread* t = rt.t;
  t->rplan_f = true;
  size_t base = t->vsp;
  pl_vpush(t, test_thunk(t, 7)); /* msg: a thunk forced by the deep mask */
  pl_val args[2] = {3, t->vstack[base]};
  pl_thread_start(t, test_op82_thunk(t, ax_s4('S', 'e', 'n', 'd'), 2, args));
  ASSERT_EQ(test_run(t), PL_RUN_BLOCKED);

  pl_cell* p = pl_as(PL_TAG_APP, pl_thread_request(t));
  ASSERT_NOT_NULL(p);
  ASSERT_EQ(pl_app_head(p), ax_s4('S', 'e', 'n', 'd'));
  ASSERT_EQ(pl_app_n(p), 2);
  ASSERT_EQ(pl_app_args(p)[0], 3);
  /* the payload was deep-normalized before the request parked */
  ASSERT_EQ(pl_app_args(p)[1], 7);

  pl_thread_deposit(t, 0);
  ASSERT_EQ(test_run(t), PL_RUN_DONE);
  ASSERT_EQ(pl_thread_result(t), 0);
  t->vsp = base;
  test_rt_free(&rt);
}

TEST(op82, write_file_honors_file_root) {
  char dir[] = "/tmp/enki-write-root-XXXXXX";
  ASSERT_NOT_NULL(mkdtemp(dir), "failed to make temp dir");

  char root[512], inside[512], secret[512], link[512];
  int s = snprintf(root, sizeof(root), "%s/files", dir);
  ASSERT(s >= 0 && (size_t)s < sizeof(root));
  ASSERT_EQ(mkdir(root, 0700), 0);
  s = snprintf(inside, sizeof(inside), "%s/out.txt", root);
  ASSERT(s >= 0 && (size_t)s < sizeof(inside));
  s = snprintf(secret, sizeof(secret), "%s/secret.txt", dir);
  ASSERT(s >= 0 && (size_t)s < sizeof(secret));
  s = snprintf(link, sizeof(link), "%s/link.txt", root);
  ASSERT(s >= 0 && (size_t)s < sizeof(link));

  FILE* f = fopen(inside, "wb");
  ASSERT_NOT_NULL(f);
  fputs("old", f);
  fclose(f);
  f = fopen(secret, "wb");
  ASSERT_NOT_NULL(f);
  fputs("secret", f);
  fclose(f);
  ASSERT_EQ(symlink(secret, link), 0);

  test_rt rt = test_rt_new();
  pl_thread* t = rt.t;
  t->rplan_f = true;
  t->rplan_file_root_c = root;

  static const uint8_t inside_bytes[] = "inside-ok\001";
  ASSERT_EQ(test_op82_write_file(t, "out.txt", inside_bytes,
                                 sizeof(inside_bytes) - 1),
            1);
  ASSERT(test_file_eq(inside, "inside-ok"));

  static const uint8_t leak_bytes[] = "leaked\001";
  ASSERT_EQ(test_op82_write_file(t, "../secret.txt", leak_bytes,
                                 sizeof(leak_bytes) - 1),
            0);
  ASSERT(test_file_eq(secret, "secret"));

  ASSERT_EQ(
      test_op82_write_file(t, "link.txt", leak_bytes, sizeof(leak_bytes) - 1),
      0);
  ASSERT(test_file_eq(secret, "secret"));

  test_rt_free(&rt);
}

TEST(op82, spawn_normalizes_fn_at_initiation) {
  test_rt rt = test_rt_new();
  pl_thread* t = rt.t;
  t->rplan_f = true;
  size_t base = t->vsp;
  pl_vpush(t, test_thunk(t, 7));
  pl_val args[1] = {t->vstack[base]};
  pl_thread_start(t,
                  test_op82_thunk(t, ax_s5('S', 'p', 'a', 'w', 'n'), 1, args));
  ASSERT_EQ(test_run(t), PL_RUN_BLOCKED);

  pl_cell* p = pl_as(PL_TAG_APP, pl_thread_request(t));
  ASSERT_NOT_NULL(p);
  ASSERT_EQ(pl_app_head(p), ax_s5('S', 'p', 'a', 'w', 'n'));
  ASSERT_EQ(pl_app_n(p), 1);
  ASSERT_EQ(pl_app_args(p)[0], 7); /* forced at initiation */

  pl_thread_deposit(t, 1); /* fresh child handle */
  ASSERT_EQ(test_run(t), PL_RUN_DONE);
  ASSERT_EQ(pl_thread_result(t), 1);
  t->vsp = base;
  test_rt_free(&rt);
}

TEST(op82, payload_effects_block_before_the_request) {
  test_rt rt = test_rt_new();
  pl_thread* t = rt.t;
  t->rplan_f = true;
  /* Send a payload whose normalization performs a Recv: the inner
   * effect blocks FIRST, as the sender's own execution, and only then
   * does the Send request park with the settled payload. */
  size_t base = t->vsp;
  pl_val rargs[1] = {0};
  pl_vpush(t, test_op82_thunk(t, ax_s4('R', 'e', 'c', 'v'), 1, rargs));
  pl_val sargs[2] = {3, t->vstack[base]};
  pl_thread_start(t, test_op82_thunk(t, ax_s4('S', 'e', 'n', 'd'), 2, sargs));

  ASSERT_EQ(test_run(t), PL_RUN_BLOCKED);
  pl_cell* p = pl_as(PL_TAG_APP, pl_thread_request(t));
  ASSERT_NOT_NULL(p);
  ASSERT_EQ(pl_app_head(p), ax_s4('R', 'e', 'c', 'v')); /* inner first */

  pl_thread_deposit(t, 5);
  ASSERT_EQ(test_run(t), PL_RUN_BLOCKED);
  p = pl_as(PL_TAG_APP, pl_thread_request(t));
  ASSERT_NOT_NULL(p);
  ASSERT_EQ(pl_app_head(p), ax_s4('S', 'e', 'n', 'd'));
  ASSERT_EQ(pl_app_args(p)[0], 3);
  ASSERT_EQ(pl_app_args(p)[1], 5); /* the deposited response */

  pl_thread_deposit(t, 0);
  ASSERT_EQ(test_run(t), PL_RUN_DONE);
  ASSERT_EQ(pl_thread_result(t), 0);
  t->vsp = base;
  test_rt_free(&rt);
}

TEST(op82, recv_inside_nor_conditional) {
  test_rt rt = test_rt_new();
  pl_thread* t = rt.t;
  t->rplan_f = true;
  /* (P66 % (Nor 0 <recv>)): Nor's conditional strictness is an F_NIL
   * frame, so the forced arm may block — no C-entry remains. */
  size_t base = t->vsp;
  pl_val rargs[1] = {0};
  pl_vpush(t, test_op82_thunk(t, ax_s4('R', 'e', 'c', 'v'), 1, rargs));
  pl_val nargs[2] = {0, t->vstack[base]};
  pl_vpush(t, test_app(t, ax_s3('N', 'o', 'r'), 2, nargs));
  pl_vpush(t, test_app1(t, 0, t->vstack[base + 1])); /* (0 norrow) */
  pl_vpush(t, test_app1(t, 0, test_p66(t)));         /* (0 P66)    */
  pl_val expr = test_app2(t, 0, t->vstack[base + 3], t->vstack[base + 2]);
  t->vsp = base;
  pl_thread_start(t, test_thunk(t, expr));

  ASSERT_EQ(test_run(t), PL_RUN_BLOCKED);
  pl_cell* p = pl_as(PL_TAG_APP, pl_thread_request(t));
  ASSERT_NOT_NULL(p);
  ASSERT_EQ(pl_app_head(p), ax_s4('R', 'e', 'c', 'v'));

  pl_thread_deposit(t, 0); /* planNil 0 = 1 */
  ASSERT_EQ(test_run(t), PL_RUN_DONE);
  ASSERT_EQ(pl_thread_result(t), 1);
  test_rt_free(&rt);
}

TEST(op82, recv_inside_dynamic_law_body) {
  test_rt rt = test_rt_new();
  pl_thread* t = rt.t;
  t->rplan_f = true;
  /* A law whose body field is a thunk that performs a Recv: JUDGE's
   * chain scan suspends under the F_JUDGE frame and resumes with the
   * deposited value as the body.  The response (1 5 7) is a let chain,
   * so the scan also continues correctly after the resume. */
  size_t base = t->vsp;
  pl_val rargs[1] = {0};
  pl_vpush(t, test_op82_thunk(t, ax_s4('R', 'e', 'c', 'v'), 1, rargs));
  pl_vpush(t, test_law(t, 1, 0, t->vstack[base]));   /* body = recv thunk */
  pl_vpush(t, test_app1(t, 0, t->vstack[base + 1])); /* (0 L) */
  pl_vpush(t, test_app1(t, 0, 0));                   /* (0 0) */
  pl_val expr = test_app2(t, 0, t->vstack[base + 2], t->vstack[base + 3]);
  t->vsp = base;
  pl_thread_start(t, test_thunk(t, expr));

  ASSERT_EQ(test_run(t), PL_RUN_BLOCKED);
  pl_cell* p = pl_as(PL_TAG_APP, pl_thread_request(t));
  ASSERT_NOT_NULL(p);
  ASSERT_EQ(pl_app_head(p), ax_s4('R', 'e', 'c', 'v'));

  size_t rb = t->vsp;
  pl_vpush(t, test_app2(t, 1, 5, 7)); /* body: (1 5 7) — let, then 7 */
  pl_val resp = t->vstack[rb];
  t->vsp = rb;
  pl_thread_deposit(t, resp);
  ASSERT_EQ(test_run(t), PL_RUN_DONE);
  ASSERT_EQ(pl_thread_result(t), 7);
  test_rt_free(&rt);
}

TEST(op82, recv_blocks_under_try) {
  test_rt rt = test_rt_new();
  pl_thread* t = rt.t;
  t->rplan_f = true;
  /* (P66 % (Try f 0)) where (f 0) performs a Recv: the Try barrier is
   * a machine frame, so the thread suspends beneath it and the resumed
   * result comes back wrapped as (0 v). */
  size_t base = t->vsp;
  pl_val rargs[1] = {0};
  pl_vpush(t, test_app(t, ax_s4('R', 'e', 'c', 'v'), 1, rargs));
  pl_vpush(t, test_app1(t, 0, t->vstack[base])); /* (0 recvrow) */
  pl_vpush(t, test_app1(t, 0, test_p82(t)));     /* (0 P82)     */
  pl_vpush(t, test_app2(t, 0, t->vstack[base + 2], t->vstack[base + 1]));
  pl_vpush(t, test_law(t, 1, 0, t->vstack[base + 3])); /* f z = recv */
  pl_val targs[2] = {t->vstack[base + 4], 0};
  pl_vpush(t, test_app(t, ax_s3('T', 'r', 'y'), 2, targs));
  pl_vpush(t, test_app1(t, 0, t->vstack[base + 5])); /* (0 tryrow) */
  pl_vpush(t, test_app1(t, 0, test_p66(t)));         /* (0 P66)    */
  pl_val expr = test_app2(t, 0, t->vstack[base + 7], t->vstack[base + 6]);
  t->vsp = base;
  pl_thread_start(t, test_thunk(t, expr));

  ASSERT_EQ(test_run(t), PL_RUN_BLOCKED);
  pl_cell* p = pl_as(PL_TAG_APP, pl_thread_request(t));
  ASSERT_NOT_NULL(p);
  ASSERT_EQ(pl_app_head(p), ax_s4('R', 'e', 'c', 'v'));

  pl_thread_deposit(t, 9);
  ASSERT_EQ(test_run(t), PL_RUN_DONE);
  pl_cell* r = pl_as(PL_TAG_APP, pl_thread_result(t));
  ASSERT_NOT_NULL(r);
  ASSERT_EQ(pl_app_head(r), 0); /* planTry's Right */
  ASSERT_EQ(pl_app_args(r)[0], 9);
  test_rt_free(&rt);
}

TEST(op82, blocked_request_survives_gc) {
  test_rt rt = test_rt_new();
  pl_thread* t = rt.t;
  t->rplan_f = true;
  size_t base = t->vsp;
  pl_vpush(t, test_thunk(t, 7));
  pl_val args[2] = {3, t->vstack[base]};
  pl_thread_start(t, test_op82_thunk(t, ax_s4('S', 'e', 'n', 'd'), 2, args));
  ASSERT_EQ(test_run(t), PL_RUN_BLOCKED);

  pl_gc_collect_now(t); /* moves the request and the parked continuation */
  pl_cell* p = pl_as(PL_TAG_APP, pl_thread_request(t));
  ASSERT_NOT_NULL(p);
  ASSERT_EQ(pl_app_head(p), ax_s4('S', 'e', 'n', 'd'));
  ASSERT_EQ(pl_app_args(p)[0], 3);

  pl_thread_deposit(t, 0);
  ASSERT_EQ(test_run(t), PL_RUN_DONE);
  ASSERT_EQ(pl_thread_result(t), 0);
  t->vsp = base;
  test_rt_free(&rt);
}

TEST(op82, recv_rejects_nonzero_arg) {
  test_rt rt = test_rt_new();
  pl_thread* t = rt.t;
  t->rplan_f = true;
  pl_val args[1] = {1};
  pl_thread_start(t, test_op82_thunk(t, ax_s4('R', 'e', 'c', 'v'), 1, args));
  ASSERT_EQ(test_run(t), PL_RUN_EXN); /* crash path, not catchable */
  ASSERT_NOT_NULL(t->exn_msg);
  test_rt_free(&rt);
}

TEST(op82, unknown_op_is_runtime_error) {
  test_rt rt = test_rt_new();
  pl_thread* t = rt.t;
  t->rplan_f = true;
  pl_val args[1] = {0};
  pl_thread_start(t, test_op82_thunk(t, ax_s4('F', 'r', 'o', 'b'), 1, args));
  ASSERT_EQ(test_run(t), PL_RUN_EXN);
  ASSERT_NOT_NULL(t->exn_msg);
  test_rt_free(&rt);
}

TEST(op82, requires_rplan_mode) {
  test_rt rt = test_rt_new();
  pl_thread* t = rt.t; /* rplan_f defaults to false */
  pl_val args[1] = {0};
  pl_thread_start(t, test_op82_thunk(t, ax_s4('R', 'e', 'c', 'v'), 1, args));
  ASSERT_EQ(test_run(t), PL_RUN_EXN);
  ASSERT_NOT_NULL(t->exn_msg);
  test_rt_free(&rt);
}

TEST(op82, host_entry_has_no_executor) {
  test_rt rt = test_rt_new();
  pl_thread* t = rt.t;
  t->rplan_f = true;
  /* pl_whnf cannot service a coordination op: runtime error on both the
   * direct path (initiation at centry_depth > 0) and the YIELD_STRESS
   * stress drive (PL_RUN_BLOCKED converted to the same raise). */
  pl_val args[1] = {0};
  pl_val v = test_op82_thunk(t, ax_s4('R', 'e', 'c', 'v'), 1, args);
  pl_catch c;
  pl_catch_init(t, &c);
  if (setjmp(c.jb) == 0) {
    (void)pl_whnf(t, v);
    FAIL_TEST("expected a runtime error");
  }
  pl_catch_unwind(t, &c);
  ASSERT_NOT_NULL(t->exn_msg);
  test_rt_free(&rt);
}

TEST(op82, direct_ops_still_run_inline) {
  test_rt rt = test_rt_new();
  pl_thread* t = rt.t;
  t->rplan_f = true;
  /* Now is a direct effect: no suspension, result inline. */
  time_t before = time(NULL);
  ASSERT_NEQ(before, (time_t)-1);
  pl_val args[1] = {0};
  pl_thread_start(t, test_op82_thunk(t, ax_s3('N', 'o', 'w'), 1, args));
  ASSERT_EQ(test_run(t), PL_RUN_DONE);
  time_t after = time(NULL);
  ASSERT_NEQ(after, (time_t)-1);

  pl_val result = pl_thread_result(t);
  ASSERT(pl_is_nat(result));
  uint64_t now_ns = pl_nat_u64_clamp(result);
  ASSERT_GTE(now_ns, (uint64_t)before * UINT64_C(1000000000));
  ASSERT_LT(now_ns, ((uint64_t)after + 1) * UINT64_C(1000000000));
  test_rt_free(&rt);
}
