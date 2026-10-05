#include "plan/store.h"

#include <inttypes.h>
#include <setjmp.h>
#include <stdatomic.h>
#include <assert.h>
#include <errno.h>
#include <lmdb.h>
#include <pthread.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <sys/stat.h>

#include "axsys/arena.h"
#include "axsys/assume.h"
#include "axsys/sha256.h"
#include "axsys/ds.h"
#include "axsys/profile.h"
#include "axsys/util.h"
#include "internal.h"
#include "plan/build.h"
#include "store_internal.h"

/* Default reserved (overcommitted) size of the store region. */
#ifndef PL_STORE_REGION_BYTES
#define PL_STORE_REGION_BYTES (((size_t)1) << 38)
#endif

/* Store spans use the active logical PLAN lane when called by an executor.
 * Host-side work gets a stable lane per native thread so concurrent
 * backend calls never produce crossed B/E pairs on one Chrome Trace lane. */
static const uint8_t pl_store_profile_category[] = "splan.store";
static _Atomic uint64_t pl_store_profile_next_span = 1;
static _Atomic uint64_t pl_store_profile_next_host_lane = UINT32_MAX;
static _Thread_local uint64_t pl_store_profile_host_lane;

static uint64_t pl_store_profile_lane(void) {
  uint64_t lane = pl_profile_current_lane();
  bool host = lane == 0;
  if (host) {
    if (pl_store_profile_host_lane == 0) {
      pl_store_profile_host_lane = atomic_fetch_sub_explicit(
          &pl_store_profile_next_host_lane, 1, memory_order_relaxed);
      ax_assume(pl_store_profile_host_lane != 0,
                "store profile lane id exhausted");
    }
    lane = pl_store_profile_host_lane;
  }

  char name[64];
  int n;
  if (host) {
    uint64_t ordinal = UINT32_MAX - lane + 1;
    n = snprintf(name, sizeof(name), "Store thread %" PRIu64, ordinal);
  } else {
    n = snprintf(name, sizeof(name), "PLAN thread %" PRIu64, lane);
  }
  if (n >= 0) {
    size_t name_n = (size_t)n < sizeof(name) ? (size_t)n : sizeof(name) - 1;
    ax_profile_json_thread_name(lane, name, name_n);
  }
  return lane;
}

pl_store_profile_scope pl_store_profile_begin(const char* name, size_t name_n) {
  if (!ax_profile_json_enabled())
    return (pl_store_profile_scope){0};
  pl_store_profile_scope scope = {
      .lane = pl_store_profile_lane(),
      .span = atomic_fetch_add_explicit(&pl_store_profile_next_span, 1,
                                        memory_order_relaxed),
      .name = (const uint8_t*)name,
      .name_n = name_n,
      .active = true,
  };
  ax_assume(scope.span != 0, "store profile span id exhausted");
  ax_profile_json_span_begin(scope.lane, scope.span, pl_store_profile_category,
                             sizeof(pl_store_profile_category) - 1, scope.name,
                             scope.name_n);
  return scope;
}

void pl_store_profile_end(pl_store_profile_scope* scope) {
  if (!scope->active)
    return;
  ax_profile_json_span_end(scope->lane, scope->span, pl_store_profile_category,
                           sizeof(pl_store_profile_category) - 1, scope->name,
                           scope->name_n);
  scope->active = false;
}

#define PL_STORE_PROFILE(name)                                                 \
  __attribute__((cleanup(pl_store_profile_end))) pl_store_profile_scope        \
      pl_store_profile_scope_ = pl_store_profile_begin(name, sizeof(name) - 1)

bool pl_staged_put(pl_staged_blob** staged, const uint8_t hash[32],
                   const uint8_t* bytes, size_t len) {
  uint8_t* copy = malloc(len != 0 ? len : 1);
  if (copy == NULL)
    return false;
  memcpy(copy, bytes, len);
  pl_staged_blob entry = {.value = {.bytes = copy, .len = len}};
  memcpy(entry.key.b, hash, sizeof(entry.key.b));
  ptrdiff_t at = ax_hmgeti(*staged, entry.key);
  if (at >= 0)
    free((*staged)[at].value.bytes);
  ax_hmput(*staged, entry.key, entry.value);
  return true;
}

bool pl_staged_get(pl_staged_blob* staged, const uint8_t hash[32],
                   uint8_t** out, size_t* len) {
  pl_hash key;
  memcpy(key.b, hash, sizeof(key.b));
  ptrdiff_t at = ax_hmgeti(staged, key);
  if (at < 0)
    return false;
  size_t n = staged[at].value.len;
  uint8_t* copy = malloc(n != 0 ? n : 1);
  ax_assume(copy != NULL, "oom");
  memcpy(copy, staged[at].value.bytes, n);
  *out = copy;
  *len = n;
  return true;
}

void pl_staged_clear(pl_staged_blob** staged) {
  for (ptrdiff_t i = 0; i < ax_hmlen(*staged); i++)
    free((*staged)[i].value.bytes);
  ax_hmfree(*staged);
  *staged = NULL;
}

/* ── Global compile cache ──────────────────────────────────────────────
 *
 * A machine-wide LMDB at PL_CODECACHE_DIR mapping the same
 * (compiler, law) keys as the per-snap cache to the encoded Silo
 * stream of the code-row pin.  Because streams carry their subpin
 * hashes and rebuilds are content-verified, a fresh snap can adopt
 * rows compiled by any earlier snap — `rm -rf snap` no longer means a
 * cold compiler. Writes remain in memory until Save. An unset dir
 * (library users, tests) disables it; an unopenable path is a cache miss.
 * PL_CODECACHE=0 forces it off. */
static pthread_mutex_t plgc_mu = PTHREAD_MUTEX_INITIALIZER;
static MDB_env* plgc_env;
static MDB_dbi plgc_dbi;
static int plgc_state; /* 0 unopened, 1 open, -1 disabled */
static bool plgc_writable;
static pl_staged_blob* plgc_staged;

static bool plgc_configured(void) {
  const char* flag = getenv("PL_CODECACHE");
  if (flag != NULL && strcmp(flag, "0") == 0)
    return false;
  const char* dir = getenv("PL_CODECACHE_DIR");
  return dir != NULL && dir[0] != '\0';
}

static bool plgc_open(bool writable) {
  if (plgc_state < 0)
    return false;
  if (plgc_env != NULL && (!writable || plgc_writable))
    return true;
  if (!plgc_configured()) {
    plgc_state = -1;
    return false;
  }
  /* Reads (including compiler lookups during Ice) must not create the
   * cache or perform a write transaction.  Upgrade only at a Save. */
  if (plgc_env != NULL) {
    mdb_env_close(plgc_env);
    plgc_env = NULL;
    plgc_state = 0;
  }
  const char* dir = getenv("PL_CODECACHE_DIR");
  if (writable)
    (void)mkdir(dir, 0755);
  MDB_env* env = NULL;
  if (mdb_env_create(&env) != 0)
    return false;
  if (mdb_env_set_maxdbs(env, 1) != 0 ||
      mdb_env_set_mapsize(env, (size_t)1 << 33) != 0 ||
      mdb_env_open(env, dir, writable ? 0 : MDB_RDONLY, 0664) != 0) {
    mdb_env_close(env);
    return false;
  }
  MDB_txn* txn = NULL;
  if (mdb_txn_begin(env, NULL, writable ? 0 : MDB_RDONLY, &txn) != 0 ||
      mdb_dbi_open(txn, "cache", writable ? MDB_CREATE : 0, &plgc_dbi) != 0) {
    if (txn != NULL)
      mdb_txn_abort(txn);
    mdb_env_close(env);
    return false;
  }
  if (mdb_txn_commit(txn) != 0) {
    mdb_env_close(env);
    return false;
  }
  plgc_env = env;
  plgc_state = 1;
  plgc_writable = writable;
  return true;
}

static bool plgc_get(const uint8_t key[32], uint8_t** out_b, size_t* out_n) {
  pthread_mutex_lock(&plgc_mu);
  bool ok = pl_staged_get(plgc_staged, key, out_b, out_n);
  if (!ok && plgc_open(false)) {
    MDB_txn* txn;
    if (mdb_txn_begin(plgc_env, NULL, MDB_RDONLY, &txn) == 0) {
      MDB_val k = {32, (void*)key};
      MDB_val v;
      if (mdb_get(txn, plgc_dbi, &k, &v) == 0) {
        *out_b = malloc(v.mv_size);
        if (*out_b != NULL) {
          memcpy(*out_b, v.mv_data, v.mv_size);
          *out_n = v.mv_size;
          ok = true;
        }
      }
      mdb_txn_abort(txn);
    }
  }
  pthread_mutex_unlock(&plgc_mu);
  return ok;
}

static void plgc_put(const uint8_t key[32], const uint8_t* b, size_t n) {
  pthread_mutex_lock(&plgc_mu);
  if (plgc_configured())
    (void)pl_staged_put(&plgc_staged, key, b, n);
  pthread_mutex_unlock(&plgc_mu);
}

/* Derived cache persistence is best-effort, but may only sync at Save. */
void pl_store_cache_checkpoint(void) {
  pthread_mutex_lock(&plgc_mu);
  if (ax_hmlen(plgc_staged) != 0 && plgc_open(true)) {
    MDB_txn* txn;
    if (mdb_txn_begin(plgc_env, NULL, 0, &txn) == 0) {
      bool ok = true;
      for (ptrdiff_t i = 0; i < ax_hmlen(plgc_staged); i++) {
        MDB_val k = {32, plgc_staged[i].key.b};
        MDB_val v = {plgc_staged[i].value.len, plgc_staged[i].value.bytes};
        if (mdb_put(txn, plgc_dbi, &k, &v, 0) != 0) {
          ok = false;
          break;
        }
      }
      if (!ok)
        mdb_txn_abort(txn);
      else if (mdb_txn_commit(txn) == 0)
        pl_staged_clear(&plgc_staged);
    }
  }
  pthread_mutex_unlock(&plgc_mu);
}

/* ── Memoised-application cache (op 66 Memo) ───────────────────────────
 *
 * (Memo f x) ≡ (f x); when f and x are canonical hashed pins and the
 * result is a nat63 computed without initiating any effect, the pair
 * may be served from this machine-global cache (spec:
 * doc/sigoflaw-memo-spec.md).  Two layers: an in-process map (always
 * on) and the same LMDB environment as the code cache under a "plgm"
 * key tag (subject to the PL_CODECACHE knobs via plgc_open).  A
 * persistent value that fails to parse as a nat63 is a miss. */

typedef struct {
  uint8_t b[64]; /* f_hash ‖ x_hash: the in-process map needs no hashing */
} pl_memo_key;

typedef struct {
  pl_memo_key key;
  uint64_t value;
} pl_memo_ent;

static pthread_mutex_t memo_mu = PTHREAD_MUTEX_INITIALIZER;
static pl_memo_ent* memo_map; /* stb_ds hashmap, keyed on the 32 bytes */
static uint64_t memo_probes, memo_hits, memo_recorded;

static pl_memo_key memo_raw_key(const uint8_t f_hash[32],
                                const uint8_t x_hash[32]) {
  pl_memo_key k;
  memcpy(k.b, f_hash, 32);
  memcpy(k.b + 32, x_hash, 32);
  return k;
}

/* The persistent layer keys on sha256("plgm" ‖ f ‖ x).  Compute it only
 * when the in-process map misses, so a warm hit is one hashmap lookup. */
static void memo_key(const uint8_t f_hash[32], const uint8_t x_hash[32],
                     uint8_t out[32]) {
  uint8_t pre[68];
  memcpy(pre, "plgm", 4);
  memcpy(pre + 4, f_hash, 32);
  memcpy(pre + 36, x_hash, 32);
  ax_sha256(pre, sizeof(pre), out);
}

static void memo_stats_print(void) {
  fprintf(stderr,
          "plan: memo probes=%" PRIu64 " hits=%" PRIu64 " records=%" PRIu64
          "\n",
          memo_probes, memo_hits, memo_recorded);
}

static bool memo_stats_wanted(void) {
  static int wanted = -1;
  if (wanted < 0) {
    const char* flag = getenv("PL_MEMO_STATS");
    wanted = flag != NULL && strcmp(flag, "1") == 0;
    if (wanted)
      atexit(memo_stats_print);
  }
  return wanted > 0;
}

bool pl_memo_probe(const uint8_t f_hash[32], const uint8_t x_hash[32],
                   uint64_t* out) {
  pl_memo_key key = memo_raw_key(f_hash, x_hash);
  bool ok = false;
  pthread_mutex_lock(&memo_mu);
  (void)memo_stats_wanted();
  memo_probes++;
  ptrdiff_t at = ax_hmgeti(memo_map, key);
  if (at >= 0) {
    *out = memo_map[at].value;
    memo_hits++;
    ok = true;
  }
  pthread_mutex_unlock(&memo_mu);
  if (ok)
    return true;
  uint8_t pkey[32];
  memo_key(f_hash, x_hash, pkey);
  uint8_t* b = NULL;
  size_t n = 0;
  if (!plgc_get(pkey, &b, &n))
    return false;
  if (n == 8) {
    uint64_t v = 0;
    for (int i = 7; i >= 0; i--)
      v = (v << 8) | b[i];
    if (pl_is_nat63(v)) {
      *out = v;
      ok = true;
      pthread_mutex_lock(&memo_mu);
      memo_hits++;
      if (ax_hmgeti(memo_map, key) < 0)
        ax_hmput(memo_map, key, v); /* backfill: later probes skip LMDB */
      pthread_mutex_unlock(&memo_mu);
    }
  }
  free(b);
  return ok;
}

void pl_memo_record(const uint8_t f_hash[32], const uint8_t x_hash[32],
                    uint64_t value) {
  if (!pl_is_nat63(value))
    return;
  pl_memo_key key = memo_raw_key(f_hash, x_hash);
  pthread_mutex_lock(&memo_mu);
  memo_recorded++;
  if (ax_hmgeti(memo_map, key) < 0)
    ax_hmput(memo_map, key, value);
  pthread_mutex_unlock(&memo_mu);
  uint8_t b[8];
  for (int i = 0; i < 8; i++)
    b[i] = (uint8_t)(value >> (8 * i));
  uint8_t pkey[32];
  memo_key(f_hash, x_hash, pkey);
  plgc_put(pkey, b, sizeof(b));
}

void pl_memo_stats(uint64_t* probes, uint64_t* hits, uint64_t* records) {
  pthread_mutex_lock(&memo_mu);
  if (probes != NULL)
    *probes = memo_probes;
  if (hits != NULL)
    *hits = memo_hits;
  if (records != NULL)
    *records = memo_recorded;
  pthread_mutex_unlock(&memo_mu);
}

/* Lock order is save_mu -> mu.  save_mu serializes persistence operations and
 * the compiler machine; mu protects the arena and in-memory registries. */

void pl_store_lock(pl_store* s) {
  ax_assume(pthread_mutex_lock(&s->mu) == 0, "pthread_mutex_lock");
}

void pl_store_unlock(pl_store* s) {
  ax_assume(pthread_mutex_unlock(&s->mu) == 0, "pthread_mutex_unlock");
}

void pl_store_save_lock(pl_store* s) {
  ax_assume(pthread_mutex_lock(&s->save_mu) == 0, "save pthread_mutex_lock");
}

void pl_store_save_unlock(pl_store* s) {
  ax_assume(pthread_mutex_unlock(&s->save_mu) == 0,
            "save pthread_mutex_unlock");
}

/* ── Region allocation ─────────────────────────────────────────────────── */

pl_cell* pl_store_alloc(pl_store* s, size_t cells) {
  pl_store_lock(s);
  void* p = ax_arena_alloc_aligned(s->region, cells * sizeof(pl_cell), 8);
  ax_assume(p != NULL, "store region exhausted");
  pl_store_unlock(s);
  return p;
}

size_t pl_store_mark(pl_store* s) {
  pl_store_lock(s);
  size_t mark = s->region->off_o;
  pl_store_unlock(s);
  return mark;
}

size_t pl_store_memory_bytes(pl_store* s) {
  return pl_store_mark(s);
}

void pl_store_release(pl_store* s, size_t mark) {
  pl_store_lock(s);
  s->region->off_o = mark;
  if (s->decoded_values != NULL)
    memset(s->decoded_values, 0, (1u << 18) * sizeof(pl_val));
  pl_store_unlock(s);
}

/* Saved versions often repeat the same unpinned immutable subtrees. Their
 * bytes, hashes and values are unchanged by sharing their decoded storage.
 * A bounded direct-mapped cache makes eviction a performance issue only.
 * Only the newest, unpublished allocation may be rewound. PIN identities
 * never enter this cache. A failed load clears it before arena rollback. */
pl_val pl_store_reuse_decoded(pl_store* s, pl_val value) {
  if (pl_is_nat63(value) || pl_tag(value) == PL_TAG_PIN) return value;
  pl_cell* p = pl_ptr(value);
  size_t bytes = (size_t)pl_hdr_cells(p[0]) * sizeof(pl_cell);
  pl_store_lock(s);
  size_t start = (size_t)(pl_addr(value) - (uintptr_t)s->region->ptr);
  if (start + bytes != s->region->off_o) {
    pl_store_unlock(s);
    return value;
  }
  if (s->decoded_values == NULL)
    s->decoded_values = calloc(1u << 18, sizeof(pl_val));
  if (s->decoded_values == NULL) {
    pl_store_unlock(s);
    return value;
  }
  uint64_t hash = UINT64_C(0x9e3779b97f4a7c15);
  for (size_t i = 0; i < bytes / sizeof(pl_cell); i++) {
    hash ^= p[i] + UINT64_C(0x9e3779b97f4a7c15) + (hash << 6) + (hash >> 2);
  }
  hash ^= hash >> 33;
  hash *= UINT64_C(0xff51afd7ed558ccd);
  hash ^= hash >> 33;
  size_t index = (size_t)hash & ((1u << 18) - 1);
  pl_val prior = s->decoded_values[index];
  if (prior != 0 && pl_tag(prior) == pl_tag(value) &&
      pl_hdr_cells(pl_ptr(prior)[0]) == pl_hdr_cells(p[0]) &&
      memcmp(pl_ptr(prior), p, bytes) == 0) {
    s->region->off_o = start;
    value = prior;
  } else {
    s->decoded_values[index] = value;
  }
  pl_store_unlock(s);
  return value;
}

/* ── Intern table ──────────────────────────────────────────────────────── */

static pl_cell* pl_store_require_canonical_pin(pl_store* s, pl_val pin,
                                               const char* caller) {
  /* Check the original value before using the proxy-transparent accessors:
   * a resolved moving proxy has a canonical hash and body, but retaining the
   * proxy itself in a store registry would leave a dangling heap pointer. */
  ax_assume(pl_tag(pin) == PL_TAG_PIN && pl_store_owns(s, pin),
            "%s: PIN is not store-owned", caller);
  pl_cell* p = pl_ptr(pin);
  ax_assume(pl_hdr_kind(p[0]) == PL_K_PIN && !pl_pin_is_proxy(p) &&
                (pl_hdr_flags(p[0]) & PL_F_PIN_HASHED) != 0 &&
                pl_hdr_cells(p[0]) == PL_PIN_CELLS(pl_hdr_meta(p[0])),
            "%s: PIN is not canonical", caller);
  ax_assume(pl_is_nat63((pl_val)p[5]) || pl_store_owns(s, (pl_val)p[5]),
            "%s: PIN body is not a closed store graph", caller);
  return p;
}

static void pl_store_index_hashed_law_locked(pl_store* s, pl_val pin) {
  pl_cell* p = pl_store_require_canonical_pin(s, pin, "index_hashed_law");
  pl_val body = (pl_val)p[5];
  ax_assume(pl_tag(body) == PL_TAG_LAW &&
                pl_hdr_kind(pl_ptr(body)[0]) == PL_K_LAW,
            "index_hashed_law: non-LAW PIN");
  pl_hash key;
  memcpy(key.b, pl_pin_hash_bytes(p), sizeof(key.b));
  ptrdiff_t at = ax_hmgeti(s->code_targets, key);
  if (at < 0) {
    pl_val* targets = NULL;
    ax_arrpush(targets, pin);
    ax_hmput(s->code_targets, key, targets);
  } else {
    ax_arrpush(s->code_targets[at].value, pin);
  }
  ptrdiff_t code_at = ax_hmgeti(s->code_cache, key);
  if (code_at >= 0)
    pl_pin_set_code(p, s->code_cache[code_at].value);
}

void pl_store_index_hashed_law(pl_store* s, pl_val pin) {
  pl_store_lock(s);
  pl_store_index_hashed_law_locked(s, pin);
  pl_store_unlock(s);
}

pl_val pl_store_intern_get(pl_store* s, const uint8_t hash[32]) {
  pl_store_lock(s);
  pl_hash k;
  memcpy(k.b, hash, 32);
  ptrdiff_t i = ax_hmgeti(s->intern, k);
  pl_val value = i < 0 ? 0 : s->intern[i].value;
  pl_store_unlock(s);
  return value;
}

void pl_store_intern_put(pl_store* s, const uint8_t hash[32], pl_val pin) {
  ax_assume(hash != NULL, "intern_put: NULL hash");
  pl_cell* p = pl_store_require_canonical_pin(s, pin, "intern_put");
  ax_assume(memcmp(hash, pl_pin_hash_bytes(p), 32) == 0,
            "intern_put: hash does not match canonical PIN");
  /* Registration keeps every canonical-PIN index in sync and rejects a
   * second representative for an existing hash. */
  pl_store_register_canonical(s, pin);
}

bool pl_store_backend_put(pl_store* s, const uint8_t hash[32], const uint8_t* b,
                          size_t n) {
  PL_STORE_PROFILE("store.backend.put");
  pl_store_save_lock(s);
  bool ok = s->be.put(s->be.ctx, hash, b, n);
  pl_store_save_unlock(s);
  return ok;
}

bool pl_store_backend_get(pl_store* s, const uint8_t hash[32], uint8_t** out_b,
                          size_t* out_s) {
  PL_STORE_PROFILE("store.backend.get");
  pl_store_save_lock(s);
  bool ok = s->be.get(s->be.ctx, hash, out_b, out_s);
  pl_store_save_unlock(s);
  return ok;
}

bool pl_store_put_root(pl_store* s, const uint8_t hash[32]) {
  PL_STORE_PROFILE("store.root.put");
  pl_store_save_lock(s);
  bool ok = s->be.put_root(s->be.ctx, hash);
  pl_store_save_unlock(s);
  if (ok)
    pl_store_cache_checkpoint();
  return ok;
}

bool pl_store_get_root(pl_store* s, uint8_t hash[32]) {
  PL_STORE_PROFILE("store.root.get");
  pl_store_save_lock(s);
  bool ok = s->be.get_root(s->be.ctx, hash);
  pl_store_save_unlock(s);
  return ok;
}

/* ── Explicit non-persistent lifetime boundary ────────────────────────── */

typedef struct pl_snapshot_entry {
  pl_val key;
  pl_val value;
} pl_snapshot_entry;

static pl_val snapshot_copy(pl_store* s, pl_snapshot_entry** map, pl_val v) {
  if (pl_is_nat63(v))
    return v;

  ptrdiff_t hit = ax_hmgeti(*map, v);
  if (hit >= 0)
    return (*map)[hit].value;

  pl_cell* p = pl_ptr(v);
  if (pl_tag(v) == PL_TAG_PIN && pl_pin_is_proxy(p)) {
    pl_val target = pl_pin_proxy_target(p);
    if (target != 0) {
      ax_assume(pl_tag(target) == PL_TAG_PIN && pl_store_owns(s, target),
                "snapshot: proxy target is not a canonical store PIN");
      ax_hmput(*map, v, target);
      return target;
    }
    if (pl_store_owns(s, v))
      return v; /* an unresolved store proxy is already a closed graph */

    ax_assume(pl_hdr_cells(p[0]) == PL_PIN_CELLS(0),
              "snapshot: heap proxy has an inline PIN table");
    pl_val proxy = pl_store_mk_proxy(s, 0);
    ax_hmput(*map, v, proxy); /* before the body: preserve graph sharing */
    pl_ptr(proxy)[5] = snapshot_copy(s, map, (pl_val)p[5]);
    return proxy;
  }

  if (pl_store_owns(s, v))
    return v; /* all store graphs are closed by construction */

  pl_val out;
  switch (pl_tag(v)) {
  case PL_TAG_NAT: {
    uint32_t used = pl_nat_limbs(p);
    pl_cell* np = pl_store_alloc(s, PL_NAT_CELLS(used));
    np[0] = pl_hdr_make(PL_K_NAT, PL_F_NORMAL, used, PL_NAT_CELLS(used));
    memcpy(np + 1, pl_nat_limb_ptr(p), (size_t)used * sizeof(pl_cell));
    out = pl_make(PL_TAG_NAT, np);
    ax_hmput(*map, v, out);
    return out;
  }
  case PL_TAG_LAW: {
    pl_cell* np = pl_store_alloc(s, PL_LAW_CELLS);
    np[0] = pl_hdr_make(PL_K_LAW, PL_F_NORMAL, 0, PL_LAW_CELLS);
    np[1] = pl_law_arity(p);
    out = pl_make(PL_TAG_LAW, np);
    ax_hmput(*map, v, out);
    np[2] = snapshot_copy(s, map, pl_law_name(p));
    np[3] = snapshot_copy(s, map, pl_law_body(p));
    return out;
  }
  case PL_TAG_APP: {
    uint32_t n = pl_app_n(p);
    pl_cell* np = pl_store_alloc(s, PL_APP_CELLS(n));
    np[0] = pl_hdr_make(PL_K_APP, PL_F_NORMAL, pl_app_need(p), PL_APP_CELLS(n));
    out = pl_make(PL_TAG_APP, np);
    ax_hmput(*map, v, out);
    np[1] = snapshot_copy(s, map, pl_app_head(p));
    for (uint32_t i = 0; i < n; i++)
      np[2 + i] = snapshot_copy(s, map, pl_app_args(p)[i]);
    return out;
  }
  case PL_TAG_PIN:
    ax_abort("snapshot: non-proxy PIN outside the store");
  default:
    ax_abort("snapshot: non-normal value (tag 0x%llx)",
             (unsigned long long)pl_tag(v));
  }
}

pl_val pl_store_snapshot_normal(pl_thread* t, pl_val v) {
  pl_store* s = pl_heap_store(t->heap);
  ax_assume(s != NULL, "snapshot requires a store");
  ax_assume(pl_is_normal(v), "snapshot requires a normal value");
  if (pl_is_nat63(v))
    return v;
  if (pl_tag(v) != PL_TAG_PIN && pl_store_owns(s, v))
    return v;

  pl_snapshot_entry* map = NULL;
  pl_val out = snapshot_copy(s, &map, v);
  ax_hmfree(map);
  ax_assume(pl_is_nat63(out) || pl_store_owns(s, out),
            "snapshot produced a non-store value");
  return out;
}

void pl_store_put_code(pl_store* s, const uint8_t hash[32]) {
  pl_store_save_lock(s);
  pl_store_lock(s);
  if (!s->compiler_f || s->compiler_t == NULL) {
    pl_store_unlock(s);
    pl_store_save_unlock(s);
    return;
  }
  pl_hash key;
  memcpy(key.b, hash, sizeof(key.b));
  ptrdiff_t targets_at = ax_hmgeti(s->code_targets, key);
  if (targets_at < 0) {
    pl_store_unlock(s); /* only canonical LAW PINs execute bytecode */
    pl_store_save_unlock(s);
    return;
  }
  ptrdiff_t cached_at = ax_hmgeti(s->code_cache, key);
  if (cached_at >= 0) {
    pl_code* code = s->code_cache[cached_at].value;
    for (ptrdiff_t i = 0; i < ax_arrlen(s->code_targets[targets_at].value); i++)
      pl_pin_set_code(pl_ptr(s->code_targets[targets_at].value[i]), code);
    pl_store_unlock(s);
    pl_store_save_unlock(s);
    return;
  }
  pl_thread* t = s->compiler_t;
  uint8_t compiler_hash[32];
  memcpy(compiler_hash, s->compiler, 32);
  /* save_mu serializes this single PLAN machine and prevents replacement.
   * The machine's loads and snapshots take mu only around their own arena and
   * registry accesses, so do not retain the general lock while PLAN runs. */
  pl_store_unlock(s);
  PL_STORE_PROFILE("store.compile.law");
  /* Persistent (compiler, law) -> code-row cache.  The compiler is a
   * pure function, so a row computed by any earlier process (or an
   * earlier Install of the same compiler in this one) is THE answer:
   * a hit skips the compiler entirely.  Rows are persisted as ordinary
   * anonymous root pins; the mapping entry stores the row pin's hash
   * under a tagged key, so keys can never dangle across snapshots.
   * Keyed by compiler hash, a new compiler simply opens a fresh
   * keyspace — no invalidation.  save_mu is recursive, so the save /
   * load / backend re-entry below is safe. */
  uint8_t codecache_key[32];
  bool codecache = s->be.get != NULL && s->be.put != NULL;
  if (codecache) {
    uint8_t pre[68];
    memcpy(pre, "plgc", 4);
    memcpy(pre + 4, compiler_hash, 32);
    memcpy(pre + 36, hash, 32);
    ax_sha256(pre, sizeof(pre), codecache_key);
    uint8_t* got = NULL;
    size_t gn = 0;
    if (pl_store_backend_get(s, codecache_key, &got, &gn)) {
      volatile bool served = false;
      if (gn == 32 && (s->be.has == NULL || s->be.has(s->be.ctx, got))) {
        pl_catch cc;
        pl_catch_init(t, &cc);
        if (setjmp(cc.jb) != 0) {
          /* stale or unreadable cache row: recompile below */
          pl_catch_unwind(t, &cc);
        } else {
          pl_val rowpin = pl_store_load(t, got);
          pl_catch_pop(t, &cc);
          pl_cell* rp = pl_as(PL_TAG_PIN, rowpin);
          if (rp != NULL) {
            pl_code* code = pl_bytecode_from_val(pl_pin_body(rp));
            if (code != NULL) {
              pl_store_lock(s);
              ptrdiff_t hit_at = ax_hmgeti(s->code_cache, key);
              if (hit_at >= 0) {
                pl_bytecode_free(code);
                code = s->code_cache[hit_at].value;
              } else {
                ax_arrpush(s->codes, code);
                ax_hmput(s->code_cache, key, code);
              }
              targets_at = ax_hmgeti(s->code_targets, key);
              if (targets_at >= 0)
                for (ptrdiff_t i = 0;
                     i < ax_arrlen(s->code_targets[targets_at].value); i++)
                  pl_pin_set_code(pl_ptr(s->code_targets[targets_at].value[i]),
                                  code);
              pl_store_unlock(s);
            }
            /* an undecodable cached row (unknown-op wrapper) also
             * counts: the compile would reproduce it exactly */
            served = true;
            /* migrate snap-local entries machine-wide so older snaps'
             * work survives their deletion */
            if (s->format == PL_STORE_FORMAT_SILO_V1) {
              uint8_t* have = NULL;
              size_t have_n = 0;
              if (plgc_get(codecache_key, &have, &have_n)) {
                free(have);
              } else {
                pl_silo_reader rd = {0};
                char rerr[192] = {0};
                if (pl_store_silo_open(s, got, &rd, rerr, sizeof(rerr))) {
                  uint8_t* buf = malloc(rd.len);
                  if (buf != NULL && rd.rewind(rd.ctx) &&
                      rd.read(rd.ctx, buf, rd.len))
                    plgc_put(codecache_key, buf, rd.len);
                  free(buf);
                  pl_store_silo_close_reader(&rd);
                }
              }
            }
          }
        }
      }
      free(got);
      if (served) {
        pl_store_save_unlock(s);
        return;
      }
    }
    /* global (snap-independent) layer: an encoded row stream from any
     * earlier snap; subpin resolution against this store validates it */
    uint8_t* gb = NULL;
    size_t gbn = 0;
    if (s->format == PL_STORE_FORMAT_SILO_V1 &&
        plgc_get(codecache_key, &gb, &gbn)) {
      volatile bool served = false;
      pl_catch cc;
      pl_catch_init(t, &cc);
      if (setjmp(cc.jb) != 0) {
        pl_catch_unwind(t, &cc);
      } else {
        char lerr[192] = {0};
        pl_val rowpin = 0;
        bool loaded = pl_store_load_silo_stream(t, s, gb, gbn, &rowpin, lerr,
                                                sizeof(lerr));
        pl_catch_pop(t, &cc);
        pl_cell* rp = loaded ? pl_as(PL_TAG_PIN, rowpin) : NULL;
        if (rp != NULL) {
          pl_code* code = pl_bytecode_from_val(pl_pin_body(rp));
          if (code != NULL) {
            pl_store_lock(s);
            ptrdiff_t hit_at = ax_hmgeti(s->code_cache, key);
            if (hit_at >= 0) {
              pl_bytecode_free(code);
              code = s->code_cache[hit_at].value;
            } else {
              ax_arrpush(s->codes, code);
              ax_hmput(s->code_cache, key, code);
            }
            targets_at = ax_hmgeti(s->code_targets, key);
            if (targets_at >= 0)
              for (ptrdiff_t i = 0;
                   i < ax_arrlen(s->code_targets[targets_at].value); i++)
                pl_pin_set_code(pl_ptr(s->code_targets[targets_at].value[i]),
                                code);
            pl_store_unlock(s);
          }
          served = true;
        }
      }
      free(gb);
      if (served) {
        pl_store_save_unlock(s);
        return;
      }
    }
  }
  /* the compiler is installed PLAN code: a compile failure must not
   * take the runtime down — the law just stays interpreted */
  pl_catch c;
  pl_catch_init(t, &c);
  if (setjmp(c.jb) != 0) {
    pl_catch_unwind(t, &c);
    fprintf(stderr, "bytecode compile raised: %s\n",
            t->exn_msg != NULL ? t->exn_msg : "PLAN exn");
    pl_store_save_unlock(s);
    return;
  }
  struct timespec compile_t0;
  clock_gettime(CLOCK_MONOTONIC, &compile_t0);
  pl_val compiler = pl_store_load(t, compiler_hash);
  pl_val fun = pl_store_load(t, hash);
  pl_val res = pl_apply(t, compiler, fun);
  /* Decoded OP_PUSH_LIT operands are retained in malloc-owned bytecode after
   * this compiler heap moves or is replaced.  Normalize and cross the explicit
   * store-lifetime boundary before the decoder borrows any pl_val pointers. */
  size_t result_at = t->vsp;
  pl_vpush(t, res);
  t->vstack[result_at] = pl_nf(t, t->vstack[result_at]);
  pl_val stable = pl_store_snapshot_normal(t, t->vstack[result_at]);
  t->vsp = result_at;
  pl_catch_pop(t, &c);
  pl_code* code = pl_bytecode_from_val(stable);
  if (code != NULL) {
    /* Attach the cached code to every canonical LAW registered for this hash.
     */
    pl_store_lock(s);
    cached_at = ax_hmgeti(s->code_cache, key);
    if (cached_at >= 0) {
      pl_bytecode_free(code); /* a re-entrant compile won the generation */
      code = s->code_cache[cached_at].value;
    } else {
      ax_arrpush(s->codes, code);
      ax_hmput(s->code_cache, key, code);
    }
    targets_at = ax_hmgeti(s->code_targets, key);
    ax_assume(targets_at >= 0, "compiled law left the hash index");
    for (ptrdiff_t i = 0; i < ax_arrlen(s->code_targets[targets_at].value); i++)
      pl_pin_set_code(pl_ptr(s->code_targets[targets_at].value[i]), code);
    pl_store_unlock(s);
  }
  struct timespec compile_t1;
  clock_gettime(CLOCK_MONOTONIC, &compile_t1);
  uint64_t compile_ns =
      (uint64_t)(compile_t1.tv_sec - compile_t0.tv_sec) * 1000000000u +
      (uint64_t)(compile_t1.tv_nsec - compile_t0.tv_nsec);
  /* Keep the existing 10ms admission threshold: caching also serializes a
   * row pin, retains staging memory, and adds work to the next Save. */
  if (codecache && compile_ns < 10000000u)
    codecache = false;
  if (codecache) {
    /* persist the row as a pin and record the (compiler, law) -> row
     * mapping; cached regardless of whether the row decoded
     * (undecodable rows still skip future compiles).  The save may
     * queue compiles for law literals inside the row — the recursive
     * save_mu and the code_cache early-return make the re-entry
     * safe. */
    size_t rb = t->vsp;
    pl_vpush(t, stable);
    pl_catch cc;
    pl_catch_init(t, &cc);
    if (setjmp(cc.jb) != 0) {
      pl_catch_unwind(t, &cc); /* cache write is best-effort */
    } else {
      t->vstack[rb] = pl_pin(t, t->vstack[rb]);
      pl_catch_pop(t, &cc);
      uint8_t rowhash[32];
      char err[192] = {0};
      if (pl_store_save_pin(s, t->vstack[rb], rowhash, err, sizeof(err))) {
        (void)pl_store_backend_put(s, codecache_key, rowhash, 32);
        if (s->format == PL_STORE_FORMAT_SILO_V1) {
          /* publish the encoded stream machine-wide: read the bytes
           * the save just wrote back out of the pack */
          pl_silo_reader rd = {0};
          char rerr[192] = {0};
          if (pl_store_silo_open(s, rowhash, &rd, rerr, sizeof(rerr))) {
            uint8_t* buf = malloc(rd.len);
            if (buf != NULL && rd.rewind(rd.ctx) &&
                rd.read(rd.ctx, buf, rd.len))
              plgc_put(codecache_key, buf, rd.len);
            free(buf);
            pl_store_silo_close_reader(&rd);
          }
        }
      }
    }
    t->vsp = rb;
  }
  pl_store_save_unlock(s);
}

/*
 * Compile every law pin already interned.  Canonical laws registered before
 * the compiler was installed (the boot prelude and loaded snapshots) would
 * otherwise never get bytecode.  Snapshot the hashes under the registry lock
 * so compilation can run afterward through the save_mu -> mu lock order.
 */
static void pl_store_compile_existing(pl_store* s) {
  PL_STORE_PROFILE("store.compile.existing");
  pl_intern_entry* laws = NULL;
  pl_store_lock(s);
  for (ptrdiff_t i = 0; i < ax_arrlen(s->pins); i++) {
    pl_cell* p = pl_ptr(s->pins[i]);
    if ((pl_hdr_flags(p[0]) & PL_F_PIN_HASHED) == 0 ||
        pl_tag(pl_pin_body(p)) != PL_TAG_LAW)
      continue;
    pl_hash key;
    memcpy(key.b, pl_pin_hash_bytes(p), 32);
    if (ax_hmgeti(laws, key) < 0)
      ax_hmput(laws, key, s->pins[i]);
  }
  pl_store_unlock(s);
  for (ptrdiff_t i = 0; i < ax_hmlen(laws); i++)
    pl_store_put_code(s, laws[i].key.b);
  ax_hmfree(laws);
}

static void pl_store_invalidate_code_locked(pl_store* s) {
  for (ptrdiff_t i = 0; i < ax_arrlen(s->pins); i++)
    pl_pin_set_code(pl_ptr(s->pins[i]), NULL);
  ax_hmfree(s->code_cache);
  s->code_cache = NULL;
}

static void pl_store_free_code(pl_store* s) {
  for (ptrdiff_t i = 0; i < ax_arrlen(s->codes); i++)
    pl_bytecode_free(s->codes[i]);
  ax_arrfree(s->codes);
  s->codes = NULL;
}

bool pl_store_put_compiler(pl_store* s, const uint8_t hash[32]) {
  PL_STORE_PROFILE("store.compiler.install");
  pl_store_save_lock(s);
  pl_store_lock(s);
  bool enabled = hash[0] ? memcmp(hash, hash + 1, 31) != 0 : true;
  if (s->compiler_f == enabled &&
      memcmp(s->compiler, hash, sizeof(s->compiler)) == 0) {
    pl_store_unlock(s);
    pl_store_save_unlock(s);
    return false;
  }

  pl_store_invalidate_code_locked(s);
  if (s->compiler_t != NULL) {
    pl_thread_free(s->compiler_t);
    s->compiler_t = NULL;
  }
  if (s->compiler_h != NULL) {
    pl_heap_free(s->compiler_h);
    s->compiler_h = NULL;
  }
  s->compiler_f = enabled;
  memcpy(s->compiler, hash, 32);
  bool sweep = s->compiler_f;
  if (sweep) {
    /* Collect compiler scratch sooner instead of retaining up to 512 MiB
     * of garbage per semispace. The live heap still grows when necessary. */
    s->compiler_h = pl_heap_new(((size_t)1 << 20), s);
    s->compiler_t = pl_thread_new(s->compiler_h);
  }
  pl_store_unlock(s);
  pl_store_save_unlock(s);
  if (sweep) {
    fprintf(stderr, "store: installing bytecode compiler\r\n");
    pl_store_compile_existing(s);
  }
  return true;
}

/* ── Store-resident value construction (no GC interaction) ─────────────── */

static pl_val st_app(pl_store* s, pl_val head, uint32_t n, const pl_val* args) {
  pl_cell* p = pl_store_alloc(s, PL_APP_CELLS(n));
  uint64_t a = pl_arity(head);
  uint32_t need = (a == 0 || a <= n) ? 0 : (uint32_t)(a - n);
  p[0] = pl_hdr_make(PL_K_APP, PL_F_NORMAL, need, PL_APP_CELLS(n));
  p[1] = head;
  memcpy(p + 2, args, n * sizeof(pl_val));
  return pl_make(PL_TAG_APP, p);
}

pl_val pl_store_mk_proxy(pl_store* s, pl_val body) {
  ax_assume(pl_is_nat63(body) || pl_store_owns(s, body),
            "store proxy body is not closed");
  pl_cell* p = pl_store_alloc(s, PL_PIN_CELLS(0));
  p[0] =
      pl_hdr_make(PL_K_PIN, PL_F_NORMAL | PL_F_PIN_PROXY, 0, PL_PIN_CELLS(0));
  memset(p + 1, 0, 4 * sizeof(pl_cell));
  p[5] = body;
  __atomic_store_n(&p[6], (pl_cell)0, __ATOMIC_RELEASE);
  return pl_make(PL_TAG_PIN, p);
}

void pl_store_register_canonical(pl_store* s, pl_val pin) {
  pl_cell* p = pl_store_require_canonical_pin(s, pin, "register_canonical");

  pl_hash key;
  memcpy(key.b, pl_pin_hash_bytes(p), sizeof(key.b));
  pl_store_lock(s);
  ptrdiff_t at = ax_hmgeti(s->intern, key);
  if (at >= 0) {
    pl_val existing = s->intern[at].value;
    ax_assume(pl_store_owns(s, existing),
              "register_canonical: intern table retained a moving PIN");
    ax_assume(existing == pin,
              "register_canonical: duplicate canonical PIN for one hash");
    pl_store_unlock(s);
    return; /* idempotent registration of the same representative */
  }
  ax_hmput(s->intern, key, pin);
  ax_arrpush(s->pins, pin);
  if (pl_tag((pl_val)p[5]) == PL_TAG_LAW)
    pl_store_index_hashed_law_locked(s, pin);
  pl_store_unlock(s);
}

pl_val pl_store_mk_pin(pl_store* s, const uint8_t* hash, pl_val body,
                       uint32_t npins, const pl_val* subpins) {
  ax_assume(hash != NULL, "pl_store_mk_pin requires a canonical hash");
  ax_assume(npins <= PL_HDR_META_MAX,
            "canonical PIN exceeds the direct PIN-table limit");
  ax_assume(pl_is_nat63(body) || pl_store_owns(s, body),
            "canonical PIN body is not closed");
  pl_cell* p = pl_store_alloc(s, PL_PIN_CELLS(npins));
  p[0] = pl_hdr_make(PL_K_PIN, PL_F_NORMAL | PL_F_PIN_HASHED, npins,
                     PL_PIN_CELLS(npins));
  memcpy(p + 1, hash, 32);
  p[5] = body;
  pl_pin_set_code(p, NULL);
  if (npins > 0)
    memcpy(p + 7, subpins, npins * sizeof(pl_val));
  pl_val pin = pl_make(PL_TAG_PIN, p);
  for (uint32_t i = 0; i < npins; i++)
    ax_assume(pl_store_owns(s, subpins[i]),
              "canonical PIN table retained a moving PIN");
  pl_store_register_canonical(s, pin);
  return pin;
}

bool pl_pin_is_hashed(pl_val pin) {
  pl_cell* p = pl_as(PL_TAG_PIN, pin);
  if (p == NULL)
    return false;
  if (pl_pin_is_proxy(p)) {
    pin = pl_pin_proxy_target(p);
    if (pin == 0)
      return false;
    p = pl_as(PL_TAG_PIN, pin);
    ax_assume(p != NULL && !pl_pin_is_proxy(p),
              "resolved PIN proxy does not target a canonical PIN");
  }
  return (pl_hdr_flags(p[0]) & PL_F_PIN_HASHED) != 0;
}

const uint8_t* pl_pin_hash(pl_val pin) {
  pl_cell* p = pl_as(PL_TAG_PIN, pin);
  ax_assume(p != NULL, "pl_pin_hash on a non-pin");
  if (pl_pin_is_proxy(p)) {
    pin = pl_pin_proxy_target(p);
    if (pin == 0)
      return NULL;
    p = pl_as(PL_TAG_PIN, pin);
    ax_assume(p != NULL && !pl_pin_is_proxy(p),
              "resolved PIN proxy does not target a canonical PIN");
  }
  if ((pl_hdr_flags(p[0]) & PL_F_PIN_HASHED) == 0)
    return NULL;
  return pl_pin_hash_bytes(p);
}

/* ── Lazy Row machinery (op_row): ix0/ix1 body expressions ─────────────── */

/*
 * Element k of a lazy row is the unforced `Ix0 (Ix1^k xs)`.  We encode
 * those redexes as thunks over a 2-slot env [_, prefix] whose body is
 * the law-body expression
 *
 *   (0 (0 P66) (0 (0 "IxK") 1))   ==  apply(P66, apply("IxK", slot1))
 *
 * where P66 is the interned pin of nat 66.  Both expressions are built
 * once, store-resident, at first use.
 */
static pl_val st_ix_expr(pl_store* s, pl_val p66, uint64_t name) {
  pl_val q66 = st_app(s, 0, 1, &p66);    /* (0 P66)        */
  pl_val qname = st_app(s, 0, 1, &name); /* (0 "IxK")      */
  pl_val inner[2] = {qname, 1};          /* (0 (0 n) 1)    */
  pl_val row = st_app(s, 0, 2, inner);
  pl_val outer[2] = {q66, row}; /* (0 (0 P66) ..) */
  return st_app(s, 0, 2, outer);
}

static void pl_store_init_ix(pl_store* s) {
  pl_store_lock(s);
  if (s->ix0_expr != 0)
    goto done;
  pl_val p66 = pl_store_pin_of_nat(s, 66);
  s->ix0_expr = st_ix_expr(s, p66, ax_s3('I', 'x', '0'));
  s->ix1_expr = st_ix_expr(s, p66, ax_s3('I', 'x', '1'));
done:
  pl_store_unlock(s);
}

pl_val pl_store_ix0_expr(pl_store* s) {
  pl_store_init_ix(s);
  return s->ix0_expr;
}

pl_val pl_store_ix1_expr(pl_store* s) {
  pl_store_init_ix(s);
  return s->ix1_expr;
}

/* ── Store lifecycle ───────────────────────────────────────────────────── */

pl_store* pl_store_new(pl_store_backend backend) {
  PL_STORE_PROFILE("store.open");
  pl_store* s = calloc(1, sizeof(*s));
  ax_assume(s != NULL, "oom");
  pthread_mutexattr_t attr;
  ax_assume(pthread_mutexattr_init(&attr) == 0, "pthread_mutexattr_init");
  ax_assume(pthread_mutexattr_settype(&attr, PTHREAD_MUTEX_RECURSIVE) == 0,
            "pthread_mutexattr_settype");
  ax_assume(pthread_mutex_init(&s->save_mu, &attr) == 0,
            "save pthread_mutex_init");
  ax_assume(pthread_mutex_init(&s->mu, &attr) == 0, "pthread_mutex_init");
  pthread_mutexattr_destroy(&attr);
  s->region = ax_arena_create_overcommit(PL_STORE_REGION_BYTES);
  ax_assume(s->region != NULL, "store region reservation failed");
  s->lo = (uint8_t*)s->region;
  s->hi = (uint8_t*)ax_arena_end(s->region);
  ax_assume(((uintptr_t)s->hi & ~PL_ADDR_MASK) == 0,
            "store address exceeds 56 bits");
  s->intern = NULL;
  s->be = backend;
  return s;
}

void pl_store_free(pl_store* s) {
  if (s == NULL)
    return;
  PL_STORE_PROFILE("store.close");
  if (s->compiler_t != NULL)
    pl_thread_free(s->compiler_t);
  if (s->compiler_h != NULL)
    pl_heap_free(s->compiler_h);
  pl_store_invalidate_code_locked(s);
  pl_store_free_code(s);
  for (ptrdiff_t i = 0; i < ax_hmlen(s->code_targets); i++)
    ax_arrfree(s->code_targets[i].value);
  ax_hmfree(s->code_targets);
  ax_hmfree(s->intern);
  ax_arrfree(s->pins);
  ax_arrfree(s->loading);
  if (s->be.close != NULL)
    s->be.close(s->be.ctx);
  free(s->decoded_values);
  ax_arena_destroy(s->region);
  pthread_mutex_destroy(&s->mu);
  pthread_mutex_destroy(&s->save_mu);
  free(s);
}

/* ── Memory backend ────────────────────────────────────────────────────── */

typedef struct mem_entry {
  pl_hash key;
  struct {
    uint8_t* b;
    size_t n;
  } value;
} mem_entry;

typedef struct mem_backend {
  mem_entry* map;
  uint8_t root[32];
  bool has_root;
} mem_backend;

static bool mem_get(void* ctx, const uint8_t hash[32], uint8_t** out_b,
                    size_t* out_s) {
  mem_backend* m = ctx;
  pl_hash k;
  memcpy(k.b, hash, 32);
  ptrdiff_t i = ax_hmgeti(m->map, k);
  if (i < 0)
    return false;
  *out_b = malloc(m->map[i].value.n);
  ax_assume(*out_b != NULL, "oom");
  memcpy(*out_b, m->map[i].value.b, m->map[i].value.n);
  *out_s = m->map[i].value.n;
  return true;
}

static bool mem_put(void* ctx, const uint8_t hash[32], const uint8_t* b,
                    size_t n) {
  mem_backend* m = ctx;
  pl_hash k;
  memcpy(k.b, hash, 32);
  if (ax_hmgeti(m->map, k) >= 0)
    return true;
  uint8_t* copy = malloc(n);
  ax_assume(copy != NULL, "oom");
  memcpy(copy, b, n);
  ax_hmput(m->map, k, ((typeof(m->map[0].value)){copy, n}));
  return true;
}

static bool mem_has(void* ctx, const uint8_t hash[32]) {
  mem_backend* m = ctx;
  pl_hash k;
  memcpy(k.b, hash, 32);
  return ax_hmgeti(m->map, k) >= 0;
}

static bool mem_put_root(void* ctx, const uint8_t hash[32]) {
  mem_backend* m = ctx;
  memcpy(m->root, hash, 32);
  m->has_root = true;
  return true;
}

static bool mem_get_root(void* ctx, uint8_t hash[32]) {
  mem_backend* m = ctx;
  if (!m->has_root)
    return false;
  memcpy(hash, m->root, 32);
  return true;
}

static void mem_close(void* ctx) {
  mem_backend* m = ctx;
  for (ptrdiff_t i = 0; i < ax_hmlen(m->map); i++)
    free(m->map[i].value.b);
  ax_hmfree(m->map);
  free(m);
}

pl_store* pl_store_new_mem(void) {
  mem_backend* m = calloc(1, sizeof(*m));
  ax_assume(m != NULL, "oom");
  return pl_store_new((pl_store_backend){
      .ctx = m,
      .get = mem_get,
      .put = mem_put,
      .has = mem_has,
      .put_root = mem_put_root,
      .get_root = mem_get_root,
      .close = mem_close,
  });
}

/* ── LMDB backend ──────────────────────────────────────────────────────── */

typedef struct lmdb_backend {
  MDB_env* env;
  MDB_dbi dbi;
  pl_staged_blob* staged; /* protected by the owning store's save_mu */
} lmdb_backend;

static const uint8_t pl_root_key[32] = {'r', 'o', 'o', 't'};

static bool lmdb_put_kv(lmdb_backend* l, const uint8_t key[32],
                        const uint8_t* b, size_t n) {
  return pl_staged_put(&l->staged, key, b, n);
}

static bool lmdb_get_kv(lmdb_backend* l, const uint8_t key[32], uint8_t** out_b,
                        size_t* out_s) {
  if (pl_staged_get(l->staged, key, out_b, out_s))
    return true;
  MDB_txn* txn;
  if (mdb_txn_begin(l->env, NULL, MDB_RDONLY, &txn) != 0)
    return false;
  MDB_val k = {32, (void*)key};
  MDB_val v;
  if (mdb_get(txn, l->dbi, &k, &v) != 0) {
    mdb_txn_abort(txn);
    return false;
  }
  *out_b = malloc(v.mv_size);
  ax_assume(*out_b != NULL, "oom");
  memcpy(*out_b, v.mv_data, v.mv_size);
  *out_s = v.mv_size;
  mdb_txn_abort(txn);
  return true;
}

static bool lmdb_get(void* ctx, const uint8_t hash[32], uint8_t** out_b,
                     size_t* out_s) {
  return lmdb_get_kv(ctx, hash, out_b, out_s);
}

static bool lmdb_put(void* ctx, const uint8_t hash[32], const uint8_t* b,
                     size_t n) {
  return lmdb_put_kv(ctx, hash, b, n);
}

static bool lmdb_has(void* ctx, const uint8_t hash[32]) {
  uint8_t* b;
  size_t n;
  if (!lmdb_get_kv(ctx, hash, &b, &n))
    return false;
  free(b);
  return true;
}

static bool lmdb_put_root(void* ctx, const uint8_t hash[32]) {
  lmdb_backend* l = ctx;
  MDB_txn* txn;
  if (mdb_txn_begin(l->env, NULL, 0, &txn) != 0)
    return false;
  for (ptrdiff_t i = 0; i < ax_hmlen(l->staged); i++) {
    MDB_val k = {32, l->staged[i].key.b};
    MDB_val v = {l->staged[i].value.len, l->staged[i].value.bytes};
    if (mdb_put(txn, l->dbi, &k, &v, 0) != 0) {
      mdb_txn_abort(txn);
      return false;
    }
  }
  MDB_val k = {32, (void*)pl_root_key};
  MDB_val v = {32, (void*)hash};
  if (mdb_put(txn, l->dbi, &k, &v, 0) != 0) {
    mdb_txn_abort(txn);
    return false;
  }
  if (mdb_txn_commit(txn) != 0)
    return false;
  pl_staged_clear(&l->staged);
  return true;
}

static bool lmdb_get_root(void* ctx, uint8_t hash[32]) {
  uint8_t* b;
  size_t n;
  if (!lmdb_get_kv(ctx, pl_root_key, &b, &n))
    return false;
  bool ok = n == 32;
  if (ok)
    memcpy(hash, b, 32);
  free(b);
  return ok;
}

static void lmdb_close(void* ctx) {
  lmdb_backend* l = ctx;
  pl_staged_clear(&l->staged);
  mdb_dbi_close(l->env, l->dbi);
  mdb_env_close(l->env);
  free(l);
}

pl_store* pl_store_new_lmdb(const char* path, size_t map_size) {
  PL_STORE_PROFILE("store.lmdb.open");
  lmdb_backend* l = calloc(1, sizeof(*l));
  if (l == NULL)
    return NULL;
  if (mdb_env_create(&l->env) != 0) {
    free(l);
    return NULL;
  }
  if (mdb_env_set_mapsize(l->env, map_size) != 0 ||
      mdb_env_open(l->env, path, 0, 0664) != 0) {
    mdb_env_close(l->env);
    free(l);
    return NULL;
  }
  MDB_txn* txn;
  if (mdb_txn_begin(l->env, NULL, 0, &txn) != 0 ||
      mdb_dbi_open(txn, NULL, MDB_CREATE, &l->dbi) != 0 ||
      mdb_txn_commit(txn) != 0) {
    mdb_env_close(l->env);
    free(l);
    return NULL;
  }
  return pl_store_new((pl_store_backend){
      .ctx = l,
      .get = lmdb_get,
      .put = lmdb_put,
      .has = lmdb_has,
      .put_root = lmdb_put_root,
      .get_root = lmdb_get_root,
      .close = lmdb_close,
  });
}
