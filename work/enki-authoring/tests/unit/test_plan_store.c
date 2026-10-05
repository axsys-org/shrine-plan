#include "test.h"
#include <errno.h>
#include <fcntl.h>
#include <lmdb.h>
#include <pthread.h>
#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <sys/wait.h>
#include <unistd.h>

#include "axsys/allocator.h"
#include "axsys/ds.h"
#include "axsys/profile.h"
#include "axsys/sha256.h"
#include "plan/canon.h"
#include "../../pkg/plan/src/store_internal.h"
#include "test_plan.h"

typedef struct store_lock_probe {
  pl_store* store;
  bool acquired;
} store_lock_probe;

typedef struct store_both_lock_probe {
  pl_store* store;
  bool general_acquired;
  bool save_acquired;
} store_both_lock_probe;

typedef struct save_probe_blob {
  uint8_t* bytes;
  size_t len;
} save_probe_blob;

typedef struct save_probe_entry {
  pl_hash key;
  save_probe_blob value;
} save_probe_entry;

typedef struct save_probe_backend {
  pthread_mutex_t mu;
  pthread_cond_t cv;
  save_probe_entry* objects;
  uint8_t root[32];
  bool has_root;
  bool block_put;
  bool put_entered;
  bool release_put;
  bool fail_root;
  bool fail_put;
  unsigned active_puts;
  unsigned max_active_puts;
} save_probe_backend;

typedef struct save_root_worker {
  pl_store* store;
  pl_val root;
  uint8_t hash[32];
  char err[192];
  bool ok;
} save_root_worker;

static void* store_trylock_thread(void* arg) {
  store_lock_probe* probe = arg;
  probe->acquired = pthread_mutex_trylock(&probe->store->mu) == 0;
  if (probe->acquired)
    (void)pthread_mutex_unlock(&probe->store->mu);
  return NULL;
}

static void* store_try_both_locks_thread(void* arg) {
  store_both_lock_probe* probe = arg;
  probe->general_acquired = pthread_mutex_trylock(&probe->store->mu) == 0;
  if (probe->general_acquired)
    (void)pthread_mutex_unlock(&probe->store->mu);
  probe->save_acquired = pthread_mutex_trylock(&probe->store->save_mu) == 0;
  if (probe->save_acquired)
    (void)pthread_mutex_unlock(&probe->store->save_mu);
  return NULL;
}

static bool test_pin_raises(pl_thread* t, pl_val value) {
  pl_catch c;
  pl_catch_init(t, &c);
  if (setjmp(c.jb) == 0) {
    (void)pl_pin(t, value);
    pl_catch_pop(t, &c);
    return false;
  }
  pl_catch_unwind(t, &c);
  return true;
}

static pl_val test_lazy_app1(pl_thread* t, pl_val value) {
  size_t base = t->vsp;
  pl_vpush(t, test_app1(t, 0, value));
  pl_gc_reserve(t, PL_ENV_CELLS(1) + PL_THUNK_CELLS);
  pl_vpush(t, pl_mk_env(t, 1));
  pl_vpush(t, pl_mk_thunk(t, t->vstack[base + 1], t->vstack[base]));
  pl_val out = test_app1(t, 0, t->vstack[base + 2]);
  t->vsp = base;
  return out;
}

static bool test_store_load_raises(pl_thread* t, const uint8_t hash[32]) {
  pl_catch c;
  pl_catch_init(t, &c);
  if (setjmp(c.jb) == 0) {
    (void)pl_store_load(t, hash);
    pl_catch_pop(t, &c);
    return false;
  }
  pl_catch_unwind(t, &c);
  return true;
}

static bool save_probe_get(void* ctx, const uint8_t hash[32], uint8_t** out,
                           size_t* out_len) {
  save_probe_backend* backend = ctx;
  pl_hash key;
  memcpy(key.b, hash, sizeof(key.b));
  (void)pthread_mutex_lock(&backend->mu);
  ptrdiff_t at = ax_hmgeti(backend->objects, key);
  if (at < 0) {
    (void)pthread_mutex_unlock(&backend->mu);
    return false;
  }
  size_t len = backend->objects[at].value.len;
  uint8_t* bytes = malloc(len != 0 ? len : 1);
  if (bytes == NULL) {
    (void)pthread_mutex_unlock(&backend->mu);
    return false;
  }
  memcpy(bytes, backend->objects[at].value.bytes, len);
  (void)pthread_mutex_unlock(&backend->mu);
  *out = bytes;
  *out_len = len;
  return true;
}

static bool save_probe_put(void* ctx, const uint8_t hash[32], const uint8_t* b,
                           size_t len) {
  save_probe_backend* backend = ctx;
  pl_hash key;
  memcpy(key.b, hash, sizeof(key.b));
  (void)pthread_mutex_lock(&backend->mu);
  backend->active_puts++;
  if (backend->active_puts > backend->max_active_puts)
    backend->max_active_puts = backend->active_puts;
  backend->put_entered = true;
  (void)pthread_cond_broadcast(&backend->cv);
  while (backend->block_put && !backend->release_put)
    (void)pthread_cond_wait(&backend->cv, &backend->mu);

  bool ok = !backend->fail_put;
  if (ok && ax_hmgeti(backend->objects, key) < 0) {
    uint8_t* copy = malloc(len != 0 ? len : 1);
    if (copy == NULL) {
      ok = false;
    } else {
      memcpy(copy, b, len);
      ax_hmput(backend->objects, key,
               ((save_probe_blob){.bytes = copy, .len = len}));
    }
  }
  backend->active_puts--;
  (void)pthread_cond_broadcast(&backend->cv);
  (void)pthread_mutex_unlock(&backend->mu);
  return ok;
}

static bool save_probe_has(void* ctx, const uint8_t hash[32]) {
  save_probe_backend* backend = ctx;
  pl_hash key;
  memcpy(key.b, hash, sizeof(key.b));
  (void)pthread_mutex_lock(&backend->mu);
  bool found = ax_hmgeti(backend->objects, key) >= 0;
  (void)pthread_mutex_unlock(&backend->mu);
  return found;
}

static bool save_probe_put_root(void* ctx, const uint8_t hash[32]) {
  save_probe_backend* backend = ctx;
  (void)pthread_mutex_lock(&backend->mu);
  bool ok = !backend->fail_root;
  if (ok) {
    memcpy(backend->root, hash, sizeof(backend->root));
    backend->has_root = true;
  }
  (void)pthread_mutex_unlock(&backend->mu);
  return ok;
}

static bool save_probe_get_root(void* ctx, uint8_t hash[32]) {
  save_probe_backend* backend = ctx;
  (void)pthread_mutex_lock(&backend->mu);
  bool ok = backend->has_root;
  if (ok)
    memcpy(hash, backend->root, sizeof(backend->root));
  (void)pthread_mutex_unlock(&backend->mu);
  return ok;
}

static void save_probe_close(void* ctx) {
  save_probe_backend* backend = ctx;
  for (ptrdiff_t i = 0; i < ax_hmlen(backend->objects); i++)
    free(backend->objects[i].value.bytes);
  ax_hmfree(backend->objects);
  (void)pthread_cond_destroy(&backend->cv);
  (void)pthread_mutex_destroy(&backend->mu);
  free(backend);
}

static pl_store* save_probe_store(save_probe_backend** out_backend) {
  save_probe_backend* backend = calloc(1, sizeof(*backend));
  ASSERT_NOT_NULL(backend);
  ASSERT_EQ(pthread_mutex_init(&backend->mu, NULL), 0);
  ASSERT_EQ(pthread_cond_init(&backend->cv, NULL), 0);
  *out_backend = backend;
  return pl_store_new((pl_store_backend){
      .ctx = backend,
      .get = save_probe_get,
      .put = save_probe_put,
      .has = save_probe_has,
      .put_root = save_probe_put_root,
      .get_root = save_probe_get_root,
      .close = save_probe_close,
  });
}

static void* save_root_thread(void* arg) {
  save_root_worker* worker = arg;
  worker->ok = pl_store_save_root(worker->store, worker->root, worker->hash,
                                  worker->err, sizeof(worker->err));
  return NULL;
}

static bool store_test_ice(pl_thread* t, pl_val pin) {
  pl_catch c;
  pl_catch_init(t, &c);
  if (setjmp(c.jb) == 0) {
    pl_val result = test_op66(t, ax_s3('I', 'c', 'e'), 1, &pin);
    pl_catch_pop(t, &c);
    ASSERT_EQ(result, 0);
    return true;
  }
  pl_catch_unwind(t, &c);
  return false;
}

TEST(store, ice_failure_is_retryable_without_root_or_snapshot_publication) {
  save_probe_backend* backend = NULL;
  pl_store* s = save_probe_store(&backend);
  pl_heap* h = pl_heap_new(1 << 16, s);
  pl_thread* t = pl_thread_new(h);
  size_t base = t->vsp;
  pl_vpush(t, pl_pin(t, 1));
  uint8_t root[32];
  char err[192] = {0};
  ASSERT(pl_store_save_root(s, t->vstack[base], root, err, sizeof(err)), "%s",
         err);
  pl_vpush(t, test_lazy_app1(t, 42));
  t->vstack[base + 1] = pl_pin(t, t->vstack[base + 1]);
  pl_vpush(t, test_app1(t, 0, t->vstack[base + 1]));
  t->vstack[base + 2] = pl_pin(t, t->vstack[base + 2]);
  size_t mark = pl_store_mark(s);
  ptrdiff_t intern_count = ax_hmlen(s->intern);
  backend->fail_put = true;
  ASSERT_FALSE(store_test_ice(t, t->vstack[base + 2]));
  ASSERT_STR_EQ(t->exn_msg, "Ice: Legacy store backend put failed");
  ASSERT_EQ(pl_store_mark(s), mark);
  ASSERT_EQ(ax_hmlen(s->intern), intern_count);
  for (size_t i = 1; i <= 2; i++) {
    ASSERT_EQ(pl_pin_proxy_target(pl_ptr(t->vstack[base + i])), 0);
    ASSERT_NULL(pl_pin_hash(t->vstack[base + i]));
  }
  ASSERT_EQ(memcmp(backend->root, root, sizeof(root)), 0);

  backend->fail_put = false;
  backend->fail_root = true; /* Ice must not try to publish a root. */
  char dir[] = "/tmp/enki-test-ice-XXXXXX";
  ASSERT_NOT_NULL(mkdtemp(dir));
  char* cwd = getcwd(NULL, 0);
  ASSERT_NOT_NULL(cwd);
  ASSERT_EQ(chdir(dir), 0);
  bool ok = store_test_ice(t, t->vstack[base + 2]);
  ASSERT_EQ(chdir(cwd), 0);
  free(cwd);
  ASSERT(ok, "%s", t->exn_msg != NULL ? t->exn_msg : "Ice failed");
  char snap_path[128];
  snprintf(snap_path, sizeof(snap_path), "%s/snap", dir);
  struct stat st;
  ASSERT_EQ(stat(snap_path, &st), -1);
  ASSERT_EQ(errno, ENOENT);
  ASSERT_EQ(rmdir(dir), 0);
  for (size_t i = 1; i <= 2; i++) {
    ASSERT_NOT_NULL(pl_pin_hash(t->vstack[base + i]));
    ASSERT(save_probe_has(backend, pl_pin_hash(t->vstack[base + i])));
  }
  ASSERT_EQ(memcmp(backend->root, root, sizeof(root)), 0);
  ASSERT(store_test_ice(t, t->vstack[base + 2]));
  pl_thread_free(t);
  pl_heap_free(h);
  pl_store_free(s);
}

TEST(store, save_persistence_does_not_hold_general_store_lock) {
  save_probe_backend* backend;
  pl_store* store = save_probe_store(&backend);
  pl_heap* heap = pl_heap_new(1 << 16, store);
  pl_thread* t = pl_thread_new(heap);
  pl_vpush(t, test_law(t, 1, 7, 42));
  pl_val root = pl_pin(t, t->vstack[t->vsp - 1]);

  backend->block_put = true;
  save_root_worker worker = {.store = store, .root = root};
  pthread_t thread;
  ASSERT_EQ(pthread_create(&thread, NULL, save_root_thread, &worker), 0);

  (void)pthread_mutex_lock(&backend->mu);
  while (!backend->put_entered)
    (void)pthread_cond_wait(&backend->cv, &backend->mu);
  (void)pthread_mutex_unlock(&backend->mu);

  int general_rc = pthread_mutex_trylock(&store->mu);
  if (general_rc == 0)
    (void)pthread_mutex_unlock(&store->mu);
  int save_rc = pthread_mutex_trylock(&store->save_mu);
  if (save_rc == 0)
    (void)pthread_mutex_unlock(&store->save_mu);

  (void)pthread_mutex_lock(&backend->mu);
  backend->release_put = true;
  (void)pthread_cond_broadcast(&backend->cv);
  (void)pthread_mutex_unlock(&backend->mu);
  ASSERT_EQ(pthread_join(thread, NULL), 0);

  ASSERT_EQ(general_rc, 0,
            "backend persistence retained the general store lock");
  ASSERT_EQ(save_rc, EBUSY, "Save did not retain its persistence mutex");
  ASSERT(worker.ok, "%s", worker.err);
  ASSERT_EQ(backend->max_active_puts, 1);

  pl_thread_free(t);
  pl_heap_free(heap);
  pl_store_free(store);
}

TEST(store, legacy_failed_root_is_arena_and_publication_rollback) {
  save_probe_backend* backend;
  pl_store* store = save_probe_store(&backend);
  pl_heap* heap = pl_heap_new(1 << 16, store);
  pl_thread* t = pl_thread_new(heap);
  size_t base = t->vsp;
  pl_vpush(t, 42);
  t->vstack[base] = pl_pin(t, t->vstack[base]);
  pl_vpush(t, test_app2(t, 0, t->vstack[base], 7));
  t->vstack[base + 1] = pl_pin(t, t->vstack[base + 1]);
  pl_val child = t->vstack[base];
  pl_val parent = t->vstack[base + 1];

  size_t mark = pl_store_mark(store);
  ptrdiff_t intern_count = ax_hmlen(store->intern);
  ptrdiff_t pin_count = ax_arrlen(store->pins);
  backend->fail_root = true;
  char err[192] = {0};
  ASSERT_FALSE(pl_store_save_root(store, parent, NULL, err, sizeof(err)), "%s",
               err);
  ASSERT_STR_EQ(err, "Legacy root publication failed");
  ASSERT_EQ(pl_store_mark(store), mark);
  ASSERT_EQ(ax_hmlen(store->intern), intern_count);
  ASSERT_EQ(ax_arrlen(store->pins), pin_count);
  ASSERT_EQ(pl_pin_proxy_target(pl_ptr(child)), 0);
  ASSERT_EQ(pl_pin_proxy_target(pl_ptr(parent)), 0);
  ASSERT_NULL(pl_pin_hash(child));
  ASSERT_NULL(pl_pin_hash(parent));

  backend->fail_root = false;
  ASSERT(pl_store_save_root(store, parent, NULL, err, sizeof(err)), "%s", err);
  ASSERT_NEQ(pl_pin_proxy_target(pl_ptr(child)), 0);
  ASSERT_NEQ(pl_pin_proxy_target(pl_ptr(parent)), 0);

  pl_thread_free(t);
  pl_heap_free(heap);
  pl_store_free(store);
}

TEST(store, snapshots_share_closed_store_graphs) {
  pl_store* store = pl_store_new_mem();
  pl_heap* heap = pl_heap_new(1 << 16, store);
  pl_thread* t = pl_thread_new(heap);
  size_t base = t->vsp;
  pl_vpush(t, 0);
  for (size_t i = 0; i < 512; i++)
    t->vstack[base] = test_app2(t, 0, i, t->vstack[base]);
  t->vstack[base] = pl_pin(t, t->vstack[base]);
  uint8_t hash[32];
  char err[192] = {0};
  ASSERT(pl_store_save_root(store, t->vstack[base], hash, err, sizeof(err)), "%s", err);
  pl_val shared = pl_pin_body(pl_ptr(t->vstack[base]));
  size_t before = pl_store_mark(store);
  for (size_t i = 0; i < 20; i++) {
    pl_vpush(t, test_app2(t, 0, i, shared));
    t->vstack[base + 1] = pl_pin(t, t->vstack[base + 1]);
    ASSERT(pl_store_save_root(store, t->vstack[base + 1], hash, err, sizeof(err)), "%s", err);
    pl_val body = pl_pin_body(pl_ptr(t->vstack[base + 1]));
    ASSERT_EQ(pl_app_args(pl_ptr(body))[1], shared);
    t->vsp = base + 1;
  }
  ASSERT_LT(pl_store_mark(store) - before, 4096);
  /* Persisted values retain their ordinary hashes and are still loadable. */
  pl_val loaded = pl_store_load(t, hash);
  ASSERT_EQ(pl_app_args(pl_ptr(pl_pin_body(pl_ptr(loaded))))[0], 19);
  t->vsp = base;
  pl_thread_free(t);
  pl_heap_free(heap);
  pl_store_free(store);
}

TEST(store, pins_saved_together_share_moving_substructure) {
  pl_store* store = pl_store_new_mem();
  pl_heap* heap = pl_heap_new(1 << 16, store);
  pl_thread* t = pl_thread_new(heap);
  pl_vpush(t, 0);
  for (size_t i = 0; i < 512; i++)
    t->vstack[0] = test_app2(t, 0, i, t->vstack[0]);
  pl_vpush(t, test_app2(t, 0, 1, t->vstack[0]));
  t->vstack[1] = pl_pin(t, t->vstack[1]);
  pl_vpush(t, test_app2(t, 0, 2, t->vstack[0]));
  t->vstack[2] = pl_pin(t, t->vstack[2]);
  pl_vpush(t, test_app2(t, 0, t->vstack[1], t->vstack[2]));
  t->vstack[3] = pl_pin(t, t->vstack[3]);
  uint8_t hash[32];
  char err[192] = {0};
  ASSERT(pl_store_save_root(store, t->vstack[3], hash, err, sizeof(err)), "%s", err);
  pl_val left = pl_pin_body(pl_ptr(t->vstack[1]));
  pl_val right = pl_pin_body(pl_ptr(t->vstack[2]));
  ASSERT_EQ(pl_app_args(pl_ptr(left))[1], pl_app_args(pl_ptr(right))[1]);
  t->vsp = 0;
  pl_thread_free(t);
  pl_heap_free(heap);
  pl_store_free(store);
}

TEST(store, legacy_parent_hash_includes_pinned_nat_body) {
  pl_store* store = pl_store_new_mem();
  pl_heap* heap = pl_heap_new(1 << 16, store);
  pl_thread* t = pl_thread_new(heap);
  size_t base = t->vsp;
  pl_vpush(t, 42);
  t->vstack[base] = pl_pin(t, t->vstack[base]);
  pl_vpush(t, test_app2(t, 0, t->vstack[base], 7));
  t->vstack[base + 1] = pl_pin(t, t->vstack[base + 1]);
  pl_val child = t->vstack[base];
  pl_val parent = t->vstack[base + 1];

  uint8_t saved_hash[32];
  char err[192] = {0};
  ASSERT(pl_store_save_root(store, parent, saved_hash, err, sizeof(err)), "%s",
         err);
  pl_val canonical_child = pl_pin_proxy_target(pl_ptr(child));
  pl_val canonical_parent = pl_pin_proxy_target(pl_ptr(parent));
  ASSERT_NEQ(canonical_child, 0);
  ASSERT_NEQ(canonical_parent, 0);
  ASSERT_EQ(pl_pin_body(pl_ptr(canonical_child)), 42);
  pl_val parent_body = pl_pin_body(pl_ptr(canonical_parent));
  pl_cell* body = pl_as(PL_TAG_APP, parent_body);
  ASSERT_NOT_NULL(body);
  ASSERT_EQ(pl_app_args(body)[0], canonical_child);

  size_t text_len = 0;
  char* text = pl_canonize(ax_allocator_system(), parent_body, &text_len);
  uint8_t expected_hash[32];
  ax_sha256((const uint8_t*)text, text_len, expected_hash);
  ax_free(ax_allocator_system(), text);
  ASSERT_EQ(memcmp(saved_hash, expected_hash, sizeof(saved_hash)), 0);

  pl_thread_free(t);
  pl_heap_free(heap);
  pl_store_free(store);
}

TEST(store,
     legacy_mixed_known_and_provisional_equal_children_share_wire_entry) {
  save_probe_backend* backend;
  pl_store* store = save_probe_store(&backend);
  pl_heap* heap = pl_heap_new(1 << 16, store);
  pl_thread* t = pl_thread_new(heap);
  size_t base = t->vsp;

  pl_vpush(t, 42);
  t->vstack[base] = pl_pin(t, t->vstack[base]);
  uint8_t child_hash[32];
  char err[192] = {0};
  ASSERT(
      pl_store_save_root(store, t->vstack[base], child_hash, err, sizeof(err)),
      "%s", err);
  pl_val known = pl_pin_proxy_target(pl_ptr(t->vstack[base]));
  ASSERT_NEQ(known, 0);

  pl_vpush(t, 42);
  t->vstack[base + 1] = pl_pin(t, t->vstack[base + 1]);
  pl_vpush(t, test_app2(t, 0, t->vstack[base + 1], known));
  t->vstack[base + 2] = pl_pin(t, t->vstack[base + 2]);

  uint8_t parent_hash[32];
  ASSERT(pl_store_save_root(store, t->vstack[base + 2], parent_hash, err,
                            sizeof(err)),
         "%s", err);
  pl_val fresh = pl_pin_proxy_target(pl_ptr(t->vstack[base + 1]));
  pl_val parent = pl_pin_proxy_target(pl_ptr(t->vstack[base + 2]));
  ASSERT_EQ(fresh, known);
  ASSERT_NEQ(parent, 0);
  ASSERT_EQ(pl_pin_npins(pl_ptr(parent)), 1);
  pl_cell* parent_body = pl_as(PL_TAG_APP, pl_pin_body(pl_ptr(parent)));
  ASSERT_NOT_NULL(parent_body);
  ASSERT_EQ(pl_app_args(parent_body)[0], known);
  ASSERT_EQ(pl_app_args(parent_body)[1], known);

  uint8_t* wire = NULL;
  size_t wire_len = 0;
  ASSERT(save_probe_get(backend, parent_hash, &wire, &wire_len));
  ASSERT_GTE(wire_len, 41);
  ASSERT_EQ(wire[0], 1);
  ASSERT_EQ(wire[1], 1);
  for (size_t i = 2; i < 9; i++)
    ASSERT_EQ(wire[i], 0);
  ASSERT_EQ(memcmp(wire + 9, child_hash, sizeof(child_hash)), 0);
  free(wire);

  pl_store* reload = pl_store_new((pl_store_backend){
      .ctx = backend,
      .get = save_probe_get,
      .put = save_probe_put,
      .has = save_probe_has,
      .put_root = save_probe_put_root,
      .get_root = save_probe_get_root,
  });
  pl_heap* reload_heap = pl_heap_new(1 << 16, reload);
  pl_thread* reload_t = pl_thread_new(reload_heap);
  pl_val loaded = pl_store_load(reload_t, parent_hash);
  ASSERT_EQ(pl_pin_npins(pl_ptr(loaded)), 1);
  pl_cell* loaded_body = pl_as(PL_TAG_APP, pl_pin_body(pl_ptr(loaded)));
  ASSERT_NOT_NULL(loaded_body);
  ASSERT_EQ(pl_app_args(loaded_body)[0], pl_app_args(loaded_body)[1]);
  ASSERT_EQ(pl_pin_subpins(pl_ptr(loaded))[0], pl_app_args(loaded_body)[0]);
  ASSERT_EQ(memcmp(pl_pin_hash(pl_pin_subpins(pl_ptr(loaded))[0]), child_hash,
                   sizeof(child_hash)),
            0);

  pl_thread_free(reload_t);
  pl_heap_free(reload_heap);
  pl_store_free(reload);
  pl_thread_free(t);
  pl_heap_free(heap);
  pl_store_free(store);
}

static char* store_test_read_file(const char* path) {
  FILE* f = fopen(path, "rb");
  ASSERT_NOT_NULL(f);
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

static size_t store_test_count(const char* haystack, const char* needle) {
  size_t count = 0;
  size_t needle_n = strlen(needle);
  for (const char* p = haystack; (p = strstr(p, needle)) != NULL; p += needle_n)
    count++;
  return count;
}

/* ── Interning ─────────────────────────────────────────────────────────── */

TEST(store, save_treats_canonical_descendants_as_opaque_leaves) {
  save_probe_backend* backend;
  pl_store* store = save_probe_store(&backend);
  pl_heap* heap = pl_heap_new(1 << 16, store);
  pl_thread* t = pl_thread_new(heap);
  size_t base = t->vsp;

  pl_vpush(t, 42);
  t->vstack[base] = pl_pin(t, t->vstack[base]);
  char err[192] = {0};
  ASSERT(pl_store_save_root(store, t->vstack[base], NULL, err, sizeof(err)),
         "%s", err);
  pl_val known = pl_pin_proxy_target(pl_ptr(t->vstack[base]));
  pl_cell* known_p = pl_ptr(known);
  ASSERT_NEQ(known, 0);
  ASSERT(pl_store_owns(store, known));
  ASSERT_NOT_NULL(pl_pin_hash(known));
  ASSERT(save_probe_has(backend, pl_pin_hash(known)));

  /* A canonical child's body is outside a later Save's discovery domain.  Use
   * an unsupported tag as a tripwire, then restore the immutable value before
   * examining the newly promoted parent.  Descending into known_p would make
   * Save report "non-normal tag" before the parent can be persisted. */
  pl_val known_body = pl_pin_body(known_p);
  known_p[5] = pl_make(PL_TAG_ENV, known_p);
  pl_vpush(t, test_app2(t, 0, known, 7));
  t->vstack[base + 1] = pl_pin(t, t->vstack[base + 1]);
  bool saved =
      pl_store_save_root(store, t->vstack[base + 1], NULL, err, sizeof(err));
  known_p[5] = known_body;
  ASSERT(saved, "%s", err);

  pl_val parent = pl_pin_proxy_target(pl_ptr(t->vstack[base + 1]));
  ASSERT_NEQ(parent, 0);
  ASSERT_EQ(pl_pin_npins(pl_ptr(parent)), 1);
  ASSERT_EQ(pl_pin_subpins(pl_ptr(parent))[0], known);
  pl_cell* body = pl_as(PL_TAG_APP, pl_pin_body(pl_ptr(parent)));
  ASSERT_NOT_NULL(body);
  ASSERT_EQ(pl_app_args(body)[0], known);

  pl_thread_free(t);
  pl_heap_free(heap);
  pl_store_free(store);
}

TEST(store, compiler_install_is_generation_idempotent) {
  pl_store* s = pl_store_new_mem();
  pl_heap* h = pl_heap_new(1 << 16, s);
  pl_thread* t = pl_thread_new(h);
  pl_vpush(t, test_law(t, 1, 7, 1));
  pl_val pin = pl_pin(t, t->vstack[t->vsp - 1]);
  char save_err[192] = {0};
  ASSERT(pl_store_save_root(s, pin, NULL, save_err, sizeof(save_err)), "%s",
         save_err);
  pl_hash law_key;
  memcpy(law_key.b, pl_pin_hash(pin), sizeof(law_key.b));

  uint8_t enabled[32];
  for (size_t i = 0; i < sizeof(enabled); i++)
    enabled[i] = (uint8_t)i;

  ASSERT(pl_store_put_compiler(s, enabled));
  pl_thread* installed_t = s->compiler_t;
  pl_heap* installed_h = s->compiler_h;
  ASSERT_NOT_NULL(installed_t);
  ASSERT_NOT_NULL(installed_h);
  ASSERT_FALSE(pl_store_put_compiler(s, enabled));
  ASSERT_EQ(s->compiler_t, installed_t);
  ASSERT_EQ(s->compiler_h, installed_h);

  pl_code* code = calloc(1, sizeof(*code));
  ASSERT_NOT_NULL(code);
  code->ops = calloc(1, sizeof(*code->ops));
  ASSERT_NOT_NULL(code->ops);
  ax_arrpush(s->codes, code);
  ax_hmput(s->code_cache, law_key, code);
  ASSERT_NULL(pl_pin_code(pl_ptr(pin)));
  pl_store_put_code(s, law_key.b);
  ASSERT_EQ(pl_pin_code(pl_ptr(pin)), code);
  pl_store_put_code(s, law_key.b);
  ASSERT_EQ(ax_arrlen(s->codes), 1);
  ASSERT_EQ(ax_hmlen(s->code_cache), 1);

  uint8_t disabled[32];
  memset(disabled, 0xff, sizeof(disabled));
  ASSERT(pl_store_put_compiler(s, disabled));
  ASSERT_NULL(pl_pin_code(pl_ptr(pin)));
  /* A suspended PL_F_EXEC frame may still point at the old generation.  The
   * store owns retired code until teardown rather than freeing it here. */
  ASSERT_EQ(ax_arrlen(s->codes), 1);
  ASSERT_EQ(s->codes[0], code);
  ASSERT_EQ(ax_hmlen(s->code_cache), 0);
  ASSERT_NULL(s->compiler_t);
  ASSERT_NULL(s->compiler_h);
  ASSERT_FALSE(pl_store_put_compiler(s, disabled));
  pl_thread_free(t);
  pl_heap_free(h);
  pl_store_free(s);
}

enum { TEST_SIGABRT_EXIT = 128 + SIGABRT };

static void test_sigabrt_exit(int signal_number) {
  (void)signal_number;
  _exit(TEST_SIGABRT_EXIT);
}

static void test_expect_sigabrt(void) {
  if (signal(SIGABRT, test_sigabrt_exit) == SIG_ERR)
    _exit(EXIT_FAILURE);
}

static void assert_sigabrt(pid_t child) {
  ASSERT_GT(child, 0);
  int status = 0;
  ASSERT_EQ(waitpid(child, &status, 0), child);
  ASSERT(WIFEXITED(status));
  ASSERT_EQ(WEXITSTATUS(status), TEST_SIGABRT_EXIT);
}

TEST(store, registries_reject_resolved_moving_pin_proxies) {
  test_rt rt = test_rt_new();
  pl_thread* t = rt.t;
  pl_vpush(t, test_law(t, 1, 7, 1));
  pl_val proxy = pl_pin(t, t->vstack[t->vsp - 1]);
  char save_err[192] = {0};
  ASSERT(pl_store_save_root(rt.store, proxy, NULL, save_err, sizeof(save_err)),
         "%s", save_err);
  ASSERT_NEQ(pl_pin_proxy_target(pl_ptr(proxy)), 0);
  const uint8_t* hash = pl_pin_hash(proxy);
  ASSERT_NOT_NULL(hash);

  pid_t child = fork();
  if (child == 0) {
    test_expect_sigabrt();
    pl_store_index_hashed_law(rt.store, proxy);
    _exit(0);
  }
  assert_sigabrt(child);

  child = fork();
  if (child == 0) {
    test_expect_sigabrt();
    pl_store_intern_put(rt.store, hash, proxy);
    _exit(0);
  }
  assert_sigabrt(child);

  pl_val canonical = pl_pin_proxy_target(pl_ptr(proxy));
  uint8_t wrong_hash[32];
  memcpy(wrong_hash, hash, sizeof(wrong_hash));
  wrong_hash[0] ^= 1;
  child = fork();
  if (child == 0) {
    test_expect_sigabrt();
    pl_store_intern_put(rt.store, wrong_hash, canonical);
    _exit(0);
  }
  assert_sigabrt(child);

  pl_vpush(t, 42);
  pl_val nat_proxy = pl_pin(t, t->vstack[t->vsp - 1]);
  ASSERT(
      pl_store_save_root(rt.store, nat_proxy, NULL, save_err, sizeof(save_err)),
      "%s", save_err);
  pl_val nat_canonical = pl_pin_proxy_target(pl_ptr(nat_proxy));
  ASSERT_NEQ(nat_canonical, 0);
  child = fork();
  if (child == 0) {
    test_expect_sigabrt();
    pl_store_index_hashed_law(rt.store, nat_canonical);
    _exit(0);
  }
  assert_sigabrt(child);

  test_rt_free(&rt);
}

TEST(pin, dedup_is_semantic) {
  test_rt rt = test_rt_new();
  pl_thread* t = rt.t;
  size_t base = t->vsp;
  /* Pin is allocation-only. Save later gives equal proxies one canonical
   * representative without changing their public identities. */
  pl_vpush(t, test_app2(t, 0, 7, test_law(t, 1, 0, 1)));
  pl_vpush(t, test_app2(t, 0, 7, test_law(t, 1, 0, 1)));
  t->vstack[base] = pl_pin(t, t->vstack[base]);
  t->vstack[base + 1] = pl_pin(t, t->vstack[base + 1]);
  pl_val p1 = t->vstack[base];
  pl_val p2 = t->vstack[base + 1];
  ASSERT_NEQ(p1, p2);
  ASSERT_NULL(pl_pin_hash(p1));
  ASSERT_NULL(pl_pin_hash(p2));
  char err[192] = {0};
  ASSERT(pl_store_save_root(rt.store, p1, NULL, err, sizeof(err)), "%s", err);
  ASSERT(pl_store_save_root(rt.store, p2, NULL, err, sizeof(err)), "%s", err);
  ASSERT_EQ(memcmp(pl_pin_hash(p1), pl_pin_hash(p2), 32), 0);
  ASSERT_EQ(pl_pin_proxy_target(pl_ptr(p1)), pl_pin_proxy_target(pl_ptr(p2)));
  test_rt_free(&rt);
}

TEST(pin, sub_pins_collected_shallow) {
  test_rt rt = test_rt_new();
  pl_thread* t = rt.t;
  size_t base = t->vsp;
  pl_vpush(t, 42);
  t->vstack[base] = pl_pin(t, t->vstack[base]);
  pl_vpush(t, test_app2(t, 0, t->vstack[base], t->vstack[base]));
  t->vstack[base + 1] = pl_pin(t, t->vstack[base + 1]);
  pl_val inner = t->vstack[base];
  pl_val outer = t->vstack[base + 1];
  pl_cell* p = pl_as(PL_TAG_PIN, outer);
  ASSERT_NOT_NULL(p);
  ASSERT_EQ(pl_pin_npins(p), 0); /* proxies never carry inline tables */
  char err[192] = {0};
  ASSERT(pl_store_save_root(rt.store, outer, NULL, err, sizeof(err)), "%s",
         err);
  ASSERT_EQ(pl_pin_npins(p), 1); /* deduplicated, shallow */
  ASSERT_EQ(pl_pin_subpins(p)[0], pl_pin_proxy_target(pl_ptr(inner)));
  test_rt_free(&rt);
}

TEST(pin, pinning_only_forces_to_whnf) {
  test_rt rt = test_rt_new();
  pl_thread* t = rt.t;
  size_t base = t->vsp;
  pl_vpush(t, test_lazy_app1(t, 42));
  pl_vpush(t, pl_pin(t, t->vstack[base]));

  pl_cell* proxy = pl_ptr(t->vstack[base + 1]);
  pl_cell* body = pl_as(PL_TAG_APP, pl_pin_body(proxy));
  ASSERT_NOT_NULL(body);
  ASSERT_EQ(pl_tag(pl_app_args(body)[0]), PL_TAG_DEFER);
  ASSERT_EQ(pl_hdr_flags(proxy[0]) & PL_F_NORMAL, 0);

  t->vstack[base + 1] = pl_nf(t, t->vstack[base + 1]);
  proxy = pl_ptr(t->vstack[base + 1]);
  body = pl_as(PL_TAG_APP, pl_pin_body(proxy));
  ASSERT_NOT_NULL(body);
  ASSERT_EQ(pl_app_args(body)[0], 42);
  ASSERT_NEQ(pl_hdr_flags(proxy[0]) & PL_F_NORMAL, 0);
  test_rt_free(&rt);
}

TEST(pin, normalization_raise_does_not_leak_store_lock) {
  test_rt rt = test_rt_new();
  pl_thread* t = rt.t;

  /* A thunk whose expression resolves to its own blackholed env slot. */
  pl_gc_reserve(t, PL_ENV_CELLS(1) + PL_THUNK_CELLS);
  pl_val env = pl_mk_env(t, 1);
  pl_val thunk = pl_mk_thunk(t, env, 0);
  pl_env_slots(pl_ptr(env))[0] = thunk;

  bool raised = test_pin_raises(t, thunk);
  ASSERT(raised, "expected pin normalization to raise");
  ASSERT_STR_EQ(t->exn_msg, "<<loop>>");

  store_lock_probe probe = {.store = rt.store, .acquired = false};
  pthread_t worker;
  ASSERT_EQ(pthread_create(&worker, NULL, store_trylock_thread, &probe), 0);
  ASSERT_EQ(pthread_join(worker, NULL), 0);
  if (!probe.acquired)
    (void)pthread_mutex_unlock(&rt.store->mu); /* clean up a regressed build */
  ASSERT(probe.acquired, "pl_pin leaked the store lock after pl_nf raised");

  test_rt_free(&rt);
}

/* ── Round trips through the backend ───────────────────────────────────── */

static void roundtrip_via(pl_store* (*mk)(const char* dir), const char* dir) {
  uint8_t hash[32];

  /* First session: pin a structured value, remember its hash. */
  {
    pl_store* s = mk(dir);
    ASSERT_NOT_NULL(s);
    pl_heap* h = pl_heap_new(1 << 16, s);
    pl_thread* t = pl_thread_new(h);
    size_t base = t->vsp;
    pl_vpush(t, 42);
    t->vstack[base] = pl_pin(t, t->vstack[base]);
    pl_vpush(t, test_law(t, 2, ax_s2('h', 'i'), 1));
    pl_vpush(t, test_app2(t, 0, t->vstack[base], t->vstack[base + 1]));
    t->vstack[base + 2] = pl_pin(t, t->vstack[base + 2]);
    pl_val pin = t->vstack[base + 2];
    char err[192] = {0};
    ASSERT_NULL(pl_pin_hash(pin));
    ASSERT(pl_store_save_root(s, pin, hash, err, sizeof(err)), "%s", err);
    pl_thread_free(t);
    pl_heap_free(h);
    pl_store_free(s);
  }

  /* Second session: load by hash, re-pin, expect the identical hash. */
  {
    pl_store* s = mk(dir);
    ASSERT_NOT_NULL(s);
    pl_heap* h = pl_heap_new(1 << 16, s);
    pl_thread* t = pl_thread_new(h);

    uint8_t root[32];
    ASSERT(pl_store_get_root(s, root));
    ASSERT_EQ(memcmp(root, hash, 32), 0);

    pl_val pin = pl_store_load(t, hash);
    ASSERT_EQ(memcmp(pl_pin_hash(pin), hash, 32), 0);

    pl_cell* p = pl_as(PL_TAG_PIN, pin);
    ASSERT_NOT_NULL(p);
    pl_cell* body = pl_as(PL_TAG_APP, pl_pin_body(p));
    ASSERT_NOT_NULL(body);
    ASSERT_EQ(pl_app_n(body), 2);
    ASSERT_EQ(pl_app_head(body), 0);
    pl_cell* ip = pl_as(PL_TAG_PIN, pl_app_args(body)[0]);
    ASSERT_NOT_NULL(ip);
    ASSERT_EQ(pl_pin_body(ip), 42);
    pl_cell* lp = pl_as(PL_TAG_LAW, pl_app_args(body)[1]);
    ASSERT_NOT_NULL(lp);
    ASSERT_EQ(pl_law_arity(lp), 2);
    ASSERT_EQ(pl_law_name(lp), (pl_val)ax_s2('h', 'i'));

    /* re-pinning the rehydrated body yields the same hash */
    size_t base = t->vsp;
    pl_vpush(t, pl_pin_body(p));
    pl_val again = pl_pin(t, t->vstack[base]);
    char err[192] = {0};
    uint8_t again_hash[32];
    ASSERT_NEQ(again, pin);
    ASSERT_NULL(pl_pin_hash(again));
    ASSERT(pl_store_save_root(s, again, again_hash, err, sizeof(err)), "%s",
           err);
    ASSERT_EQ(memcmp(again_hash, hash, 32), 0);
    ASSERT_EQ(pl_pin_proxy_target(pl_ptr(again)), pin);

    pl_thread_free(t);
    pl_heap_free(h);
    pl_store_free(s);
  }
}

static pl_store* mk_lmdb(const char* dir) {
  return pl_store_new_lmdb(dir, (size_t)64 << 20);
}

static pl_store* mk_silo(const char* dir) {
  return pl_store_new_silo(dir, (size_t)64 << 20);
}

static void cleanup_store_dir(const char* dir, bool pack) {
  char path[128];
  if (pack) {
    snprintf(path, sizeof(path), "%s/pins.pack", dir);
    (void)unlink(path);
  }
  snprintf(path, sizeof(path), "%s/data.mdb", dir);
  (void)unlink(path);
  snprintf(path, sizeof(path), "%s/lock.mdb", dir);
  (void)unlink(path);
  (void)rmdir(dir);
}

TEST(store, ice_silo_becomes_durable_only_on_save) {
  char dir[] = "/tmp/enki-test-ice-silo-XXXXXX";
  ASSERT_NOT_NULL(mkdtemp(dir));
  uint8_t first[32], second[32], root[32];
  for (unsigned session = 0; session < 3; session++) {
    pl_store* s = mk_silo(dir);
    ASSERT_NOT_NULL(s);
    pl_heap* h = pl_heap_new(1 << 16, s);
    pl_thread* t = pl_thread_new(h);
    size_t base = t->vsp;
    if (session == 0) {
      pl_vpush(t, pl_pin(t, 42));
      ASSERT(store_test_ice(t, t->vstack[base]));
      memcpy(first, pl_pin_hash(t->vstack[base]), sizeof(first));
      ASSERT_FALSE(pl_store_get_root(s, root));
      ASSERT_EQ(pl_store_root_log_head(s), 0);
    } else if (session == 1) {
      ASSERT_FALSE(pl_store_get_root(s, root));
      ASSERT_EQ(pl_store_root_log_head(s), 0);
      ASSERT(test_store_load_raises(t, first));
      pl_vpush(t, pl_pin(t, 42));
      ASSERT(store_test_ice(t, t->vstack[base]));
      ASSERT_EQ(pl_pin_body(pl_ptr(t->vstack[base])), 42);
      char err[192] = {0};
      ASSERT(pl_store_save_root(s, t->vstack[base], NULL, err, sizeof(err)),
             "%s", err);
      pl_vpush(t, pl_pin(t, 43));
      pl_vpush(t, test_app2(t, 0, t->vstack[base], t->vstack[base + 1]));
      t->vstack[base + 2] = pl_pin(t, t->vstack[base + 2]);
      ASSERT(store_test_ice(t, t->vstack[base + 2]));
      memcpy(second, pl_pin_hash(t->vstack[base + 2]), sizeof(second));
      ASSERT(store_test_ice(t, t->vstack[base + 2]));
      ASSERT(pl_store_get_root(s, root));
      ASSERT_EQ(memcmp(first, root, sizeof(root)), 0);
      ASSERT_EQ(pl_store_root_log_head(s), 1);
      /* Even an unchanged root checkpoints all intervening Ice writes. */
      ASSERT(pl_store_save_root(s, t->vstack[base], NULL, err, sizeof(err)),
             "%s", err);
      ASSERT_EQ(pl_store_root_log_head(s), 1);
    } else {
      ASSERT(pl_store_get_root(s, root));
      ASSERT_EQ(memcmp(first, root, sizeof(root)), 0);
      ASSERT_EQ(pl_store_root_log_head(s), 1);
      pl_val loaded = pl_store_load(t, second);
      pl_cell* body = pl_as(PL_TAG_APP, pl_pin_body(pl_ptr(loaded)));
      ASSERT_NOT_NULL(body);
      ASSERT_EQ(pl_app_n(body), 2);
      ASSERT_EQ(pl_pin_body(pl_ptr(pl_app_args(body)[0])), 42);
      ASSERT_EQ(pl_pin_body(pl_ptr(pl_app_args(body)[1])), 43);
    }
    pl_thread_free(t);
    pl_heap_free(h);
    pl_store_free(s);
  }
  cleanup_store_dir(dir, true);
}

static void silo_pin_nat(const char* dir, uint64_t natural, uint8_t hash[32]) {
  pl_store* s = mk_silo(dir);
  ASSERT_NOT_NULL(s);
  pl_heap* h = pl_heap_new(1 << 16, s);
  pl_thread* t = pl_thread_new(h);
  pl_vpush(t, natural);
  pl_val pin = pl_pin(t, t->vstack[t->vsp - 1]);
  char err[192] = {0};
  ASSERT_NULL(pl_pin_hash(pin));
  ASSERT(pl_store_save_root(s, pin, hash, err, sizeof(err)), "%s", err);
  pl_thread_free(t);
  pl_heap_free(h);
  pl_store_free(s);
}

static void pin_sample(pl_store* s, uint8_t hash[32]) {
  pl_heap* h = pl_heap_new(1 << 16, s);
  pl_thread* t = pl_thread_new(h);
  pl_vpush(t, test_law(t, 2, ax_s2('h', 'i'), 1));
  pl_vpush(t, test_app2(t, 0, t->vstack[t->vsp - 1], 42));
  pl_val pin = pl_pin(t, t->vstack[t->vsp - 1]);
  char err[192] = {0};
  ASSERT(pl_store_save_root(s, pin, hash, err, sizeof(err)), "%s", err);
  pl_thread_free(t);
  pl_heap_free(h);
}

static bool fd_read_exact(int fd, uint8_t* out, size_t len) {
  size_t done = 0;
  while (done < len) {
    ssize_t n = read(fd, out + done, len - done);
    if (n < 0 && errno == EINTR)
      continue;
    if (n <= 0)
      return false;
    done += (size_t)n;
  }
  return true;
}

static bool silo_load_raises(const char* dir, const uint8_t hash[32]) {
  pl_store* s = mk_silo(dir);
  ASSERT_NOT_NULL(s);
  pl_heap* h = pl_heap_new(1 << 16, s);
  pl_thread* t = pl_thread_new(h);
  bool raised = test_store_load_raises(t, hash);
  pl_thread_free(t);
  pl_heap_free(h);
  pl_store_free(s);
  return raised;
}

static void check_object_record(const char* dir, const uint8_t hash[32]) {
  MDB_env* env;
  MDB_txn* txn;
  MDB_dbi objects;
  ASSERT_EQ(mdb_env_create(&env), 0);
  ASSERT_EQ(mdb_env_set_maxdbs(env, 2), 0);
  ASSERT_EQ(mdb_env_open(env, dir, MDB_RDONLY, 0), 0);
  ASSERT_EQ(mdb_txn_begin(env, NULL, MDB_RDONLY, &txn), 0);
  ASSERT_EQ(mdb_dbi_open(txn, "objects", 0, &objects), 0);
  MDB_val key = {.mv_size = 32, .mv_data = (void*)hash};
  MDB_val value;
  ASSERT_EQ(mdb_get(txn, objects, &key, &value), 0);
  ASSERT_EQ(value.mv_size, 24);
  ASSERT_EQ(memcmp(value.mv_data, "pinpack\1", 8), 0);
  mdb_txn_abort(txn);
  mdb_env_close(env);
}

static void delete_object_record(const char* dir, const uint8_t hash[32]) {
  MDB_env* env;
  MDB_txn* txn;
  MDB_dbi objects;
  ASSERT_EQ(mdb_env_create(&env), 0);
  ASSERT_EQ(mdb_env_set_maxdbs(env, 2), 0);
  ASSERT_EQ(mdb_env_open(env, dir, 0, 0600), 0);
  ASSERT_EQ(mdb_txn_begin(env, NULL, 0, &txn), 0);
  ASSERT_EQ(mdb_dbi_open(txn, "objects", 0, &objects), 0);
  MDB_val key = {.mv_size = 32, .mv_data = (void*)hash};
  ASSERT_EQ(mdb_del(txn, objects, &key, NULL), 0);
  ASSERT_EQ(mdb_txn_commit(txn), 0);
  mdb_env_close(env);
}

static void put_object_record(const char* dir, const uint8_t hash[32],
                              const uint8_t* bytes, size_t len) {
  MDB_env* env;
  MDB_txn* txn;
  MDB_dbi objects;
  ASSERT_EQ(mdb_env_create(&env), 0);
  ASSERT_EQ(mdb_env_set_maxdbs(env, 2), 0);
  ASSERT_EQ(mdb_env_open(env, dir, 0, 0600), 0);
  ASSERT_EQ(mdb_txn_begin(env, NULL, 0, &txn), 0);
  ASSERT_EQ(mdb_dbi_open(txn, "objects", 0, &objects), 0);
  MDB_val key = {.mv_size = 32, .mv_data = (void*)hash};
  MDB_val value = {.mv_size = len, .mv_data = (void*)bytes};
  ASSERT_EQ(mdb_put(txn, objects, &key, &value, 0), 0);
  ASSERT_EQ(mdb_txn_commit(txn), 0);
  mdb_env_close(env);
}

static void test_put64le(uint8_t bytes[8], uint64_t value) {
  for (unsigned i = 0; i < 8; i++)
    bytes[i] = (uint8_t)(value >> (8u * i));
}

static size_t silo_last_txnid(const char* dir) {
  MDB_env* env;
  MDB_envinfo info;
  ASSERT_EQ(mdb_env_create(&env), 0);
  ASSERT_EQ(mdb_env_open(env, dir, MDB_RDONLY, 0), 0);
  ASSERT_EQ(mdb_env_info(env, &info), 0);
  mdb_env_close(env);
  return (size_t)info.me_last_txnid;
}

static void exercise_repeated_canonical_save(pl_store* s,
                                             const char* pack_path) {
  pl_heap* h = pl_heap_new(1 << 16, s);
  pl_thread* t = pl_thread_new(h);
  size_t base = t->vsp;

  pl_vpush(t, 41);
  t->vstack[base] = pl_pin(t, t->vstack[base]);
  pl_vpush(t, test_app2(t, 0, t->vstack[base], 7));
  t->vstack[base + 1] = pl_pin(t, t->vstack[base + 1]);

  char err[192] = {0};
  uint8_t first_hash[32], second_hash[32], repeated_hash[32], root_hash[32];
  ASSERT(
      pl_store_save_root(s, t->vstack[base + 1], first_hash, err, sizeof(err)),
      "%s", err);
  pl_val first = pl_pin_proxy_target(pl_ptr(t->vstack[base + 1]));
  ASSERT_NEQ(first, 0);

  pl_vpush(t, 99);
  t->vstack[base + 2] = pl_pin(t, t->vstack[base + 2]);
  ASSERT(
      pl_store_save_root(s, t->vstack[base + 2], second_hash, err, sizeof(err)),
      "%s", err);
  pl_val second = pl_pin_proxy_target(pl_ptr(t->vstack[base + 2]));
  ASSERT_NEQ(second, 0);
  ASSERT_NEQ(memcmp(first_hash, second_hash, sizeof(first_hash)), 0);

  struct stat before = {0};
  if (pack_path != NULL)
    ASSERT_EQ(stat(pack_path, &before), 0);
  size_t arena_before = pl_store_mark(s);

  /* Exercise both public aliases and canonical values.  Neither call may
   * revisit or rematerialize the already-persisted closure. */
  ASSERT(pl_store_save_root(s, t->vstack[base + 1], repeated_hash, err,
                            sizeof(err)),
         "%s", err);
  ASSERT_EQ(memcmp(repeated_hash, first_hash, sizeof(first_hash)), 0);
  ASSERT(pl_store_get_root(s, root_hash));
  ASSERT_EQ(memcmp(root_hash, first_hash, sizeof(first_hash)), 0);

  pl_thread_free(t);
  pl_heap_free(h);
  ASSERT(pl_store_save_root(s, second, repeated_hash, err, sizeof(err)), "%s",
         err);
  ASSERT_EQ(memcmp(repeated_hash, second_hash, sizeof(second_hash)), 0);
  ASSERT(pl_store_get_root(s, root_hash));
  ASSERT_EQ(memcmp(root_hash, second_hash, sizeof(second_hash)), 0);
  ASSERT_EQ(pl_store_mark(s), arena_before);

  if (pack_path != NULL) {
    struct stat after;
    ASSERT_EQ(stat(pack_path, &after), 0);
    ASSERT_EQ(after.st_size, before.st_size);
  }

  /* Keep the first canonical representative observably valid after its
   * source heap has gone away. */
  ASSERT_EQ(memcmp(pl_pin_hash(first), first_hash, sizeof(first_hash)), 0);
}

TEST(store, legacy_repeated_save_republishes_canonical_root) {
  pl_store* s = pl_store_new_mem();
  exercise_repeated_canonical_save(s, NULL);
  pl_store_free(s);
}

TEST(store, silo_repeated_save_republishes_root_without_pack_writes) {
  char dir[64];
  snprintf(dir, sizeof(dir), "/tmp/enki-test-silo-resave-%lu",
           (unsigned long)getpid());
  ASSERT(mkdir(dir, 0700) == 0 || errno == EEXIST);
  pl_store* s = mk_silo(dir);
  ASSERT_NOT_NULL(s);
  char pack_path[96];
  snprintf(pack_path, sizeof(pack_path), "%s/pins.pack", dir);
  exercise_repeated_canonical_save(s, pack_path);
  pl_store_free(s);
  cleanup_store_dir(dir, true);
}

TEST(store, lmdb_round_trip) {
  char dir[64];
  snprintf(dir, sizeof(dir), "/tmp/enki-test-store-%lu",
           (unsigned long)getpid());
  ASSERT(mkdir(dir, 0700) == 0 || errno == EEXIST);
  roundtrip_via(mk_lmdb, dir);
  char path[96];
  snprintf(path, sizeof(path), "%s/data.mdb", dir);
  unlink(path);
  snprintf(path, sizeof(path), "%s/lock.mdb", dir);
  unlink(path);
  rmdir(dir);
}

TEST(store, silo_pack_round_trip) {
  char dir[64];
  snprintf(dir, sizeof(dir), "/tmp/enki-test-silo-%lu",
           (unsigned long)getpid());
  ASSERT(mkdir(dir, 0700) == 0 || errno == EEXIST);
  roundtrip_via(mk_silo, dir);

  char path[96];
  snprintf(path, sizeof(path), "%s/pins.pack", dir);
  struct stat st;
  ASSERT_EQ(stat(path, &st), 0);
  ASSERT_GT(st.st_size, 0);
  cleanup_store_dir(dir, true);
}

TEST(store, silo_pin_defers_hash_and_io_until_save) {
  char dir[64];
  snprintf(dir, sizeof(dir), "/tmp/enki-test-silo-defer-%lu",
           (unsigned long)getpid());
  ASSERT(mkdir(dir, 0700) == 0 || errno == EEXIST);
  pl_store* s = mk_silo(dir);
  ASSERT_NOT_NULL(s);
  pl_heap* h = pl_heap_new(1 << 16, s);
  pl_thread* t = pl_thread_new(h);

  size_t base = t->vsp;
  pl_vpush(t, 42);
  t->vstack[base] = pl_pin(t, t->vstack[base]);
  pl_vpush(t, 43);
  t->vstack[base + 1] = pl_pin(t, t->vstack[base + 1]);
  pl_val unreachable = t->vstack[base];
  pl_val root = t->vstack[base + 1];
  ASSERT_NULL(pl_pin_hash(unreachable));
  ASSERT_NULL(pl_pin_hash(root));

  char path[96];
  snprintf(path, sizeof(path), "%s/pins.pack", dir);
  struct stat before, after;
  ASSERT_EQ(stat(path, &before), 0);
  ASSERT_EQ(before.st_size, 0);
  uint8_t absent[32];
  ASSERT_FALSE(pl_store_get_root(s, absent));

  uint8_t hash[32];
  char err[192] = {0};
  ASSERT(pl_store_save_root(s, root, hash, err, sizeof(err)), "%s", err);
  ASSERT_NOT_NULL(pl_pin_hash(root));
  ASSERT_NULL(pl_pin_hash(unreachable));
  ASSERT_EQ(stat(path, &after), 0);
  ASSERT_GT(after.st_size, 0);

  pl_thread_free(t);
  pl_heap_free(h);
  pl_store_free(s);
  cleanup_store_dir(dir, true);
}

TEST(store, silo_batches_closure_in_one_transaction) {
  char dir[64];
  snprintf(dir, sizeof(dir), "/tmp/enki-test-silo-batch-%lu",
           (unsigned long)getpid());
  ASSERT(mkdir(dir, 0700) == 0 || errno == EEXIST);

  pl_store* initialized = mk_silo(dir);
  ASSERT_NOT_NULL(initialized);
  pl_store_free(initialized);
  size_t before_txnid = silo_last_txnid(dir);

  uint8_t root_hash[32];
  pl_store* s = mk_silo(dir);
  ASSERT_NOT_NULL(s);
  pl_heap* h = pl_heap_new(1 << 16, s);
  pl_thread* t = pl_thread_new(h);
  pl_vpush(t, 0);
  pl_val root = pl_pin(t, t->vstack[t->vsp - 1]);
  for (uint64_t i = 1; i <= 32; i++) {
    pl_vpush(t, test_app2(t, 0, root, i));
    root = pl_pin(t, t->vstack[t->vsp - 1]);
  }

  char err[192] = {0};
  ASSERT(pl_store_save_root(s, root, root_hash, err, sizeof(err)), "%s", err);
  char path[96];
  snprintf(path, sizeof(path), "%s/pins.pack", dir);
  struct stat first, second;
  ASSERT_EQ(stat(path, &first), 0);
  ASSERT(pl_store_save_root(s, root, NULL, err, sizeof(err)), "%s", err);
  ASSERT_EQ(stat(path, &second), 0);
  ASSERT_EQ(second.st_size, first.st_size);

  pl_thread_free(t);
  pl_heap_free(h);
  pl_store_free(s);
  size_t after_txnid = silo_last_txnid(dir);
  /* Reopening the backend may consume one no-op initialization transaction;
   * the 33-object Save itself must consume only one more. */
  ASSERT_GTE(after_txnid, before_txnid + 1);
  ASSERT_LTE(after_txnid, before_txnid + 2);
  ASSERT_FALSE(silo_load_raises(dir, root_hash));
  cleanup_store_dir(dir, true);
}

TEST(store, silo_failed_batch_keeps_provisional_pins_retryable) {
  char dir[64];
  snprintf(dir, sizeof(dir), "/tmp/enki-test-silo-retry-%lu",
           (unsigned long)getpid());
  ASSERT(mkdir(dir, 0700) == 0 || errno == EEXIST);
  pl_store* s = mk_silo(dir);
  ASSERT_NOT_NULL(s);
  pl_heap* h = pl_heap_new(1 << 16, s);
  pl_thread* t = pl_thread_new(h);

  size_t base = t->vsp;
  pl_vpush(t, 42);
  pl_vpush(t, 42);
  t->vstack[base] = pl_pin(t, t->vstack[base]);
  t->vstack[base + 1] = pl_pin(t, t->vstack[base + 1]);
  pl_vpush(t, test_app2(t, 0, t->vstack[base], t->vstack[base + 1]));
  size_t valid_at = t->vsp - 1;
  pl_vpush(t, test_law(t, 0, 0, 1));
  pl_vpush(t, test_law(t, 1, t->vstack[t->vsp - 1], t->vstack[valid_at]));
  size_t invalid_at = t->vsp - 1;
  t->vstack[invalid_at] = pl_pin(t, t->vstack[invalid_at]);
  ASSERT_EQ(pl_pin_npins(pl_ptr(t->vstack[invalid_at])), 0);

  char err[192] = {0};
  ASSERT_FALSE(
      pl_store_save_root(s, t->vstack[invalid_at], NULL, err, sizeof(err)));
  ASSERT(strstr(err, "LAW arity") != NULL, "%s", err);
  ASSERT_FALSE(pl_pin_is_hashed(t->vstack[base]));
  ASSERT_FALSE(pl_pin_is_hashed(t->vstack[base + 1]));
  ASSERT_FALSE(pl_pin_is_hashed(t->vstack[invalid_at]));
  ASSERT_EQ(pl_pin_npins(pl_ptr(t->vstack[invalid_at])), 0);

  t->vstack[valid_at] = pl_pin(t, t->vstack[valid_at]);
  ASSERT(pl_store_save_root(s, t->vstack[valid_at], NULL, err, sizeof(err)),
         "%s", err);
  ASSERT(pl_pin_is_hashed(t->vstack[base]));
  ASSERT(pl_pin_is_hashed(t->vstack[base + 1]));
  ASSERT_EQ(memcmp(pl_pin_hash(t->vstack[base]),
                   pl_pin_hash(t->vstack[base + 1]), 32),
            0);
  ASSERT_EQ(pl_pin_npins(pl_ptr(t->vstack[valid_at])), 1);

  pl_thread_free(t);
  pl_heap_free(h);
  pl_store_free(s);
  cleanup_store_dir(dir, true);
}

TEST(store, silo_failed_batch_truncates_flushed_pack_tail) {
  char dir[64];
  snprintf(dir, sizeof(dir), "/tmp/enki-test-silo-rollback-%lu",
           (unsigned long)getpid());
  ASSERT(mkdir(dir, 0700) == 0 || errno == EEXIST);
  pl_store* s = mk_silo(dir);
  ASSERT_NOT_NULL(s);
  pl_heap* h = pl_heap_new(1 << 18, s);
  pl_thread* t = pl_thread_new(h);

  const size_t byte_len = (size_t)128 * 1024 + 17;
  uint8_t* bytes = malloc(byte_len);
  ASSERT_NOT_NULL(bytes);
  for (size_t i = 0; i < byte_len; i++)
    bytes[i] = (uint8_t)(i * 29u + 5u);
  bytes[byte_len - 1] = 1;
  size_t base = t->vsp;
  pl_vpush(t, pl_nat_from_bytes(t, bytes, byte_len));
  t->vstack[base] = pl_pin(t, t->vstack[base]);
  pl_vpush(t, test_law(t, 0, 0, t->vstack[base]));
  t->vstack[base + 1] = pl_pin(t, t->vstack[base + 1]);

  char path[96];
  snprintf(path, sizeof(path), "%s/pins.pack", dir);
  struct stat before, after;
  ASSERT_EQ(stat(path, &before), 0);
  char err[192] = {0};
  ASSERT_FALSE(
      pl_store_save_root(s, t->vstack[base + 1], NULL, err, sizeof(err)));
  ASSERT(strstr(err, "LAW arity") != NULL, "%s", err);
  ASSERT_EQ(stat(path, &after), 0);
  ASSERT_EQ(after.st_size, before.st_size);
  ASSERT_FALSE(pl_pin_is_hashed(t->vstack[base]));
  ASSERT_FALSE(pl_pin_is_hashed(t->vstack[base + 1]));

  ASSERT(pl_store_save_root(s, t->vstack[base], NULL, err, sizeof(err)), "%s",
         err);
  ASSERT(pl_pin_is_hashed(t->vstack[base]));

  free(bytes);
  pl_thread_free(t);
  pl_heap_free(h);
  pl_store_free(s);
  cleanup_store_dir(dir, true);
}

TEST(store, silo_buffered_write_and_mapped_read_cross_chunk_boundaries) {
  char dir[64];
  snprintf(dir, sizeof(dir), "/tmp/enki-test-silo-large-%lu",
           (unsigned long)getpid());
  ASSERT(mkdir(dir, 0700) == 0 || errno == EEXIST);
  const size_t byte_len = (size_t)128 * 1024 + 17;
  uint8_t* bytes = malloc(byte_len);
  ASSERT_NOT_NULL(bytes);
  for (size_t i = 0; i < byte_len; i++)
    bytes[i] = (uint8_t)(i * 17u + 3u);
  bytes[byte_len - 1] = 1;

  uint8_t large_hash[32];
  {
    pl_store* s = mk_silo(dir);
    ASSERT_NOT_NULL(s);
    pl_heap* h = pl_heap_new(1 << 18, s);
    pl_thread* t = pl_thread_new(h);

    pl_vpush(t, 7);
    pl_val prefix = pl_pin(t, t->vstack[t->vsp - 1]);
    char err[192] = {0};
    ASSERT(pl_store_save_root(s, prefix, NULL, err, sizeof(err)), "%s", err);

    pl_vpush(t, pl_nat_from_bytes(t, bytes, byte_len));
    pl_val large = pl_pin(t, t->vstack[t->vsp - 1]);
    ASSERT(pl_store_save_root(s, large, large_hash, err, sizeof(err)), "%s",
           err);
    pl_thread_free(t);
    pl_heap_free(h);
    pl_store_free(s);
  }

  {
    pl_store* s = mk_silo(dir);
    ASSERT_NOT_NULL(s);
    pl_heap* h = pl_heap_new(1 << 18, s);
    pl_thread* t = pl_thread_new(h);
    pl_val loaded = pl_store_load(t, large_hash);
    pl_val body = pl_pin_body(pl_ptr(loaded));
    ASSERT_EQ(pl_nat_byte_len(body), byte_len);
    ASSERT_EQ(pl_nat_byte_at(body, 0), bytes[0]);
    ASSERT_EQ(pl_nat_byte_at(body, 65536), bytes[65536]);
    ASSERT_EQ(pl_nat_byte_at(body, byte_len - 1), bytes[byte_len - 1]);
    pl_thread_free(t);
    pl_heap_free(h);
    pl_store_free(s);
  }

  free(bytes);
  cleanup_store_dir(dir, true);
}

TEST(store, silo_equal_provisional_pins_share_wire_identity) {
  char dir[64];
  snprintf(dir, sizeof(dir), "/tmp/enki-test-silo-equal-%lu",
           (unsigned long)getpid());
  ASSERT(mkdir(dir, 0700) == 0 || errno == EEXIST);
  pl_store* s = mk_silo(dir);
  ASSERT_NOT_NULL(s);
  pl_heap* h = pl_heap_new(1 << 16, s);
  pl_thread* t = pl_thread_new(h);

  size_t base = t->vsp;
  pl_vpush(t, test_law(t, 1, 7, 1));
  pl_vpush(t, test_law(t, 1, 7, 1));
  t->vstack[base] = pl_pin(t, t->vstack[base]);
  t->vstack[base + 1] = pl_pin(t, t->vstack[base + 1]);
  pl_val first = t->vstack[base];
  pl_val second = t->vstack[base + 1];
  ASSERT_NEQ(first, second);
  ASSERT_EQ(test_op66_2(t, ax_s5('E', 'q', 'u', 'a', 'l'), first, second), 1);
  pl_vpush(t, test_app2(t, 0, t->vstack[base], t->vstack[base + 1]));
  t->vstack[base + 2] = pl_pin(t, t->vstack[base + 2]);
  first = t->vstack[base];
  second = t->vstack[base + 1];
  pl_val outer = t->vstack[base + 2];
  ASSERT_EQ(pl_pin_npins(pl_ptr(outer)), 0);

  char err[192] = {0};
  ASSERT(pl_store_save_root(s, outer, NULL, err, sizeof(err)), "%s", err);
  ASSERT_EQ(memcmp(pl_pin_hash(first), pl_pin_hash(second), 32), 0);
  ASSERT_EQ(pl_pin_proxy_target(pl_ptr(first)),
            pl_pin_proxy_target(pl_ptr(second)));
  ASSERT_EQ(pl_pin_npins(pl_ptr(outer)), 1);
  pl_hash key;
  memcpy(key.b, pl_pin_hash(first), sizeof(key.b));
  ptrdiff_t at = ax_hmgeti(s->code_targets, key);
  ASSERT_GTE(at, 0);
  ASSERT_EQ(ax_arrlen(s->code_targets[at].value), 1);
  memcpy(key.b, pl_pin_hash(outer), sizeof(key.b));
  ASSERT_LT(ax_hmgeti(s->code_targets, key), 0);

  pl_thread_free(t);
  pl_heap_free(h);
  pl_store_free(s);
  cleanup_store_dir(dir, true);
}

TEST(store, silo_prints_pending_pins_as_liquid) {
  char dir[64];
  snprintf(dir, sizeof(dir), "/tmp/enki-test-silo-print-%lu",
           (unsigned long)getpid());
  ASSERT(mkdir(dir, 0700) == 0 || errno == EEXIST);
  pl_store* s = mk_silo(dir);
  ASSERT_NOT_NULL(s);
  pl_heap* h = pl_heap_new(1 << 16, s);
  pl_thread* t = pl_thread_new(h);

  pl_vpush(t, test_law(t, 1, (pl_val)'h', 1));
  pl_val inner = pl_pin(t, t->vstack[t->vsp - 1]);
  ASSERT_FALSE(pl_pin_is_hashed(inner));
  char* shown = pl_show_val(ax_allocator_system(), inner, NULL);
  ASSERT_STR_EQ(shown, "liquid");
  ax_free(ax_allocator_system(), shown);

  pl_vpush(t, test_app2(t, 0, inner, 7));
  shown = pl_show_val(ax_allocator_system(), t->vstack[t->vsp - 1], NULL);
  ASSERT_STR_EQ(shown, "(0 liquid 7)");
  ax_free(ax_allocator_system(), shown);

  pl_thread_free(t);
  pl_heap_free(h);
  pl_store_free(s);
  cleanup_store_dir(dir, true);
}

TEST(store, silo_rejects_text_hash_store_revision) {
  char dir[64];
  snprintf(dir, sizeof(dir), "/tmp/enki-test-silo-v1-%lu",
           (unsigned long)getpid());
  ASSERT(mkdir(dir, 0700) == 0 || errno == EEXIST);

  MDB_env* env;
  MDB_txn* txn;
  MDB_dbi meta, objects;
  ASSERT_EQ(mdb_env_create(&env), 0);
  ASSERT_EQ(mdb_env_set_maxdbs(env, 2), 0);
  ASSERT_EQ(mdb_env_open(env, dir, 0, 0600), 0);
  ASSERT_EQ(mdb_txn_begin(env, NULL, 0, &txn), 0);
  ASSERT_EQ(mdb_dbi_open(txn, "objects", MDB_CREATE, &objects), 0);
  ASSERT_EQ(mdb_dbi_open(txn, "meta", MDB_CREATE, &meta), 0);
  static const char key[] = "format";
  static const uint8_t old_format[] = {'S', 'I', 'L', 'O', 1};
  MDB_val k = {.mv_size = sizeof(key) - 1, .mv_data = (void*)key};
  MDB_val v = {.mv_size = sizeof(old_format), .mv_data = (void*)old_format};
  ASSERT_EQ(mdb_put(txn, meta, &k, &v, 0), 0);
  ASSERT_EQ(mdb_txn_commit(txn), 0);
  mdb_env_close(env);

  ASSERT_NULL(mk_silo(dir));
  cleanup_store_dir(dir, true);
}

TEST(store, silo_deduplicates_and_tolerates_orphan_pack_tails) {
  char dir[64];
  snprintf(dir, sizeof(dir), "/tmp/enki-test-silo-tail-%lu",
           (unsigned long)getpid());
  ASSERT(mkdir(dir, 0700) == 0 || errno == EEXIST);
  uint8_t first[32], again[32], second[32];
  silo_pin_nat(dir, 42, first);
  check_object_record(dir, first);

  char path[96];
  snprintf(path, sizeof(path), "%s/pins.pack", dir);
  struct stat before, after;
  ASSERT_EQ(stat(path, &before), 0);
  silo_pin_nat(dir, 42, again);
  ASSERT_EQ(memcmp(first, again, 32), 0);
  ASSERT_EQ(stat(path, &after), 0);
  ASSERT_EQ(after.st_size, before.st_size);

  int fd = open(path, O_WRONLY | O_APPEND);
  ASSERT_GTE(fd, 0);
  static const uint8_t orphan[] = {0xde, 0xad, 0xbe, 0xef};
  ASSERT_EQ(write(fd, orphan, sizeof(orphan)), (ssize_t)sizeof(orphan));
  ASSERT_EQ(close(fd), 0);
  ASSERT_FALSE(silo_load_raises(dir, first));

  silo_pin_nat(dir, 43, second);
  check_object_record(dir, second);
  ASSERT_FALSE(silo_load_raises(dir, first));
  ASSERT_FALSE(silo_load_raises(dir, second));
  cleanup_store_dir(dir, true);
}

TEST(store, silo_rejects_indexed_pack_truncation) {
  char dir[64];
  snprintf(dir, sizeof(dir), "/tmp/enki-test-silo-truncate-%lu",
           (unsigned long)getpid());
  ASSERT(mkdir(dir, 0700) == 0 || errno == EEXIST);
  uint8_t hash[32];
  silo_pin_nat(dir, 99, hash);

  char path[96];
  snprintf(path, sizeof(path), "%s/pins.pack", dir);
  struct stat st;
  ASSERT_EQ(stat(path, &st), 0);
  ASSERT_GT(st.st_size, 0);
  ASSERT_EQ(truncate(path, st.st_size - 1), 0);
  ASSERT(silo_load_raises(dir, hash));
  cleanup_store_dir(dir, true);
}

TEST(store, silo_rejects_corrupt_object_indices) {
  char dir[64];
  snprintf(dir, sizeof(dir), "/tmp/enki-test-silo-index-%lu",
           (unsigned long)getpid());
  ASSERT(mkdir(dir, 0700) == 0 || errno == EEXIST);
  uint8_t hash[32];
  silo_pin_nat(dir, 99, hash);
  put_object_record(dir, hash, (const uint8_t[]){0}, 1);
  ASSERT(silo_load_raises(dir, hash));
  cleanup_store_dir(dir, true);
}

TEST(store, silo_rejects_semantic_hash_mismatches) {
  char dir[64];
  snprintf(dir, sizeof(dir), "/tmp/enki-test-silo-hash-mismatch-%lu",
           (unsigned long)getpid());
  ASSERT(mkdir(dir, 0700) == 0 || errno == EEXIST);
  uint8_t hash[32];
  silo_pin_nat(dir, 99, hash);

  char path[96];
  snprintf(path, sizeof(path), "%s/pins.pack", dir);
  int fd = open(path, O_RDWR);
  ASSERT_GTE(fd, 0);
  struct stat st;
  ASSERT_EQ(fstat(fd, &st), 0);
  ASSERT_GT(st.st_size, 0);
  uint8_t replacement = 100;
  ASSERT_EQ(pwrite(fd, &replacement, 1, st.st_size - 1), 1);
  ASSERT_EQ(close(fd), 0);

  /* The modified stream is well formed but denotes a different PLAN value. */
  ASSERT(silo_load_raises(dir, hash));
  cleanup_store_dir(dir, true);
}

TEST(store, silo_reports_missing_referents) {
  char dir[64];
  snprintf(dir, sizeof(dir), "/tmp/enki-test-silo-missing-ref-%lu",
           (unsigned long)getpid());
  ASSERT(mkdir(dir, 0700) == 0 || errno == EEXIST);
  uint8_t inner_hash[32], outer_hash[32];
  {
    pl_store* s = mk_silo(dir);
    ASSERT_NOT_NULL(s);
    pl_heap* h = pl_heap_new(1 << 16, s);
    pl_thread* t = pl_thread_new(h);
    size_t base = t->vsp;
    pl_vpush(t, 42);
    t->vstack[base] = pl_pin(t, t->vstack[base]);
    pl_vpush(t, test_app2(t, 0, t->vstack[base], 7));
    t->vstack[base + 1] = pl_pin(t, t->vstack[base + 1]);
    char err[192] = {0};
    ASSERT(pl_store_save_root(s, t->vstack[base + 1], NULL, err, sizeof(err)),
           "%s", err);
    memcpy(inner_hash, pl_pin_hash(t->vstack[base]), 32);
    memcpy(outer_hash, pl_pin_hash(t->vstack[base + 1]), 32);
    pl_thread_free(t);
    pl_heap_free(h);
    pl_store_free(s);
  }
  delete_object_record(dir, inner_hash);
  ASSERT(silo_load_raises(dir, outer_hash));
  cleanup_store_dir(dir, true);
}

TEST(store, silo_rejects_cyclic_referent_loads) {
  char dir[64];
  snprintf(dir, sizeof(dir), "/tmp/enki-test-silo-cycle-%lu",
           (unsigned long)getpid());
  ASSERT(mkdir(dir, 0700) == 0 || errno == EEXIST);
  uint8_t inner_hash[32], outer_hash[32];
  {
    pl_store* s = mk_silo(dir);
    ASSERT_NOT_NULL(s);
    pl_heap* h = pl_heap_new(1 << 16, s);
    pl_thread* t = pl_thread_new(h);
    size_t base = t->vsp;
    pl_vpush(t, 42);
    t->vstack[base] = pl_pin(t, t->vstack[base]);
    pl_vpush(t, test_app2(t, 0, t->vstack[base], 7));
    t->vstack[base + 1] = pl_pin(t, t->vstack[base + 1]);
    char err[192] = {0};
    ASSERT(pl_store_save_root(s, t->vstack[base + 1], NULL, err, sizeof(err)),
           "%s", err);
    memcpy(inner_hash, pl_pin_hash(t->vstack[base]), 32);
    memcpy(outer_hash, pl_pin_hash(t->vstack[base + 1]), 32);
    pl_thread_free(t);
    pl_heap_free(h);
    pl_store_free(s);
  }

  /* Replace the inner index with a valid Silo object whose direct PIN is
   * the already-loading outer object. The semantic mismatch is never reached:
   * dependency resolution must reject the cycle first. */
  uint8_t cycle[41] = {'S', 'I', 'L', 'O', 1, 1, 1};
  memcpy(cycle + 7, outer_hash, 32);
  cycle[39] = 0xf1;
  cycle[40] = 0;
  char path[96];
  snprintf(path, sizeof(path), "%s/pins.pack", dir);
  int fd = open(path, O_WRONLY | O_APPEND);
  ASSERT_GTE(fd, 0);
  off_t offset = lseek(fd, 0, SEEK_END);
  ASSERT_GTE(offset, 0);
  ASSERT_EQ(write(fd, cycle, sizeof(cycle)), (ssize_t)sizeof(cycle));
  ASSERT_EQ(close(fd), 0);
  uint8_t record[24] = {'p', 'i', 'n', 'p', 'a', 'c', 'k', 1};
  test_put64le(record + 8, (uint64_t)offset);
  test_put64le(record + 16, sizeof(cycle));
  put_object_record(dir, inner_hash, record, sizeof(record));

  ASSERT(silo_load_raises(dir, outer_hash));
  cleanup_store_dir(dir, true);
}

TEST(store, silo_hashes_canonical_stream_not_canonical_text) {
  uint8_t memory_hash[32], silo_hash[32];
  pl_store* memory = pl_store_new_mem();
  pin_sample(memory, memory_hash);
  pl_store_free(memory);

  char dir[64];
  snprintf(dir, sizeof(dir), "/tmp/enki-test-silo-hash-%lu",
           (unsigned long)getpid());
  ASSERT(mkdir(dir, 0700) == 0 || errno == EEXIST);
  pl_store* silo = mk_silo(dir);
  ASSERT_NOT_NULL(silo);
  pin_sample(silo, silo_hash);
  pl_store_free(silo);
  ASSERT_NEQ(memcmp(memory_hash, silo_hash, 32), 0);

  silo = pl_store_new_silo_ro(dir, (size_t)64 << 20);
  ASSERT_NOT_NULL(silo);
  pl_silo_reader reader = {0}; char err[192] = {0};
  ASSERT(pl_store_silo_open(silo, silo_hash, &reader, err, sizeof(err)));
  uint8_t* bytes = malloc(reader.len);
  ASSERT_NOT_NULL(bytes);
  ASSERT(reader.read(reader.ctx, bytes, reader.len));
  uint8_t expected[32];
  ax_sha256(bytes, reader.len, expected);
  free(bytes);
  pl_store_silo_close_reader(&reader);
  pl_store_free(silo);
  ASSERT_EQ(memcmp(expected, silo_hash, sizeof(expected)), 0);
  cleanup_store_dir(dir, true);
}

TEST(store, silo_serializes_concurrent_process_writers) {
  char dir[64];
  snprintf(dir, sizeof(dir), "/tmp/enki-test-silo-writers-%lu",
           (unsigned long)getpid());
  ASSERT(mkdir(dir, 0700) == 0 || errno == EEXIST);
  pl_store* initialized = mk_silo(dir);
  ASSERT_NOT_NULL(initialized);
  pl_store_free(initialized);

  int result[2][2];
  ASSERT_EQ(pipe(result[0]), 0);
  ASSERT_EQ(pipe(result[1]), 0);
  pid_t children[2];
  for (unsigned i = 0; i < 2; i++) {
    children[i] = fork();
    ASSERT_NEQ(children[i], -1);
    if (children[i] == 0) {
      (void)close(result[i][0]);
      uint8_t hash[32];
      silo_pin_nat(dir, 100 + i, hash);
      bool ok =
          write(result[i][1], hash, sizeof(hash)) == (ssize_t)sizeof(hash);
      (void)close(result[i][1]);
      _exit(ok ? 0 : 1);
    }
    (void)close(result[i][1]);
  }

  uint8_t hash[2][32];
  for (unsigned i = 0; i < 2; i++) {
    ASSERT(fd_read_exact(result[i][0], hash[i], sizeof(hash[i])));
    (void)close(result[i][0]);
    int status;
    ASSERT_EQ(waitpid(children[i], &status, 0), children[i]);
    ASSERT(WIFEXITED(status));
    ASSERT_EQ(WEXITSTATUS(status), 0);
  }
  ASSERT_NEQ(memcmp(hash[0], hash[1], 32), 0);
  ASSERT_FALSE(silo_load_raises(dir, hash[0]));
  ASSERT_FALSE(silo_load_raises(dir, hash[1]));
  cleanup_store_dir(dir, true);
}

TEST(store, missing_pin_raises) {
  test_rt rt = test_rt_new();
  pl_thread* t = rt.t;
  uint8_t nohash[32] = {1, 2, 3};
  pl_catch c;
  pl_catch_init(t, &c);
  if (setjmp(c.jb) == 0) {
    (void)pl_store_load(t, nohash);
    FAIL_TEST("expected raise");
  }
  pl_catch_unwind(t, &c);
  ASSERT_NOT_NULL(t->exn_msg);
  test_rt_free(&rt);
}

TEST(store, legacy_nested_missing_pin_cleans_resources_and_locks) {
  save_probe_backend* backend;
  pl_store* store = save_probe_store(&backend);
  pl_heap* heap = pl_heap_new(1 << 16, store);
  pl_thread* t = pl_thread_new(heap);
  uint8_t child_hash[32] = {0x11};
  uint8_t missing_hash[32] = {0x22};
  uint8_t parent_hash[32] = {0x33};

  uint8_t child[19] = {0};
  child[0] = 1; /* PL_CANON_VERSION */
  test_put64le(child + 1, 0);
  child[9] = 'n';
  test_put64le(child + 10, 1);
  child[18] = 42;
  ASSERT(pl_store_backend_put(store, child_hash, child, sizeof(child)));

  uint8_t parent[78] = {0};
  parent[0] = 1; /* PL_CANON_VERSION */
  test_put64le(parent + 1, 2);
  memcpy(parent + 9, child_hash, sizeof(child_hash));
  memcpy(parent + 41, missing_hash, sizeof(missing_hash));
  parent[73] = 'p';
  ASSERT(pl_store_backend_put(store, parent_hash, parent, sizeof(parent)));

  bool raised = test_store_load_raises(t, parent_hash);
  ASSERT(raised, "expected nested missing PIN to raise");
  ASSERT_STR_EQ(t->exn_msg, "store_load: missing pin");
  ASSERT_EQ(ax_arrlen(store->loading), 0);

  store_both_lock_probe probe = {.store = store};
  pthread_t worker;
  ASSERT_EQ(pthread_create(&worker, NULL, store_try_both_locks_thread, &probe),
            0);
  ASSERT_EQ(pthread_join(worker, NULL), 0);
  if (!probe.general_acquired)
    (void)pthread_mutex_unlock(&store->mu);
  if (!probe.save_acquired)
    (void)pthread_mutex_unlock(&store->save_mu);
  ASSERT(probe.general_acquired, "nested Legacy load leaked store mu");
  ASSERT(probe.save_acquired, "nested Legacy load leaked save_mu");

  pl_thread_free(t);
  pl_heap_free(heap);
  pl_store_free(store);
}

TEST(store, legacy_rejects_pin_table_larger_than_header_meta) {
  save_probe_backend* backend;
  pl_store* store = save_probe_store(&backend);
  pl_heap* heap = pl_heap_new(1 << 16, store);
  pl_thread* t = pl_thread_new(heap);
  uint8_t hash[32] = {0x44};
  uint8_t record[9] = {1}; /* PL_CANON_VERSION */
  test_put64le(record + 1, (uint64_t)PL_HDR_META_MAX + 1);
  ASSERT(pl_store_backend_put(store, hash, record, sizeof(record)));

  bool raised = test_store_load_raises(t, hash);
  ASSERT(raised, "expected oversized Legacy PIN table to raise");
  ASSERT_STR_EQ(t->exn_msg,
                "store_load: PIN exceeds the direct PIN-table limit");
  ASSERT_EQ(ax_arrlen(store->loading), 0);

  pl_thread_free(t);
  pl_heap_free(heap);
  pl_store_free(store);
}

TEST(store, chrome_json_profiles_slow_store_operations) {
  char path[] = "/tmp/enki-profile-store-XXXXXX";
  int fd = mkstemp(path);
  ASSERT_GTE(fd, 0);
  ASSERT_EQ(close(fd), 0);
  ASSERT(ax_profile_json_start(path));

  char dir[] = "/tmp/enki-profile-store-db-XXXXXX";
  ASSERT_NOT_NULL(mkdtemp(dir));
  roundtrip_via(mk_lmdb, dir);

  ASSERT(ax_profile_json_finish());
  char* json = store_test_read_file(path);
  ASSERT_NOT_NULL(strstr(json, "\"cat\":\"splan.store\""));
  ASSERT_NOT_NULL(strstr(json, "\"name\":\"store.open\""));
  ASSERT_NOT_NULL(strstr(json, "\"name\":\"store.backend.put\""));
  ASSERT_NOT_NULL(strstr(json, "\"name\":\"store.backend.get\""));
  ASSERT_NOT_NULL(strstr(json, "\"name\":\"store.serialize\""));
  ASSERT_NOT_NULL(strstr(json, "\"name\":\"store.deserialize\""));
  ASSERT_NOT_NULL(strstr(json, "\"name\":\"store.root.put\""));
  ASSERT_NOT_NULL(strstr(json, "\"name\":\"store.root.get\""));
  ASSERT_NOT_NULL(strstr(json, "\"name\":\"store.close\""));
  ASSERT_NOT_NULL(strstr(json, "\"args\":{\"span\":"));
  ASSERT_NOT_NULL(strstr(json, "Store thread "));
  ASSERT_EQ(store_test_count(json, "\"ph\":\"B\""),
            store_test_count(json, "\"ph\":\"E\""));
  free(json);
  ASSERT_EQ(unlink(path), 0);
  char db_path[96];
  snprintf(db_path, sizeof(db_path), "%s/data.mdb", dir);
  ASSERT_EQ(unlink(db_path), 0);
  snprintf(db_path, sizeof(db_path), "%s/lock.mdb", dir);
  ASSERT_EQ(unlink(db_path), 0);
  ASSERT_EQ(rmdir(dir), 0);
}

TEST(store, silo_root_journal_records_publications) {
  char dir[64];
  snprintf(dir, sizeof(dir), "/tmp/enki-test-silo-journal-%lu",
           (unsigned long)getpid());
  ASSERT(mkdir(dir, 0700) == 0 || errno == EEXIST);
  pl_store* s = mk_silo(dir);
  ASSERT_NOT_NULL(s);
  pl_heap* h = pl_heap_new(1 << 16, s);
  pl_thread* t = pl_thread_new(h);
  char err[192] = {0};

  ASSERT_EQ(pl_store_root_log_head(s), 0);

  uint8_t first[32], second[32];
  pl_vpush(t, 1);
  pl_val pin1 = pl_pin(t, t->vstack[t->vsp - 1]);
  pl_vpush(t, pin1);
  ASSERT(pl_store_save_root(s, pin1, first, err, sizeof(err)), "%s", err);
  ASSERT_EQ(pl_store_root_log_head(s), 1);

  /* Republishing an unchanged root appends nothing. */
  pl_val again = t->vstack[t->vsp - 1];
  ASSERT(pl_store_save_root(s, again, NULL, err, sizeof(err)), "%s", err);
  ASSERT_EQ(pl_store_root_log_head(s), 1);

  pl_vpush(t, 2);
  pl_val pin2 = pl_pin(t, t->vstack[t->vsp - 1]);
  ASSERT(pl_store_save_root(s, pin2, second, err, sizeof(err)), "%s", err);
  ASSERT_EQ(pl_store_root_log_head(s), 2);

  pl_store_root_entry entries[4];
  ASSERT_EQ(pl_store_root_log(s, 1, entries, 4), 2);
  ASSERT_EQ(entries[0].seq, 1);
  ASSERT_EQ(memcmp(entries[0].hash, first, 32), 0);
  ASSERT_GT(entries[0].unix_ns, 0);
  ASSERT_GT(entries[0].pack_bytes, 0);
  ASSERT_EQ(entries[1].seq, 2);
  ASSERT_EQ(memcmp(entries[1].hash, second, 32), 0);
  ASSERT_GTE(entries[1].pack_bytes, entries[0].pack_bytes);

  char path[96];
  struct stat st;
  snprintf(path, sizeof(path), "%s/pins.pack", dir);
  ASSERT_EQ(stat(path, &st), 0);
  ASSERT_EQ((uint64_t)st.st_size, entries[1].pack_bytes);

  /* The replay seam journals too — but only actual root changes. */
  ASSERT(pl_store_put_root(s, first));
  ASSERT_EQ(pl_store_root_log_head(s), 3);
  ASSERT(pl_store_put_root(s, first));
  ASSERT_EQ(pl_store_root_log_head(s), 3);
  ASSERT_EQ(pl_store_root_log(s, 3, entries, 4), 1);
  ASSERT_EQ(entries[0].seq, 3);
  ASSERT_EQ(memcmp(entries[0].hash, first, 32), 0);

  pl_thread_free(t);
  pl_heap_free(h);
  pl_store_free(s);
  cleanup_store_dir(dir, true);
}

TEST(store, silo_compressed_objects_keep_hash_and_cold_value) {
  char dir[96], pack[128];
  snprintf(dir, sizeof(dir), "/tmp/enki-test-silo-compressed-%lu", (unsigned long)getpid());
  ASSERT_EQ(mkdir(dir, 0700), 0);
  pl_store* s = mk_silo(dir);
  ASSERT_NOT_NULL(s);
  pl_heap* h = pl_heap_new(1 << 16, s);
  pl_thread* t = pl_thread_new(h);
  pl_val args[6000];
  for (size_t i = 0; i < 6000; i++) args[i] = i % 11;
  pl_vpush(t, test_app(t, 0, 6000, args));
  pl_vpush(t, pl_pin(t, t->vstack[0]));
  char err[192] = {0};
  uint8_t hash[32];
  ASSERT(pl_store_save_root(s, t->vstack[1], hash, err, sizeof(err)), "%s", err);
  pl_silo_reader reader = {0};
  ASSERT(pl_store_silo_open(s, hash, &reader, err, sizeof(err)));
  size_t n = reader.len;
  uint8_t* encoded = malloc(n);
  ASSERT_NOT_NULL(encoded);
  ASSERT(reader.read(reader.ctx, encoded, n));
  uint8_t digest[32];
  ax_sha256(encoded, n, digest);
  ASSERT_EQ(memcmp(hash, digest, 32), 0);
  pl_store_silo_close_reader(&reader);
  snprintf(pack, sizeof(pack), "%s/pins.pack", dir);
  struct stat st;
  ASSERT_EQ(stat(pack, &st), 0);
  ASSERT_LT(st.st_size, n / 2);
  free(encoded);
  pl_thread_free(t); pl_heap_free(h); pl_store_free(s);
  s = pl_store_new_silo_ro(dir, (size_t)64 << 20);
  ASSERT_NOT_NULL(s);
  h = pl_heap_new(1 << 16, s); t = pl_thread_new(h);
  pl_val loaded = pl_store_load(t, hash);
  pl_cell* body = pl_ptr(pl_pin_body(pl_ptr(loaded)));
  ASSERT_EQ(pl_app_n(body), 6000);
  for (size_t i = 0; i < 6000; i++) ASSERT_EQ(pl_app_args(body)[i], i % 11);
  pl_thread_free(t); pl_heap_free(h); pl_store_free(s);
  /* A damaged compression checksum must fail before any value is published. */
  int fd = open(pack, O_RDWR);
  ASSERT_GTE(fd, 0);
  uint8_t last;
  ASSERT_EQ(pread(fd, &last, 1, st.st_size - 1), 1);
  last ^= 1;
  ASSERT_EQ(pwrite(fd, &last, 1, st.st_size - 1), 1);
  close(fd);
  s = pl_store_new_silo_ro(dir, (size_t)64 << 20);
  ASSERT_NOT_NULL(s);
  ASSERT_FALSE(pl_store_silo_open(s, hash, &reader, err, sizeof(err)));
  pl_store_free(s);
  cleanup_store_dir(dir, true);
}

TEST(store, silo_read_only_open_inspects_the_store) {
  char dir[64];
  snprintf(dir, sizeof(dir), "/tmp/enki-test-silo-ro-%lu",
           (unsigned long)getpid());
  ASSERT(mkdir(dir, 0700) == 0 || errno == EEXIST);

  uint8_t hash[32];
  pl_store* rw = mk_silo(dir);
  ASSERT_NOT_NULL(rw);
  pin_sample(rw, hash);
  pl_store_free(rw);

  pl_store* s = pl_store_new_silo_ro(dir, (size_t)64 << 20);
  ASSERT_NOT_NULL(s);
  uint8_t root[32];
  ASSERT(pl_store_get_root(s, root));
  ASSERT_EQ(memcmp(root, hash, 32), 0);
  ASSERT_EQ(pl_store_root_log_head(s), 1);

  /* Loading works read-only… */
  pl_heap* h = pl_heap_new(1 << 16, s);
  pl_thread* t = pl_thread_new(h);
  pl_val pin = pl_store_load(t, hash);
  ASSERT_EQ(memcmp(pl_pin_hash(pin), hash, 32), 0);

  /* …while every mutation path fails cleanly. */
  char err[192] = {0};
  pl_silo_batch* batch = NULL;
  ASSERT_FALSE(pl_store_silo_batch_begin(s, &batch, err, sizeof(err)));
  ASSERT_NULL(batch);
  ASSERT_FALSE(pl_store_put_root(s, hash));
  size_t base = t->vsp;
  pl_vpush(t, 7);
  pl_val fresh = pl_pin(t, t->vstack[base]);
  uint8_t fresh_hash[32];
  ASSERT_FALSE(pl_store_save_root(s, fresh, fresh_hash, err, sizeof(err)));

  pl_thread_free(t);
  pl_heap_free(h);
  pl_store_free(s);
  cleanup_store_dir(dir, true);
}

TEST(store, silo_object_info_reports_stream_and_subpins) {
  char dir[64];
  snprintf(dir, sizeof(dir), "/tmp/enki-test-silo-info-%lu",
           (unsigned long)getpid());
  ASSERT(mkdir(dir, 0700) == 0 || errno == EEXIST);
  pl_store* s = mk_silo(dir);
  ASSERT_NOT_NULL(s);
  pl_heap* h = pl_heap_new(1 << 16, s);
  pl_thread* t = pl_thread_new(h);

  size_t base = t->vsp;
  pl_vpush(t, 42);
  t->vstack[base] = pl_pin(t, t->vstack[base]);
  pl_vpush(t, test_app2(t, 0, t->vstack[base], 5));
  pl_val root = pl_pin(t, t->vstack[base + 1]);
  char err[192] = {0};
  uint8_t hash[32];
  ASSERT(pl_store_save_root(s, root, hash, err, sizeof(err)), "%s", err);
  const uint8_t* inner_hash = pl_pin_hash(t->vstack[base]);
  ASSERT_NOT_NULL(inner_hash);

  uint64_t len = 0;
  pl_hash* subs = NULL;
  size_t nsub = 0;
  ASSERT(
      pl_store_silo_object_info(s, hash, &len, &subs, &nsub, err, sizeof(err)),
      "%s", err);
  ASSERT_GT(len, 0);
  ASSERT_EQ(nsub, 1);
  ASSERT_EQ(memcmp(subs[0].b, inner_hash, 32), 0);
  free(subs);

  ASSERT(pl_store_silo_object_info(s, inner_hash, &len, &subs, &nsub, err,
                                   sizeof(err)),
         "%s", err);
  ASSERT_GT(len, 0);
  ASSERT_EQ(nsub, 0);
  ASSERT_NULL(subs);

  uint8_t missing[32] = {0xff};
  ASSERT_FALSE(pl_store_silo_object_info(s, missing, &len, &subs, &nsub, err,
                                         sizeof(err)));

  pl_thread_free(t);
  pl_heap_free(h);
  pl_store_free(s);
  cleanup_store_dir(dir, true);
}
