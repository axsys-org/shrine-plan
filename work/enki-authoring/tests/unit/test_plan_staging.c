#include "test.h"
#include <errno.h>
#include <lmdb.h>
#include <sys/stat.h>
#include <sys/wait.h>

#include "../../pkg/plan/src/store_internal.h"
#include "test_plan.h"

static test_rt staging_open(const char* dir, bool silo) {
  test_rt rt = {0};
  rt.store =
      silo ? pl_store_new_silo(dir, 1 << 20) : pl_store_new_lmdb(dir, 1 << 20);
  ASSERT_NOT_NULL(rt.store);
  rt.heap = pl_heap_new(1 << 16, rt.store);
  rt.t = pl_thread_new(rt.heap);
  return rt;
}

static void staging_cleanup(const char* dir) {
  const char* files[] = {"pins.pack", "data.mdb", "lock.mdb"};
  for (size_t i = 0; i < sizeof(files) / sizeof(files[0]); i++) {
    char path[256];
    snprintf(path, sizeof(path), "%s/%s", dir, files[i]);
    (void)unlink(path);
  }
  (void)rmdir(dir);
}

static void staging_ice(pl_thread* t, size_t slot) {
  pl_val pin = t->vstack[slot];
  ASSERT_EQ(test_op66(t, ax_s3('I', 'c', 'e'), 1, &pin), 0);
  ASSERT_NOT_NULL(pl_pin_hash(t->vstack[slot]));
}

static void staging_save(test_rt* rt, size_t slot) {
  char err[192] = {0};
  ASSERT(pl_store_save_root(rt->store, rt->t->vstack[slot], NULL, err,
                            sizeof(err)),
         "%s", err);
}

typedef struct disk_state {
  size_t txnid;
  bool object, cache, root;
  uint8_t root_hash[32];
} disk_state;

/* Use a separate process: opening the same LMDB twice in one process can
 * interfere with its POSIX locks. Never operate on the inherited store. */
static bool disk_read(const char* dir, bool silo, const uint8_t hash[32],
                      const uint8_t cache[32], disk_state* out) {
  MDB_env* env = NULL;
  MDB_txn* txn = NULL;
  MDB_dbi objects, kv, meta;
  bool ok = false;
  if (mdb_env_create(&env) != 0)
    return false;
  if (mdb_env_set_maxdbs(env, 4) != 0 ||
      mdb_env_open(env, dir, MDB_RDONLY, 0664) != 0 ||
      mdb_txn_begin(env, NULL, MDB_RDONLY, &txn) != 0 ||
      mdb_dbi_open(txn, silo ? "objects" : NULL, 0, &objects) != 0 ||
      mdb_dbi_open(txn, silo ? "codecache" : NULL, 0, &kv) != 0 ||
      mdb_dbi_open(txn, silo ? "meta" : NULL, 0, &meta) != 0)
    goto done;
  out->txnid = mdb_txn_id(txn);
  MDB_val k = {32, (void*)hash}, v;
  out->object = mdb_get(txn, objects, &k, &v) == 0;
  k.mv_data = (void*)cache;
  out->cache = mdb_get(txn, kv, &k, &v) == 0;
  uint8_t root_key[32] = {'r', 'o', 'o', 't'};
  k = (MDB_val){silo ? 4 : 32, root_key};
  out->root = mdb_get(txn, meta, &k, &v) == 0 && v.mv_size == 32;
  if (out->root)
    memcpy(out->root_hash, v.mv_data, 32);
  ok = true;
done:
  if (txn != NULL)
    mdb_txn_abort(txn);
  mdb_env_close(env);
  return ok;
}

static void child_ok(pid_t pid) {
  int status;
  ASSERT_EQ(waitpid(pid, &status, 0), pid);
  ASSERT(WIFEXITED(status));
  ASSERT_EQ(WEXITSTATUS(status), 0, "child exit %d", WEXITSTATUS(status));
}

static disk_state staging_disk(const char* dir, bool silo,
                               const uint8_t hash[32],
                               const uint8_t cache[32]) {
  int fds[2];
  ASSERT_EQ(pipe(fds), 0);
  pid_t pid = fork();
  ASSERT_GTE(pid, 0);
  if (pid == 0) {
    close(fds[0]);
    disk_state out = {0};
    bool ok = disk_read(dir, silo, hash, cache, &out);
    if (ok)
      ok = write(fds[1], &out, sizeof(out)) == (ssize_t)sizeof(out);
    _exit(ok ? 0 : 1);
  }
  close(fds[1]);
  disk_state out = {0};
  ssize_t n;
  do {
    n = read(fds[0], &out, sizeof(out));
  } while (n < 0 && errno == EINTR);
  close(fds[0]);
  child_ok(pid);
  ASSERT_EQ(n, (ssize_t)sizeof(out));
  return out;
}

static void check_staging(bool silo) {
  char dir[] = "/tmp/enki-stage-XXXXXX";
  ASSERT_NOT_NULL(mkdtemp(dir));
  test_rt rt = staging_open(dir, silo);
  pl_thread* t = rt.t;
  uint8_t key[32] = {0xCA}, hash[32], root[32];
  disk_state before = staging_disk(dir, silo, key, key);
  pl_vpush(t, pl_pin(t, 42));
  staging_ice(t, 0);
  memcpy(hash, pl_pin_hash(t->vstack[0]), 32);
  pl_vpush(t, pl_pin(t, 42));
  staging_ice(t, 1);
  ASSERT_EQ(pl_pin_proxy_target(pl_ptr(t->vstack[0])),
            pl_pin_proxy_target(pl_ptr(t->vstack[1])));
  ASSERT(pl_store_backend_put(rt.store, key, (const uint8_t*)"cached", 6));
  uint8_t* bytes = NULL;
  size_t len = 0;
  ASSERT(pl_store_backend_get(rt.store, key, &bytes, &len));
  ASSERT_EQ(len, 6);
  ASSERT_MEM_EQ(bytes, "cached", 6);
  free(bytes);
  if (silo) {
    /* Exercise the staging overlay below the canonical in-memory lookup. */
    pl_silo_reader reader;
    char err[192] = {0};
    ASSERT(pl_store_silo_open(rt.store, hash, &reader, err, sizeof(err)));
    ASSERT_GT(reader.len, 0);
    uint8_t byte;
    ASSERT(reader.read(reader.ctx, &byte, 1));
    pl_store_silo_close_reader(&reader);
  }
  disk_state iced = staging_disk(dir, silo, hash, key);
  ASSERT_EQ(iced.txnid, before.txnid);
  ASSERT_FALSE(iced.object);
  ASSERT_FALSE(iced.cache);
  ASSERT_FALSE(iced.root);
  ASSERT_FALSE(pl_store_get_root(rt.store, root));
  staging_save(&rt, 0);
  disk_state saved = staging_disk(dir, silo, hash, key);
  ASSERT_EQ(saved.txnid, before.txnid + 1);
  ASSERT(saved.object && saved.cache && saved.root);
  ASSERT_MEM_EQ(saved.root_hash, hash, 32);

  /* Save the same root after staging an unrelated pin and replacing a KV. */
  pl_vpush(t, pl_pin(t, 43));
  staging_ice(t, 2);
  memcpy(hash, pl_pin_hash(t->vstack[2]), 32);
  ASSERT(pl_store_backend_put(rt.store, key, (const uint8_t*)"new", 3));
  iced = staging_disk(dir, silo, hash, key);
  ASSERT_EQ(iced.txnid, saved.txnid);
  ASSERT_FALSE(iced.object);
  staging_save(&rt, 0);
  disk_state again = staging_disk(dir, silo, hash, key);
  ASSERT_EQ(again.txnid, saved.txnid + 1);
  ASSERT(again.object);
  ASSERT_MEM_EQ(again.root_hash, saved.root_hash, 32);
  if (silo)
    ASSERT_EQ(pl_store_root_log_head(rt.store), 1);
  test_rt_free(&rt);
  rt = staging_open(dir, silo);
  ASSERT_EQ(pl_pin_body(pl_ptr(pl_store_load(rt.t, hash))), 43);
  ASSERT(pl_store_backend_get(rt.store, key, &bytes, &len));
  ASSERT_EQ(len, 3);
  ASSERT_MEM_EQ(bytes, "new", 3);
  free(bytes);
  test_rt_free(&rt);
  staging_cleanup(dir);
}

TEST(staging, silo_ice_does_not_commit) {
  check_staging(true);
}
TEST(staging, legacy_ice_does_not_commit) {
  check_staging(false);
}

static void check_retry(bool silo) {
  char dir[] = "/tmp/enki-stage-retry-XXXXXX";
  ASSERT_NOT_NULL(mkdtemp(dir));
  test_rt rt = staging_open(dir, silo);
  pl_vpush(rt.t, pl_pin(rt.t, 42));
  staging_save(&rt, 0);
  pl_vpush(rt.t, pl_pin(rt.t, 43));
  staging_ice(rt.t, 1);
  uint8_t key[32] = {0xCB}, hash[32];
  memcpy(hash, pl_pin_hash(rt.t->vstack[1]), 32);
  disk_state before = staging_disk(dir, silo, hash, key);
  /* Staging can exceed the LMDB map. Save fails atomically, retaining the
   * entire overlay; replacing the oversized cache row allows a retry. */
  size_t large_len = 2 << 20;
  uint8_t* large = calloc(1, large_len);
  ASSERT_NOT_NULL(large);
  ASSERT(pl_store_backend_put(rt.store, key, large, large_len));
  free(large);
  char err[192] = {0};
  ASSERT_FALSE(
      pl_store_save_root(rt.store, rt.t->vstack[1], NULL, err, sizeof(err)));
  disk_state failed = staging_disk(dir, silo, hash, key);
  ASSERT_EQ(failed.txnid, before.txnid);
  ASSERT_MEM_EQ(failed.root_hash, before.root_hash, 32);
  ASSERT_FALSE(failed.object || failed.cache);
  ASSERT_EQ(pl_pin_body(pl_ptr(pl_store_load(rt.t, hash))), 43);
  staging_ice(rt.t, 1);
  ASSERT(pl_store_backend_put(rt.store, key, (const uint8_t*)"ok", 2));
  staging_save(&rt, 1);
  disk_state saved = staging_disk(dir, silo, hash, key);
  ASSERT_EQ(saved.txnid, before.txnid + 1);
  ASSERT(saved.object && saved.cache);
  ASSERT_MEM_EQ(saved.root_hash, hash, 32);
  test_rt_free(&rt);
  rt = staging_open(dir, silo);
  ASSERT_EQ(pl_pin_body(pl_ptr(pl_store_load(rt.t, hash))), 43);
  test_rt_free(&rt);
  staging_cleanup(dir);
}

TEST(staging, silo_failed_save_retains_staging) {
  check_retry(true);
}
TEST(staging, legacy_failed_save_retains_staging) {
  check_retry(false);
}

TEST(staging, closing_keeps_saved_root_and_discards_later_ice) {
  for (unsigned silo = 0; silo < 2; silo++) {
    char dir[] = "/tmp/enki-stage-discard-XXXXXX";
    ASSERT_NOT_NULL(mkdtemp(dir));
    test_rt rt = staging_open(dir, silo != 0);
    pl_vpush(rt.t, pl_pin(rt.t, 42));
    staging_save(&rt, 0);
    uint8_t root[32], staged[32];
    ASSERT(pl_store_get_root(rt.store, root));
    pl_vpush(rt.t, pl_pin(rt.t, 43));
    staging_ice(rt.t, 1);
    memcpy(staged, pl_pin_hash(rt.t->vstack[1]), 32);
    test_rt_free(&rt);
    rt = staging_open(dir, silo != 0);
    ASSERT_FALSE(rt.store->be.has(rt.store->be.ctx, staged));
    uint8_t current[32];
    ASSERT(pl_store_get_root(rt.store, current));
    ASSERT_MEM_EQ(current, root, 32);
    ASSERT_EQ(pl_pin_body(pl_ptr(pl_store_load(rt.t, root))), 42);
    test_rt_free(&rt);
    staging_cleanup(dir);
  }
}

TEST(staging, close_discards_staging_without_truncating_another_writer) {
  char dir[] = "/tmp/enki-stage-writers-XXXXXX";
  ASSERT_NOT_NULL(mkdtemp(dir));
  for (unsigned checkpoint = 0; checkpoint < 2; checkpoint++) {
    test_rt rt = staging_open(dir, true);
    pl_vpush(rt.t, pl_pin(rt.t, 40 + checkpoint));
    staging_ice(rt.t, 0);
    uint8_t staged_hash[32];
    memcpy(staged_hash, pl_pin_hash(rt.t->vstack[0]), 32);
    pid_t pid = fork();
    ASSERT_GTE(pid, 0);
    if (pid == 0) {
      pl_store* s = pl_store_new_silo(dir, 1 << 20);
      if (s == NULL)
        _exit(1);
      pl_heap* h = pl_heap_new(1 << 16, s);
      pl_thread* t = pl_thread_new(h);
      /* On the second iteration this duplicates the parent's staged pin. */
      pl_vpush(t, pl_pin(t, checkpoint ? 41 : 99));
      char err[192];
      bool ok = pl_store_save_root(s, t->vstack[0], NULL, err, sizeof(err));
      pl_thread_free(t);
      pl_heap_free(h);
      pl_store_free(s);
      _exit(ok ? 0 : 1);
    }
    child_ok(pid);
    uint8_t root[32];
    ASSERT(pl_store_get_root(rt.store, root));
    ASSERT_EQ(pl_pin_body(pl_ptr(pl_store_load(rt.t, root))),
              checkpoint ? 41 : 99);
    if (checkpoint)
      staging_save(&rt, 0); /* accept the other writer's index for our hash */
    test_rt_free(&rt);
    disk_state disk = staging_disk(dir, true, staged_hash, staged_hash);
    ASSERT_EQ(disk.object, checkpoint != 0);
    rt = staging_open(dir, true);
    ASSERT_EQ(pl_pin_body(pl_ptr(pl_store_load(rt.t, root))),
              checkpoint ? 41 : 99);
    test_rt_free(&rt);
  }
  staging_cleanup(dir);
}

/* All cache activity lives in children so each phase starts with empty
 * process-global Memo/compiler maps and the environment is test-local. */
TEST(staging, global_cache_only_commits_on_save) {
  char dir[] = "/tmp/enki-stage-cache-XXXXXX";
  ASSERT_NOT_NULL(mkdtemp(dir));
  char path[256];
  snprintf(path, sizeof(path), "%s/data.mdb", dir);
  for (unsigned phase = 0; phase < 4; phase++) {
    pid_t pid = fork();
    ASSERT_GTE(pid, 0);
    if (pid == 0) {
      if (setenv("PL_CODECACHE_DIR", dir, 1) != 0 ||
          setenv("PL_CODECACHE", "1", 1) != 0)
        _exit(1);
      uint8_t f[32] = {0xF1}, x[32] = {0xF2};
      if (phase == 3)
        x[0] = 0xF3;
      uint64_t out = 0;
      bool found = pl_memo_probe(f, x, &out);
      if (phase == 3)
        _exit(found && out == 43 ? 0 : 2);
      if (phase == 2 && (!found || out != 42))
        _exit(3);
      if (phase < 2 && found)
        _exit(3);
      if (phase == 2)
        x[0] = 0xF3;
      uint64_t value = phase == 2 ? 43 : 42;
      pl_memo_record(f, x, value);
      if (!pl_memo_probe(f, x, &out) || out != value ||
          (phase < 2 && access(path, F_OK) == 0))
        _exit(4);
      if (phase != 0) {
        /* Phase 2 upgrades the read-only cache opened by the probe. */
        test_rt rt = test_rt_new();
        pl_vpush(rt.t, pl_pin(rt.t, 1));
        char err[192];
        bool ok = pl_store_save_root(rt.store, rt.t->vstack[0], NULL, err,
                                     sizeof(err));
        test_rt_free(&rt);
        if (!ok || access(path, F_OK) != 0)
          _exit(5);
      }
      _exit(0);
    }
    child_ok(pid);
  }
  staging_cleanup(dir);
}
