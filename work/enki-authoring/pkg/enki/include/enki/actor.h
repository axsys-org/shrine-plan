#ifndef ER_ACTOR_H
#define ER_ACTOR_H

/*
 * Actor runtime: one er_actor = one pl_thread with a
 * private heap; an actor's whole life is one deep normalization of
 * (fn 0).  The single-OS-thread deterministic executor drives actors in
 * FIFO run-queue order with a fixed fuel quantum and services the
 * coordination effects (op 82 Spawn/Send/SendCaps/Recv/CloseHandle and the
 * current provisional op 83 primops, Fetch/ReadFolder) that pl_thread_run
 * parks as PL_RUN_BLOCKED requests.  Op 83 is a staging area: its PLAN-level
 * primop semantics are not yet settled.
 *
 * HTTP (op 83 Fetch, src/http.c): a libcurl-backed req/res effect.
 * ReadFolder is an op-83 req/res effect that returns filesystem entries;
 * it observes the same file-root jail as ReadFile.
 * The caller parks while the transfer runs on a scheduler-owned multi
 * handle; other actors keep executing, and the run loops block in
 * curl_multi_poll only when the run queue is empty.  The Result value
 * is (0 [status urlBar headersRow bodyBar]) or (1 errCode); see
 * src/http.c for the request/config ABI and the error taxonomy.
 * Caveat: transfers accept all curl content encodings, so the body
 * arrives decoded while Content-Length/Content-Encoding response
 * headers still describe the wire form.
 *
 * Messaging: deeply normalized payloads cross actors in mailbox-owned
 * transport storage, then are copied into the receiver's collected heap.
 * Existing canonical store graphs may be shared; sending does not promote
 * transient values into the permanent store or publish persistence. PLAN
 * code addresses actors through per-actor handle tables; handle 0 is
 * self, fresh handles are minted by Spawn and by cap transfer in Recv.
 */

#include "plan/eval.h"
#include "plan/heap.h"
#include "plan/store.h"
#include "plan/value.h"

typedef struct er_actor er_actor;
typedef struct er_scheduler er_scheduler;
typedef struct er_mt_executor er_mt_executor;

typedef enum {
  ER_ACTOR_RUNNABLE = 0, /* in the run queue (or not yet started) */
  ER_ACTOR_BLOCKED,      /* parked on Recv against an empty mailbox */
  ER_ACTOR_HALTED,       /* (fn 0) reached normal form */
  ER_ACTOR_CRASHED, /* uncaught exception or invalid effect; never resumed */
} er_actor_status;

typedef struct er_config {
  /* Worker/deterministic fuel per slice (>= 2); zero uses the default. */
  uint64_t quantum;
  size_t heap_cells;       /* per-actor semispace cells; 0 = default (8192) */
  const char* file_root_c; /* spawned actors' ReadFile/ReadFolder jail */
  /* HTTP driver (op 83 Fetch) */
  long http_max_total_connections;  /* CURLM connection cap; 0 = curl default */
  uint64_t http_connect_default_ms; /* connectMs None default; 0 = 10000 */
  /* MT adopted-root fuel per slice (>= 2).  Zero reads ENKI_ROOT_QUANTUM,
   * then conservatively inherits quantum when the variable is unset. */
  uint64_t root_quantum;
} er_config;

er_scheduler* er_scheduler_new(pl_store* store, er_config cfg);
void er_scheduler_free(er_scheduler* sys);

/*
 * Create an actor (unstarted, not in the run queue).  Its thread is
 * exposed so the embedder can build the boot function in the actor's
 * own heap; arm and enqueue with er_actor_start.
 */
er_actor* er_scheduler_actor(er_scheduler* sys);
pl_thread* er_actor_thread(er_actor* a);
void er_actor_start(er_actor* a, pl_val fn);

/*
 * Adopt an existing thread (and its heap) as an actor — the reference
 * withNewRts: the embedder's own thread becomes an actor.  Ownership
 * stays with the embedder (er_scheduler_free will not free it), and the
 * scheduler never marks it HALTED: the embedder arms a computation on
 * it (pl_thread_start* family) and runs it with er_scheduler_drive, any
 * number of times.
 */
er_actor* er_scheduler_adopt(er_scheduler* sys, pl_thread* t);

typedef enum {
  ER_DRIVE_DONE,     /* the driven computation completed (pl_thread_result) */
  ER_DRIVE_EXN,      /* it raised; t->exn / t->exn_msg carry the payload */
  ER_DRIVE_DEADLOCK, /* it parked on Recv and nothing can ever wake it */
} er_drive_status;

/* Run the system until the adopted actor's armed computation leaves the
 * runnable set; spawned actors are scheduled and serviced along the way and
 * survive (parked or runnable) across drives.  After ER_DRIVE_EXN or
 * ER_DRIVE_DEADLOCK the current continuation and its run-local profiling zones
 * are discarded; re-arm the adopted thread before driving it again. */
er_drive_status er_scheduler_drive(er_scheduler* sys, er_actor* root);

typedef enum {
  ER_RUN_IDLE,      /* no live actors: every actor halted or crashed */
  ER_RUN_QUIESCENT, /* live actors remain, all receive-blocked */
} er_run_reason;

/* Drive the system until nothing is runnable. */
er_run_reason er_scheduler_run(er_scheduler* sys);

typedef struct er_mt_config {
  uint32_t workers; /* shared-pool width; 0 = default (hardware or 2) */
} er_mt_config;

/*
 * Optional multithreaded executor.  This runner shares the scheduler/actor
 * objects created by the API above but may run different scheduler-owned
 * actors on different OS threads.  er_mt_executor_drive keeps the adopted
 * root actor on the caller thread while a persistent worker pool runs spawned
 * actors in parallel.  The first descriptor-marked host effect permanently
 * binds a spawned actor to its current worker.  Profiling-only op-83 work does
 * not bind.  That worker runs no other actor; the executor replaces it in the
 * shared pool so a blocking syscall cannot strand unrelated actors.  Finished
 * dedicated workers are retained as spares and reused by later effectful
 * actors.
 *
 * One executor may be attached to a scheduler at a time.  Its threads persist
 * across run/drive calls and are joined by er_mt_executor_free; free the
 * executor before the scheduler.  While it is attached, use its run/drive
 * functions exclusively; effectful actors retain worker affinity between
 * calls.  er_mt_executor_drive has the same adopted-root completion and
 * abandonment contract as er_scheduler_drive.  The deterministic
 * er_scheduler_run / er_scheduler_drive paths remain the replay-capable
 * reference executor after the MT executor is freed; record/replay mode is
 * intentionally rejected here because concurrent direct-effect ordering is
 * nondeterministic.
 */
er_mt_executor* er_mt_executor_new(er_scheduler* sys, er_mt_config cfg);
void er_mt_executor_free(er_mt_executor* ex);
er_run_reason er_mt_executor_run(er_mt_executor* ex);
er_drive_status er_mt_executor_drive(er_mt_executor* ex, er_actor* root);

/*
 * Host injection: append a message to an actor's mailbox (waking it if
 * receive-blocked).  In live mode the payload must already be shareable — a
 * nat63 or any value owned by the scheduler's store (e.g. loaded or explicitly
 * snapshotted) — since it enters the actor's heap without copying.  Recorded
 * and replayed injections have a narrower portable encoding: the payload must
 * be a nat63 or a persistently hashed canonical store PIN.  Unhashed PINs and
 * non-PIN store snapshots cannot be recorded or replayed.  Host threads may
 * inject concurrently with an active MT run/drive call.  With the
 * deterministic executor, inject only between run/drive calls.
 */
void er_scheduler_inject(er_scheduler* sys, er_actor* to, pl_val payload);

/* Live HTTP transfers (op 83 Fetch) registered on this scheduler. */
size_t er_http_inflight_count(const er_scheduler* sys);

er_actor_status er_actor_state(const er_actor* a);
uint64_t er_actor_id(const er_actor* a);
/* Creation-ordered lookup; IDs never reuse. A Spawn actor with no remaining
 * capability may be reclaimed after termination. Lookups are borrowed;
 * C-created/adopted actors remain roots until er_scheduler_free. */
er_actor* er_scheduler_actor_by_id(er_scheduler* sys, uint64_t id);
/* Normal-form result of a retained HALTED actor. C-created actors keep their
 * result until scheduler_free; Spawn actors follow capability reachability. */
pl_val er_actor_result(er_actor* a);

/*
 * ── Event log & replay ─────────────────────────────────────────────────────
 *
 * The log records exactly the external inputs: every direct (unix)
 * effect's result as (actor, op name, args hash, result-nat bytes), every
 * ReadFolder result, every host injection, and every HTTP fetch result, in
 * occurrence order.  Internal events — actor messages, yields, scheduling —
 * are reproducible and never logged.
 *
 * HTTP fetches are the one source of completion-order nondeterminism,
 * so recording constrains when they resume: a completion deposits only
 * when the run queue is empty, exactly one per empty-queue point, with
 * its event appended immediately before the deposit (validation
 * failures deposit at their service point instead).  Replay reaches
 * the same empty-queue points in the same order and consumes one event
 * per point — no curl handle is ever created and the network is never
 * touched; validation is not re-run.
 *
 * Recording: attach with er_scheduler_record before running; direct
 * effects execute live and their results are appended.
 *
 * Replay: attach with er_scheduler_replay (same QUANTUM, same program,
 * same store contents, same embedder script); direct effects
 * perform no syscalls — the logged result is substituted after the
 * (actor, op, args-hash) of the site is verified against the log, and
 * er_scheduler_inject verifies injections likewise.  Injection events encode
 * a nat63 by value or a persistently hashed canonical store PIN by hash;
 * arbitrary store snapshots accepted in live mode are not record/replay
 * payloads.  Any mismatch is a divergence and aborts.  Replay reproduces
 * state, not side effects: Output/Print/Warn write nothing.
 *
 * Limitation: a direct effect that raises a host error (bad handle,
 * failed socket) crashes its actor before a record is appended, so a
 * recorded run replays only up to such a crash.
 */

typedef struct er_log er_log;

er_log* er_log_new(void);
void er_log_free(er_log* log);
size_t er_log_events(const er_log* log);

/* Binary round trip (format: header { magic, version, quantum } then
 * length-prefixed records).  NULL / false on IO or format errors. */
bool er_log_write_file(const er_log* log, const char* path);
er_log* er_log_read_file(const char* path);

/* Record into `log` (its quantum header is taken from this system). */
void er_scheduler_record(er_scheduler* sys, er_log* log);
/* Substitute results from `log`; asserts the quantum matches. */
void er_scheduler_replay(er_scheduler* sys, const er_log* log);
/* Replay cursor (events consumed so far); equals er_log_events when a
 * replayed run consumed the whole recording. */
size_t er_scheduler_log_cursor(const er_scheduler* sys);

#endif
