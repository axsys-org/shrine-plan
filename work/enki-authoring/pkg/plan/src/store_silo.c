#include "store_internal.h"

#include <errno.h>
#include <fcntl.h>
#include <lmdb.h>
#include <stdarg.h>
#include <stdatomic.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mman.h>
#include <sys/stat.h>
#include <time.h>
#include <unistd.h>
#include <zlib.h>

#include "axsys/ds.h"

#define SILO_INDEX_BYTES  24u
#define PACK_BUFFER_BYTES (64u * 1024u)

typedef struct silo_index_entry {
  pl_hash key;
  struct {
    uint64_t off, len;
  } value;
} silo_index_entry;

typedef struct silo_backend {
  pl_store* store; /* save_mu protects the local staging maps */
  MDB_env* env;
  MDB_dbi objects;
  MDB_dbi meta;
  MDB_dbi codecache; /* side KV: (compiler, law) -> code-row pin hash */
  MDB_dbi roots;     /* root journal: BE u64 seq -> {hash, ns, pack size} */
  int pack_fd;
  bool has_roots; /* absent when inspecting a pre-journal store read-only */
  bool rdonly;
  bool packed; /* revision 3: lossless physical envelopes, unchanged Silo hashes */
  silo_index_entry* staged;
  pl_staged_blob* staged_kv;
} silo_backend;

typedef struct pack_reader {
  void* mapping;
  size_t mapping_len;
  const uint8_t* bytes;
  size_t len;
  size_t pos;
  uint8_t* inflated;
} pack_reader;

struct pl_silo_batch {
  silo_backend* backend;
  MDB_txn* txn;
  uint64_t pack_start;
  uint64_t pack_flushed;
  uint64_t pack_end;
  size_t buffered;
  bool changed;
  bool pack_dirty;
  silo_index_entry* pending;
  uint8_t buffer[PACK_BUFFER_BYTES];
};

static const uint8_t index_magic[8] = {'p', 'i', 'n', 'p', 'a', 'c', 'k', 1};
static const uint8_t format_key[] = "format";
/* Persistence revision 2 changes object identity from canonical text to the
 * SHA-256 of the canonical Silo stream.  Revision-1 stores are rejected. */
static const uint8_t format_value[] = {'S', 'I', 'L', 'O', 3};
static const uint8_t legacy_format[] = {'S', 'I', 'L', 'O', 2};
static const uint8_t root_key[] = "root";

static bool pack_error(char* err, size_t cap, const char* fmt, ...) {
  if (err != NULL && cap != 0) {
    va_list ap;
    va_start(ap, fmt);
    (void)vsnprintf(err, cap, fmt, ap);
    va_end(ap);
  }
  return false;
}

static void index_put64(uint8_t out[8], uint64_t v) {
  for (unsigned i = 0; i < 8; i++)
    out[i] = (uint8_t)(v >> (8u * i));
}

static uint64_t index_get64(const uint8_t in[8]) {
  uint64_t v = 0;
  for (unsigned i = 0; i < 8; i++)
    v |= (uint64_t)in[i] << (8u * i);
  return v;
}

static void index_encode(uint8_t out[SILO_INDEX_BYTES], uint64_t off,
                         uint64_t len) {
  memcpy(out, index_magic, sizeof(index_magic));
  index_put64(out + 8, off);
  index_put64(out + 16, len);
}

static bool index_decode(const MDB_val* value, uint64_t* off, uint64_t* len) {
  if (value->mv_size != SILO_INDEX_BYTES ||
      memcmp(value->mv_data, index_magic, sizeof(index_magic)) != 0)
    return false;
  const uint8_t* b = value->mv_data;
  *off = index_get64(b + 8);
  *len = index_get64(b + 16);
  return true;
}

static bool pack_pwrite_exact(int fd, const uint8_t* bytes, size_t len,
                              uint64_t start) {
  if (start > (uint64_t)INT64_MAX || len > (uint64_t)INT64_MAX - start)
    return false;
  size_t done = 0;
  while (done < len) {
    off_t off = (off_t)(start + done);
    ssize_t n = pwrite(fd, bytes + done, len - done, off);
    if (n < 0) {
      if (errno == EINTR)
        continue;
      return false;
    }
    if (n == 0)
      return false;
    done += (size_t)n;
  }
  return true;
}

/*
 * Durability barrier for pins.pack.
 *
 * What a commit needs here is ordering, not immediate persistence: the
 * pack bytes must reach stable storage no later than the LMDB index entry
 * that points at them.  Losing both to a power cut is a consistent store —
 * the batch simply did not happen — but an index entry addressing pack
 * bytes still sitting in the drive's write cache is a torn one.
 *
 * F_BARRIERFSYNC says exactly that (fsync, then a drive barrier ordering
 * everything before it ahead of everything after) and is the default:
 * ~250us against ~3.2ms for the full cache flush F_FULLFSYNC forces.
 * PL_SILO_FSYNC=full restores that flush; it roughly doubles commit
 * latency, because mdb_txn_commit issues its own F_FULLFSYNC immediately
 * afterwards and a drive flush costs the same whoever asks for it.
 *
 * =data (plain fsync) and =none keep the bytes ordered only by accident:
 * they survive today because LMDB's flush is device-wide and lands right
 * after, so do not pair them with MDB_NOSYNC/MDB_NOMETASYNC on the env —
 * that combination silently gives up the invariant above.  Elsewhere the
 * fsync fallback is itself the ordering primitive.
 *
 * Cached like pl_bytecode_enabled: every thread computes the same answer.
 */
enum pack_sync_mode {
  PACK_SYNC_FULL = 0,
  PACK_SYNC_BARRIER = 1,
  PACK_SYNC_DATA = 2,
  PACK_SYNC_NONE = 3,
};

#ifdef F_BARRIERFSYNC
#define PACK_SYNC_DEFAULT PACK_SYNC_BARRIER
#else
#define PACK_SYNC_DEFAULT PACK_SYNC_DATA
#endif

static int pack_sync(int fd) {
  static _Atomic int mode = -1;
  int m = atomic_load_explicit(&mode, memory_order_relaxed);
  if (m < 0) {
    const char* flag = getenv("PL_SILO_FSYNC");
    m = PACK_SYNC_DEFAULT;
    if (flag != NULL && strcmp(flag, "full") == 0)
      m = PACK_SYNC_FULL;
    else if (flag != NULL && strcmp(flag, "barrier") == 0)
      m = PACK_SYNC_BARRIER;
    else if (flag != NULL && strcmp(flag, "data") == 0)
      m = PACK_SYNC_DATA;
    else if (flag != NULL && strcmp(flag, "none") == 0)
      m = PACK_SYNC_NONE;
    atomic_store_explicit(&mode, m, memory_order_relaxed);
  }
  if (m == PACK_SYNC_NONE)
    return 0;
#ifdef F_BARRIERFSYNC
  if (m == PACK_SYNC_BARRIER) {
    if (fcntl(fd, F_BARRIERFSYNC, 0) == 0)
      return 0;
    if (errno != ENOTSUP && errno != EINVAL)
      return -1;
    /* No barrier on this filesystem.  Fall through to the full flush,
     * which is strictly stronger than what we asked for, and stop asking. */
    m = PACK_SYNC_FULL;
    atomic_store_explicit(&mode, m, memory_order_relaxed);
  }
#endif
#ifdef F_FULLFSYNC
  if (m == PACK_SYNC_FULL)
    return fcntl(fd, F_FULLFSYNC, 0);
#endif
  return fsync(fd);
}

static bool pack_reader_read(void* ctx, uint8_t* bytes, size_t len) {
  pack_reader* r = ctx;
  if (r->pos > r->len || len > r->len - r->pos)
    return false;
  memcpy(bytes, r->bytes + r->pos, len);
  r->pos += len;
  return true;
}

static bool pack_reader_rewind(void* ctx) {
  ((pack_reader*)ctx)->pos = 0;
  return true;
}

/* Copy the location while staging is locked; the pack bytes are immutable
 * after a successful Ice/Save, so readers need not retain that lock. */
static int silo_find(silo_backend* b, const uint8_t hash[32], uint64_t* off,
                     uint64_t* len) {
  pl_store_save_lock(b->store);
  pl_hash h;
  memcpy(h.b, hash, sizeof(h.b));
  ptrdiff_t at = ax_hmgeti(b->staged, h);
  if (at >= 0) {
    *off = b->staged[at].value.off;
    *len = b->staged[at].value.len;
    pl_store_save_unlock(b->store);
    return 0;
  }
  MDB_txn* txn;
  int rc = mdb_txn_begin(b->env, NULL, MDB_RDONLY, &txn);
  if (rc != 0) {
    pl_store_save_unlock(b->store);
    return rc;
  }
  MDB_val key = {.mv_size = 32, .mv_data = (void*)hash};
  MDB_val value;
  rc = mdb_get(txn, b->objects, &key, &value);
  if (rc == 0 && (!index_decode(&value, off, len) || *len == 0))
    rc = EINVAL;
  mdb_txn_abort(txn);
  pl_store_save_unlock(b->store);
  return rc;
}

static bool silo_has(void* ctx, const uint8_t hash[32]) {
  silo_backend* b = ctx;
  uint64_t off = 0, len = 0;
  if (silo_find(b, hash, &off, &len) != 0)
    return false;
  struct stat st;
  return fstat(b->pack_fd, &st) == 0 && st.st_size >= 0 &&
         off <= (uint64_t)st.st_size && len <= (uint64_t)st.st_size - off &&
         off <= (uint64_t)INT64_MAX && len <= (uint64_t)INT64_MAX - off;
}

static bool silo_meta_get(silo_backend* b, const void* key_bytes,
                          size_t key_len, void* out, size_t out_len) {
  MDB_txn* txn;
  if (mdb_txn_begin(b->env, NULL, MDB_RDONLY, &txn) != 0)
    return false;
  MDB_val key = {.mv_size = key_len, .mv_data = (void*)key_bytes};
  MDB_val value;
  int rc = mdb_get(txn, b->meta, &key, &value);
  bool ok = rc == 0 && value.mv_size == out_len;
  if (ok)
    memcpy(out, value.mv_data, out_len);
  mdb_txn_abort(txn);
  return ok;
}

/* Root journal entry: 32-byte root hash, then LE u64 wall-clock ns and LE
 * u64 pins.pack size at publication.  Keys are big-endian u64 sequence
 * numbers so LMDB cursor order is publication order. */
#define SILO_ROOT_ENTRY_BYTES 48u

static void journal_put_seq(uint8_t out[8], uint64_t seq) {
  for (unsigned i = 0; i < 8; i++)
    out[i] = (uint8_t)(seq >> (8u * (7 - i)));
}

static uint64_t journal_get_seq(const uint8_t in[8]) {
  uint64_t v = 0;
  for (unsigned i = 0; i < 8; i++)
    v = (v << 8) | in[i];
  return v;
}

static uint64_t journal_now_ns(void) {
  struct timespec ts;
  if (clock_gettime(CLOCK_REALTIME, &ts) != 0)
    return 0;
  return (uint64_t)ts.tv_sec * 1000000000u + (uint64_t)ts.tv_nsec;
}

/* Append inside the caller's transaction so the journal entry commits
 * exactly when the root it describes does. */
static bool silo_journal_append(silo_backend* b, MDB_txn* txn,
                                const uint8_t hash[32], uint64_t pack_bytes) {
  MDB_cursor* cur;
  if (mdb_cursor_open(txn, b->roots, &cur) != 0)
    return false;
  uint64_t seq = 1;
  MDB_val last_k, last_v;
  int rc = mdb_cursor_get(cur, &last_k, &last_v, MDB_LAST);
  if (rc == 0 && last_k.mv_size == 8)
    seq = journal_get_seq(last_k.mv_data) + 1;
  mdb_cursor_close(cur);
  if (rc != 0 && rc != MDB_NOTFOUND)
    return false;

  uint8_t key_bytes[8];
  journal_put_seq(key_bytes, seq);
  uint8_t entry[SILO_ROOT_ENTRY_BYTES];
  memcpy(entry, hash, 32);
  index_put64(entry + 32, journal_now_ns());
  index_put64(entry + 40, pack_bytes);
  MDB_val key = {.mv_size = sizeof(key_bytes), .mv_data = key_bytes};
  MDB_val value = {.mv_size = sizeof(entry), .mv_data = entry};
  return mdb_put(txn, b->roots, &key, &value, MDB_NOOVERWRITE) == 0;
}

static bool silo_put_root(void* ctx, const uint8_t hash[32]) {
  silo_backend* b = ctx;
  pl_silo_batch* batch = NULL;
  return pl_store_silo_batch_begin(b->store, &batch, NULL, 0) &&
         pl_store_silo_batch_commit(batch, hash, NULL, 0);
}

static bool silo_get_root(void* ctx, uint8_t hash[32]) {
  return silo_meta_get(ctx, root_key, sizeof(root_key) - 1, hash, 32);
}

/* Generic KV over the side `codecache` DBI.  Silo's pin objects only
 * ever move through the validated batch path; this table serves small
 * derived artifacts (the bytecode compile cache) keyed by tagged
 * hashes that cannot collide with anything content-addressed. */
static bool silo_kv_get(void* ctx, const uint8_t hash[32], uint8_t** out_b,
                        size_t* out_s) {
  silo_backend* b = ctx;
  if (pl_staged_get(b->staged_kv, hash, out_b, out_s))
    return true;
  MDB_txn* txn;
  if (mdb_txn_begin(b->env, NULL, MDB_RDONLY, &txn) != 0)
    return false;
  MDB_val k = {.mv_size = 32, .mv_data = (void*)hash};
  MDB_val v;
  if (mdb_get(txn, b->codecache, &k, &v) != 0) {
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

static bool silo_kv_put(void* ctx, const uint8_t hash[32], const uint8_t* bytes,
                        size_t len) {
  silo_backend* b = ctx;
  if (b->rdonly)
    return false;
  return pl_staged_put(&b->staged_kv, hash, bytes, len);
}

static void silo_close(void* ctx) {
  silo_backend* b = ctx;
  /* Unpublished pack bytes remain harmless orphan extents.  Another
   * process may have appended after them, so never truncate on close. */
  ax_hmfree(b->staged);
  pl_staged_clear(&b->staged_kv);
  if (b->pack_fd >= 0)
    (void)close(b->pack_fd);
  mdb_dbi_close(b->env, b->objects);
  mdb_dbi_close(b->env, b->meta);
  mdb_dbi_close(b->env, b->codecache);
  if (b->has_roots)
    mdb_dbi_close(b->env, b->roots);
  mdb_env_close(b->env);
  free(b);
}

static bool batch_flush(pl_silo_batch* batch, char* err, size_t err_cap) {
  if (batch->buffered == 0)
    return true;
  if (!pack_pwrite_exact(batch->backend->pack_fd, batch->buffer,
                         batch->buffered, batch->pack_flushed))
    return pack_error(err, err_cap, "cannot append pins.pack");
  batch->pack_flushed += batch->buffered;
  batch->buffered = 0;
  batch->pack_dirty = true;
  return true;
}

static bool batch_append(pl_silo_batch* batch, const uint8_t* bytes, size_t len,
                         char* err, size_t err_cap) {
  if (len > UINT64_MAX - batch->pack_end ||
      len > (uint64_t)INT64_MAX - batch->pack_end)
    return pack_error(err, err_cap, "pins.pack length overflow");
  size_t left = len;
  while (left != 0) {
    size_t room = sizeof(batch->buffer) - batch->buffered;
    if (room == 0) {
      if (!batch_flush(batch, err, err_cap))
        return false;
      room = sizeof(batch->buffer);
    }
    size_t take = left < room ? left : room;
    memcpy(batch->buffer + batch->buffered, bytes + (len - left), take);
    batch->buffered += take;
    batch->pack_end += take;
    left -= take;
  }
  return true;
}

bool pl_store_silo_batch_begin(pl_store* store, pl_silo_batch** out, char* err,
                               size_t err_cap) {
  if (out == NULL)
    return pack_error(err, err_cap, "invalid Silo batch output");
  *out = NULL;
  if (store == NULL || store->format != PL_STORE_FORMAT_SILO_V1)
    return pack_error(err, err_cap, "store is not a Silo backend");
  if (((silo_backend*)store->be.ctx)->rdonly)
    return pack_error(err, err_cap, "Silo store is read-only");
  pl_silo_batch* batch = calloc(1, sizeof(*batch));
  if (batch == NULL)
    return pack_error(err, err_cap, "out of memory for Silo batch");
  batch->backend = store->be.ctx;
  if (mdb_txn_begin(batch->backend->env, NULL, 0, &batch->txn) != 0) {
    free(batch);
    return pack_error(err, err_cap, "cannot begin Silo save transaction");
  }

  /* The LMDB write transaction is also the cross-process append lock.  It
   * must be held before choosing the pack offset. */
  struct stat st;
  if (fstat(batch->backend->pack_fd, &st) != 0 || st.st_size < 0 ||
      (uint64_t)st.st_size > (uint64_t)INT64_MAX) {
    mdb_txn_abort(batch->txn);
    free(batch);
    return pack_error(err, err_cap, "cannot determine pins.pack length");
  }
  batch->pack_start = (uint64_t)st.st_size;
  batch->pack_flushed = batch->pack_start;
  batch->pack_end = batch->pack_start;
  *out = batch;
  return true;
}

bool pl_store_silo_batch_contains(pl_silo_batch* batch, const uint8_t hash[32],
                                  bool* out, char* err, size_t err_cap) {
  if (batch == NULL || batch->txn == NULL || hash == NULL || out == NULL)
    return pack_error(err, err_cap, "invalid Silo batch query");
  pl_hash hash_key;
  memcpy(hash_key.b, hash, sizeof(hash_key.b));
  ptrdiff_t at = ax_hmgeti(batch->pending, hash_key);
  uint64_t extent = batch->pack_start;
  uint64_t off = 0, len = 0;
  if (at >= 0) {
    off = batch->pending[at].value.off;
    len = batch->pending[at].value.len;
    extent = batch->pack_end;
  } else if ((at = ax_hmgeti(batch->backend->staged, hash_key)) >= 0) {
    off = batch->backend->staged[at].value.off;
    len = batch->backend->staged[at].value.len;
  } else {
    MDB_val key = {.mv_size = 32, .mv_data = (void*)hash};
    MDB_val value;
    int rc = mdb_get(batch->txn, batch->backend->objects, &key, &value);
    if (rc == MDB_NOTFOUND) {
      *out = false;
      return true;
    }
    if (rc != 0)
      return pack_error(err, err_cap, "cannot query Silo object index");
    if (!index_decode(&value, &off, &len))
      return pack_error(err, err_cap, "existing Silo object index is invalid");
  }
  if (len == 0 || off > extent || len > extent - off ||
      off > (uint64_t)INT64_MAX || len > (uint64_t)INT64_MAX - off)
    return pack_error(err, err_cap, "existing Silo object index is invalid");
  *out = true;
  return true;
}

bool pl_store_silo_batch_put(pl_silo_batch* batch, const uint8_t hash[32],
                             const uint8_t* bytes, size_t len, char* err,
                             size_t err_cap) {
  if (batch == NULL || batch->txn == NULL || hash == NULL || bytes == NULL ||
      len == 0)
    return pack_error(err, err_cap, "invalid Silo batch object");
  bool present;
  if (!pl_store_silo_batch_contains(batch, hash, &present, err, err_cap))
    return false;
  if (present)
    return true;

  uint64_t off = batch->pack_end;
  /* Compression belongs to the physical backend, never the canonical stream.
   * Every revision-3 object has an envelope: 0 + raw bytes, or 1 + LE logical
   * length + zlib bytes. Old engines reject revision 3 before opening objects. */
  uint8_t header[9] = {0};
  uint8_t* compressed = NULL;
  const uint8_t* payload = bytes;
  size_t payload_len = len, header_len = 1;
  if (len >= 1024 && len <= 128u * 1024u * 1024u) {
    uLongf capacity = compressBound((uLong)len);
    compressed = malloc(capacity);
    if (compressed != NULL &&
        compress2(compressed, &capacity, bytes, (uLong)len, Z_BEST_SPEED) == Z_OK &&
        capacity + 9 < len - len / 8) {
      header[0] = 1;
      index_put64(header + 1, len);
      header_len = sizeof(header);
      payload = compressed;
      payload_len = capacity;
    }
  }
  bool appended = batch_append(batch, header, header_len, err, err_cap) &&
                  batch_append(batch, payload, payload_len, err, err_cap);
  free(compressed);
  if (!appended) return false;
  silo_index_entry entry = {.value = {.off = off, .len = header_len + payload_len}};
  memcpy(entry.key.b, hash, sizeof(entry.key.b));
  ax_hmput(batch->pending, entry.key, entry.value);
  batch->changed = true;
  return true;
}

void pl_store_silo_batch_abort(pl_silo_batch* batch) {
  if (batch == NULL)
    return;
  if (batch->txn != NULL) {
    /* The active LMDB write transaction still owns the cross-process append
     * lock, so no cooperating writer can have appended behind this batch.
     * Best-effort rollback prevents retryable failures from accumulating a
     * full orphan closure; a failed truncate remains safe as an orphan tail. */
    if (batch->pack_end > batch->pack_start &&
        ftruncate(batch->backend->pack_fd, (off_t)batch->pack_start) != 0) {
      /* glibc marks ftruncate warn-unused-result; the failure is
       * acceptable here per the comment above */
    }
    mdb_txn_abort(batch->txn);
  }
  ax_hmfree(batch->pending);
  free(batch);
}

static bool batch_index(pl_silo_batch* batch, silo_index_entry* entries,
                        char* err, size_t err_cap) {
  for (ptrdiff_t i = 0; i < ax_hmlen(entries); i++) {
    uint64_t off = entries[i].value.off, len = entries[i].value.len;
    if (len == 0 || off > batch->pack_end || len > batch->pack_end - off)
      return pack_error(err, err_cap, "staged object is outside pins.pack");
    uint8_t index[SILO_INDEX_BYTES];
    index_encode(index, off, len);
    MDB_val key = {.mv_size = 32, .mv_data = entries[i].key.b};
    MDB_val value = {.mv_size = sizeof(index), .mv_data = index};
    int rc = mdb_put(batch->txn, batch->backend->objects, &key, &value,
                     MDB_NOOVERWRITE);
    if (rc == MDB_KEYEXIST) {
      /* Another writer may already have saved the same object. */
      if (!index_decode(&value, &off, &len) || len == 0 ||
          off > batch->pack_start || len > batch->pack_start - off)
        return pack_error(err, err_cap,
                          "existing Silo object index is invalid");
    } else if (rc != 0) {
      return pack_error(err, err_cap, "cannot publish Silo object index");
    }
  }
  return true;
}

bool pl_store_silo_batch_commit(pl_silo_batch* batch,
                                const uint8_t root_hash[32], char* err,
                                size_t err_cap) {
  /* Ice only stages offsets: retain the pack append, then abort the empty
   * LMDB transaction used as a cross-process append lock.  Save atomically
   * publishes all staged offsets/cache writes and the requested root. */
  if (batch == NULL || batch->txn == NULL) {
    pl_store_silo_batch_abort(batch);
    return pack_error(err, err_cap, "invalid Silo batch commit");
  }
  silo_backend* b = batch->backend;
  if (root_hash == NULL) {
    if (!batch_flush(batch, err, err_cap)) {
      pl_store_silo_batch_abort(batch);
      return false;
    }
    for (ptrdiff_t i = 0; i < ax_hmlen(batch->pending); i++)
      ax_hmput(b->staged, batch->pending[i].key, batch->pending[i].value);
    mdb_txn_abort(batch->txn);
    batch->txn = NULL; /* keep the successfully staged pack extents */
    pl_store_silo_batch_abort(batch);
    return true;
  }
  bool root_changed = false;
  MDB_val root_k = {.mv_size = sizeof(root_key) - 1,
                    .mv_data = (void*)root_key};
  if (root_hash != NULL) {
    bool root_present = false;
    if (!pl_store_silo_batch_contains(batch, root_hash, &root_present, err,
                                      err_cap)) {
      pl_store_silo_batch_abort(batch);
      return false;
    }
    if (!root_present) {
      pl_store_silo_batch_abort(batch);
      return pack_error(err, err_cap, "Silo root object is not indexed");
    }

    MDB_val old_root;
    int root_rc = mdb_get(batch->txn, batch->backend->meta, &root_k, &old_root);
    root_changed =
        root_rc == MDB_NOTFOUND ||
        (root_rc == 0 && (old_root.mv_size != 32 ||
                          memcmp(old_root.mv_data, root_hash, 32) != 0));
    if (root_rc != 0 && root_rc != MDB_NOTFOUND) {
      pl_store_silo_batch_abort(batch);
      return pack_error(err, err_cap, "cannot query Silo root");
    }
  }

  bool staged = ax_hmlen(b->staged) != 0;
  bool staged_kv = ax_hmlen(b->staged_kv) != 0;
  if (!batch->changed && !staged && !staged_kv && !root_changed) {
    pl_store_silo_batch_abort(batch);
    return true;
  }
  if (!batch_flush(batch, err, err_cap)) {
    pl_store_silo_batch_abort(batch);
    return false;
  }
  if (batch->pack_dirty || staged) {
    if (pack_sync(batch->backend->pack_fd) != 0) {
      pl_store_silo_batch_abort(batch);
      return pack_error(err, err_cap, "cannot sync pins.pack");
    }
  }
  if (!batch_index(batch, b->staged, err, err_cap) ||
      !batch_index(batch, batch->pending, err, err_cap)) {
    pl_store_silo_batch_abort(batch);
    return false;
  }
  for (ptrdiff_t i = 0; i < ax_hmlen(b->staged_kv); i++) {
    MDB_val key = {.mv_size = 32, .mv_data = b->staged_kv[i].key.b};
    MDB_val value = {.mv_size = b->staged_kv[i].value.len,
                     .mv_data = b->staged_kv[i].value.bytes};
    if (mdb_put(batch->txn, b->codecache, &key, &value, 0) != 0) {
      pl_store_silo_batch_abort(batch);
      return pack_error(err, err_cap, "cannot publish staged cache entry");
    }
  }
  if (root_changed) {
    MDB_val root_v = {.mv_size = 32, .mv_data = (void*)root_hash};
    if (mdb_put(batch->txn, batch->backend->meta, &root_k, &root_v, 0) != 0 ||
        !silo_journal_append(batch->backend, batch->txn, root_hash,
                             batch->pack_end)) {
      pl_store_silo_batch_abort(batch);
      return pack_error(err, err_cap, "cannot publish Silo root");
    }
  }

  MDB_txn* txn = batch->txn;
  batch->txn = NULL; /* mdb_txn_commit consumes the handle on every result. */
  int rc = mdb_txn_commit(txn);
  if (rc == 0) {
    ax_hmfree(b->staged);
    b->staged = NULL;
    pl_staged_clear(&b->staged_kv);
  }
  ax_hmfree(batch->pending);
  free(batch);
  return rc == 0
             ? true
             : pack_error(err, err_cap, "cannot commit Silo save transaction");
}

bool pl_store_silo_open(pl_store* store, const uint8_t hash[32],
                        pl_silo_reader* out, char* err, size_t err_cap) {
  if (store == NULL || store->format != PL_STORE_FORMAT_SILO_V1 || out == NULL)
    return pack_error(err, err_cap, "store is not a Silo backend");
  silo_backend* b = store->be.ctx;
  uint64_t off = 0, len = 0;
  int rc = silo_find(b, hash, &off, &len);
  if (rc == MDB_NOTFOUND)
    return pack_error(err, err_cap, "missing Silo pin");
  if (rc != 0)
    return pack_error(err, err_cap, "invalid Silo object index");
  struct stat st;
  if (fstat(b->pack_fd, &st) != 0 || st.st_size < 0 ||
      off > (uint64_t)st.st_size || len > (uint64_t)st.st_size - off ||
      off > (uint64_t)INT64_MAX || len > (uint64_t)INT64_MAX - off)
    return pack_error(err, err_cap, "Silo object index is outside pins.pack");
  /* The page size is a process constant: ask the kernel once, not per pin. */
  static _Atomic long page_size_cache;
  long page_size = atomic_load_explicit(&page_size_cache, memory_order_relaxed);
  if (page_size <= 0) {
    page_size = sysconf(_SC_PAGESIZE);
    if (page_size <= 0)
      return pack_error(err, err_cap, "cannot determine system page size");
    atomic_store_explicit(&page_size_cache, page_size, memory_order_relaxed);
  }
  uint64_t page = (uint64_t)page_size;
  uint64_t map_off = off - off % page;
  uint64_t delta = off - map_off;
  if (len > SIZE_MAX || delta > SIZE_MAX - (size_t)len)
    return pack_error(err, err_cap, "Silo object is too large to map");
  size_t mapping_len = (size_t)delta + (size_t)len;
  pack_reader* pr = calloc(1, sizeof(*pr));
  if (pr == NULL)
    return pack_error(err, err_cap, "out of memory for Silo reader");
  void* mapping = mmap(NULL, mapping_len, PROT_READ, MAP_SHARED, b->pack_fd,
                       (off_t)map_off);
  if (mapping == MAP_FAILED) {
    free(pr);
    return pack_error(err, err_cap, "cannot map Silo object");
  }
  *pr = (pack_reader){.mapping = mapping,
                      .mapping_len = mapping_len,
                      .bytes = (const uint8_t*)mapping + (size_t)delta,
                      .len = (size_t)len};
  if (b->packed) {
    if (pr->len < 2 || pr->bytes[0] > 1) goto bad_envelope;
    if (pr->bytes[0] == 0) {
      pr->bytes++;
      pr->len--;
    } else {
      if (pr->len <= 9) goto bad_envelope;
      uint64_t logical = index_get64(pr->bytes + 1);
      if (!logical || logical > 128u * 1024u * 1024u) goto bad_envelope;
      pr->inflated = malloc((size_t)logical);
      if (pr->inflated == NULL) goto bad_envelope;
      uLongf output_len = logical;
      uLong input_len = pr->len - 9;
      if (uncompress2(pr->inflated, &output_len, pr->bytes + 9, &input_len) != Z_OK ||
          output_len != logical || input_len != pr->len - 9) goto bad_envelope;
      pr->bytes = pr->inflated;
      pr->len = logical;
    }
  }
  *out = (pl_silo_reader){.ctx = pr,
                          .read = pack_reader_read,
                          .rewind = pack_reader_rewind,
                          .len = pr->len};
  return true;
bad_envelope:
  munmap(pr->mapping, pr->mapping_len);
  free(pr->inflated);
  free(pr);
  return pack_error(err, err_cap, "invalid compressed Silo envelope");
}

void pl_store_silo_close_reader(pl_silo_reader* r) {
  if (r == NULL)
    return;
  pack_reader* pr = r->ctx;
  if (pr != NULL) {
    (void)munmap(pr->mapping, pr->mapping_len);
    free(pr->inflated);
    free(pr);
  }
  memset(r, 0, sizeof(*r));
}

pl_store* pl_store_new_silo(const char* path, size_t map_size) {
  silo_backend* b = calloc(1, sizeof(*b));
  if (b == NULL)
    return NULL;
  b->pack_fd = -1;
  if (mdb_env_create(&b->env) != 0 || mdb_env_set_maxdbs(b->env, 4) != 0 ||
      mdb_env_set_mapsize(b->env, map_size) != 0 ||
      mdb_env_open(b->env, path, 0, 0664) != 0)
    goto fail_env;

  char pack_path[4096];
  int path_len = snprintf(pack_path, sizeof(pack_path), "%s/pins.pack", path);
  if (path_len < 0 || (size_t)path_len >= sizeof(pack_path))
    goto fail_env;
  b->pack_fd = open(pack_path, O_RDWR | O_CREAT, 0664);
  if (b->pack_fd < 0)
    goto fail_env;

  MDB_txn* txn;
  if (mdb_txn_begin(b->env, NULL, 0, &txn) != 0)
    goto fail_pack;
  if (mdb_dbi_open(txn, "objects", MDB_CREATE, &b->objects) != 0 ||
      mdb_dbi_open(txn, "meta", MDB_CREATE, &b->meta) != 0 ||
      mdb_dbi_open(txn, "codecache", MDB_CREATE, &b->codecache) != 0 ||
      mdb_dbi_open(txn, "roots", MDB_CREATE, &b->roots) != 0) {
    mdb_txn_abort(txn);
    goto fail_pack;
  }
  b->has_roots = true;
  b->packed = true;
  MDB_val fkey = {.mv_size = sizeof(format_key) - 1,
                  .mv_data = (void*)format_key};
  MDB_val found;
  int rc = mdb_get(txn, b->meta, &fkey, &found);
  if (rc == MDB_NOTFOUND) {
    MDB_val fval = {.mv_size = sizeof(format_value),
                    .mv_data = (void*)format_value};
    rc = mdb_put(txn, b->meta, &fkey, &fval, 0);
  } else if (rc == 0 &&
             (found.mv_size != sizeof(format_value) ||
              memcmp(found.mv_data, format_value, sizeof(format_value)) != 0)) {
    rc = EINVAL;
  }
  if (rc != 0) {
    mdb_txn_abort(txn);
    goto fail_pack;
  }
  if (mdb_txn_commit(txn) != 0)
    goto fail_pack;

  pl_store* store = pl_store_new((pl_store_backend){
      .ctx = b,
      .get = silo_kv_get,
      .put = silo_kv_put,
      .has = silo_has,
      .put_root = silo_put_root,
      .get_root = silo_get_root,
      .close = silo_close,
  });
  store->format = PL_STORE_FORMAT_SILO_V1;
  b->store = store;
  return store;

fail_pack:
  if (b->pack_fd >= 0)
    (void)close(b->pack_fd);
fail_env:
  if (b->env != NULL)
    mdb_env_close(b->env);
  free(b);
  return NULL;
}

pl_store* pl_store_new_silo_ro(const char* path, size_t map_size) {
  silo_backend* b = calloc(1, sizeof(*b));
  if (b == NULL)
    return NULL;
  b->pack_fd = -1;
  b->rdonly = true;
  if (mdb_env_create(&b->env) != 0 || mdb_env_set_maxdbs(b->env, 4) != 0 ||
      mdb_env_set_mapsize(b->env, map_size) != 0 ||
      mdb_env_open(b->env, path, MDB_RDONLY, 0664) != 0)
    goto fail_env;

  char pack_path[4096];
  int path_len = snprintf(pack_path, sizeof(pack_path), "%s/pins.pack", path);
  if (path_len < 0 || (size_t)path_len >= sizeof(pack_path))
    goto fail_env;
  b->pack_fd = open(pack_path, O_RDONLY);
  if (b->pack_fd < 0)
    goto fail_env;

  MDB_txn* txn;
  if (mdb_txn_begin(b->env, NULL, MDB_RDONLY, &txn) != 0)
    goto fail_pack;
  if (mdb_dbi_open(txn, "objects", 0, &b->objects) != 0 ||
      mdb_dbi_open(txn, "meta", 0, &b->meta) != 0 ||
      mdb_dbi_open(txn, "codecache", 0, &b->codecache) != 0) {
    mdb_txn_abort(txn);
    goto fail_pack;
  }
  /* Pre-journal stores lack the roots DBI; inspect them without history. */
  b->has_roots = mdb_dbi_open(txn, "roots", 0, &b->roots) == 0;
  MDB_val fkey = {.mv_size = sizeof(format_key) - 1,
                  .mv_data = (void*)format_key};
  MDB_val found;
  if (mdb_get(txn, b->meta, &fkey, &found) != 0 ||
      found.mv_size != sizeof(format_value) ||
      (memcmp(found.mv_data, format_value, sizeof(format_value)) != 0 &&
       memcmp(found.mv_data, legacy_format, sizeof(legacy_format)) != 0)) {
    mdb_txn_abort(txn);
    goto fail_pack;
  }
  b->packed = memcmp(found.mv_data, format_value, sizeof(format_value)) == 0;
  /* Commit rather than abort: DBI handles opened in an aborted read
   * transaction must not be reused. */
  if (mdb_txn_commit(txn) != 0)
    goto fail_pack;

  pl_store* store = pl_store_new((pl_store_backend){
      .ctx = b,
      .get = silo_kv_get,
      .put = silo_kv_put,
      .has = silo_has,
      .put_root = silo_put_root,
      .get_root = silo_get_root,
      .close = silo_close,
  });
  store->format = PL_STORE_FORMAT_SILO_V1;
  b->store = store;
  return store;

fail_pack:
  if (b->pack_fd >= 0)
    (void)close(b->pack_fd);
fail_env:
  if (b->env != NULL)
    mdb_env_close(b->env);
  free(b);
  return NULL;
}

uint64_t pl_store_root_log_head(pl_store* store) {
  if (store == NULL || store->format != PL_STORE_FORMAT_SILO_V1)
    return 0;
  silo_backend* b = store->be.ctx;
  if (!b->has_roots)
    return 0;
  MDB_txn* txn;
  if (mdb_txn_begin(b->env, NULL, MDB_RDONLY, &txn) != 0)
    return 0;
  uint64_t seq = 0;
  MDB_cursor* cur;
  if (mdb_cursor_open(txn, b->roots, &cur) == 0) {
    MDB_val key, value;
    if (mdb_cursor_get(cur, &key, &value, MDB_LAST) == 0 && key.mv_size == 8)
      seq = journal_get_seq(key.mv_data);
    mdb_cursor_close(cur);
  }
  mdb_txn_abort(txn);
  return seq;
}

size_t pl_store_root_log(pl_store* store, uint64_t from,
                         pl_store_root_entry* out, size_t cap) {
  if (store == NULL || store->format != PL_STORE_FORMAT_SILO_V1 || out == NULL)
    return 0;
  silo_backend* b = store->be.ctx;
  if (!b->has_roots)
    return 0;
  MDB_txn* txn;
  if (mdb_txn_begin(b->env, NULL, MDB_RDONLY, &txn) != 0)
    return 0;
  size_t n = 0;
  MDB_cursor* cur;
  if (mdb_cursor_open(txn, b->roots, &cur) == 0) {
    uint8_t key_bytes[8];
    journal_put_seq(key_bytes, from);
    MDB_val key = {.mv_size = sizeof(key_bytes), .mv_data = key_bytes};
    MDB_val value;
    int rc = mdb_cursor_get(cur, &key, &value, MDB_SET_RANGE);
    while (rc == 0 && n < cap) {
      if (key.mv_size == 8 && value.mv_size == SILO_ROOT_ENTRY_BYTES) {
        const uint8_t* vb = value.mv_data;
        out[n].seq = journal_get_seq(key.mv_data);
        memcpy(out[n].hash, vb, 32);
        out[n].unix_ns = index_get64(vb + 32);
        out[n].pack_bytes = index_get64(vb + 40);
        n++;
      }
      rc = mdb_cursor_get(cur, &key, &value, MDB_NEXT);
    }
    mdb_cursor_close(cur);
  }
  mdb_txn_abort(txn);
  return n;
}

size_t pl_store_silo_objects(pl_store* store, pl_store_silo_object_fn fn,
                             void* ctx) {
  if (store == NULL || store->format != PL_STORE_FORMAT_SILO_V1 || fn == NULL)
    return 0;
  silo_backend* b = store->be.ctx;
  MDB_txn* txn;
  if (mdb_txn_begin(b->env, NULL, MDB_RDONLY, &txn) != 0)
    return 0;
  size_t n = 0;
  MDB_cursor* cur;
  if (mdb_cursor_open(txn, b->objects, &cur) == 0) {
    MDB_val key, value;
    int rc = mdb_cursor_get(cur, &key, &value, MDB_FIRST);
    while (rc == 0) {
      uint64_t off = 0, len = 0;
      if (key.mv_size == 32 && index_decode(&value, &off, &len)) {
        fn(ctx, key.mv_data, off, len);
        n++;
      }
      rc = mdb_cursor_get(cur, &key, &value, MDB_NEXT);
    }
    mdb_cursor_close(cur);
  }
  mdb_txn_abort(txn);
  return n;
}

bool pl_store_silo_object_info(pl_store* store, const uint8_t hash[32],
                               uint64_t* out_len, pl_hash** out_subpins,
                               size_t* out_nsub, char* err, size_t err_cap) {
  if (out_len == NULL || out_subpins == NULL || out_nsub == NULL)
    return pack_error(err, err_cap, "invalid Silo object info query");
  *out_len = 0;
  *out_subpins = NULL;
  *out_nsub = 0;
  pl_silo_reader r;
  if (!pl_store_silo_open(store, hash, &r, err, err_cap))
    return false;
  pl_silo_scan scan = {0};
  bool ok = pl_silo_scan_stream(&r, true, &scan, err, err_cap);
  if (ok) {
    *out_len = r.len;
    *out_nsub = scan.pin_count;
    if (scan.pin_count != 0) {
      *out_subpins = malloc(scan.pin_count * sizeof(pl_hash));
      if (*out_subpins == NULL) {
        ok = pack_error(err, err_cap, "out of memory for Silo subpin list");
        *out_nsub = 0;
      } else {
        memcpy(*out_subpins, scan.pins, scan.pin_count * sizeof(pl_hash));
      }
    }
  }
  pl_silo_scan_free(&scan);
  pl_store_silo_close_reader(&r);
  return ok;
}
