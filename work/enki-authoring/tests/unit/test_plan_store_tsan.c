#include <pthread.h>
#include <stdbool.h>
#include <stdio.h>

#include "plan/build.h"
#include "plan/heap.h"
#include "plan/store.h"
#include "test.h"
#include "test_plan.h"
#include "../../pkg/plan/src/store_internal.h"

typedef struct store_pin_worker {
  pl_store* store;
  pl_val canonical;
  unsigned group;
  bool ok;
} store_pin_worker;

typedef struct pin_code_race {
  pl_cell* pin;
  pl_code* first;
  pl_code* second;
  bool start;
  bool ok;
} pin_code_race;

typedef struct pin_equal_race {
  pl_store* store;
  pl_val* proxies;
  size_t count;
  pl_val canonical;
  bool* start;
  unsigned operation;
  bool ok;
} pin_equal_race;

static void* pin_equal_thread(void* arg) {
  pin_equal_race* race = arg;
  pl_heap* heap = pl_heap_new(1 << 14, race->store);
  pl_thread* t = pl_thread_new(heap);
  while (!__atomic_load_n(race->start, __ATOMIC_ACQUIRE)) {
  }
  for (size_t i = 0; i < race->count; i++) {
    pl_val pin = race->proxies[i];
    if (race->operation < 2) {
      pl_val a = race->operation == 0 ? pin : race->canonical;
      pl_val b = race->operation == 0 ? race->canonical : pin;
      race->ok = test_op66_2(t, ax_s5('E', 'q', 'u', 'a', 'l'), a, b) == 1;
    } else if (race->operation == 2) {
      race->ok = test_op66(t, ax_s3('I', 'c', 'e'), 1, &pin) == 0;
    } else {
      char err[192] = {0};
      race->ok = pl_store_save_root(race->store, pin, NULL, err, sizeof(err));
    }
    if (!race->ok || pl_pin_proxy_target(pl_ptr(pin)) != race->canonical) {
      race->ok = false;
      break;
    }
  }
  pl_thread_free(t);
  pl_heap_free(heap);
  return NULL;
}

static void* store_pin_thread(void* arg) {
  store_pin_worker* w = arg;
  pl_heap* heap = pl_heap_new(1 << 14, w->store);
  pl_thread* t = pl_thread_new(heap);
  for (int i = 0; i < 100; i++) {
    size_t base = t->vsp;
    pl_vpush(t, test_law(t, 1, ax_s4('T', 's', 'a', 'n'), 42 + w->group));
    t->vstack[base] = pl_pin(t, t->vstack[base]);
    pl_val proxy = t->vstack[base];
    pl_cell* pp = pl_as(PL_TAG_PIN, proxy);
    if (pp == NULL || !pl_pin_is_proxy(pp) || pl_pin_proxy_target(pp) != 0 ||
        pl_store_owns(w->store, proxy)) {
      w->ok = false;
      break;
    }

    uint8_t hash[32];
    char err[192] = {0};
    if (!pl_store_save_root(w->store, proxy, hash, err, sizeof(err))) {
      fprintf(stderr, "concurrent Save failed: %s\n", err);
      w->ok = false;
      break;
    }
    pl_val canonical = pl_pin_proxy_target(pl_ptr(t->vstack[base]));
    if (canonical == 0 || !pl_store_owns(w->store, canonical) ||
        !pl_pin_is_hashed(canonical) || pl_store_load(t, hash) != canonical) {
      w->ok = false;
      break;
    }
    if (w->canonical != 0 && w->canonical != canonical) {
      w->ok = false;
      break;
    }
    w->canonical = canonical;
    t->vsp = base;
  }
  pl_thread_free(t);
  pl_heap_free(heap);
  return NULL;
}

static void* pin_code_writer(void* arg) {
  pin_code_race* race = arg;
  while (!__atomic_load_n(&race->start, __ATOMIC_ACQUIRE)) {
  }
  for (size_t i = 0; i < 100000; i++)
    pl_pin_set_code(race->pin, (i & 1u) != 0 ? race->first : race->second);
  return NULL;
}

static void* pin_code_reader(void* arg) {
  pin_code_race* race = arg;
  while (!__atomic_load_n(&race->start, __ATOMIC_ACQUIRE)) {
  }
  for (size_t i = 0; i < 100000; i++) {
    void* code = pl_pin_code(race->pin);
    if (code != NULL && code != race->first && code != race->second) {
      race->ok = false;
      break;
    }
  }
  return NULL;
}

static int test_concurrent_saves_publish_equal_and_distinct_values(void) {
  pl_store* store = pl_store_new_mem();
  enum { NTHREADS = 4 };
  store_pin_worker workers[NTHREADS];
  pthread_t threads[NTHREADS];
  bool started[NTHREADS] = {0};
  int status = 0;
  pl_val canonical[2] = {0};

  for (size_t i = 0; i < NTHREADS; i++) {
    workers[i] = (store_pin_worker){
        .store = store, .group = (unsigned)(i % 2), .ok = true};
    int err = pthread_create(&threads[i], NULL, store_pin_thread, &workers[i]);
    if (err != 0) {
      fprintf(stderr, "pthread_create(%zu) failed: %d\n", i, err);
      status = 1;
      break;
    }
    started[i] = true;
  }
  for (size_t i = 0; i < NTHREADS; i++) {
    if (!started[i])
      continue;
    int err = pthread_join(threads[i], NULL);
    if (err != 0) {
      fprintf(stderr, "pthread_join(%zu) failed: %d\n", i, err);
      status = 1;
      continue;
    }
    if (!workers[i].ok) {
      fprintf(stderr, "store pin worker %zu failed proxy publication\n", i);
      status = 1;
    } else if (canonical[workers[i].group] == 0) {
      canonical[workers[i].group] = workers[i].canonical;
    } else if (workers[i].canonical != canonical[workers[i].group]) {
      fprintf(stderr,
              "equal concurrent Saves published different canonicals\n");
      status = 1;
    }
  }
  if (canonical[0] == 0 || canonical[1] == 0 || canonical[0] == canonical[1]) {
    fprintf(stderr, "distinct concurrent Saves did not stay distinct\n");
    status = 1;
  }
  pl_store_free(store);
  return status;
}

static int test_pin_code_publication_is_atomic(void) {
  pl_cell pin[PL_PIN_CELLS(0)] = {0};
  pin[0] =
      pl_hdr_make(PL_K_PIN, PL_F_NORMAL | PL_F_PIN_HASHED, 0, PL_PIN_CELLS(0));
  pl_code first = {0};
  pl_code second = {0};
  pin_code_race race = {
      .pin = pin, .first = &first, .second = &second, .ok = true};
  pthread_t writer;
  pthread_t reader;

  int err = pthread_create(&writer, NULL, pin_code_writer, &race);
  if (err != 0) {
    fprintf(stderr, "pin code writer pthread_create failed: %d\n", err);
    return 1;
  }
  err = pthread_create(&reader, NULL, pin_code_reader, &race);
  if (err != 0) {
    fprintf(stderr, "pin code reader pthread_create failed: %d\n", err);
    __atomic_store_n(&race.start, true, __ATOMIC_RELEASE);
    (void)pthread_join(writer, NULL);
    return 1;
  }

  __atomic_store_n(&race.start, true, __ATOMIC_RELEASE);
  int status = 0;
  err = pthread_join(writer, NULL);
  if (err != 0) {
    fprintf(stderr, "pin code writer pthread_join failed: %d\n", err);
    status = 1;
  }
  err = pthread_join(reader, NULL);
  if (err != 0) {
    fprintf(stderr, "pin code reader pthread_join failed: %d\n", err);
    status = 1;
  }
  if (!race.ok) {
    fprintf(stderr, "pin code reader observed an invalid code pointer\n");
    status = 1;
  }
  return status;
}

TEST(store_tsan, concurrent_saves_publish_equal_and_distinct_values) {
  ASSERT_EQ(test_concurrent_saves_publish_equal_and_distinct_values(), 0);
}

TEST(store_tsan, pin_code_publication_is_atomic) {
  ASSERT_EQ(test_pin_code_publication_is_atomic(), 0);
}

TEST(store_tsan, equal_ice_and_save_publish_shared_proxies) {
  test_rt rt = test_rt_new();
  pl_thread* t = rt.t;
  enum { COUNT = 128, WORKERS = 4 };
  pl_val proxies[COUNT];
  size_t base = t->vsp;
  pl_vpush(t, pl_pin(t, 42));
  pl_val pin = t->vstack[base];
  ASSERT_EQ(test_op66(t, ax_s3('I', 'c', 'e'), 1, &pin), 0);
  pl_val canonical = pl_pin_proxy_target(pl_ptr(t->vstack[base]));
  for (size_t i = 0; i < COUNT; i++) {
    pl_vpush(t, pl_pin(t, 42));
    t->vstack[base + 1] = pl_nf(t, t->vstack[base + 1]);
    proxies[i] = pl_store_snapshot_normal(t, t->vstack[base + 1]);
    ASSERT_EQ(pl_pin_proxy_target(pl_ptr(proxies[i])), 0);
    t->vsp = base + 1;
  }
  bool start = false;
  pin_equal_race races[WORKERS];
  pthread_t threads[WORKERS];
  unsigned started = 0;
  int create_error = 0;
  for (unsigned i = 0; i < WORKERS; i++) {
    races[i] = (pin_equal_race){.store = rt.store,
                                .proxies = proxies,
                                .count = COUNT,
                                .canonical = canonical,
                                .start = &start,
                                .operation = i,
                                .ok = true};
    create_error =
        pthread_create(&threads[i], NULL, pin_equal_thread, &races[i]);
    if (create_error != 0)
      break;
    started++;
  }
  __atomic_store_n(&start, true, __ATOMIC_RELEASE);
  bool ok = true;
  for (unsigned i = 0; i < started; i++) {
    if (pthread_join(threads[i], NULL) != 0 || !races[i].ok)
      ok = false;
  }
  ASSERT_EQ(create_error, 0);
  ASSERT(ok);
  for (size_t i = 0; i < COUNT; i++)
    ASSERT_EQ(pl_pin_proxy_target(pl_ptr(proxies[i])), canonical);
  test_rt_free(&rt);
}

static void* staging_thread(void* arg) {
  store_pin_worker* w = arg;
  pl_heap* h = pl_heap_new(1 << 14, w->store);
  pl_thread* t = pl_thread_new(h);
  for (unsigned i = 0; i < 32 && w->ok; i++) {
    t->vsp = 0;
    pl_vpush(t, pl_pin(t, i + 32 * w->group));
    pl_val pin = t->vstack[0];
    w->ok = test_op66(t, ax_s3('I', 'c', 'e'), 1, &pin) == 0;
    const uint8_t* hash = pl_pin_hash(t->vstack[0]);
    pl_silo_reader reader;
    char err[192];
    if (!w->ok || hash == NULL ||
        !pl_store_silo_open(w->store, hash, &reader, err, sizeof(err))) {
      w->ok = false;
      break;
    }
    uint8_t byte;
    w->ok = reader.read(reader.ctx, &byte, 1);
    pl_store_silo_close_reader(&reader);
    uint8_t key[32] = {0xCC, (uint8_t)w->group};
    w->ok = w->ok && pl_store_backend_put(w->store, key, &byte, 1);
    uint8_t* got = NULL;
    size_t n = 0;
    w->ok = w->ok && pl_store_backend_get(w->store, key, &got, &n);
    w->ok = w->ok && n == 1 && *got == byte;
    free(got);
    if (w->ok && i % 4 == 0)
      w->ok =
          pl_store_save_root(w->store, t->vstack[0], NULL, err, sizeof(err));
  }
  pl_thread_free(t);
  pl_heap_free(h);
  return NULL;
}

static void staging_object(void* ctx, const uint8_t hash[32], uint64_t off,
                           uint64_t len) {
  (void)ctx;
  (void)hash;
  (void)off;
  (void)len;
}

TEST(store_tsan, silo_staging_reads_and_checkpoints_are_serialized) {
  char dir[] = "/tmp/enki-tsan-staging-XXXXXX";
  ASSERT_NOT_NULL(mkdtemp(dir));
  pl_store* s = pl_store_new_silo(dir, 1 << 20);
  ASSERT_NOT_NULL(s);
  enum { N = 4 };
  store_pin_worker workers[N];
  pthread_t threads[N];
  unsigned started = 0;
  int create_error = 0;
  for (unsigned i = 0; i < N; i++) {
    workers[i] = (store_pin_worker){.store = s, .group = i, .ok = true};
    create_error =
        pthread_create(&threads[i], NULL, staging_thread, &workers[i]);
    if (create_error != 0)
      break;
    started++;
  }
  bool ok = true;
  for (unsigned i = 0; i < started; i++)
    if (pthread_join(threads[i], NULL) != 0 || !workers[i].ok)
      ok = false;
  ASSERT_EQ(create_error, 0);
  ASSERT(ok);
  uint8_t root[32];
  ASSERT(pl_store_get_root(s, root));
  ASSERT(pl_store_put_root(s, root));
  ASSERT_EQ(pl_store_silo_objects(s, staging_object, NULL), 128);
  pl_store_free(s);
  const char* files[] = {"pins.pack", "data.mdb", "lock.mdb"};
  for (unsigned i = 0; i < 3; i++) {
    char path[256];
    snprintf(path, sizeof(path), "%s/%s", dir, files[i]);
    (void)unlink(path);
  }
  (void)rmdir(dir);
}
