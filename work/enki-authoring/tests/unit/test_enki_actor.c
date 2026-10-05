#include "test.h"

#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <sys/stat.h>
#include <time.h>
#include <unistd.h>

#include "axsys/fd.h"
#include "enki/actor.h"
#include "test_plan.h"

/* Configuration assertions intentionally inspect the scheduler's resolved
 * values; execution behavior remains covered through the public API below. */
#include "../../pkg/enki/src/actor_internal.h"

/*
 * Actor runtime: er_scheduler drives er_actors — each one
 * deep normalization of (fn 0) — servicing the op-82 coordination
 * effects parked by PL_RUN_BLOCKED.
 *
 * Test programs are arity-1 laws whose body code applies the op-82 pin
 * to effect rows.  In KAL body code under the 2-slot env [self, arg]:
 * (0 f x) is application (operands deferred as thunks), (0 v) is a
 * literal, and nats >= 2 are self-literals.  Effect rows are hand-built
 * APP spines (data by the under-application invariant); rows built *by*
 * the program arise from applying name nats, which have arity 0 and so
 * also accumulate as data.
 *
 * GC discipline: a heap pl_val in a C local must not be a sibling
 * argument of another allocating call — every intermediate is parked on
 * the value stack and re-read from its slot.
 */

static pl_val code_lit(pl_thread* t, pl_val v) {
  return test_app1(t, 0, v);
}

static pl_val code_app(pl_thread* t, pl_val f, pl_val x) {
  return test_app2(t, 0, f, x);
}

/* The pin of nat 82 (rplan I/O). */
static pl_val test_p82(pl_thread* t) {
  size_t base = t->vsp;
  pl_vpush(t, 82);
  pl_val pin = pl_pin(t, t->vstack[base]);
  t->vsp = base;
  return pin;
}

/* The pin of nat 83 (structured request/response drivers). */
static pl_val test_p83(pl_thread* t) {
  size_t base = t->vsp;
  pl_vpush(t, 83);
  pl_val pin = pl_pin(t, t->vstack[base]);
  t->vsp = base;
  return pin;
}

/* Code performing (P82 % row) for a hand-built effect row. */
static pl_val code_effect(pl_thread* t, pl_val name, size_t n,
                          const pl_val* args) {
  size_t base = t->vsp;
  pl_vpush(t, code_lit(t, test_app(t, name, n, args)));
  pl_vpush(t, code_lit(t, test_p82(t)));
  pl_val out = code_app(t, t->vstack[base + 1], t->vstack[base]);
  t->vsp = base;
  return out;
}

/* Code performing (P83 % row) for a hand-built effect row. */
static pl_val code_effect83(pl_thread* t, pl_val name, size_t n,
                            const pl_val* args) {
  size_t base = t->vsp;
  pl_vpush(t, code_lit(t, test_app(t, name, n, args)));
  pl_vpush(t, code_lit(t, test_p83(t)));
  pl_val out = code_app(t, t->vstack[base + 1], t->vstack[base]);
  t->vsp = base;
  return out;
}

/* Code sequencing a then b: (P66 % (Seq a b)), Seq strict only in a. */
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

/* An arity-1 law (the actor boot fn) with the given body code. */
static pl_val actor_fn(pl_thread* t, pl_val body) {
  return test_law(t, 1, 0, body);
}

static pl_val recv_code(pl_thread* t) {
  pl_val args[1] = {0};
  return code_effect(t, ax_s4('R', 'e', 'c', 'v'), 1, args);
}

static pl_val sleep_code(pl_thread* t, uint64_t seconds) {
  pl_val args[1] = {seconds};
  return code_effect83(t, ax_s5('S', 'l', 'e', 'e', 'p'), 1, args);
}

static pl_val zone_start_code(pl_thread* t, pl_val label) {
  size_t base = t->vsp;
  pl_vpush(t, label);
  pl_vpush(t, pl_nat_from_bytes(t, (const uint8_t*)"ZoneStart", 9));
  pl_val args[1] = {t->vstack[base]};
  pl_val out = code_effect83(t, t->vstack[base + 1], 1, args);
  t->vsp = base;
  return out;
}

/* Arm an adopted root to deep-normalize (actor_fn body % 0). */
static void root_start_body(pl_thread* t, pl_val body) {
  size_t base = t->vsp;
  pl_vpush(t, body);
  pl_val fn = actor_fn(t, t->vstack[base]);
  t->vsp = base;
  pl_thread_start_call_nf(t, fn, 0);
}

static double monotonic_seconds(void) {
  struct timespec ts;
  ASSERT_EQ(clock_gettime(CLOCK_MONOTONIC, &ts), 0);
  return (double)ts.tv_sec + (double)ts.tv_nsec / 1000000000.0;
}

typedef struct mt_run_task {
  er_mt_executor* ex;
  er_run_reason reason;
} mt_run_task;

static void* mt_run_task_main(void* arg) {
  mt_run_task* task = arg;
  task->reason = er_mt_executor_run(task->ex);
  return NULL;
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

TEST(actor, readfolder_lists_entries_and_honors_file_root) {
  char dir[] = "/tmp/enki-read-folder-XXXXXX";
  ASSERT_NOT_NULL(mkdtemp(dir));
  char root[512], listing[512], child[512], file[512];
  int n = snprintf(root, sizeof(root), "%s/files", dir);
  ASSERT(n >= 0 && (size_t)n < sizeof(root));
  n = snprintf(listing, sizeof(listing), "%s/listing", root);
  ASSERT(n >= 0 && (size_t)n < sizeof(listing));
  n = snprintf(child, sizeof(child), "%s/subdir", listing);
  ASSERT(n >= 0 && (size_t)n < sizeof(child));
  n = snprintf(file, sizeof(file), "%s/plain.txt", listing);
  ASSERT(n >= 0 && (size_t)n < sizeof(file));
  ASSERT_EQ(mkdir(root, 0700), 0);
  ASSERT_EQ(mkdir(listing, 0700), 0);
  ASSERT_EQ(mkdir(child, 0700), 0);
  FILE* f = fopen(file, "wb");
  ASSERT_NOT_NULL(f);
  fputs("contents", f);
  fclose(f);

  test_rt rt = test_rt_new();
  er_scheduler* sys =
      er_scheduler_new(rt.store, (er_config){.file_root_c = root});
  er_actor* inside = er_scheduler_actor(sys);
  pl_thread* inside_t = er_actor_thread(inside);
  size_t base = inside_t->vsp;
  pl_vpush(inside_t,
           pl_nat_from_bytes(inside_t, (const uint8_t*)"ReadFolder", 10));
  pl_vpush(inside_t, pl_nat_from_bytes(inside_t, (const uint8_t*)"listing", 7));
  pl_val args[1] = {inside_t->vstack[base + 1]};
  pl_val body = code_effect83(inside_t, inside_t->vstack[base], 1, args);
  inside_t->vsp = base;
  er_actor_start(inside, actor_fn(inside_t, body));

  er_actor* outside = er_scheduler_actor(sys);
  pl_thread* outside_t = er_actor_thread(outside);
  base = outside_t->vsp;
  pl_vpush(outside_t,
           pl_nat_from_bytes(outside_t, (const uint8_t*)"ReadFolder", 10));
  pl_vpush(outside_t, pl_nat_from_bytes(outside_t, (const uint8_t*)"../", 3));
  args[0] = outside_t->vstack[base + 1];
  body = code_effect83(outside_t, outside_t->vstack[base], 1, args);
  outside_t->vsp = base;
  er_actor_start(outside, actor_fn(outside_t, body));

  ASSERT_EQ(er_scheduler_run(sys), ER_RUN_IDLE);
  ASSERT_EQ(er_actor_state(inside), ER_ACTOR_HALTED);
  pl_val row = er_actor_result(inside);
  pl_cell* row_p = pl_as(PL_TAG_APP, row);
  ASSERT_NOT_NULL(row_p);
  ASSERT_EQ(pl_app_head(row_p), 0);
  ASSERT_EQ(pl_app_n(row_p), 2);
  pl_cell* subdir = folder_entry(row, "subdir");
  ASSERT_NOT_NULL(subdir);
  ASSERT_EQ(pl_app_args(subdir)[0], 1);
  pl_cell* plain = folder_entry(row, "plain.txt");
  ASSERT_NOT_NULL(plain);
  ASSERT_EQ(pl_app_args(plain)[0], 0);

  ASSERT_EQ(er_actor_state(outside), ER_ACTOR_HALTED);
  ASSERT_EQ(er_actor_result(outside), 0);
  er_scheduler_free(sys);
  test_rt_free(&rt);

  ASSERT_EQ(unlink(file), 0);
  ASSERT_EQ(rmdir(child), 0);
  ASSERT_EQ(rmdir(listing), 0);
  ASSERT_EQ(rmdir(root), 0);
  ASSERT_EQ(rmdir(dir), 0);
}

TEST(actor, single_actor_halts_with_result) {
  test_rt rt = test_rt_new();
  er_scheduler* sys = er_scheduler_new(rt.store, (er_config){0});
  er_actor* a = er_scheduler_actor(sys);
  pl_thread* t = er_actor_thread(a);
  er_actor_start(a, actor_fn(t, 7)); /* body: self-literal 7 */
  ASSERT_EQ(er_scheduler_run(sys), ER_RUN_IDLE);
  ASSERT_EQ(er_actor_state(a), ER_ACTOR_HALTED);
  ASSERT_EQ(er_actor_result(a), 7);
  ASSERT_EQ(er_actor_id(a), 0);
  er_scheduler_free(sys);
  test_rt_free(&rt);
}

TEST(actor, crash_is_isolated) {
  test_rt rt = test_rt_new();
  er_scheduler* sys = er_scheduler_new(rt.store, (er_config){0});
  er_actor* a = er_scheduler_actor(sys);
  er_actor* b = er_scheduler_actor(sys);
  {
    /* a: (P66 % (Throw 9)) */
    pl_thread* t = er_actor_thread(a);
    size_t base = t->vsp;
    pl_vpush(t, code_lit(t, ax_s5('T', 'h', 'r', 'o', 'w')));
    pl_vpush(t, code_lit(t, 9));
    pl_vpush(t, code_app(t, t->vstack[base], t->vstack[base + 1]));
    pl_vpush(t, code_lit(t, test_p66(t)));
    pl_val body = code_app(t, t->vstack[base + 3], t->vstack[base + 2]);
    t->vsp = base;
    er_actor_start(a, actor_fn(t, body));
  }
  {
    pl_thread* t = er_actor_thread(b);
    er_actor_start(b, actor_fn(t, 7));
  }
  ASSERT_EQ(er_scheduler_run(sys), ER_RUN_IDLE);
  ASSERT_EQ(er_actor_state(a), ER_ACTOR_CRASHED);
  ASSERT_EQ(er_actor_state(b), ER_ACTOR_HALTED);
  ASSERT_EQ(er_actor_result(b), 7);
  er_scheduler_free(sys);
  test_rt_free(&rt);
}

/* Send 42 to self (handle 0), then Recv it: result [42, 0]. */
static void run_self_ping(pl_store* store, uint64_t quantum) {
  er_scheduler* sys = er_scheduler_new(store, (er_config){.quantum = quantum});
  er_actor* a = er_scheduler_actor(sys);
  pl_thread* t = er_actor_thread(a);
  size_t base = t->vsp;
  pl_val sargs[2] = {0, 42};
  pl_vpush(t, code_effect(t, ax_s4('S', 'e', 'n', 'd'), 2, sargs));
  pl_vpush(t, recv_code(t));
  pl_val body = code_seq(t, t->vstack[base], t->vstack[base + 1]);
  t->vsp = base;
  er_actor_start(a, actor_fn(t, body));

  ASSERT_EQ(er_scheduler_run(sys), ER_RUN_IDLE);
  ASSERT_EQ(er_actor_state(a), ER_ACTOR_HALTED);
  pl_cell* r = pl_as(PL_TAG_APP, er_actor_result(a));
  ASSERT_NOT_NULL(r);
  ASSERT_EQ(pl_app_head(r), 0);
  ASSERT_EQ(pl_app_n(r), 2);
  ASSERT_EQ(pl_app_args(r)[0], 42);
  ASSERT_EQ(pl_app_args(r)[1], 0); /* no caps: the empty row is 0 */
  er_scheduler_free(sys);
}

TEST(actor, send_to_self_then_recv) {
  test_rt rt = test_rt_new();
  run_self_ping(rt.store, 0);
  test_rt_free(&rt);
}

TEST(actor, mt_multiple_actors_halt) {
  test_rt rt = test_rt_new();
  er_scheduler* sys = er_scheduler_new(rt.store, (er_config){.quantum = 2});
  er_actor* a = er_scheduler_actor(sys);
  er_actor* b = er_scheduler_actor(sys);
  er_actor_start(a, actor_fn(er_actor_thread(a), 7));
  er_actor_start(b, actor_fn(er_actor_thread(b), 9));

  er_mt_executor* ex = er_mt_executor_new(sys, (er_mt_config){.workers = 2});
  ASSERT_EQ(er_mt_executor_run(ex), ER_RUN_IDLE);
  ASSERT_EQ(er_actor_state(a), ER_ACTOR_HALTED);
  ASSERT_EQ(er_actor_result(a), 7);
  ASSERT_EQ(er_actor_state(b), ER_ACTOR_HALTED);
  ASSERT_EQ(er_actor_result(b), 9);
  er_mt_executor_free(ex);
  er_scheduler_free(sys);
  test_rt_free(&rt);
}

TEST(actor, mt_profile_only_actor_does_not_bind_worker) {
  test_rt rt = test_rt_new();
  er_scheduler* sys = er_scheduler_new(rt.store, (er_config){0});
  er_actor* a = er_scheduler_actor(sys);
  pl_thread* t = er_actor_thread(a);
  size_t base = t->vsp;
  pl_vpush(t, zone_start_code(t, 21));
  pl_val fn = actor_fn(t, t->vstack[base]);
  t->vsp = base;
  er_actor_start(a, fn);

  er_mt_executor* ex = er_mt_executor_new(sys, (er_mt_config){.workers = 1});
  ASSERT_EQ(er_mt_executor_run(ex), ER_RUN_IDLE);
  ASSERT_EQ(er_actor_state(a), ER_ACTOR_HALTED);
  ASSERT_FALSE(a->effectful);

  size_t worker_n = 0;
  for (er_mt_worker* w = ex->worker_head; w != NULL; w = w->next)
    worker_n++;
  ASSERT_EQ(worker_n, 1, "profiling-only actor grew the executor worker pool");

  er_mt_executor_free(ex);
  er_scheduler_free(sys);
  test_rt_free(&rt);
}

TEST(actor, mt_bound_spawn_wakes_general_worker_without_broadcast) {
  int pipe_fd[2];
  ASSERT_EQ(pipe(pipe_fd), 0);
  size_t read_handle = ax_fd_add(pipe_fd[0]);
  size_t write_handle = ax_fd_add(pipe_fd[1]);
  ASSERT_NEQ(read_handle, AX_FD_INVALID);
  ASSERT_NEQ(write_handle, AX_FD_INVALID);

  test_rt rt = test_rt_new();
  er_scheduler* sys = er_scheduler_new(rt.store, (er_config){0});
  er_actor* parent = er_scheduler_actor(sys);
  pl_thread* t = er_actor_thread(parent);
  size_t base = t->vsp;
  pl_vpush(t, recv_code(t));
  pl_val read_args[2] = {read_handle, 1};
  pl_vpush(t, code_effect(t, ax_s4('R', 'e', 'a', 'd'), 2, read_args));
  pl_vpush(t, actor_fn(t, 7));
  pl_val spawn_args[1] = {t->vstack[base + 2]};
  pl_vpush(t, code_effect(t, ax_s5('S', 'p', 'a', 'w', 'n'), 1, spawn_args));
  pl_vpush(t, code_seq(t, t->vstack[base + 1], t->vstack[base + 3]));
  pl_val body = code_seq(t, t->vstack[base], t->vstack[base + 4]);
  t->vsp = base;
  er_actor_start(parent, actor_fn(t, body));

  /* Recv binds the parent to the only original worker and leaves the
   * replacement general worker parked between executor generations. */
  er_mt_executor* ex = er_mt_executor_new(sys, (er_mt_config){.workers = 1});
  ASSERT_EQ(er_mt_executor_run(ex), ER_RUN_QUIESCENT);
  ASSERT_EQ(er_actor_state(parent), ER_ACTOR_BLOCKED);

  /* On the second generation the replacement runs sentinel while the bound
   * parent waits in Read.  The general worker holds sys->mu continuously from
   * marking sentinel HALTED until it waits on sys->cv, so observing HALTED
   * under that mutex proves the worker has reached the shared-cv wait. */
  er_actor* sentinel = er_scheduler_actor(sys);
  er_actor_start(sentinel, actor_fn(er_actor_thread(sentinel), 9));
  er_scheduler_inject(sys, parent, 123);
  mt_run_task task = {.ex = ex};
  pthread_t runner;
  ASSERT_EQ(pthread_create(&runner, NULL, mt_run_task_main, &task), 0);

  for (;;) {
    pthread_mutex_lock(&sys->mu);
    if (sentinel->status == ER_ACTOR_HALTED)
      break;
    pthread_mutex_unlock(&sys->mu);
    struct timespec pause = {.tv_sec = 0, .tv_nsec = 1000000};
    (void)nanosleep(&pause, NULL);
  }
  ASSERT(ex->running);
  ASSERT_NULL(sys->qhead);
  uint8_t byte = 42;
  ASSERT_EQ(write(pipe_fd[1], &byte, 1), 1);
  pthread_mutex_unlock(&sys->mu);

  ASSERT_EQ(pthread_join(runner, NULL), 0);
  ASSERT_EQ(task.reason, ER_RUN_IDLE);
  ASSERT_EQ(er_actor_state(parent), ER_ACTOR_HALTED);
  ASSERT_EQ(er_actor_result(parent), 1);
  ASSERT_EQ(er_actor_state(sentinel), ER_ACTOR_HALTED);
  ASSERT_EQ(er_actor_result(sentinel), 9);
  er_actor* child = er_scheduler_actor_by_id(sys, 2);
  ASSERT_NOT_NULL(child);
  ASSERT_EQ(er_actor_state(child), ER_ACTOR_HALTED);
  ASSERT_EQ(er_actor_result(child), 7);

  er_mt_executor_free(ex);
  er_scheduler_free(sys);
  test_rt_free(&rt);
  ASSERT_EQ(ax_fd_close(read_handle), 0);
  ASSERT_EQ(ax_fd_close(write_handle), 0);
}

TEST(actor, root_quantum_config_environment_and_precedence) {
  const char* old_c = getenv("ENKI_ROOT_QUANTUM");
  char* old = old_c == NULL ? NULL : strdup(old_c);
  ASSERT(old_c == NULL || old != NULL);
  ASSERT_EQ(unsetenv("ENKI_ROOT_QUANTUM"), 0);

  test_rt rt = test_rt_new();
  er_scheduler* inherited =
      er_scheduler_new(rt.store, (er_config){.quantum = 17});
  ASSERT_EQ(inherited->cfg.quantum, 17);
  ASSERT_EQ(inherited->cfg.root_quantum, 17);
  er_scheduler_free(inherited);

  ASSERT_EQ(setenv("ENKI_ROOT_QUANTUM", "257", 1), 0);
  er_scheduler* from_env =
      er_scheduler_new(rt.store, (er_config){.quantum = 17});
  ASSERT_EQ(from_env->cfg.quantum, 17);
  ASSERT_EQ(from_env->cfg.root_quantum, 257);
  er_scheduler_free(from_env);

  er_scheduler* explicit = er_scheduler_new(
      rt.store, (er_config){.quantum = 17, .root_quantum = 33});
  ASSERT_EQ(explicit->cfg.quantum, 17);
  ASSERT_EQ(explicit->cfg.root_quantum, 33);
  er_scheduler_free(explicit);
  test_rt_free(&rt);

  if (old != NULL) {
    ASSERT_EQ(setenv("ENKI_ROOT_QUANTUM", old, 1), 0);
    free(old);
  } else {
    ASSERT_EQ(unsetenv("ENKI_ROOT_QUANTUM"), 0);
  }
}

TEST(actor, mt_blocking_effect_replenishes_shared_pool) {
  test_rt rt = test_rt_new();
  er_scheduler* sys = er_scheduler_new(rt.store, (er_config){0});
  er_actor* a = er_scheduler_actor(sys);
  er_actor* b = er_scheduler_actor(sys);
  pl_thread* at = er_actor_thread(a);
  pl_thread* bt = er_actor_thread(b);
  er_actor_start(a, actor_fn(at, sleep_code(at, 1)));
  er_actor_start(b, actor_fn(bt, sleep_code(bt, 1)));

  /* With one shared worker and no executor affinity/compensation these
   * sleeps serialize and take at least two seconds.  Each actor's first
   * RPLAN effect instead claims its worker and immediately replenishes the
   * shared pool, allowing both blocking syscalls to overlap. */
  er_mt_executor* ex = er_mt_executor_new(sys, (er_mt_config){.workers = 1});
  double before = monotonic_seconds();
  ASSERT_EQ(er_mt_executor_run(ex), ER_RUN_IDLE);
  double elapsed = monotonic_seconds() - before;
  ASSERT_LT(elapsed, 1.95,
            "blocking effects serialized across the shared pool: %.3fs",
            elapsed);
  ASSERT_EQ(er_actor_state(a), ER_ACTOR_HALTED);
  ASSERT_EQ(er_actor_state(b), ER_ACTOR_HALTED);

  er_mt_executor_free(ex);
  er_scheduler_free(sys);
  test_rt_free(&rt);
}

TEST(actor, mt_direct_read_replenishes_before_blocking) {
  int pipe_fd[2];
  ASSERT_EQ(pipe(pipe_fd), 0);
  size_t read_handle = ax_fd_add(pipe_fd[0]);
  size_t write_handle = ax_fd_add(pipe_fd[1]);
  ASSERT_NEQ(read_handle, AX_FD_INVALID);
  ASSERT_NEQ(write_handle, AX_FD_INVALID);

  test_rt rt = test_rt_new();
  er_scheduler* sys = er_scheduler_new(rt.store, (er_config){0});
  er_actor* reader = er_scheduler_actor(sys);
  er_actor* writer = er_scheduler_actor(sys);
  pl_thread* reader_t = er_actor_thread(reader);
  pl_thread* writer_t = er_actor_thread(writer);
  pl_val read_args[2] = {read_handle, 1};
  pl_val write_args[2] = {write_handle, ((pl_val)1 << 8) | 42};
  er_actor_start(
      reader,
      actor_fn(reader_t,
               code_effect(reader_t, ax_s4('R', 'e', 'a', 'd'), 2, read_args)));
  er_actor_start(
      writer,
      actor_fn(writer_t, code_effect(writer_t, ax_s5('W', 'r', 'i', 't', 'e'),
                                     2, write_args)));

  /* The reader is first in the queue and blocks in read(2).  With one
   * shared worker, the writer can run only if the effect hook binds the
   * reader and replenishes the pool before entering the direct-op body. */
  er_mt_executor* ex = er_mt_executor_new(sys, (er_mt_config){.workers = 1});
  ASSERT_EQ(er_mt_executor_run(ex), ER_RUN_IDLE);
  ASSERT_EQ(er_actor_state(reader), ER_ACTOR_HALTED);
  ASSERT_EQ(er_actor_result(reader), ((pl_val)1 << 8) | 42);
  ASSERT_EQ(er_actor_state(writer), ER_ACTOR_HALTED);
  ASSERT_EQ(er_actor_result(writer), 0);

  er_mt_executor_free(ex);
  er_scheduler_free(sys);
  test_rt_free(&rt);
  ASSERT_EQ(ax_fd_close(read_handle), 0);
  ASSERT_EQ(ax_fd_close(write_handle), 0);
}

TEST(actor, mt_recv_blocks_until_injection) {
  test_rt rt = test_rt_new();
  er_scheduler* sys = er_scheduler_new(rt.store, (er_config){0});
  er_actor* a = er_scheduler_actor(sys);
  pl_thread* t = er_actor_thread(a);
  er_actor_start(a, actor_fn(t, recv_code(t)));

  er_mt_executor* ex = er_mt_executor_new(sys, (er_mt_config){.workers = 2});
  ASSERT_EQ(er_mt_executor_run(ex), ER_RUN_QUIESCENT);
  ASSERT_EQ(er_actor_state(a), ER_ACTOR_BLOCKED);

  er_scheduler_inject(sys, a, 123);
  ASSERT_EQ(er_mt_executor_run(ex), ER_RUN_IDLE);
  ASSERT_EQ(er_actor_state(a), ER_ACTOR_HALTED);
  pl_cell* r = pl_as(PL_TAG_APP, er_actor_result(a));
  ASSERT_NOT_NULL(r);
  ASSERT_EQ(pl_app_args(r)[0], 123);
  er_mt_executor_free(ex);
  er_scheduler_free(sys);
  test_rt_free(&rt);
}

static er_drive_status drive_adopted(er_scheduler* sys, er_mt_executor* ex,
                                     er_actor* root) {
  return ex == NULL ? er_scheduler_drive(sys, root)
                    : er_mt_executor_drive(ex, root);
}

static void run_adopted_root_abandon_zones(bool mt) {
  test_rt rt = test_rt_new();
  pl_thread* t = rt.t;
  t->rplan_f = true;
  er_scheduler* sys =
      er_scheduler_new(rt.store, (er_config){.quantum = 2, .root_quantum = 2});
  er_mt_executor* ex =
      mt ? er_mt_executor_new(sys, (er_mt_config){.workers = 1}) : NULL;
  er_actor* root = er_scheduler_adopt(sys, t);

  /* A zone from a completed run is host-scoped and must survive abandoning
   * either of the later runs.  Root its handle across all allocations. */
  size_t outer_slot = t->vsp;
  root_start_body(t, zone_start_code(t, 11));
  ASSERT_EQ(drive_adopted(sys, ex, root), ER_DRIVE_DONE);
  pl_vpush(t, pl_thread_result(t));
  ASSERT_EQ(t->profile_zone_n, 1);
  ASSERT_EQ(t->profile_zones[0].handle, t->vstack[outer_slot]);

  /* Deadlock abandons a continuation parked on Recv. */
  size_t run_vsp = t->vsp;
  size_t run_fsp = t->fsp;
  pl_vpush(t, zone_start_code(t, 12));
  pl_vpush(t, recv_code(t));
  pl_val body = code_seq(t, t->vstack[run_vsp], t->vstack[run_vsp + 1]);
  t->vsp = run_vsp;
  root_start_body(t, body);
  ASSERT_EQ(drive_adopted(sys, ex, root), ER_DRIVE_DEADLOCK);
  ASSERT_EQ(t->vsp, run_vsp);
  ASSERT_EQ(t->fsp, run_fsp);
  ASSERT_EQ(t->profile_zone_n, 1);
  ASSERT_EQ(t->profile_zones[0].handle, t->vstack[outer_slot]);

  /* A service-detected crash abandons the same kind of parked continuation. */
  pl_vpush(t, zone_start_code(t, 13));
  pl_val send_args[2] = {99, 7};
  pl_vpush(t, code_effect(t, ax_s4('S', 'e', 'n', 'd'), 2, send_args));
  body = code_seq(t, t->vstack[run_vsp], t->vstack[run_vsp + 1]);
  t->vsp = run_vsp;
  root_start_body(t, body);
  ASSERT_EQ(drive_adopted(sys, ex, root), ER_DRIVE_EXN);
  ASSERT_STR_EQ(t->exn_msg, "invalid actor handle");
  ASSERT_EQ(t->vsp, run_vsp);
  ASSERT_EQ(t->fsp, run_fsp);
  ASSERT_EQ(t->profile_zone_n, 1);
  ASSERT_EQ(t->profile_zones[0].handle, t->vstack[outer_slot]);

  /* The embedder can immediately re-arm the adopted root after either
   * abandonment path; no discarded zone may reopen on this run. */
  pl_thread_start(t, 42);
  ASSERT_EQ(drive_adopted(sys, ex, root), ER_DRIVE_DONE);
  ASSERT_EQ(pl_thread_result(t), 42);
  ASSERT_EQ(t->profile_zone_n, 1);
  ASSERT_EQ(t->profile_zones[0].handle, t->vstack[outer_slot]);

  er_mt_executor_free(ex);
  er_scheduler_free(sys);
  test_rt_free(&rt);
}

TEST(actor, adopted_root_abandon_drops_current_run_zones) {
  run_adopted_root_abandon_zones(false);
}

TEST(actor, mt_adopted_root_abandon_drops_current_run_zones) {
  run_adopted_root_abandon_zones(true);
}

TEST(actor, mt_free_detaches_bound_actor) {
  test_rt rt = test_rt_new();
  er_scheduler* sys = er_scheduler_new(rt.store, (er_config){0});
  er_actor* a = er_scheduler_actor(sys);
  pl_thread* t = er_actor_thread(a);
  er_actor_start(a, actor_fn(t, recv_code(t)));

  er_mt_executor* ex = er_mt_executor_new(sys, (er_mt_config){.workers = 1});
  ASSERT_EQ(er_mt_executor_run(ex), ER_RUN_QUIESCENT);
  ASSERT_EQ(er_actor_state(a), ER_ACTOR_BLOCKED);
  er_mt_executor_free(ex); /* releases the actor's private worker affinity */

  er_scheduler_inject(sys, a, 77);
  ASSERT_EQ(er_scheduler_run(sys), ER_RUN_IDLE);
  ASSERT_EQ(er_actor_state(a), ER_ACTOR_HALTED);
  pl_cell* r = pl_as(PL_TAG_APP, er_actor_result(a));
  ASSERT_NOT_NULL(r);
  ASSERT_EQ(pl_app_args(r)[0], 77);

  er_scheduler_free(sys);
  test_rt_free(&rt);
}

TEST(actor, results_independent_of_quantum) {
  /* results must not depend on the quantum: one step per quantum and a huge
   * quantum agree */
  test_rt rt = test_rt_new();
  run_self_ping(rt.store, 2);
  run_self_ping(rt.store, 1 << 20);
  test_rt_free(&rt);
}

TEST(actor, tiny_heaps_collect_through_service) {
  /* 256-cell semispaces force collection (and growth) inside pinning
   * and response building — a GC-pressure pass over the service paths
   * without the PL_GC_STRESS build flag. */
  test_rt rt = test_rt_new();
  er_scheduler* sys =
      er_scheduler_new(rt.store, (er_config){.quantum = 2, .heap_cells = 256});
  er_actor* a = er_scheduler_actor(sys);
  pl_thread* t = er_actor_thread(a);
  size_t base = t->vsp;
  pl_val sargs[2] = {0, 42};
  pl_vpush(t, code_effect(t, ax_s4('S', 'e', 'n', 'd'), 2, sargs));
  pl_vpush(t, recv_code(t));
  pl_val body = code_seq(t, t->vstack[base], t->vstack[base + 1]);
  t->vsp = base;
  er_actor_start(a, actor_fn(t, body));
  ASSERT_EQ(er_scheduler_run(sys), ER_RUN_IDLE);
  ASSERT_EQ(er_actor_state(a), ER_ACTOR_HALTED);
  pl_cell* r = pl_as(PL_TAG_APP, er_actor_result(a));
  ASSERT_NOT_NULL(r);
  ASSERT_EQ(pl_app_args(r)[0], 42);
  er_scheduler_free(sys);
  test_rt_free(&rt);
}

TEST(actor, recv_blocks_until_injection) {
  test_rt rt = test_rt_new();
  er_scheduler* sys = er_scheduler_new(rt.store, (er_config){0});
  er_actor* a = er_scheduler_actor(sys);
  pl_thread* t = er_actor_thread(a);
  er_actor_start(a, actor_fn(t, recv_code(t)));

  ASSERT_EQ(er_scheduler_run(sys), ER_RUN_QUIESCENT);
  ASSERT_EQ(er_actor_state(a), ER_ACTOR_BLOCKED);

  er_scheduler_inject(sys, a, 99);
  ASSERT_EQ(er_scheduler_run(sys), ER_RUN_IDLE);
  ASSERT_EQ(er_actor_state(a), ER_ACTOR_HALTED);
  pl_cell* r = pl_as(PL_TAG_APP, er_actor_result(a));
  ASSERT_NOT_NULL(r);
  ASSERT_EQ(pl_app_args(r)[0], 99);
  er_scheduler_free(sys);
  test_rt_free(&rt);
}

TEST(actor, spawn_runs_child_and_returns_handle) {
  test_rt rt = test_rt_new();
  er_scheduler* sys = er_scheduler_new(rt.store, (er_config){0});
  er_actor* parent = er_scheduler_actor(sys);
  pl_thread* t = er_actor_thread(parent);
  size_t base = t->vsp;
  pl_vpush(t, actor_fn(t, 7)); /* child halts with 7 */
  pl_val spargs[1] = {t->vstack[base]};
  pl_val body = code_effect(t, ax_s5('S', 'p', 'a', 'w', 'n'), 1, spargs);
  t->vsp = base;
  er_actor_start(parent, actor_fn(t, body));

  ASSERT_EQ(er_scheduler_run(sys), ER_RUN_IDLE);
  ASSERT_EQ(er_actor_state(parent), ER_ACTOR_HALTED);
  ASSERT_EQ(er_actor_result(parent), 1); /* first minted handle */
  er_actor* child = er_scheduler_actor_by_id(sys, 1);
  ASSERT_NOT_NULL(child);
  ASSERT_EQ(er_actor_state(child), ER_ACTOR_HALTED);
  ASSERT_EQ(er_actor_result(child), 7);
  er_scheduler_free(sys);
  test_rt_free(&rt);
}

TEST(actor, sendcaps_reminted_in_receiver) {
  test_rt rt = test_rt_new();
  er_scheduler* sys = er_scheduler_new(rt.store, (er_config){0});
  er_actor* parent = er_scheduler_actor(sys);
  pl_thread* t = er_actor_thread(parent);
  /* parent: Seq(Spawn <recv-child>, SendCaps 1 5 [0]); the child handle
   * is deterministically 1 (first minted), so the row embeds it. */
  size_t base = t->vsp;
  pl_vpush(t, actor_fn(t, recv_code(t))); /* child: Recv, halt */
  pl_val spargs[1] = {t->vstack[base]};
  pl_vpush(t, code_effect(t, ax_s5('S', 'p', 'a', 'w', 'n'), 1, spargs));
  pl_vpush(t, test_app1(t, 0, 0)); /* caps row [0]: self */
  pl_val scargs[3] = {1, 5, t->vstack[base + 2]};
  pl_vpush(t, code_effect(t, ax_s8('S', 'e', 'n', 'd', 'C', 'a', 'p', 's'), 3,
                          scargs));
  pl_val body = code_seq(t, t->vstack[base + 1], t->vstack[base + 3]);
  t->vsp = base;
  er_actor_start(parent, actor_fn(t, body));

  ASSERT_EQ(er_scheduler_run(sys), ER_RUN_IDLE);
  ASSERT_EQ(er_actor_state(parent), ER_ACTOR_HALTED);
  ASSERT_EQ(er_actor_result(parent), 0); /* SendCaps response */
  er_actor* child = er_scheduler_actor_by_id(sys, 1);
  ASSERT_NOT_NULL(child);
  ASSERT_EQ(er_actor_state(child), ER_ACTOR_HALTED);
  pl_cell* r = pl_as(PL_TAG_APP, er_actor_result(child));
  ASSERT_NOT_NULL(r);
  ASSERT_EQ(pl_app_args(r)[0], 5);
  pl_cell* caps = pl_as(PL_TAG_APP, pl_app_args(r)[1]);
  ASSERT_NOT_NULL(caps);
  ASSERT_EQ(pl_app_n(caps), 1);
  ASSERT_EQ(pl_app_args(caps)[0], 1); /* fresh receiver-local handle */
  er_scheduler_free(sys);
  test_rt_free(&rt);
}

TEST(actor, send_to_closed_handle_crashes_sender) {
  test_rt rt = test_rt_new();
  er_scheduler* sys = er_scheduler_new(rt.store, (er_config){0});
  er_actor* a = er_scheduler_actor(sys);
  pl_thread* t = er_actor_thread(a);
  /* Seq(CloseHandle 0, Send 0 9): the self handle is revocable; the
   * send through the closed handle is the reference's host error. */
  size_t base = t->vsp;
  pl_vpush(t, pl_nat_from_bytes(t, (const uint8_t*)"CloseHandle", 11));
  pl_val cargs[1] = {0};
  pl_vpush(t, code_effect(t, t->vstack[base], 1, cargs));
  pl_val sargs[2] = {0, 9};
  pl_vpush(t, code_effect(t, ax_s4('S', 'e', 'n', 'd'), 2, sargs));
  pl_val body = code_seq(t, t->vstack[base + 1], t->vstack[base + 2]);
  t->vsp = base;
  er_actor_start(a, actor_fn(t, body));

  ASSERT_EQ(er_scheduler_run(sys), ER_RUN_IDLE);
  ASSERT_EQ(er_actor_state(a), ER_ACTOR_CRASHED);
  er_scheduler_free(sys);
  test_rt_free(&rt);
}

TEST(actor, cross_actor_payload_is_receiver_owned) {
  /* Send a structured payload (a law) to a recv-blocked child: it must
   * arrive intact in the receiver's collected heap, forced at send. */
  test_rt rt = test_rt_new();
  er_scheduler* sys = er_scheduler_new(rt.store, (er_config){0});
  er_actor* parent = er_scheduler_actor(sys);
  pl_thread* t = er_actor_thread(parent);
  size_t base = t->vsp;
  pl_vpush(t, actor_fn(t, recv_code(t)));     /* child: Recv, halt */
  pl_vpush(t, test_law(t, 2, ax_s1('K'), 1)); /* payload: the K law */
  pl_val spargs[1] = {t->vstack[base]};
  pl_vpush(t, code_effect(t, ax_s5('S', 'p', 'a', 'w', 'n'), 1, spargs));
  pl_val sargs[2] = {1, t->vstack[base + 1]};
  pl_vpush(t, code_effect(t, ax_s4('S', 'e', 'n', 'd'), 2, sargs));
  pl_val body = code_seq(t, t->vstack[base + 2], t->vstack[base + 3]);
  t->vsp = base;
  er_actor_start(parent, actor_fn(t, body));
  size_t store_before = pl_store_memory_bytes(rt.store);
  ASSERT_EQ(er_scheduler_run(sys), ER_RUN_IDLE);
  er_actor* child = er_scheduler_actor_by_id(sys, 1);
  ASSERT_NOT_NULL(child);
  ASSERT_EQ(er_actor_state(child), ER_ACTOR_HALTED);
  pl_cell* r = pl_as(PL_TAG_APP, er_actor_result(child));
  ASSERT_NOT_NULL(r);
  pl_cell* law = pl_as(PL_TAG_LAW, pl_app_args(r)[0]);
  ASSERT_NOT_NULL(law);
  ASSERT_EQ(pl_law_arity(law), 2);
  ASSERT_EQ(pl_law_name(law), ax_s1('K'));
  ASSERT_FALSE(pl_store_owns(rt.store, pl_app_args(r)[0]));
  ASSERT_EQ(pl_store_memory_bytes(rt.store), store_before);
  pl_gc_collect_now(er_actor_thread(parent));
  pl_gc_collect_now(er_actor_thread(child));
  r = pl_as(PL_TAG_APP, er_actor_result(child));
  law = pl_as(PL_TAG_LAW, pl_app_args(r)[0]);
  ASSERT_EQ(pl_law_name(law), ax_s1('K'));
  er_scheduler_free(sys);
  test_rt_free(&rt);
}

static void run_spawn_lifetime(bool mt) {
  test_rt rt = test_rt_new();
  pl_thread* t = rt.t;
  t->rplan_f = true;
  er_scheduler* sys = er_scheduler_new(rt.store, (er_config){.quantum = 2});
  er_actor* root = er_scheduler_adopt(sys, t);
  er_mt_executor* ex = mt ? er_mt_executor_new(sys, (er_mt_config){.workers = 2}) : NULL;
  for (size_t i = 0; i < 256; i++) {
    size_t base = t->vsp;
    pl_val invalid[2] = {999999, 0};
    pl_val child_body = i % 2 == 0 ? 42 : code_effect(t, ax_s4('S','e','n','d'), 2, invalid);
    pl_vpush(t, actor_fn(t, child_body));
    pl_val spawn[1] = {t->vstack[base]};
    pl_vpush(t, code_effect(t, ax_s5('S','p','a','w','n'), 1, spawn));
    /* Keep the first child's capability in a queued message, close its
     * original handle, then create enough dead actors to force collection. */
    pl_val body = t->vstack[base + 1];
    if (i == 0) {
      pl_vpush(t, test_app1(t, 0, 1));
      pl_val send[3] = {0, 7, t->vstack[base + 2]};
      pl_vpush(t, code_effect(t, ax_s8('S','e','n','d','C','a','p','s'), 3, send));
      body = code_seq(t, t->vstack[base + 1], t->vstack[base + 3]);
    }
    pl_vpush(t, body);
    size_t body_slot = t->vsp - 1;
    pl_vpush(t, pl_nat_from_bytes(t, (const uint8_t*)"CloseHandle", 11));
    pl_val close[1] = {i + 1};
    pl_vpush(t, code_effect(t, t->vstack[t->vsp - 1], 1, close));
    body = code_seq(t, t->vstack[body_slot], t->vstack[t->vsp - 1]);
    t->vsp = base;
    root_start_body(t, body);
    ASSERT_EQ(mt ? er_mt_executor_drive(ex, root) : er_scheduler_drive(sys, root), ER_DRIVE_DONE);
    ASSERT_EQ(mt ? er_mt_executor_run(ex) : er_scheduler_run(sys), ER_RUN_IDLE);
  }
  size_t retained = 0;
  for (er_actor* a = sys->all_head; a != NULL; a = a->all_next) retained++;
  ASSERT(retained <= 35, "finished actors without capabilities must be reclaimed in bounded batches");
  er_actor* kept = er_scheduler_actor_by_id(sys, 1);
  ASSERT_NOT_NULL(kept);
  ASSERT_EQ(er_actor_result(kept), 42);
  ASSERT_NOT_NULL(root->mbox_head);
  ASSERT_EQ(root->mbox_head->caps[0], kept);
  ASSERT_NULL(er_scheduler_actor_by_id(sys, 2));
  if (ex != NULL) er_mt_executor_free(ex);
  er_scheduler_free(sys);
  test_rt_free(&rt);
}

TEST(actor, spawned_lifetime_follows_capabilities) { run_spawn_lifetime(false); }
TEST(actor, mt_spawned_lifetime_follows_capabilities) { run_spawn_lifetime(true); }

TEST(actor, halted_actor_releases_unreachable_scratch) {
  test_rt rt = test_rt_new();
  er_scheduler* sys = er_scheduler_new(rt.store, (er_config){.heap_cells = 262144});
  for (size_t i = 0; i < 16; i++) {
    er_actor* a = er_scheduler_actor(sys);
    pl_thread* t = er_actor_thread(a);
    /* An HTTP connection can finish long before filling its semispace.
     * Its abandoned scratch must not wait for scheduler shutdown to collect. */
    /* One allocation window also builds real dead scratch under GC_STRESS;
     * calling test_app2 repeatedly would collect it on every iteration. */
    pl_gc_reserve(t, 4096 * PL_APP_CELLS(2));
    size_t capacity = pl_gc_headroom(t);
    PL_GC_FORBID(t);
    for (size_t j = 0; j < 4096; j++) {
      pl_val fields[2] = {j, j + 1};
      (void)pl_mk_app_from(t, 0, 2, fields);
    }
    PL_GC_ALLOW(t);
    ASSERT(pl_gc_headroom(t) < capacity - 4096, "fixture allocates dead scratch");
    er_actor_start(a, actor_fn(t, 42));
    ASSERT_EQ(er_scheduler_run(sys), ER_RUN_IDLE);
    ASSERT_EQ(er_actor_state(a), ER_ACTOR_HALTED);
    ASSERT_EQ(er_actor_result(a), 42);
    ASSERT(pl_gc_live_cells(t->heap) < 64,
           "terminated actor retains only its live result, not scratch");
    ASSERT(pl_gc_headroom(t) + pl_gc_live_cells(t->heap) <= 8192,
           "terminated actor releases its oversized physical semispaces");
  }
  er_scheduler_free(sys);
  test_rt_free(&rt);
}

TEST(actor, owned_mail_survives_collection_with_shared_proxies_and_caps) {
  test_rt rt = test_rt_new();
  pl_thread* t = rt.t;
  t->rplan_f = true;
  er_scheduler* sys = er_scheduler_new(rt.store, (er_config){.quantum = 2});
  er_actor* root = er_scheduler_adopt(sys, t);
  size_t base = t->vsp;
  pl_vpush(t, pl_nat_from_bytes(t, (const uint8_t*)"owned transport payload", 23));
  pl_vpush(t, pl_pin(t, t->vstack[base]));
  pl_vpush(t, test_app2(t, 0, t->vstack[base + 1], t->vstack[base + 1]));
  pl_vpush(t, test_app1(t, 0, 0));
  pl_val args[3] = {0, t->vstack[base + 2], t->vstack[base + 3]};
  pl_val body = code_effect(t, ax_s8('S', 'e', 'n', 'd', 'C', 'a', 'p', 's'),
                            3, args);
  t->vsp = base;
  root_start_body(t, body);
  size_t store_before = pl_store_memory_bytes(rt.store);
  ASSERT_EQ(er_scheduler_drive(sys, root), ER_DRIVE_DONE);
  ASSERT_NOT_NULL(root->mbox_head);
  ASSERT(root->mbox_head->payload.count > 0);
  ASSERT_FALSE(pl_store_owns(rt.store, root->mbox_head->payload.value));

  /* Forget the sender's entire computation before receiving the message. */
  pl_thread_start(t, 0);
  ASSERT_EQ(er_scheduler_drive(sys, root), ER_DRIVE_DONE);
  pl_gc_collect_now(t);
  root_start_body(t, recv_code(t));
  ASSERT_EQ(er_scheduler_drive(sys, root), ER_DRIVE_DONE);
  pl_gc_collect_now(t);
  pl_cell* response = pl_as(PL_TAG_APP, pl_thread_result(t));
  ASSERT_NOT_NULL(response);
  pl_cell* row = pl_as(PL_TAG_APP, pl_app_args(response)[0]);
  ASSERT_NOT_NULL(row);
  pl_val pin = pl_app_args(row)[0];
  ASSERT_EQ(pin, pl_app_args(row)[1], "message graph sharing was lost");
  ASSERT_EQ(pl_tag(pin), PL_TAG_PIN);
  ASSERT(pl_pin_is_proxy(pl_ptr(pin)));
  ASSERT_FALSE(pl_store_owns(rt.store, pin));
  ASSERT(nat_text_eq(pl_pin_body(pl_ptr(pin)), "owned transport payload"));
  pl_cell* caps = pl_as(PL_TAG_APP, pl_app_args(response)[1]);
  ASSERT_NOT_NULL(caps);
  ASSERT_EQ(pl_app_args(caps)[0], 1);
  ASSERT_EQ(root->handle_v[1], root);
  ASSERT_EQ(root->mbox_head, NULL);
  ASSERT_EQ(pl_store_memory_bytes(rt.store), store_before);
  er_scheduler_free(sys);
  test_rt_free(&rt);
}

TEST(actor, unchanged_messages_do_not_grow_store) {
  test_rt rt = test_rt_new();
  pl_thread* t = rt.t;
  t->rplan_f = true;
  er_scheduler* sys = er_scheduler_new(rt.store, (er_config){0});
  er_actor* root = er_scheduler_adopt(sys, t);
  size_t store_before = pl_store_memory_bytes(rt.store);
  for (size_t i = 0; i < 10000; i++) {
    size_t base = t->vsp;
    pl_vpush(t, test_app2(t, 0, 17, 23));
    pl_val args[2] = {0, t->vstack[base]};
    pl_val send = code_effect(t, ax_s4('S', 'e', 'n', 'd'), 2, args);
    t->vsp = base;
    root_start_body(t, send);
    ASSERT_EQ(er_scheduler_drive(sys, root), ER_DRIVE_DONE);
    root_start_body(t, recv_code(t));
    ASSERT_EQ(er_scheduler_drive(sys, root), ER_DRIVE_DONE);
    pl_cell* response = pl_as(PL_TAG_APP, pl_thread_result(t));
    pl_cell* row = pl_as(PL_TAG_APP, pl_app_args(response)[0]);
    ASSERT_EQ(pl_app_args(row)[0], 17);
    ASSERT_EQ(pl_app_args(row)[1], 23);
    ASSERT_EQ(root->mbox_head, NULL);
    if (i % 100 == 0)
      pl_gc_collect_now(t);
  }
  ASSERT_EQ(pl_store_memory_bytes(rt.store), store_before);
  er_scheduler_free(sys);
  test_rt_free(&rt);
}

static void run_abandoned_owned_mail(bool crash) {
  test_rt rt = test_rt_new();
  er_scheduler* sys = er_scheduler_new(rt.store, (er_config){0});
  er_actor* actor = er_scheduler_actor(sys);
  pl_thread* t = er_actor_thread(actor);
  size_t base = t->vsp;
  pl_vpush(t, test_app2(t, 0, 12, 34));
  pl_val args[2] = {0, t->vstack[base]};
  pl_vpush(t, code_effect(t, ax_s4('S', 'e', 'n', 'd'), 2, args));
  pl_val body = t->vstack[base + 1];
  if (crash) {
    pl_val invalid[2] = {9999, 0};
    pl_vpush(t, code_effect(t, ax_s4('S', 'e', 'n', 'd'), 2, invalid));
    body = code_seq(t, t->vstack[base + 1], t->vstack[base + 2]);
  }
  t->vsp = base;
  er_actor_start(actor, actor_fn(t, body));
  size_t store_before = pl_store_memory_bytes(rt.store);
  ASSERT_EQ(er_scheduler_run(sys), ER_RUN_IDLE);
  ASSERT_EQ(er_actor_state(actor), crash ? ER_ACTOR_CRASHED : ER_ACTOR_HALTED);
  ASSERT_EQ(actor->mbox_head, NULL);
  ASSERT_EQ(actor->mbox_tail, NULL);
  ASSERT_EQ(pl_store_memory_bytes(rt.store), store_before);
  er_scheduler_free(sys);
  test_rt_free(&rt);
}

TEST(actor, termination_discards_owned_mail) {
  run_abandoned_owned_mail(false);
  run_abandoned_owned_mail(true);
}

TEST(actor, scheduler_shutdown_discards_unreceived_owned_mail) {
  test_rt rt = test_rt_new();
  pl_thread* t = rt.t;
  t->rplan_f = true;
  er_scheduler* sys = er_scheduler_new(rt.store, (er_config){0});
  er_actor* root = er_scheduler_adopt(sys, t);
  size_t base = t->vsp;
  pl_vpush(t, test_app2(t, 0, 12, 34));
  pl_val args[2] = {0, t->vstack[base]};
  pl_val body = code_effect(t, ax_s4('S', 'e', 'n', 'd'), 2, args);
  t->vsp = base;
  root_start_body(t, body);
  ASSERT_EQ(er_scheduler_drive(sys, root), ER_DRIVE_DONE);
  ASSERT_NOT_NULL(root->mbox_head);
  ASSERT(root->mbox_head->payload.count > 0);
  er_scheduler_free(sys); /* ASan/leak checks cover the unreceived graph. */
  test_rt_free(&rt);
}
