#include "test.h"

#include <stdio.h>
#include <string.h>
#include <sys/stat.h>
#include <unistd.h>

#include "enki/actor.h"
#include "test_plan.h"

/*
 * Event log & replay: direct-effect results and host
 * injections are recorded; a replay run substitutes the recorded
 * results without performing syscalls, verifying (actor, op, args)
 * at every site.  Coordination effects are internal and never logged.
 *
 * Law-body code combinators as in test_enki_actor.c.
 */

static pl_val code_lit(pl_thread* t, pl_val v) {
  return test_app1(t, 0, v);
}

static pl_val code_app(pl_thread* t, pl_val f, pl_val x) {
  return test_app2(t, 0, f, x);
}

static pl_val test_p82(pl_thread* t) {
  size_t base = t->vsp;
  pl_vpush(t, 82);
  pl_val pin = pl_pin(t, t->vstack[base]);
  t->vsp = base;
  return pin;
}

static pl_val test_p83(pl_thread* t) {
  size_t base = t->vsp;
  pl_vpush(t, 83);
  pl_val pin = pl_pin(t, t->vstack[base]);
  t->vsp = base;
  return pin;
}

static pl_val code_effect(pl_thread* t, pl_val name, size_t n,
                          const pl_val* args) {
  size_t base = t->vsp;
  pl_vpush(t, code_lit(t, test_app(t, name, n, args)));
  pl_vpush(t, code_lit(t, test_p82(t)));
  pl_val out = code_app(t, t->vstack[base + 1], t->vstack[base]);
  t->vsp = base;
  return out;
}

static pl_val code_effect83(pl_thread* t, pl_val name, size_t n,
                            const pl_val* args) {
  size_t base = t->vsp;
  pl_vpush(t, code_lit(t, test_app(t, name, n, args)));
  pl_vpush(t, code_lit(t, test_p83(t)));
  pl_val out = code_app(t, t->vstack[base + 1], t->vstack[base]);
  t->vsp = base;
  return out;
}

static pl_val code_seq(pl_thread* t, pl_val a, pl_val b) {
  size_t base = t->vsp;
  pl_vpush(t, a);
  pl_vpush(t, b);
  pl_vpush(t, code_lit(t, ax_s3('S', 'e', 'q')));
  pl_vpush(t, code_app(t, t->vstack[base + 2], t->vstack[base]));
  pl_vpush(t, code_app(t, t->vstack[base + 3], t->vstack[base + 1]));
  pl_vpush(t, code_lit(t, test_p66(t)));
  pl_val out = code_app(t, t->vstack[base + 5], t->vstack[base + 4]);
  t->vsp = base;
  return out;
}

static pl_val actor_fn(pl_thread* t, pl_val body) {
  return test_law(t, 1, 0, body);
}

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

static pl_val recv_code(pl_thread* t) {
  pl_val args[1] = {0};
  return code_effect(t, ax_s4('R', 'e', 'c', 'v'), 1, args);
}

static er_actor* start_recv_actor(er_scheduler* sys) {
  er_actor* a = er_scheduler_actor(sys);
  pl_thread* t = er_actor_thread(a);
  size_t base = t->vsp;
  pl_vpush(t, recv_code(t));
  pl_val fn = actor_fn(t, t->vstack[base]);
  t->vsp = base;
  er_actor_start(a, fn);
  return a;
}

static pl_val recv_result_payload(er_actor* a) {
  ASSERT_EQ(er_actor_state(a), ER_ACTOR_HALTED);
  pl_cell* row = pl_as(PL_TAG_APP, er_actor_result(a));
  ASSERT_NOT_NULL(row);
  ASSERT_EQ(pl_app_head(row), 0);
  ASSERT_EQ(pl_app_n(row), 2);
  return pl_app_args(row)[0];
}

/* An actor whose result is the ReadFile bar of `path`. */
static void start_readfile_actor(er_scheduler* sys, const char* path) {
  er_actor* a = er_scheduler_actor(sys);
  pl_thread* t = er_actor_thread(a);
  size_t base = t->vsp;
  pl_vpush(t, pl_nat_from_bytes(t, (const uint8_t*)path, strlen(path)));
  pl_vpush(t, pl_nat_from_bytes(t, (const uint8_t*)"ReadFile", 8));
  /* read the rooted slots only after every allocating call above */
  pl_val rargs[1] = {t->vstack[base]};
  pl_val body = code_effect(t, t->vstack[base + 1], 1, rargs);
  t->vsp = base;
  er_actor_start(a, actor_fn(t, body));
}

static void start_readfolder_actor(er_scheduler* sys, const char* path) {
  er_actor* a = er_scheduler_actor(sys);
  pl_thread* t = er_actor_thread(a);
  size_t base = t->vsp;
  pl_vpush(t, pl_nat_from_bytes(t, (const uint8_t*)path, strlen(path)));
  pl_vpush(t, pl_nat_from_bytes(t, (const uint8_t*)"ReadFolder", 10));
  pl_val rargs[1] = {t->vstack[base]};
  pl_val body = code_effect83(t, t->vstack[base + 1], 1, rargs);
  t->vsp = base;
  er_actor_start(a, actor_fn(t, body));
}

static void assert_bar(pl_val v, const char* s) {
  size_t n = strlen(s);
  ASSERT(pl_is_nat(v), "expected a bar nat");
  ASSERT_EQ(pl_nat_byte_len(v), n + 1);
  for (size_t i = 0; i < n; i++)
    ASSERT_EQ(pl_nat_byte_at(v, i), (uint8_t)s[i]);
  ASSERT_EQ(pl_nat_byte_at(v, n), 1); /* bar terminator */
}

static bool nat_text_eq(pl_val value, const char* text) {
  size_t n = strlen(text);
  if (!pl_is_nat(value) || pl_nat_byte_len(value) != n)
    return false;
  for (size_t i = 0; i < n; i++)
    if (pl_nat_byte_at(value, i) != (uint8_t)text[i])
      return false;
  return true;
}

static pl_cell* folder_entry(pl_val row, const char* name) {
  pl_cell* row_p = pl_as(PL_TAG_APP, row);
  if (row_p == NULL || pl_app_head(row_p) != 0)
    return NULL;
  for (uint32_t i = 0; i < pl_app_n(row_p); i++) {
    pl_cell* entry = pl_as(PL_TAG_APP, pl_app_args(row_p)[i]);
    if (entry != NULL && pl_app_head(entry) == 0 && pl_app_n(entry) == 2 &&
        nat_text_eq(pl_app_args(entry)[1], name))
      return entry;
  }
  return NULL;
}

TEST(replay, readfile_substitutes_without_syscall) {
  char dir[] = "/tmp/enki-replay-XXXXXX";
  ASSERT_NOT_NULL(mkdtemp(dir));
  char path[256], logpath[256];
  (void)snprintf(path, sizeof(path), "%s/data.txt", dir);
  (void)snprintf(logpath, sizeof(logpath), "%s/run.enkilog", dir);
  FILE* f = fopen(path, "w");
  ASSERT_NOT_NULL(f);
  fputs("alpha", f);
  fclose(f);

  test_rt rt = test_rt_new();

  /* record: the effect really reads the file */
  er_log* log = er_log_new();
  {
    er_scheduler* sys = er_scheduler_new(rt.store, (er_config){0});
    er_scheduler_record(sys, log);
    start_readfile_actor(sys, path);
    ASSERT_EQ(er_scheduler_run(sys), ER_RUN_IDLE);
    er_actor* a = er_scheduler_actor_by_id(sys, 0);
    ASSERT_EQ(er_actor_state(a), ER_ACTOR_HALTED);
    assert_bar(er_actor_result(a), "alpha");
    er_scheduler_free(sys);
  }
  ASSERT_EQ(er_log_events(log), 1);

  /* the log round-trips through a file; the data file is deleted, so
   * only substitution can reproduce the contents */
  ASSERT(er_log_write_file(log, logpath));
  er_log_free(log);
  ASSERT_EQ(unlink(path), 0);
  er_log* loaded = er_log_read_file(logpath);
  ASSERT_NOT_NULL(loaded);
  ASSERT_EQ(er_log_events(loaded), 1);

  {
    er_scheduler* sys = er_scheduler_new(rt.store, (er_config){0});
    er_scheduler_replay(sys, loaded);
    start_readfile_actor(sys, path);
    ASSERT_EQ(er_scheduler_run(sys), ER_RUN_IDLE);
    er_actor* a = er_scheduler_actor_by_id(sys, 0);
    ASSERT_EQ(er_actor_state(a), ER_ACTOR_HALTED);
    assert_bar(er_actor_result(a), "alpha"); /* file no longer exists */
    ASSERT_EQ(er_scheduler_log_cursor(sys), 1);
    er_scheduler_free(sys);
  }
  er_log_free(loaded);
  test_rt_free(&rt);
}

TEST(replay, readfolder_substitutes_without_directory) {
  char dir[] = "/tmp/enki-replay-folder-XXXXXX";
  ASSERT_NOT_NULL(mkdtemp(dir));
  char child[256], file[256], logpath[256];
  (void)snprintf(child, sizeof(child), "%s/subdir", dir);
  (void)snprintf(file, sizeof(file), "%s/plain.txt", dir);
  (void)snprintf(logpath, sizeof(logpath), "%s/run.enkilog", dir);
  ASSERT_EQ(mkdir(child, 0700), 0);
  FILE* f = fopen(file, "w");
  ASSERT_NOT_NULL(f);
  fputs("alpha", f);
  fclose(f);

  test_rt rt = test_rt_new();
  er_log* log = er_log_new();
  {
    er_scheduler* sys = er_scheduler_new(rt.store, (er_config){0});
    er_scheduler_record(sys, log);
    start_readfolder_actor(sys, dir);
    ASSERT_EQ(er_scheduler_run(sys), ER_RUN_IDLE);
    er_actor* a = er_scheduler_actor_by_id(sys, 0);
    pl_val row = er_actor_result(a);
    pl_cell* subdir = folder_entry(row, "subdir");
    ASSERT_NOT_NULL(subdir);
    ASSERT_EQ(pl_app_args(subdir)[0], 1);
    pl_cell* plain = folder_entry(row, "plain.txt");
    ASSERT_NOT_NULL(plain);
    ASSERT_EQ(pl_app_args(plain)[0], 0);
    er_scheduler_free(sys);
  }
  ASSERT_EQ(er_log_events(log), 1);
  ASSERT(er_log_write_file(log, logpath));
  er_log_free(log);
  ASSERT_EQ(unlink(file), 0);
  ASSERT_EQ(rmdir(child), 0);
  er_log* loaded = er_log_read_file(logpath);
  ASSERT_NOT_NULL(loaded);

  {
    er_scheduler* sys = er_scheduler_new(rt.store, (er_config){0});
    er_scheduler_replay(sys, loaded);
    start_readfolder_actor(sys, dir); /* the directory no longer exists */
    ASSERT_EQ(er_scheduler_run(sys), ER_RUN_IDLE);
    er_actor* a = er_scheduler_actor_by_id(sys, 0);
    pl_val row = er_actor_result(a);
    pl_cell* subdir = folder_entry(row, "subdir");
    ASSERT_NOT_NULL(subdir);
    ASSERT_EQ(pl_app_args(subdir)[0], 1);
    pl_cell* plain = folder_entry(row, "plain.txt");
    ASSERT_NOT_NULL(plain);
    ASSERT_EQ(pl_app_args(plain)[0], 0);
    ASSERT_EQ(er_scheduler_log_cursor(sys), 1);
    er_scheduler_free(sys);
  }
  er_log_free(loaded);
  test_rt_free(&rt);
  ASSERT_EQ(unlink(logpath), 0);
  ASSERT_EQ(rmdir(dir), 0);
}

/* Self-ping with a lazy Now payload: the clock read happens while the
 * payload is pinned at send, so the hook fires through the pinning path
 * and the recorded instant is reproduced exactly on replay. */
static pl_val run_now_ping(pl_store* store, const er_log* play, er_log* rec) {
  er_scheduler* sys = er_scheduler_new(store, (er_config){0});
  if (rec != NULL)
    er_scheduler_record(sys, rec);
  if (play != NULL)
    er_scheduler_replay(sys, play);
  er_actor* a = er_scheduler_actor(sys);
  pl_thread* t = er_actor_thread(a);
  size_t base = t->vsp;
  pl_val nargs[1] = {0};
  /* the payload must be a real thunk: a code APP embedded in the row
   * would be data by the under-application invariant and never run */
  pl_vpush(t, test_thunk(t, code_effect(t, ax_s3('N', 'o', 'w'), 1, nargs)));
  pl_val sargs[2] = {0, t->vstack[base]};
  pl_vpush(t, code_effect(t, ax_s4('S', 'e', 'n', 'd'), 2, sargs));
  pl_vpush(t, recv_code(t));
  pl_val body = code_seq(t, t->vstack[base + 1], t->vstack[base + 2]);
  t->vsp = base;
  er_actor_start(a, actor_fn(t, body));

  ASSERT_EQ(er_scheduler_run(sys), ER_RUN_IDLE);
  ASSERT_EQ(er_actor_state(a), ER_ACTOR_HALTED);
  pl_cell* r = pl_as(PL_TAG_APP, er_actor_result(a));
  ASSERT_NOT_NULL(r);
  pl_val instant = pl_app_args(r)[0];
  ASSERT(pl_is_nat63(instant));
  ASSERT_GT(instant, 0);
  if (play != NULL)
    ASSERT_EQ(er_scheduler_log_cursor(sys), er_log_events(play));
  er_scheduler_free(sys);
  return instant;
}

TEST(replay, now_through_pinning_is_stable) {
  test_rt rt = test_rt_new();
  er_log* log = er_log_new();
  pl_val recorded = run_now_ping(rt.store, NULL, log);
  ASSERT_EQ(er_log_events(log), 1); /* messaging is internal: only Now */
  pl_val replayed = run_now_ping(rt.store, log, NULL);
  ASSERT_EQ(replayed, recorded);
  er_log_free(log);
  test_rt_free(&rt);
}

TEST(replay, injections_are_logged_and_verified) {
  test_rt rt = test_rt_new();
  er_log* log = er_log_new();
  {
    er_scheduler* sys = er_scheduler_new(rt.store, (er_config){0});
    er_scheduler_record(sys, log);
    er_actor* a = er_scheduler_actor(sys);
    er_actor_start(a,
                   actor_fn(er_actor_thread(a), recv_code(er_actor_thread(a))));
    ASSERT_EQ(er_scheduler_run(sys), ER_RUN_QUIESCENT);
    er_scheduler_inject(sys, a, 99);
    ASSERT_EQ(er_scheduler_run(sys), ER_RUN_IDLE);
    pl_cell* r = pl_as(PL_TAG_APP, er_actor_result(a));
    ASSERT_NOT_NULL(r);
    ASSERT_EQ(pl_app_args(r)[0], 99);
    er_scheduler_free(sys);
  }
  ASSERT_EQ(er_log_events(log), 1);
  {
    er_scheduler* sys = er_scheduler_new(rt.store, (er_config){0});
    er_scheduler_replay(sys, log);
    er_actor* a = er_scheduler_actor(sys);
    er_actor_start(a,
                   actor_fn(er_actor_thread(a), recv_code(er_actor_thread(a))));
    ASSERT_EQ(er_scheduler_run(sys), ER_RUN_QUIESCENT);
    er_scheduler_inject(sys, a, 99); /* verified against the log */
    ASSERT_EQ(er_scheduler_run(sys), ER_RUN_IDLE);
    pl_cell* r = pl_as(PL_TAG_APP, er_actor_result(a));
    ASSERT_NOT_NULL(r);
    ASSERT_EQ(pl_app_args(r)[0], 99);
    ASSERT_EQ(er_scheduler_log_cursor(sys), 1);
    er_scheduler_free(sys);
  }
  er_log_free(log);
  test_rt_free(&rt);
}

TEST(replay, live_injection_accepts_non_pin_store_snapshot) {
  test_rt rt = test_rt_new();
  pl_thread* host = rt.t;
  size_t base = host->vsp;
  pl_vpush(host, test_app2(host, 0, 17, 23));
  host->vstack[base] = pl_nf(host, host->vstack[base]);
  pl_val payload = pl_store_snapshot_normal(host, host->vstack[base]);
  host->vsp = base;
  ASSERT_EQ(pl_tag(payload), PL_TAG_APP);
  ASSERT(pl_store_owns(rt.store, payload));

  er_scheduler* sys = er_scheduler_new(rt.store, (er_config){0});
  er_actor* a = start_recv_actor(sys);
  ASSERT_EQ(er_scheduler_run(sys), ER_RUN_QUIESCENT);
  er_scheduler_inject(sys, a, payload);
  ASSERT_EQ(er_scheduler_run(sys), ER_RUN_IDLE);

  pl_val received = recv_result_payload(a);
  ASSERT_EQ(received, payload);
  pl_cell* pair = pl_as(PL_TAG_APP, received);
  ASSERT_NOT_NULL(pair);
  ASSERT_EQ(pl_app_head(pair), 0);
  ASSERT_EQ(pl_app_n(pair), 2);
  ASSERT_EQ(pl_app_args(pair)[0], 17);
  ASSERT_EQ(pl_app_args(pair)[1], 23);

  er_scheduler_free(sys);
  test_rt_free(&rt);
}

TEST(replay, hashed_canonical_pin_injection_records_and_replays) {
  test_rt rt = test_rt_new();
  pl_thread* host = rt.t;
  size_t base = host->vsp;
  pl_vpush(host, test_app2(host, 0, 31, 37));
  host->vstack[base] = pl_pin(host, host->vstack[base]);
  uint8_t hash[32];
  char err[192] = {0};
  ASSERT(
      pl_store_save_root(rt.store, host->vstack[base], hash, err, sizeof(err)),
      "%s", err);
  pl_val recorded_payload = pl_store_snapshot_normal(host, host->vstack[base]);
  host->vsp = base;
  ASSERT_EQ(pl_tag(recorded_payload), PL_TAG_PIN);
  ASSERT(pl_store_owns(rt.store, recorded_payload));
  ASSERT(pl_pin_is_hashed(recorded_payload));
  ASSERT_EQ(memcmp(pl_pin_hash(recorded_payload), hash, sizeof(hash)), 0);

  er_log* log = er_log_new();
  {
    er_scheduler* sys = er_scheduler_new(rt.store, (er_config){0});
    er_scheduler_record(sys, log);
    er_actor* a = start_recv_actor(sys);
    ASSERT_EQ(er_scheduler_run(sys), ER_RUN_QUIESCENT);
    er_scheduler_inject(sys, a, recorded_payload);
    ASSERT_EQ(er_scheduler_run(sys), ER_RUN_IDLE);
    pl_val received = recv_result_payload(a);
    ASSERT_EQ(pl_tag(received), PL_TAG_PIN);
    ASSERT_EQ(memcmp(pl_pin_hash(received), hash, sizeof(hash)), 0);
    er_scheduler_free(sys);
  }
  ASSERT_EQ(er_log_events(log), 1);

  {
    pl_val replay_payload = pl_store_load(host, hash);
    ASSERT_EQ(pl_tag(replay_payload), PL_TAG_PIN);
    ASSERT(pl_store_owns(rt.store, replay_payload));
    ASSERT(pl_pin_is_hashed(replay_payload));

    er_scheduler* sys = er_scheduler_new(rt.store, (er_config){0});
    er_scheduler_replay(sys, log);
    er_actor* a = start_recv_actor(sys);
    ASSERT_EQ(er_scheduler_run(sys), ER_RUN_QUIESCENT);
    er_scheduler_inject(sys, a, replay_payload);
    ASSERT_EQ(er_scheduler_run(sys), ER_RUN_IDLE);
    pl_val received = recv_result_payload(a);
    ASSERT_EQ(pl_tag(received), PL_TAG_PIN);
    ASSERT_EQ(memcmp(pl_pin_hash(received), hash, sizeof(hash)), 0);
    ASSERT_EQ(er_scheduler_log_cursor(sys), 1);
    er_scheduler_free(sys);
  }

  er_log_free(log);
  test_rt_free(&rt);
}

TEST(replay, live_systems_are_unaffected_by_the_hook) {
  /* the io hook stays registered globally after a recording system is
   * freed; a plain live system must keep executing effects directly */
  test_rt rt = test_rt_new();
  er_log* log = er_log_new();
  {
    er_scheduler* sys = er_scheduler_new(rt.store, (er_config){0});
    er_scheduler_record(sys, log);
    er_scheduler_free(sys);
  }
  er_log_free(log);
  {
    er_scheduler* sys = er_scheduler_new(rt.store, (er_config){0});
    er_actor* a = er_scheduler_actor(sys);
    pl_thread* t = er_actor_thread(a);
    pl_val nargs[1] = {0};
    er_actor_start(a,
                   actor_fn(t, code_effect(t, ax_s3('N', 'o', 'w'), 1, nargs)));
    ASSERT_EQ(er_scheduler_run(sys), ER_RUN_IDLE);
    ASSERT_GT(er_actor_result(a), 0);
    er_scheduler_free(sys);
  }
  test_rt_free(&rt);
}
