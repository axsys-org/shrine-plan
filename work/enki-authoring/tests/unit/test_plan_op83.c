#include "test.h"

#include <pthread.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

#include "axsys/profile.h"
#include "test_plan.h"

/*
 * op 83 (HTTP driver) at the plan layer: Fetch is a coordination
 * effect like Send/Recv — the body rebuilds the request spine
 * [Fetch, req, cfg] and the machine parks it with PL_RUN_BLOCKED.
 * Both args deep-normalize at initiation.  All shape/URL validation
 * happens at service time in pkg/enki; none of it is visible here.
 *
 * Redexes are driven through lazy thunks with KAL body code, as in
 * test_plan_op82.c.
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

/* The pin of nat 83, the HTTP driver op set. */
static pl_val test_p83(pl_thread* t) {
  size_t base = t->vsp;
  pl_vpush(t, 83);
  pl_val pin = pl_pin(t, t->vstack[base]);
  t->vsp = base;
  return pin;
}

/* A thunk forcing (P83 % (name args…)): body (0 (0 P83) (0 row)). */
static pl_val test_op83_thunk(pl_thread* t, pl_val name, size_t n,
                              const pl_val* args) {
  size_t base = t->vsp;
  pl_vpush(t, test_app(t, name, n, args));
  pl_vpush(t, test_app1(t, 0, t->vstack[base])); /* (0 row) */
  pl_vpush(t, test_app1(t, 0, test_p83(t)));     /* (0 P83) */
  pl_val expr = test_app2(t, 0, t->vstack[base + 2], t->vstack[base + 1]);
  t->vsp = base;
  return test_thunk(t, expr);
}

static pl_val test_throwing(pl_thread* t, uint64_t code) {
  size_t base = t->vsp;
  pl_val args[1] = {code};
  pl_vpush(t, test_app(t, ax_s5('T', 'h', 'r', 'o', 'w'), 1, args));
  pl_vpush(t, test_app1(t, 0, t->vstack[base]));
  pl_vpush(t, test_app1(t, 0, test_p66(t)));
  pl_val expr = test_app2(t, 0, t->vstack[base + 2], t->vstack[base + 1]);
  t->vsp = base;
  return test_thunk(t, expr);
}

/* Run until the thread leaves the runnable set (2-fuel quanta). */
static pl_run_status test_run(pl_thread* t) {
  pl_run_status s;
  int quanta = 0;
  do {
    s = pl_thread_run(t, 2);
    ASSERT_LT(++quanta, 1 << 20, "runaway resume loop");
  } while (s == PL_RUN_YIELDED);
  return s;
}

static pl_val test_op83(pl_thread* t, pl_val name, size_t n,
                        const pl_val* args) {
  pl_thread_start(t, test_op83_thunk(t, name, n, args));
  ASSERT_EQ(test_run(t), PL_RUN_DONE);
  return pl_thread_result(t);
}

TEST(op83, reaver_string_ops_are_available_through_splan) {
  test_rt rt = test_rt_new();
  pl_thread* t = rt.t;
  t->rplan_f = true;
  size_t base = t->vsp;

  static const uint8_t source[] = {'a', 'a', 'a', 'b'};
  uint8_t mask[32] = {0};
  mask['a' / 8u] = (uint8_t)(1u << ('a' % 8u));
  pl_vpush(t, pl_nat_from_bytes(t, source, sizeof(source)));
  pl_vpush(t, pl_nat_from_bytes(t, mask, sizeof(mask)));
  pl_val scan_args[4] = {
      t->vstack[base],
      0,
      t->vstack[base + 1],
      1,
  };
  pl_val scanned = test_op83(t, ax_s5('s', 'c', 'a', 'n', '8'), 4, scan_args);
  pl_cell* row = pl_as(PL_TAG_APP, scanned);
  ASSERT_NOT_NULL(row);
  ASSERT_EQ(pl_app_head(row), 0);
  ASSERT_EQ(pl_app_n(row), 3);
  ASSERT_EQ(pl_app_args(row)[0], 3);
  ASSERT_EQ(pl_app_args(row)[1], 0);
  ASSERT_EQ(pl_app_args(row)[2], 3);

  static const uint8_t hello[] = {'h', 'e', 'l', 'l', 'o'};
  pl_vpush(t, pl_nat_from_bytes(t, hello, sizeof(hello)));
  pl_val text_args[2] = {
      ax_s4('t', 'e', 'x', 't'),
      t->vstack[t->vsp - 1],
  };
  pl_vpush(t, test_app(t, 0, 2, text_args));
  pl_val tree_args[1] = {t->vstack[t->vsp - 1]};
  ASSERT(pl_nat_eq(
      test_op83(t, ax_s7('S', 't', 'r', 'T', 'r', 'e', 'e'), 1, tree_args),
      t->vstack[t->vsp - 2]));

  t->vsp = base;
  test_rt_free(&rt);
}

#define FETCH ax_s5('F', 'e', 't', 'c', 'h')

static pl_val test_zone_call(pl_thread* t, const char* op_c, pl_val arg,
                             pl_run_status want) {
  size_t base = t->vsp;
  pl_vpush(t, arg);
  pl_vpush(t, pl_nat_from_bytes(t, (const uint8_t*)op_c, strlen(op_c)));
  pl_val args[1] = {t->vstack[base]};
  pl_thread_start(t, test_op83_thunk(t, t->vstack[base + 1], 1, args));
  ASSERT_EQ(test_run(t), want);
  pl_val result = want == PL_RUN_DONE ? pl_thread_result(t) : 0;
  t->vsp = base;
  return result;
}

static char* test_read_file(const char* path) {
  FILE* f = fopen(path, "rb");
  ASSERT_NOT_NULL(f, "failed to open `%s`", path);
  ASSERT_EQ(fseek(f, 0, SEEK_END), 0);
  long end = ftell(f);
  ASSERT_GTE(end, 0);
  ASSERT_EQ(fseek(f, 0, SEEK_SET), 0);
  char* data = malloc((size_t)end + 1);
  ASSERT_NOT_NULL(data);
  ASSERT_EQ(fread(data, 1, (size_t)end, f), (size_t)end);
  data[end] = '\0';
  ASSERT_EQ(fclose(f), 0);
  return data;
}

static size_t test_count(const char* haystack, const char* needle) {
  size_t count = 0;
  size_t needle_n = strlen(needle);
  for (const char* p = haystack; (p = strstr(p, needle)) != NULL; p += needle_n)
    count++;
  return count;
}

TEST(op83, zones_have_distinct_handles_and_end_non_lifo) {
  test_rt rt = test_rt_new();
  pl_thread* t = rt.t;
  t->rplan_f = true;
  size_t base = t->vsp;

  pl_val one = pl_nat_from_bytes(t, (const uint8_t*)"one", 3);
  pl_val h1 = test_zone_call(t, "ZoneStart", one, PL_RUN_DONE);
  pl_vpush(t, h1);
  pl_val two = pl_nat_from_bytes(t, (const uint8_t*)"two", 3);
  pl_val h2 = test_zone_call(t, "ZoneStart", two, PL_RUN_DONE);
  pl_vpush(t, h2);

  ASSERT_NEQ(t->vstack[base], t->vstack[base + 1]);
  ASSERT_EQ(t->profile_zone_n, 2);
  ASSERT_EQ(test_zone_call(t, "ZoneEnd", t->vstack[base], PL_RUN_DONE), 0);
  ASSERT_EQ(t->profile_zone_n, 1);
  ASSERT_EQ(t->profile_zones[0].handle, t->vstack[base + 1]);
  ASSERT_EQ(test_zone_call(t, "ZoneEnd", t->vstack[base + 1], PL_RUN_DONE), 0);
  ASSERT_EQ(t->profile_zone_n, 0);

  t->vsp = base;
  test_rt_free(&rt);
}

TEST(op83, zone_handles_reject_duplicate_unknown_and_cross_thread) {
  test_rt rt = test_rt_new();
  pl_thread* t = rt.t;
  t->rplan_f = true;
  size_t base = t->vsp;
  pl_val h = test_zone_call(t, "ZoneStart", 7, PL_RUN_DONE);
  pl_vpush(t, h);
  (void)test_zone_call(t, "ZoneEnd", t->vstack[base], PL_RUN_DONE);
  (void)test_zone_call(t, "ZoneEnd", t->vstack[base], PL_RUN_EXN);
  ASSERT_NOT_NULL(t->exn_msg);

  pl_val h2 = test_zone_call(t, "ZoneStart", 8, PL_RUN_DONE);
  pl_vpush(t, h2);
  pl_thread* other = pl_thread_new(rt.heap);
  other->rplan_f = true;
  (void)test_zone_call(other, "ZoneEnd", t->vstack[base + 1], PL_RUN_EXN);
  ASSERT_NOT_NULL(other->exn_msg);
  ASSERT_EQ(t->profile_zone_n, 1);

  pl_thread_free(other);
  t->vsp = base;
  test_rt_free(&rt);
}

TEST(op83, zone_start_requires_nat_label) {
  test_rt rt = test_rt_new();
  pl_thread* t = rt.t;
  t->rplan_f = true;
  pl_val not_nat = test_app1(t, 0, 1);
  (void)test_zone_call(t, "ZoneStart", not_nat, PL_RUN_EXN);
  ASSERT_NOT_NULL(t->exn_msg);
  ASSERT_EQ(t->profile_zone_n, 0);
  test_rt_free(&rt);
}

TEST(op83, zone_handle_and_copied_label_survive_gc) {
  test_rt rt = test_rt_new();
  pl_thread* t = rt.t;
  t->rplan_f = true;
  static const uint8_t label[] = "a label longer than an immediate nat";
  pl_val h = test_zone_call(t, "ZoneStart",
                            pl_nat_from_bytes(t, label, sizeof(label) - 1),
                            PL_RUN_DONE);
  ASSERT_NOT_NULL(pl_as(PL_TAG_APP, h));

  pl_gc_collect_now(t);
  ASSERT_EQ(t->profile_zone_n, 1);
  ASSERT_EQ(t->profile_zones[0].name_n, sizeof(label) - 1);
  ASSERT_MEM_EQ(t->profile_zones[0].name, label, sizeof(label) - 1);
  (void)test_zone_call(t, "ZoneEnd", t->profile_zones[0].handle, PL_RUN_DONE);
  ASSERT_EQ(t->profile_zone_n, 0);
  test_rt_free(&rt);
}

TEST(op83, host_unwind_discards_zones_created_inside_catch) {
  test_rt rt = test_rt_new();
  pl_thread* t = rt.t;
  t->rplan_f = true;
  pl_catch c;
  pl_catch_init(t, &c);
  if (setjmp(c.jb) == 0) {
    (void)test_zone_call(t, "ZoneStart", 9, PL_RUN_DONE);
    ASSERT_EQ(t->profile_zone_n, 1);
    pl_raise(t, 42);
  }
  pl_catch_unwind(t, &c);
  ASSERT_EQ(t->profile_zone_n, 0);
  test_rt_free(&rt);
}

TEST(op83, zone_pauses_across_yield_block_and_resume) {
  test_rt rt = test_rt_new();
  pl_thread* t = rt.t;
  t->rplan_f = true;
  (void)test_zone_call(t, "ZoneStart", 10, PL_RUN_DONE);

  pl_val args[2] = {11, 12};
  pl_thread_start(t, test_op83_thunk(t, FETCH, 2, args));
  ASSERT_EQ(test_run(t), PL_RUN_BLOCKED);
  ASSERT_EQ(t->profile_zone_n, 1);
  ASSERT_FALSE(t->profile_zones[0].live);
  pl_thread_deposit(t, 0);
  ASSERT_EQ(test_run(t), PL_RUN_DONE);
  ASSERT_EQ(t->profile_zone_n, 1);
  ASSERT_FALSE(t->profile_zones[0].live);

  (void)test_zone_call(t, "ZoneEnd", t->profile_zones[0].handle, PL_RUN_DONE);
  test_rt_free(&rt);
}

static pl_val test_start_then_throw_fetch(pl_thread* t) {
  size_t base = t->vsp;
  pl_vpush(t, pl_nat_from_bytes(t, (const uint8_t*)"ZoneStart", 9));
  pl_val start_args[1] = {13};
  pl_vpush(t, test_op83_thunk(t, t->vstack[base], 1, start_args));
  pl_vpush(t, test_throwing(t, 77));
  pl_val fetch_args[2] = {t->vstack[base + 1], t->vstack[base + 2]};
  pl_val out = test_op83_thunk(t, FETCH, 2, fetch_args);
  t->vsp = base;
  return out;
}

TEST(op83, uncaught_exception_discards_zones_from_failed_run) {
  test_rt rt = test_rt_new();
  pl_thread* t = rt.t;
  t->rplan_f = true;
  pl_thread_start(t, test_start_then_throw_fetch(t));
  ASSERT_EQ(test_run(t), PL_RUN_EXN);
  ASSERT_NULL(t->exn_msg);
  ASSERT_EQ(t->exn, 77);
  ASSERT_EQ(t->profile_zone_n, 0);
  test_rt_free(&rt);
}

TEST(op83, try_discards_zones_created_inside_caught_region) {
  test_rt rt = test_rt_new();
  pl_thread* t = rt.t;
  t->rplan_f = true;
  size_t base = t->vsp;
  pl_vpush(t, test_start_then_throw_fetch(t));
  pl_vpush(t, test_law(t, 1, 0, t->vstack[base]));
  pl_val args[2] = {t->vstack[base + 1], 0};
  pl_val result = test_op66(t, ax_s3('T', 'r', 'y'), 2, args);
  pl_cell* p = pl_as(PL_TAG_APP, result);
  ASSERT_NOT_NULL(p);
  ASSERT_EQ(pl_app_head(p), 1);
  ASSERT_EQ(pl_app_args(p)[0], 77);
  ASSERT_EQ(t->profile_zone_n, 0);
  t->vsp = base;
  test_rt_free(&rt);
}

TEST(op83, chrome_json_escapes_labels_and_splits_host_entries) {
  char path[] = "/tmp/enki-profile-zone-XXXXXX";
  int fd = mkstemp(path);
  ASSERT_GTE(fd, 0);
  ASSERT_EQ(close(fd), 0);

  ASSERT(ax_profile_json_start(path));
  test_rt rt = test_rt_new();
  pl_thread* t = rt.t;
  t->rplan_f = true;
  const uint8_t label[] = {'a', '"', '\\', '/', '\n', 0x80};
  pl_val h = test_zone_call(
      t, "ZoneStart", pl_nat_from_bytes(t, label, sizeof(label)), PL_RUN_DONE);
  (void)test_zone_call(t, "ZoneEnd", h, PL_RUN_DONE);
  test_rt_free(&rt);
  ASSERT(ax_profile_json_finish());

  char* json = test_read_file(path);
  ASSERT_NOT_NULL(strstr(json, "{\"traceEvents\":["));
  ASSERT_NOT_NULL(strstr(json, "\"cat\":\"splan.zone\""));
  ASSERT_NOT_NULL(strstr(json, "\"ph\":\"M\""));
  ASSERT_NOT_NULL(strstr(json, "PLAN thread "));
  ASSERT_NOT_NULL(strstr(json, "a\\\"\\\\\\/\\n\\u0080"));
  size_t begins = test_count(json, "\"ph\":\"B\"");
  size_t ends = test_count(json, "\"ph\":\"E\"");
  ASSERT_GTE(begins, 2); /* at least one segment per host entry */
  ASSERT_EQ(begins, ends);
  ASSERT_NOT_NULL(strstr(json, "\"args\":{\"zone\":"));
  ASSERT_NOT_NULL(strstr(json, "],\"displayTimeUnit\":\"ms\"}"));
  free(json);
  ASSERT_EQ(unlink(path), 0);
}

typedef struct test_json_worker_args {
  uint64_t tid;
} test_json_worker_args;

static void* test_json_worker(void* arg_v) {
  test_json_worker_args* arg = arg_v;
  char name[32];
  int n = snprintf(name, sizeof(name), "PLAN thread %llu",
                   (unsigned long long)arg->tid);
  ax_profile_json_thread_name(arg->tid, name, (size_t)n);
  for (uint64_t i = 0; i < 100; i++) {
    ax_profile_json_zone_begin(arg->tid, i, (const uint8_t*)"work", 4);
    ax_profile_json_zone_end(arg->tid, i, (const uint8_t*)"work", 4);
  }
  return NULL;
}

TEST(op83, chrome_json_serializes_concurrent_lanes) {
  char path[] = "/tmp/enki-profile-concurrent-XXXXXX";
  int fd = mkstemp(path);
  ASSERT_GTE(fd, 0);
  ASSERT_EQ(close(fd), 0);
  ASSERT(ax_profile_json_start(path));

  pthread_t threads[2];
  test_json_worker_args args[2] = {{.tid = 101}, {.tid = 202}};
  for (size_t i = 0; i < 2; i++)
    ASSERT_EQ(pthread_create(&threads[i], NULL, test_json_worker, &args[i]), 0);
  for (size_t i = 0; i < 2; i++)
    ASSERT_EQ(pthread_join(threads[i], NULL), 0);
  ASSERT(ax_profile_json_finish());

  char* json = test_read_file(path);
  ASSERT_EQ(test_count(json, "\"ph\":\"M\""), 2);
  ASSERT_EQ(test_count(json, "\"ph\":\"B\""), 200);
  ASSERT_EQ(test_count(json, "\"ph\":\"E\""), 200);
  ASSERT_NOT_NULL(strstr(json, "\"tid\":101"));
  ASSERT_NOT_NULL(strstr(json, "\"tid\":202"));
  free(json);
  ASSERT_EQ(unlink(path), 0);
}

TEST(op83, readfolder_parks_then_deposit_resumes) {
  test_rt rt = test_rt_new();
  pl_thread* t = rt.t;
  t->rplan_f = true;
  size_t base = t->vsp;
  pl_vpush(t, pl_nat_from_bytes(t, (const uint8_t*)"ReadFolder", 10));
  pl_vpush(t, pl_nat_from_bytes(t, (const uint8_t*)"folder", 6));
  pl_val args[1] = {t->vstack[base + 1]};
  pl_thread_start(t, test_op83_thunk(t, t->vstack[base], 1, args));
  ASSERT_EQ(test_run(t), PL_RUN_BLOCKED);

  pl_cell* p = pl_as(PL_TAG_APP, pl_thread_request(t));
  ASSERT_NOT_NULL(p);
  ASSERT_EQ(pl_app_head(p), t->vstack[base]);
  ASSERT_EQ(pl_app_n(p), 1);
  ASSERT_EQ(pl_app_args(p)[0], t->vstack[base + 1]);

  pl_thread_deposit(t, 0);
  ASSERT_EQ(test_run(t), PL_RUN_DONE);
  ASSERT_EQ(pl_thread_result(t), 0);
  t->vsp = base;
  test_rt_free(&rt);
}

TEST(op83, fetch_parks_then_deposit_resumes) {
  test_rt rt = test_rt_new();
  pl_thread* t = rt.t;
  t->rplan_f = true;
  size_t vsp0 = t->vsp, fsp0 = t->fsp;
  pl_val args[2] = {11, 22}; /* opaque to the plan layer */
  pl_thread_start(t, test_op83_thunk(t, FETCH, 2, args));
  ASSERT_EQ(test_run(t), PL_RUN_BLOCKED);

  pl_cell* p = pl_as(PL_TAG_APP, pl_thread_request(t));
  ASSERT_NOT_NULL(p);
  ASSERT_EQ(pl_app_head(p), FETCH);
  ASSERT_EQ(pl_app_n(p), 2);
  ASSERT_EQ(pl_app_args(p)[0], 11);
  ASSERT_EQ(pl_app_args(p)[1], 22);

  /* a synthetic (0 resp) result row, as the executor would deposit */
  size_t rb = t->vsp;
  pl_vpush(t, test_app1(t, 0, 200));
  pl_val resp = t->vstack[rb];
  t->vsp = rb;
  pl_thread_deposit(t, resp);
  ASSERT_EQ(t->blocked_on, 0);
  ASSERT_EQ(test_run(t), PL_RUN_DONE);
  pl_cell* r = pl_as(PL_TAG_APP, pl_thread_result(t));
  ASSERT_NOT_NULL(r);
  ASSERT_EQ(pl_app_head(r), 0);
  ASSERT_EQ(pl_app_args(r)[0], 200);
  ASSERT_EQ(t->vsp, vsp0);
  ASSERT_EQ(t->fsp, fsp0);
  test_rt_free(&rt);
}

TEST(op83, fetch_normalizes_both_args_at_initiation) {
  test_rt rt = test_rt_new();
  pl_thread* t = rt.t;
  t->rplan_f = true;
  size_t base = t->vsp;
  pl_vpush(t, test_thunk(t, 7)); /* req: forced by the deep mask */
  pl_vpush(t, test_thunk(t, 9)); /* cfg: forced by the deep mask */
  pl_val args[2] = {t->vstack[base], t->vstack[base + 1]};
  pl_thread_start(t, test_op83_thunk(t, FETCH, 2, args));
  ASSERT_EQ(test_run(t), PL_RUN_BLOCKED);

  pl_cell* p = pl_as(PL_TAG_APP, pl_thread_request(t));
  ASSERT_NOT_NULL(p);
  ASSERT_EQ(pl_app_head(p), FETCH);
  ASSERT_EQ(pl_app_n(p), 2);
  /* both payloads were deep-normalized before the request parked */
  ASSERT_EQ(pl_app_args(p)[0], 7);
  ASSERT_EQ(pl_app_args(p)[1], 9);

  pl_thread_deposit(t, 0);
  ASSERT_EQ(test_run(t), PL_RUN_DONE);
  ASSERT_EQ(pl_thread_result(t), 0);
  t->vsp = base;
  test_rt_free(&rt);
}

TEST(op83, payload_effects_block_before_the_request) {
  test_rt rt = test_rt_new();
  pl_thread* t = rt.t;
  t->rplan_f = true;
  /* A Fetch whose cfg normalization performs a Recv: the inner effect
   * blocks FIRST, as the caller's own execution, and only then does
   * the Fetch request park with the settled payload. */
  size_t base = t->vsp;
  pl_val rargs[1] = {0};
  pl_vpush(t, test_app(t, ax_s4('R', 'e', 'c', 'v'), 1, rargs));
  pl_vpush(t, test_app1(t, 0, t->vstack[base])); /* (0 recvrow) */
  size_t pb = t->vsp;
  pl_vpush(t, 82);
  pl_vpush(t, pl_pin(t, t->vstack[pb]));
  pl_vpush(t, test_app1(t, 0, t->vstack[pb + 1])); /* (0 P82) */
  pl_vpush(t, test_app2(t, 0, t->vstack[pb + 2], t->vstack[base + 1]));
  pl_val recv = test_thunk(t, t->vstack[pb + 3]);
  t->vsp = base;
  pl_vpush(t, recv);

  pl_val fargs[2] = {5, t->vstack[base]};
  pl_thread_start(t, test_op83_thunk(t, FETCH, 2, fargs));

  ASSERT_EQ(test_run(t), PL_RUN_BLOCKED);
  pl_cell* p = pl_as(PL_TAG_APP, pl_thread_request(t));
  ASSERT_NOT_NULL(p);
  ASSERT_EQ(pl_app_head(p), ax_s4('R', 'e', 'c', 'v')); /* inner first */

  pl_thread_deposit(t, 6);
  ASSERT_EQ(test_run(t), PL_RUN_BLOCKED);
  p = pl_as(PL_TAG_APP, pl_thread_request(t));
  ASSERT_NOT_NULL(p);
  ASSERT_EQ(pl_app_head(p), FETCH);
  ASSERT_EQ(pl_app_args(p)[0], 5);
  ASSERT_EQ(pl_app_args(p)[1], 6); /* the deposited response */

  pl_thread_deposit(t, 0);
  ASSERT_EQ(test_run(t), PL_RUN_DONE);
  ASSERT_EQ(pl_thread_result(t), 0);
  t->vsp = base;
  test_rt_free(&rt);
}

TEST(op83, requires_rplan_mode) {
  test_rt rt = test_rt_new();
  pl_thread* t = rt.t; /* rplan_f defaults to false */
  pl_val args[2] = {11, 22};
  pl_thread_start(t, test_op83_thunk(t, FETCH, 2, args));
  ASSERT_EQ(test_run(t), PL_RUN_EXN);
  ASSERT_NOT_NULL(t->exn_msg);
  test_rt_free(&rt);
}

TEST(op83, unknown_op_is_runtime_error) {
  test_rt rt = test_rt_new();
  pl_thread* t = rt.t;
  t->rplan_f = true;
  pl_val args[2] = {11, 22};
  pl_thread_start(t, test_op83_thunk(t, ax_s4('F', 'r', 'o', 'b'), 2, args));
  ASSERT_EQ(test_run(t), PL_RUN_EXN);
  ASSERT_NOT_NULL(t->exn_msg);
  test_rt_free(&rt);
}

TEST(op83, wrong_arity_is_runtime_error) {
  test_rt rt = test_rt_new();
  pl_thread* t = rt.t;
  t->rplan_f = true;
  /* Fetch is argc 2; a 1-arg row has no matching bucket entry. */
  pl_val args[1] = {11};
  pl_thread_start(t, test_op83_thunk(t, FETCH, 1, args));
  ASSERT_EQ(test_run(t), PL_RUN_EXN);
  ASSERT_NOT_NULL(t->exn_msg);
  test_rt_free(&rt);
}

TEST(op83, blocked_request_survives_gc) {
  test_rt rt = test_rt_new();
  pl_thread* t = rt.t;
  t->rplan_f = true;
  size_t base = t->vsp;
  pl_vpush(t, test_thunk(t, 7));
  pl_val args[2] = {t->vstack[base], 3};
  pl_thread_start(t, test_op83_thunk(t, FETCH, 2, args));
  ASSERT_EQ(test_run(t), PL_RUN_BLOCKED);

  pl_gc_collect_now(t); /* moves the request and the parked continuation */
  pl_cell* p = pl_as(PL_TAG_APP, pl_thread_request(t));
  ASSERT_NOT_NULL(p);
  ASSERT_EQ(pl_app_head(p), FETCH);
  ASSERT_EQ(pl_app_args(p)[0], 7);
  ASSERT_EQ(pl_app_args(p)[1], 3);

  pl_thread_deposit(t, 0);
  ASSERT_EQ(test_run(t), PL_RUN_DONE);
  ASSERT_EQ(pl_thread_result(t), 0);
  t->vsp = base;
  test_rt_free(&rt);
}

/* Hex is in wire order; bars store those bytes little-endian plus 0x01. */
static pl_val test_crypto_bar(pl_thread* t, const char* hex) {
  size_t n = strlen(hex) / 2;
  uint8_t bytes[1025];
  ASSERT_LT(n, sizeof(bytes));
  for (size_t i = 0; i < n; i++) {
    unsigned int byte;
    ASSERT_EQ(sscanf(hex + 2 * i, "%2x", &byte), 1);
    bytes[i] = (uint8_t)byte;
  }
  bytes[n] = 1;
  return pl_nat_from_bytes(t, bytes, n + 1);
}

/* Arguments live in rooted slots; copy them after allocating the long name. */
static pl_val test_crypto_thunk(pl_thread* t, const char* name, size_t n,
                                size_t args_base) {
  pl_val op = pl_nat_from_bytes(t, (const uint8_t*)name, strlen(name));
  pl_val args[3];
  ASSERT_LT(n, 4);
  for (size_t i = 0; i < n; i++)
    args[i] = t->vstack[args_base + i];
  return test_op83_thunk(t, op, n, args);
}

static pl_val test_crypto(pl_thread* t, const char* name, size_t n,
                          size_t args_base) {
  pl_thread_start(t, test_crypto_thunk(t, name, n, args_base));
  ASSERT_EQ(test_run(t), PL_RUN_DONE);
  return pl_thread_result(t);
}

TEST(op83, crypto_hash_known_answers) {
  const char* names[] = {"Blake3", "Sha256"};
  const char* messages[] = {"", "616263", "00"};
  const char* digests[2][3] = {
      {"af1349b9f5f9a1a6a0404dea36dcc9499bcb25c9adc112b7cc9a93cae41f3262",
       "6437b3ac38465133ffb63b75273a8db548c558465d79db03fd359c6cd5bd9d85",
       "2d3adedff11b61f14c886e35afa036736dcd87a74d27b5c1510225d0f592e213"},
      {"e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
       "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad",
       "6e340b9cffb37a989ca544e6bb780a2c78901d3fb33738768511a30617afa01d"}};
  test_rt rt = test_rt_new();
  pl_thread* t = rt.t;
  t->rplan_f = true;
  size_t base = t->vsp;
  for (size_t alg = 0; alg < 2; alg++) {
    for (size_t msg = 0; msg < 3; msg++) {
      pl_vpush(t, test_crypto_bar(t, messages[msg]));
      pl_vpush(t, test_crypto_bar(t, digests[alg][msg]));
      pl_val out = test_crypto(t, names[alg], 1, base);
      ASSERT(pl_nat_eq(out, t->vstack[base + 1]));
      ASSERT_EQ(pl_nat_byte_len(out), 33);
      t->vsp = base;
    }
  }
  test_rt_free(&rt);
}

TEST(op83, ed25519_rfc8032_and_tampering) {
  /* RFC 8032 section 7.1, test 1 (empty message). */
  test_rt rt = test_rt_new();
  pl_thread* t = rt.t;
  t->rplan_f = true;
  size_t base = t->vsp;
  pl_vpush(
      t,
      test_crypto_bar(
          t,
          "9d61b19deffd5a60ba844af492ec2cc44449c5697b326919703bac031cae7f60"));
  pl_vpush(t, 1);
  pl_vpush(
      t,
      test_crypto_bar(
          t,
          "e5564300c360ac729086e2cc806e828a84877f1eb8e5d974d873e06522490155"
          "5fb8821590a33bacc61e39701cf9b46bd25bf5f0595bbe24655141438e7a100b"));
  pl_vpush(
      t,
      test_crypto_bar(
          t,
          "d75a980182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f707511a"));
  pl_val pk = test_crypto(t, "Ed25519PublicKey", 1, base);
  ASSERT(pl_nat_eq(pk, t->vstack[base + 3]));
  pl_val sig = test_crypto(t, "Ed25519Sign", 2, base);
  ASSERT(pl_nat_eq(sig, t->vstack[base + 2]));
  ASSERT_EQ(pl_nat_byte_len(sig), 65);
  t->vstack[base] = t->vstack[base + 3];
  ASSERT_EQ(test_crypto(t, "Ed25519Verify", 3, base), 1);
  t->vstack[base + 1] = 256; /* one zero byte, distinct from empty */
  ASSERT_EQ(test_crypto(t, "Ed25519Verify", 3, base), 0);
  t->vstack[base + 1] = 1;
  t->vstack[base + 2] = pl_nat_inc(t, &t->vstack[base + 2]);
  ASSERT_EQ(test_crypto(t, "Ed25519Verify", 3, base), 0);
  t->vstack[base + 2] = 1; /* wrong signature length */
  ASSERT_EQ(test_crypto(t, "Ed25519Verify", 3, base), 0);
  t->vstack[base] = 1; /* wrong key length */
  ASSERT_EQ(test_crypto(t, "Ed25519Verify", 3, base), 0);
  t->vsp = base;
  test_rt_free(&rt);
}

TEST(op83, crypto_rejects_malformed_bars_and_wrong_seed_lengths) {
  const char* names[] = {"Blake3", "Sha256", "Ed25519PublicKey", "Ed25519Sign"};
  for (size_t op = 0; op < 4; op++) {
    for (size_t input = 0; input < 4; input++) {
      test_rt rt = test_rt_new();
      pl_thread* t = rt.t;
      t->rplan_f = true;
      size_t base = t->vsp;
      pl_val malformed[] = {0, 2, 0x0261};
      pl_vpush(t, input < 3 ? malformed[input] : test_app1(t, 0, 1));
      pl_vpush(t, 1);
      pl_thread_start(t,
                      test_crypto_thunk(t, names[op], op == 3 ? 2 : 1, base));
      ASSERT_EQ(test_run(t), PL_RUN_EXN);
      ASSERT_NOT_NULL(t->exn_msg);
      t->vsp = base;
      test_rt_free(&rt);
    }
  }
  for (size_t len = 31; len <= 33; len += 2) {
    test_rt rt = test_rt_new();
    pl_thread* t = rt.t;
    t->rplan_f = true;
    uint8_t bytes[34] = {0};
    bytes[len] = 1;
    size_t base = t->vsp;
    pl_vpush(t, pl_nat_from_bytes(t, bytes, len + 1));
    pl_vpush(t, 1);
    pl_thread_start(t, test_crypto_thunk(t, "Ed25519Sign", 2, base));
    ASSERT_EQ(test_run(t), PL_RUN_EXN);
    t->vsp = base;
    test_rt_free(&rt);
  }
}

TEST(op83, crypto_requires_rplan_mode_and_correct_arity) {
  test_rt rt = test_rt_new();
  pl_thread* t = rt.t;
  size_t base = t->vsp;
  pl_vpush(t, 1);
  pl_vpush(t, 1);
  pl_thread_start(t, test_crypto_thunk(t, "Blake3", 1, base));
  ASSERT_EQ(test_run(t), PL_RUN_EXN);
  t->rplan_f = true;
  pl_thread_start(t, test_crypto_thunk(t, "Blake3", 2, base));
  ASSERT_EQ(test_run(t), PL_RUN_EXN);
  t->vsp = base;
  test_rt_free(&rt);
}

TEST(op83, keyed_hash_known_answers) {
  /* BLAKE3 upstream vectors (input bytes 0..250 repeated), plus HMAC
   * RFC 4231 cases 1, 2, and 6. Empty/binary cases use Python hmac vectors. */
  static const struct {
    const char* op;
    const char* key;
    const char* message;
    const char* digest;
  } vectors[] = {
      {"Blake3Keyed",
       "77686174732074686520456c7669736820776f726420666f7220667269656e64", "",
       "92b2b75604ed3c761f9d6f62392c8a9227ad0ea3f09573e783f1498a4ed60d26"},
      {"Blake3Keyed",
       "77686174732074686520456c7669736820776f726420666f7220667269656e64", "00",
       "6d7878dfff2f485635d39013278ae14f1454b8c0a3a2d34bc1ab38228a80c95b"},
      {"HmacSha256", "0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b0b",
       "4869205468657265",
       "b0344c61d8db38535ca8afceaf0bf12b881dc200c9833da726e9376c2e32cff7"},
      {"HmacSha256", "4a656665",
       "7768617420646f2079612077616e7420666f72206e6f7468696e673f",
       "5bdcc146bf60754e6a042426089575c75a003f089d2739839dec58b964ec3843"},
      {"HmacSha256",
       "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
       "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
       "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
       "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
       "54657374205573696e67204c6172676572205468616e20426c6f636b2d53697a65204b6"
       "579202d2048617368204b6579204669727374",
       "60e431591ee0b67f0d8a26aacbf5b77f8e0bc6213728c5140546040f0ee37f54"},
      {"HmacSha256", "", "",
       "b613679a0814d9ec772f95d778c35fc5ff1697c493715653c6c712144292c5ad"},
      {"HmacSha256", "6b00", "6d00",
       "64d1bce3a9b3c4ed8db8a6c6e63765ca9fcdbe82484c230d9cc92e7fec2ad326"},
  };
  test_rt rt = test_rt_new();
  pl_thread* t = rt.t;
  t->rplan_f = true;
  size_t base = t->vsp;
  for (size_t i = 0; i < sizeof(vectors) / sizeof(vectors[0]); i++) {
    pl_vpush(t, test_crypto_bar(t, vectors[i].key));
    pl_vpush(t, test_crypto_bar(t, vectors[i].message));
    pl_vpush(t, test_crypto_bar(t, vectors[i].digest));
    pl_val out = test_crypto(t, vectors[i].op, 2, base);
    ASSERT(pl_nat_eq(out, t->vstack[base + 2]));
    ASSERT_EQ(pl_nat_byte_len(out), 33);
    t->vsp = base;
  }
  test_rt_free(&rt);
}

TEST(op83, keyed_hash_rejects_malformed_arguments) {
  const char* names[] = {"Blake3Keyed", "HmacSha256"};
  for (size_t op = 0; op < 2; op++) {
    for (size_t arg = 0; arg < 2; arg++) {
      for (size_t bad = 0; bad < 4; bad++) {
        test_rt rt = test_rt_new();
        pl_thread* t = rt.t;
        t->rplan_f = true;
        size_t base = t->vsp;
        uint8_t key[33] = {0};
        key[32] = 1;
        pl_vpush(t, pl_nat_from_bytes(t, key, sizeof(key)));
        pl_vpush(t, 1);
        pl_val malformed[] = {0, 2, 0x0261};
        t->vstack[base + arg] = bad < 3 ? malformed[bad] : test_app1(t, 0, 1);
        pl_thread_start(t, test_crypto_thunk(t, names[op], 2, base));
        ASSERT_EQ(test_run(t), PL_RUN_EXN);
        t->vsp = base;
        test_rt_free(&rt);
      }
    }
  }
  const size_t lengths[] = {0, 31, 33, 64};
  for (size_t i = 0; i < sizeof(lengths) / sizeof(lengths[0]); i++) {
    test_rt rt = test_rt_new();
    pl_thread* t = rt.t;
    t->rplan_f = true;
    size_t base = t->vsp;
    uint8_t key[65] = {0};
    key[lengths[i]] = 1;
    pl_vpush(t, pl_nat_from_bytes(t, key, lengths[i] + 1));
    pl_vpush(t, 1);
    pl_thread_start(t, test_crypto_thunk(t, "Blake3Keyed", 2, base));
    ASSERT_EQ(test_run(t), PL_RUN_EXN);
    t->vsp = base;
    test_rt_free(&rt);
  }
}
