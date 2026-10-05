#include <stdlib.h>
#include <stdio.h>
#include <stdarg.h>
#include <string.h>

#include "axsys/allocator.h"
#include "axsys/assume.h"
#include "axsys/sha256.h"
#include "axsys/ds.h"
#include "internal.h"
#include "plan/build.h"
#include "plan/canon.h"
#include "plan/nat.h"
#include "plan/store.h"
#include "store_internal.h"

/*
 * Pinning is deliberately cheap: pl_pin only forces the value to WHNF and
 * wraps it in a moving-heap proxy. Save/Ice discover the reachable proxy
 * closure, encode it in dependency order, and build or reuse a canonical DAG.
 * Ice publishes targets after successful store-local staging; Save publishes
 * after the durable commit. Failed operations remain retryable.
 *
 * The persistence backend keeps a binary rendering (below), because
 * rehydration must not depend on the enki-layer assembler; it is keyed
 * by the selected serialization hash.
 *
 * Backend byte format (version 1):
 *   u8  version
 *   u64 nsub                       (LE)
 *   32B * nsub                     (sub-pin hashes, first-occurrence LTR)
 *   body:
 *     'n' u64 len, bytes           (nat, little-endian, trimmed)
 *     'p' u32 index                (reference to sub-pin)
 *     'l' u64 arity, name, body    (law)
 *     'a' u32 nargs, head, args…   (app)
 */

#define PL_CANON_VERSION 1u

typedef struct pin_idx_entry {
  pl_val key;
  uint32_t value;
} pin_idx_entry;

typedef struct canon_ctx {
  uint8_t* buf;       /* stb_ds array */
  pl_val* subpins;    /* stb_ds array, first-occurrence order */
  pin_idx_entry* idx; /* stb_ds hashmap: pin val -> index */
} canon_ctx;

static void cput8(canon_ctx* c, uint8_t b) {
  ax_arrpush(c->buf, b);
}

static void cput32(canon_ctx* c, uint32_t v) {
  for (int i = 0; i < 4; i++)
    ax_arrpush(c->buf, (uint8_t)(v >> (8 * i)));
}

static void cput64(canon_ctx* c, uint64_t v) {
  for (int i = 0; i < 8; i++)
    ax_arrpush(c->buf, (uint8_t)(v >> (8 * i)));
}

/* Collect sub-pins, shallow, first-occurrence, left-to-right. */
static void collect_subpins(canon_ctx* c, pl_val v) {
  if (pl_is_nat(v))
    return;
  pl_cell* p = pl_ptr(v);
  switch (pl_tag(v)) {
  case PL_TAG_PIN:
    if (ax_hmgeti(c->idx, v) < 0) {
      ax_hmput(c->idx, v, (uint32_t)ax_arrlen(c->subpins));
      ax_arrpush(c->subpins, v);
    }
    return;
  case PL_TAG_LAW:
    collect_subpins(c, pl_law_name(p));
    collect_subpins(c, pl_law_body(p));
    return;
  case PL_TAG_APP: {
    collect_subpins(c, pl_app_head(p));
    uint32_t n = pl_app_n(p);
    for (uint32_t i = 0; i < n; i++)
      collect_subpins(c, pl_app_args(p)[i]);
    return;
  }
  default:
    ax_abort("collect_subpins: non-normal value (tag 0x%llx)",
             (unsigned long long)pl_tag(v));
  }
}

static void serialize(canon_ctx* c, pl_val v) {
  if (pl_is_nat(v)) {
    size_t len = pl_nat_byte_len(v);
    cput8(c, 'n');
    cput64(c, len);
    for (size_t i = 0; i < len; i++)
      cput8(c, pl_nat_byte_at(v, i));
    return;
  }
  pl_cell* p = pl_ptr(v);
  switch (pl_tag(v)) {
  case PL_TAG_PIN: {
    ptrdiff_t i = ax_hmgeti(c->idx, v);
    ax_assume(i >= 0, "serialize: pin not collected");
    cput8(c, 'p');
    cput32(c, c->idx[i].value);
    return;
  }
  case PL_TAG_LAW:
    cput8(c, 'l');
    cput64(c, pl_law_arity(p));
    serialize(c, pl_law_name(p));
    serialize(c, pl_law_body(p));
    return;
  case PL_TAG_APP: {
    uint32_t n = pl_app_n(p);
    cput8(c, 'a');
    cput32(c, n);
    serialize(c, pl_app_head(p));
    for (uint32_t i = 0; i < n; i++)
      serialize(c, pl_app_args(p)[i]);
    return;
  }
  default:
    ax_abort("serialize: non-normal value");
  }
}

/* ── Save-time promotion ───────────────────────────────────────────────── */

typedef struct copy_entry {
  pl_val key;
  pl_val value;
} copy_entry;

typedef struct save_visit {
  pl_val key;
  uint8_t value; /* 1 = active, 2 = complete */
} save_visit;

typedef struct save_item_index {
  pl_val key;
  size_t value;
} save_item_index;

typedef struct save_canonical {
  pl_hash key;
  pl_val value;
} save_canonical;

typedef struct save_item {
  pl_val source;
  pl_val* direct; /* pointer-unique, first-occurrence direct PINs */
  pl_val* table;  /* direct PINs deduplicated by prepared hash */
  pl_hash hash;
  pl_val canonical;
  bool hash_ready;
} save_item;

typedef struct save_ctx {
  pl_store* store;
  pl_silo_batch* batch;
  save_visit* visit;
  save_item_index* index;
  save_item* items;          /* dependency postorder */
  save_canonical* canonical; /* hash -> prepared/store representative */
  pl_intern_entry* compile;  /* unique finalized LAW hashes */
  pl_cell** transient;       /* Save-local Legacy canonicalization cells */
  char* err;
  size_t err_cap;
  bool no_root; /* stage objects only; leave the store root untouched */
} save_ctx;

static bool save_error(save_ctx* c, const char* fmt, ...) {
  if (c->err != NULL && c->err_cap != 0) {
    va_list ap;
    va_start(ap, fmt);
    (void)vsnprintf(c->err, c->err_cap, fmt, ap);
    va_end(ap);
  }
  return false;
}

static pl_val save_effective_pin(pl_val pin) {
  pl_cell* p = pl_as(PL_TAG_PIN, pin);
  if (p != NULL && pl_pin_is_proxy(p)) {
    pl_val target = pl_pin_proxy_target(p);
    if (target != 0)
      return target;
  }
  return pin;
}

static bool save_collect_direct(save_ctx* c, pl_val v, pl_val** out,
                                pin_idx_entry** seen, uint32_t depth) {
  if (depth > PL_SILO_MAX_DEPTH)
    return save_error(c, "PIN body exceeds depth %u", PL_SILO_MAX_DEPTH);
  if (pl_is_nat(v))
    return true;
  pl_cell* p = pl_ptr(v);
  switch (pl_tag(v)) {
  case PL_TAG_PIN:
    if (ax_hmgeti(*seen, v) < 0) {
      ax_hmput(*seen, v, (uint32_t)ax_arrlen(*out));
      ax_arrpush(*out, v);
    }
    return true;
  case PL_TAG_LAW:
    return save_collect_direct(c, pl_law_name(p), out, seen, depth + 1) &&
           save_collect_direct(c, pl_law_body(p), out, seen, depth + 1);
  case PL_TAG_APP: {
    if (!save_collect_direct(c, pl_app_head(p), out, seen, depth + 1))
      return false;
    uint32_t n = pl_app_n(p);
    for (uint32_t i = 0; i < n; i++)
      if (!save_collect_direct(c, pl_app_args(p)[i], out, seen, depth + 1))
        return false;
    return true;
  }
  default:
    return save_error(c, "Save encountered non-normal tag 0x%llx",
                      (unsigned long long)pl_tag(v));
  }
}

static bool save_discover_pin(save_ctx* c, pl_val input, uint32_t depth) {
  if (depth > PL_SILO_MAX_DEPTH)
    return save_error(c, "PIN closure exceeds depth %u", PL_SILO_MAX_DEPTH);
  pl_val pin = save_effective_pin(input);
  pl_cell* p = pl_as(PL_TAG_PIN, pin);
  if (p == NULL)
    return save_error(c, "Save encountered a non-PIN dependency");
  if (!pl_pin_is_proxy(p)) {
    if (!pl_store_owns(c->store, pin) || pl_pin_hash(pin) == NULL)
      return save_error(c, "Save encountered a noncanonical PIN");
    /* Canonical PINs are complete closure boundaries, either persisted or
     * staged in this store. Save checkpoints all staging, so their hashes
     * suffice without rediscovering the already encoded graph. */
    return true;
  }

  ptrdiff_t at = ax_hmgeti(c->visit, pin);
  if (at >= 0) {
    if (c->visit[at].value == 1)
      return save_error(c, "cyclic PIN dependency");
    return true;
  }
  ax_hmput(c->visit, pin, 1);

  pl_val* direct = NULL;
  pin_idx_entry* seen = NULL;
  bool ok = save_collect_direct(c, pl_pin_body(p), &direct, &seen, 0);
  ax_hmfree(seen);
  if (!ok) {
    ax_arrfree(direct);
    return false;
  }
  for (ptrdiff_t i = 0; i < ax_arrlen(direct); i++)
    if (!save_discover_pin(c, direct[i], depth + 1)) {
      ax_arrfree(direct);
      return false;
    }

  save_item item = {.source = pin, .direct = direct};
  ax_arrpush(c->items, item);
  ax_hmput(c->index, pin, (size_t)(ax_arrlen(c->items) - 1));
  at = ax_hmgeti(c->visit, pin);
  ax_assume(at >= 0, "Save visit disappeared");
  c->visit[at].value = 2;
  return true;
}

static const uint8_t* save_pin_hash(void* ctx, pl_val input) {
  save_ctx* c = ctx;
  const uint8_t* persistent = pl_pin_hash(input);
  if (persistent != NULL)
    return persistent;
  pl_val pin = save_effective_pin(input);
  ptrdiff_t at = ax_hmgeti(c->index, pin);
  if (at < 0)
    return NULL;
  save_item* item = &c->items[c->index[at].value];
  return item->hash_ready ? item->hash.b : NULL;
}

static bool save_prepare_table(save_ctx* c, save_item* item) {
  pl_intern_entry* unique = NULL;
  for (ptrdiff_t i = 0; i < ax_arrlen(item->direct); i++) {
    const uint8_t* hash = save_pin_hash(c, item->direct[i]);
    if (hash == NULL) {
      ax_hmfree(unique);
      return save_error(c, "child PIN hash was not prepared");
    }
    pl_hash key;
    memcpy(key.b, hash, sizeof(key.b));
    if (ax_hmgeti(unique, key) < 0) {
      ax_hmput(unique, key, item->direct[i]);
      ax_arrpush(item->table, item->direct[i]);
    }
  }
  ax_hmfree(unique);
  if ((size_t)ax_arrlen(item->table) > PL_HDR_META_MAX)
    return save_error(c, "PIN exceeds the direct PIN-table limit");
  return true;
}

static pl_val save_canonical_pin(save_ctx* c, pl_val input) {
  pl_val pin = save_effective_pin(input);
  const uint8_t* hash = save_pin_hash(c, pin);
  ax_assume(hash != NULL, "canonical child hash was not prepared");
  pl_hash key;
  memcpy(key.b, hash, sizeof(key.b));
  ptrdiff_t at = ax_hmgeti(c->canonical, key);
  if (at >= 0)
    return c->canonical[at].value;

  /* Discovery deliberately omits canonical leaves. On a map miss they
   * are their own canonical representative.  Keep the hash-map lookup first:
   * Legacy preparation may already have installed a Save-local representative
   * for an equal provisional PIN, and both references must resolve to it. */
  pl_cell* p = pl_as(PL_TAG_PIN, pin);
  ax_assume(p != NULL && !pl_pin_is_proxy(p) && pl_store_owns(c->store, pin) &&
                pl_pin_hash(pin) != NULL,
            "canonical child was not promoted");
  return pin;
}

static pl_cell* save_copy_alloc(save_ctx* c, size_t cells, bool transient) {
  if (!transient)
    return pl_store_alloc(c->store, cells);
  ax_assume(cells <= SIZE_MAX / sizeof(pl_cell),
            "Save transient allocation overflow");
  pl_cell* p = malloc(cells * sizeof(pl_cell));
  ax_assume(p != NULL, "Save transient allocation failed");
  ax_arrpush(c->transient, p);
  return p;
}

static pl_val save_copy_promoted(save_ctx* c, copy_entry** map, pl_val v,
                                 bool transient) {
  if (pl_is_nat63(v))
    return v;
  if (pl_tag(v) == PL_TAG_PIN)
    return save_canonical_pin(c, v);
  /* A canonical store graph is already closed, immutable and non-moving.
   * Copying it into every new snapshot retains the entire unchanged world
   * again. Sharing within this store changes neither Silo bytes nor hashes.
   * Transient preparation still uses its own representation. */
  if (!transient && pl_store_owns(c->store, v))
    return v;
  ptrdiff_t hit = ax_hmgeti(*map, v);
  if (hit >= 0)
    return (*map)[hit].value;
  pl_cell* p = pl_ptr(v);
  pl_val nv;
  switch (pl_tag(v)) {
  case PL_TAG_NAT: {
    uint32_t used = pl_nat_limbs(p);
    pl_cell* np = save_copy_alloc(c, PL_NAT_CELLS(used), transient);
    np[0] = pl_hdr_make(PL_K_NAT, PL_F_NORMAL, used, PL_NAT_CELLS(used));
    memcpy(np + 1, pl_nat_limb_ptr(p), used * sizeof(uint64_t));
    nv = pl_make(PL_TAG_NAT, np);
    break;
  }
  case PL_TAG_LAW: {
    pl_cell* np = save_copy_alloc(c, PL_LAW_CELLS, transient);
    np[0] = pl_hdr_make(PL_K_LAW, PL_F_NORMAL, 0, PL_LAW_CELLS);
    np[1] = pl_law_arity(p);
    nv = pl_make(PL_TAG_LAW, np);
    ax_hmput(*map, v, nv);
    np[2] = save_copy_promoted(c, map, pl_law_name(p), transient);
    np[3] = save_copy_promoted(c, map, pl_law_body(p), transient);
    return nv;
  }
  case PL_TAG_APP: {
    uint32_t n = pl_app_n(p);
    pl_cell* np = save_copy_alloc(c, PL_APP_CELLS(n), transient);
    np[0] = pl_hdr_make(PL_K_APP, PL_F_NORMAL, pl_app_need(p), PL_APP_CELLS(n));
    nv = pl_make(PL_TAG_APP, np);
    ax_hmput(*map, v, nv);
    np[1] = save_copy_promoted(c, map, pl_app_head(p), transient);
    for (uint32_t i = 0; i < n; i++)
      np[2 + i] = save_copy_promoted(c, map, pl_app_args(p)[i], transient);
    return nv;
  }
  default:
    ax_abort("save_copy_promoted: non-normal tag 0x%llx",
             (unsigned long long)pl_tag(v));
  }
  ax_hmput(*map, v, nv);
  return nv;
}

static pl_val save_transient_pin(save_ctx* c, const uint8_t hash[32],
                                 pl_val body, uint32_t npins,
                                 const pl_val* subpins) {
  pl_cell* p = save_copy_alloc(c, PL_PIN_CELLS(npins), true);
  p[0] = pl_hdr_make(PL_K_PIN, PL_F_NORMAL | PL_F_PIN_HASHED, npins,
                     PL_PIN_CELLS(npins));
  memcpy(pl_pin_hash_bytes(p), hash, 32);
  p[5] = body;
  pl_pin_set_code(p, NULL);
  if (npins != 0)
    memcpy(p + 7, subpins, (size_t)npins * sizeof(pl_val));
  return pl_make(PL_TAG_PIN, p);
}

static bool save_legacy_put(save_ctx* c, const uint8_t hash[32],
                            canon_ctx* encoded) {
  uint8_t* full = NULL;
  size_t nsub = (size_t)ax_arrlen(encoded->subpins);
  ax_arrpush(full, PL_CANON_VERSION);
  for (int i = 0; i < 8; i++)
    ax_arrpush(full, (uint8_t)((uint64_t)nsub >> (8 * i)));
  for (size_t j = 0; j < nsub; j++) {
    const uint8_t* child_hash = pl_pin_hash(encoded->subpins[j]);
    ax_assume(child_hash != NULL, "Legacy child is not canonical");
    for (int i = 0; i < 32; i++)
      ax_arrpush(full, child_hash[i]);
  }
  for (ptrdiff_t i = 0; i < ax_arrlen(encoded->buf); i++)
    ax_arrpush(full, encoded->buf[i]);
  bool ok = pl_store_backend_put(c->store, hash, full, (size_t)ax_arrlen(full));
  ax_arrfree(full);
  return ok || save_error(c, "Legacy store backend put failed");
}

static bool save_prepare_legacy(save_ctx* c, pl_val root) {
  for (ptrdiff_t i = 0; i < ax_arrlen(c->items); i++) {
    save_item* item = &c->items[i];
    const uint8_t* known = pl_pin_hash(item->source);
    if (known != NULL) {
      memcpy(item->hash.b, known, sizeof(item->hash.b));
      item->hash_ready = true;
      ptrdiff_t local_at = ax_hmgeti(c->canonical, item->hash);
      if (local_at >= 0) {
        item->canonical = c->canonical[local_at].value;
      } else {
        item->canonical = save_effective_pin(item->source);
        ax_hmput(c->canonical, item->hash, item->canonical);
      }
      if (!save_prepare_table(c, item))
        goto failed;
      continue;
    }

    if (!save_prepare_table(c, item))
      goto failed;
    copy_entry* copies = NULL;
    pl_val body =
        save_copy_promoted(c, &copies, pl_pin_body(pl_ptr(item->source)), true);
    ax_hmfree(copies);

    pl_store_profile_scope profile = pl_store_profile_begin(
        "store.serialize", sizeof("store.serialize") - 1);
    canon_ctx encoded = {0};
    collect_subpins(&encoded, body);
    serialize(&encoded, body);
    size_t text_n = 0;
    char* text = pl_canonize(ax_allocator_system(), body, &text_n);
    ax_sha256((const uint8_t*)text, text_n, item->hash.b);
    ax_free(ax_allocator_system(), text);
    pl_store_profile_end(&profile);
    item->hash_ready = true;

    ptrdiff_t local_at = ax_hmgeti(c->canonical, item->hash);
    if (local_at >= 0) {
      item->canonical = c->canonical[local_at].value;
    } else {
      if (!save_legacy_put(c, item->hash.b, &encoded)) {
        ax_arrfree(encoded.buf);
        ax_arrfree(encoded.subpins);
        ax_hmfree(encoded.idx);
        goto failed;
      }
      item->canonical = save_transient_pin(c, item->hash.b, body,
                                           (uint32_t)ax_arrlen(encoded.subpins),
                                           encoded.subpins);
      ax_hmput(c->canonical, item->hash, item->canonical);
    }
    ax_arrfree(encoded.buf);
    ax_arrfree(encoded.subpins);
    ax_hmfree(encoded.idx);
  }

  const uint8_t* root_hash = save_pin_hash(c, root);
  if (root_hash == NULL) {
    save_error(c, "Legacy root publication failed");
    goto failed;
  }
  if (!c->no_root && !pl_store_put_root(c->store, root_hash)) {
    save_error(c, "Legacy root publication failed");
    goto failed;
  }
  return true;

failed:
  return false;
}

static bool save_prepare_silo(save_ctx* c, pl_val root) {
  if (!pl_store_silo_batch_begin(c->store, &c->batch, c->err, c->err_cap))
    return false;
  for (ptrdiff_t i = 0; i < ax_arrlen(c->items); i++) {
    save_item* item = &c->items[i];
    if (!save_prepare_table(c, item))
      goto failed;
    const uint8_t* known = pl_pin_hash(item->source);
    bool present = false;
    if (known != NULL && !pl_store_silo_batch_contains(
                             c->batch, known, &present, c->err, c->err_cap))
      goto failed;

    if (known != NULL)
      memcpy(item->hash.b, known, sizeof(item->hash.b));
    if (known == NULL || !present) {
      uint8_t* bytes = NULL;
      size_t len = 0;
      uint8_t calculated[32];
      pl_store_profile_scope profile = pl_store_profile_begin(
          "store.serialize", sizeof("store.serialize") - 1);
      bool encoded = pl_silo_encode_buffer(
          pl_pin_body(pl_ptr(item->source)), item->table,
          (size_t)ax_arrlen(item->table), save_pin_hash, c, &bytes, &len,
          calculated, c->err, c->err_cap);
      pl_store_profile_end(&profile);
      if (!encoded) {
        ax_arrfree(bytes);
        goto failed;
      }
      if (known != NULL && memcmp(known, calculated, 32) != 0) {
        ax_arrfree(bytes);
        save_error(c, "runtime PIN hash does not match its Silo stream");
        goto failed;
      }
      if (known == NULL)
        memcpy(item->hash.b, calculated, sizeof(item->hash.b));
      item->hash_ready = true;
      bool stored = pl_store_silo_batch_put(c->batch, item->hash.b, bytes, len,
                                            c->err, c->err_cap);
      ax_arrfree(bytes);
      if (!stored)
        goto failed;
    } else {
      item->hash_ready = true;
    }
  }

  const uint8_t* root_hash = save_pin_hash(c, root);
  if (root_hash == NULL) {
    save_error(c, "Silo root PIN hash was not prepared");
    goto failed;
  }
  pl_silo_batch* batch = c->batch;
  c->batch = NULL;
  return pl_store_silo_batch_commit(batch, c->no_root ? NULL : root_hash,
                                    c->err, c->err_cap);

failed:
  pl_store_silo_batch_abort(c->batch);
  c->batch = NULL;
  return false;
}

static void save_build_canonical(save_ctx* c) {
  /* Legacy preparation uses this map for transient representatives.  Nothing
   * in the durable store may retain those Save-local pointers. */
  ax_hmfree(c->canonical);
  c->canonical = NULL;
  copy_entry* copies = NULL;
  for (ptrdiff_t i = 0; i < ax_arrlen(c->items); i++) {
    save_item* item = &c->items[i];
    const uint8_t* known = pl_pin_hash(item->source);
    if (known != NULL) {
      ptrdiff_t local_at = ax_hmgeti(c->canonical, item->hash);
      if (local_at >= 0) {
        item->canonical = c->canonical[local_at].value;
      } else {
        item->canonical = save_effective_pin(item->source);
        ax_hmput(c->canonical, item->hash, item->canonical);
      }
      continue;
    }
    ptrdiff_t local_at = ax_hmgeti(c->canonical, item->hash);
    pl_val hit = local_at >= 0 ? c->canonical[local_at].value
                               : pl_store_intern_get(c->store, item->hash.b);
    if (hit != 0) {
      item->canonical = hit;
      if (local_at < 0)
        ax_hmput(c->canonical, item->hash, item->canonical);
      continue;
    }

    pl_val body = save_copy_promoted(c, &copies,
                                     pl_pin_body(pl_ptr(item->source)), false);
    pl_val* subpins = NULL;
    for (ptrdiff_t j = 0; j < ax_arrlen(item->table); j++)
      ax_arrpush(subpins, save_canonical_pin(c, item->table[j]));
    item->canonical = pl_store_mk_pin(c->store, item->hash.b, body,
                                      (uint32_t)ax_arrlen(subpins), subpins);
    ax_hmput(c->canonical, item->hash, item->canonical);
    ax_arrfree(subpins);
  }
  ax_hmfree(copies);
}

static void save_publish_targets(save_ctx* c) {
  for (ptrdiff_t i = 0; i < ax_arrlen(c->items); i++) {
    save_item* item = &c->items[i];
    pl_cell* p = pl_ptr(item->source);
    if (pl_pin_is_proxy(p) && pl_pin_proxy_target(p) == 0)
      pl_pin_set_target(p, item->canonical);
  }
}

static void save_queue_compiles(save_ctx* c) {
  if (!c->store->compiler_f)
    return;
  for (ptrdiff_t i = 0; i < ax_arrlen(c->items); i++) {
    pl_val pin = c->items[i].canonical;
    pl_cell* p = pl_ptr(pin);
    if (pl_tag(pl_pin_body(p)) != PL_TAG_LAW || pl_pin_code(p) != NULL)
      continue;
    pl_hash key = c->items[i].hash;
    if (ax_hmgeti(c->compile, key) < 0)
      ax_hmput(c->compile, key, pin);
  }
}

static void save_ctx_free(save_ctx* c) {
  for (ptrdiff_t i = 0; i < ax_arrlen(c->items); i++) {
    ax_arrfree(c->items[i].direct);
    ax_arrfree(c->items[i].table);
  }
  ax_arrfree(c->items);
  ax_hmfree(c->index);
  ax_hmfree(c->visit);
  ax_hmfree(c->canonical);
  ax_hmfree(c->compile);
  for (ptrdiff_t i = 0; i < ax_arrlen(c->transient); i++)
    free(c->transient[i]);
  ax_arrfree(c->transient);
}

/* A canonical store PIN has an encoded closure, staged or already durable.
 * Save must still checkpoint staged objects even when its root is unchanged.
 * Keep Silo's root update in its validated LMDB batch transaction;
 * Legacy backends use their existing root operation after verifying that the
 * root object is still present. */
static bool save_canonical_root(save_ctx* c, pl_val input, bool* handled) {
  *handled = false;
  pl_val pin = save_effective_pin(input);
  pl_cell* p = pl_as(PL_TAG_PIN, pin);
  if (p == NULL || pl_pin_is_proxy(p) || !pl_store_owns(c->store, pin))
    return true;
  const uint8_t* hash = pl_pin_hash(pin);
  if (hash == NULL)
    return true;
  *handled = true;

  if (c->no_root) {
    /* already canonical: presence is all that matters, and the root
     * stays whatever it was */
    if (c->store->be.has != NULL && !c->store->be.has(c->store->be.ctx, hash))
      return save_error(c, "canonical object is not available");
    return true;
  }

  if (c->store->format == PL_STORE_FORMAT_SILO_V1) {
    pl_silo_batch* batch = NULL;
    if (!pl_store_silo_batch_begin(c->store, &batch, c->err, c->err_cap))
      return false;
    return pl_store_silo_batch_commit(batch, hash, c->err, c->err_cap);
  }

  if (c->store->be.has == NULL || !c->store->be.has(c->store->be.ctx, hash))
    return save_error(c, "canonical root object is not available");
  if (!c->store->be.put_root(c->store->be.ctx, hash))
    return save_error(c, "Legacy root publication failed");
  return true;
}

static bool pl_store_save_pin_or_root(pl_store* s, pl_val pin,
                                      uint8_t out_hash[32], char* err,
                                      size_t err_cap, bool no_root) {
  if (s == NULL) {
    if (err != NULL && err_cap != 0)
      (void)snprintf(err, err_cap, "Save requires a store");
    return false;
  }
  save_ctx c = {.store = s, .err = err, .err_cap = err_cap, .no_root = no_root};
  pl_store_save_lock(s);
  bool handled = false;
  bool ok = save_canonical_root(&c, pin, &handled);
  if (handled) {
    if (ok && out_hash != NULL)
      memcpy(out_hash, pl_pin_hash(save_effective_pin(pin)), 32);
    pl_store_save_unlock(s);
    return ok;
  }
  ok = save_discover_pin(&c, pin, 0);
  if (ok) {
    if (s->format == PL_STORE_FORMAT_SILO_V1)
      ok = save_prepare_silo(&c, pin);
    else
      ok = save_prepare_legacy(&c, pin);
  }
  bool compile = false;
  if (ok) {
    /* Staging or persistence is complete. Keep the general lock around arena
     * and registry publication; Save serialization remains held until every
     * source proxy has its canonical target. */
    pl_store_lock(s);
    save_build_canonical(&c);
    save_publish_targets(&c);
    save_queue_compiles(&c);
    const uint8_t* root_hash = save_pin_hash(&c, pin);
    ax_assume(root_hash != NULL, "successful Save lost its root hash");
    if (out_hash != NULL)
      memcpy(out_hash, root_hash, 32);
    compile = s->compiler_f;
    pl_store_unlock(s);
  }
  pl_store_save_unlock(s);

  if (compile)
    for (ptrdiff_t i = 0; i < ax_hmlen(c.compile); i++)
      pl_store_put_code(s, c.compile[i].key.b);
  save_ctx_free(&c);
  return ok;
}

bool pl_store_save_root(pl_store* s, pl_val pin, uint8_t out_hash[32],
                        char* err, size_t err_cap) {
  bool ok = pl_store_save_pin_or_root(s, pin, out_hash, err, err_cap, false);
  if (ok)
    pl_store_cache_checkpoint();
  return ok;
}

/* Stage a pin's closed graph without publishing a root. The bytecode
 * compile cache stages derived artifacts through the same path. */
bool pl_store_save_pin(pl_store* s, pl_val pin, uint8_t out_hash[32], char* err,
                       size_t err_cap) {
  return pl_store_save_pin_or_root(s, pin, out_hash, err, err_cap, true);
}

pl_val pl_pin(pl_thread* t, pl_val v) {
  v = pl_whnf(t, v);
  size_t root = t->vsp;
  pl_vpush(t, v);
  pl_gc_reserve(t, PL_PIN_CELLS(0));
  PL_GC_FORBID(t);
  pl_cell* p = pl_bump(t, PL_PIN_CELLS(0));
  pl_cache_stat_alloc(t, PL_K_PIN, PL_PIN_CELLS(0));
  p[0] = pl_hdr_make(PL_K_PIN, PL_F_PIN_PROXY, 0, PL_PIN_CELLS(0));
  memset(p + 1, 0, 4 * sizeof(pl_cell));
  p[5] = t->vstack[root];
  p[6] = 0;
  pl_val pin = pl_make(PL_TAG_PIN, p);
  PL_GC_ALLOW(t);
  t->vsp = root;
  return pin;
}

pl_val pl_store_pin_of_nat(pl_store* s, uint64_t n) {
  ax_assume(n <= PL_NAT63_MAX, "pin_of_nat: too large");
  return pl_store_mk_proxy(s, n);
}

/* ── Loading ───────────────────────────────────────────────────────────── */

typedef struct deser_ctx {
  const uint8_t* b;
  size_t n;
  size_t off;
  pl_val* subpins;
  size_t nsub;
  pl_thread* t;
} deser_ctx;

static uint64_t dget(deser_ctx* d, size_t width) {
  ax_assume(d->off + width <= d->n, "pin bytes truncated");
  uint64_t v = 0;
  for (size_t i = 0; i < width; i++)
    v |= (uint64_t)d->b[d->off + i] << (8 * i);
  d->off += width;
  return v;
}

static pl_val deser(pl_store* s, deser_ctx* d) {
  uint64_t tag = dget(d, 1);
  switch (tag) {
  case 'n': {
    uint64_t len = dget(d, 8);
    ax_assume(d->off + len <= d->n, "pin bytes truncated");
    const uint8_t* bytes = d->b + d->off;
    d->off += len;
    if (len < 8) {
      uint64_t v = 0;
      memcpy(&v, bytes, len);
      return v;
    }
    if (len == 8) {
      uint64_t v;
      memcpy(&v, bytes, 8);
      if (v <= PL_NAT63_MAX)
        return v;
    }
    size_t limbs = (len + 7) / 8;
    pl_cell* np = pl_store_alloc(s, PL_NAT_CELLS(limbs));
    np[0] = pl_hdr_make(PL_K_NAT, PL_F_NORMAL, (uint32_t)limbs,
                        PL_NAT_CELLS(limbs));
    np[limbs] = 0;
    memcpy(np + 1, bytes, len);
    return pl_nat_trim(pl_make(PL_TAG_NAT, np));
  }
  case 'p': {
    uint64_t i = dget(d, 4);
    ax_assume(i < d->nsub, "pin index out of range");
    return d->subpins[i];
  }
  case 'l': {
    uint64_t arity = dget(d, 8);
    pl_cell* np = pl_store_alloc(s, PL_LAW_CELLS);
    np[0] = pl_hdr_make(PL_K_LAW, PL_F_NORMAL, 0, PL_LAW_CELLS);
    np[1] = arity;
    np[2] = deser(s, d);
    np[3] = deser(s, d);
    return pl_make(PL_TAG_LAW, np);
  }
  case 'a': {
    uint64_t n = dget(d, 4);
    ax_assume(n >= 1, "empty app in pin bytes");
    pl_cell* np = pl_store_alloc(s, PL_APP_CELLS(n));
    np[0] = pl_hdr_make(PL_K_APP, PL_F_NORMAL, 0, PL_APP_CELLS(n));
    pl_val nv = pl_make(PL_TAG_APP, np);
    np[1] = deser(s, d);
    for (uint64_t i = 0; i < n; i++)
      np[2 + i] = deser(s, d);
    /* fix the need cache now that the head exists */
    uint64_t a = pl_arity((pl_val)np[1]);
    uint32_t need = (a == 0 || a <= n) ? 0 : (uint32_t)(a - n);
    np[0] = pl_hdr_make(PL_K_APP, PL_F_NORMAL, need, PL_APP_CELLS(n));
    return nv;
  }
  default:
    ax_abort("bad tag in pin bytes: %u", (unsigned)tag);
  }
}

static bool store_hash_loading(pl_store* s, const uint8_t hash[32]) {
  for (ptrdiff_t i = 0; i < ax_arrlen(s->loading); i++)
    if (memcmp(s->loading[i].b, hash, 32) == 0)
      return true;
  return false;
}

static bool load_silo_pin(pl_thread* t, pl_store* s, const uint8_t hash[32],
                          pl_val* out, pl_intern_entry** compile, char* err,
                          size_t err_cap);

/* Load a Silo object stream from an external byte buffer (the global
 * compile cache): subpins resolve through the regular store paths, so
 * a stream referencing pins this store has never seen simply fails —
 * the caller treats that as a cache miss.  The result is hashed,
 * interned, and indistinguishable from a pack-loaded pin. */
typedef struct silo_mem_reader {
  const uint8_t* b;
  size_t n;
  size_t pos;
} silo_mem_reader;

static bool silo_mem_read(void* ctx, uint8_t* bytes, size_t len) {
  silo_mem_reader* r = ctx;
  if (len > r->n - r->pos)
    return false;
  memcpy(bytes, r->b + r->pos, len);
  r->pos += len;
  return true;
}

static bool silo_mem_rewind(void* ctx) {
  silo_mem_reader* r = ctx;
  r->pos = 0;
  return true;
}

bool pl_store_load_silo_stream(pl_thread* t, pl_store* s, const uint8_t* bytes,
                               size_t len, pl_val* out, char* err,
                               size_t err_cap) {
  silo_mem_reader mem = {.b = bytes, .n = len, .pos = 0};
  pl_silo_reader reader = {.ctx = &mem,
                           .read = silo_mem_read,
                           .rewind = silo_mem_rewind,
                           .len = len,
                           .pos = 0};
  pl_silo_scan scan = {0};
  pl_val* resolved = NULL;
  pl_val* subpins = NULL;
  pl_intern_entry* compile = NULL;
  size_t mark = 0;
  bool marked = false;
  bool ok = pl_silo_scan_stream(&reader, false, &scan, err, err_cap);
  if (!ok)
    goto done;
  resolved = calloc(scan.pin_count ? scan.pin_count : 1, sizeof(*resolved));
  if (resolved == NULL) {
    (void)snprintf(err, err_cap, "out of memory resolving Silo PINs");
    ok = false;
    goto done;
  }
  for (size_t i = 0; i < scan.used_count; i++) {
    uint32_t index = scan.used[i];
    pl_val sub;
    if (!load_silo_pin(t, s, scan.pins[index].b, &sub, &compile, err,
                       err_cap)) {
      ok = false;
      goto done;
    }
    resolved[index] = sub;
    ax_arrpush(subpins, sub);
  }

  mark = pl_store_mark(s);
  marked = true;
  pl_val body;
  if (!pl_silo_build_stream(&reader, s, &scan, resolved, &body, err, err_cap)) {
    ok = false;
    goto done;
  }

  uint8_t actual[32];
  if (!pl_silo_hash(body, subpins, (size_t)ax_arrlen(subpins), actual, err,
                    err_cap)) {
    ok = false;
    goto done;
  }
  pl_val hit = pl_store_intern_get(s, actual);
  if (hit != 0) {
    pl_store_release(s, mark);
    marked = false;
    *out = hit;
    ok = true;
    goto done;
  }

  size_t pin_cells = PL_PIN_CELLS((uint32_t)scan.used_count);
  size_t region_mark = pl_store_mark(s);
  if (region_mark > s->region->cap_s ||
      pin_cells > (s->region->cap_s - region_mark) / sizeof(pl_cell)) {
    (void)snprintf(err, err_cap,
                   "decoded PIN exceeds remaining store-region capacity");
    ok = false;
    goto done;
  }

  *out = pl_store_mk_pin(s, actual, body, (uint32_t)scan.used_count, subpins);
  marked = false;
  ok = true;

done:
  if (!ok && marked)
    pl_store_release(s, mark);
  pl_silo_scan_free(&scan);
  free(resolved);
  ax_arrfree(subpins);
  if (ok)
    for (ptrdiff_t i = 0; i < ax_hmlen(compile); i++)
      pl_store_put_code(s, compile[i].key.b);
  ax_hmfree(compile);
  return ok;
}

static bool load_silo_pin(pl_thread* t, pl_store* s, const uint8_t hash[32],
                          pl_val* out, pl_intern_entry** compile, char* err,
                          size_t err_cap) {
  pl_val hit = pl_store_intern_get(s, hash);
  if (hit != 0) {
    *out = hit;
    return true;
  }
  if (store_hash_loading(s, hash)) {
    (void)snprintf(err, err_cap, "cyclic Silo PIN dependency");
    return false;
  }
  pl_hash loading;
  memcpy(loading.b, hash, 32);
  ax_arrpush(s->loading, loading);

  pl_silo_reader reader = {0};
  pl_silo_scan scan = {0};
  pl_val* resolved = NULL;
  pl_val* subpins = NULL;
  size_t mark = 0;
  bool marked = false;
  bool reader_open = false;
  bool ok = pl_store_silo_open(s, hash, &reader, err, err_cap);
  if (!ok)
    goto done;
  reader_open = true;
  if (!pl_silo_scan_stream(&reader, false, &scan, err, err_cap)) {
    ok = false;
    goto done;
  }
  resolved = calloc(scan.pin_count ? scan.pin_count : 1, sizeof(*resolved));
  if (resolved == NULL) {
    (void)snprintf(err, err_cap, "out of memory resolving Silo PINs");
    ok = false;
    goto done;
  }
  for (size_t i = 0; i < scan.used_count; i++) {
    uint32_t index = scan.used[i];
    pl_val sub;
    if (!load_silo_pin(t, s, scan.pins[index].b, &sub, compile, err, err_cap)) {
      ok = false;
      goto done;
    }
    resolved[index] = sub;
    ax_arrpush(subpins, sub);
  }

  mark = pl_store_mark(s);
  marked = true;
  pl_val body;
  pl_store_profile_scope profile = pl_store_profile_begin(
      "store.deserialize", sizeof("store.deserialize") - 1);
  bool built =
      pl_silo_build_stream(&reader, s, &scan, resolved, &body, err, err_cap);
  pl_store_profile_end(&profile);
  if (!built) {
    ok = false;
    goto done;
  }

  uint8_t actual[32];
  if (!pl_silo_hash(body, subpins, (size_t)ax_arrlen(subpins), actual, err,
                    err_cap)) {
    ok = false;
    goto done;
  }
  if (memcmp(actual, hash, 32) != 0) {
    (void)snprintf(err, err_cap,
                   "Silo value does not match canonical stream hash");
    ok = false;
    goto done;
  }

  size_t pin_cells = PL_PIN_CELLS((uint32_t)scan.used_count);
  size_t region_mark = pl_store_mark(s);
  if (region_mark > s->region->cap_s ||
      pin_cells > (s->region->cap_s - region_mark) / sizeof(pl_cell)) {
    (void)snprintf(err, err_cap,
                   "decoded PIN exceeds remaining store-region capacity");
    ok = false;
    goto done;
  }

  *out = pl_store_mk_pin(s, hash, body, (uint32_t)scan.used_count, subpins);
  if (pl_tag(body) == PL_TAG_LAW) {
    pl_hash key;
    memcpy(key.b, hash, sizeof(key.b));
    if (ax_hmgeti(*compile, key) < 0)
      ax_hmput(*compile, key, *out);
  }
  marked = false; /* the successful allocations now belong to the store */
  ok = true;

done:
  if (!ok && marked)
    pl_store_release(s, mark);
  if (reader_open)
    pl_store_silo_close_reader(&reader);
  pl_silo_scan_free(&scan);
  free(resolved);
  ax_arrfree(subpins);
  ax_assume(ax_arrlen(s->loading) > 0, "Silo loading stack underflow");
  (void)stbds_arrpop(s->loading);
  return ok;
}

/* Legacy dependency loading is deliberately error-returning.  Recursive
 * calls must not raise across an outer call's malloc-owned byte buffer or
 * sub-PIN array; the public boundary raises only after every level has
 * unwound and save_mu has been released.  save_mu serializes this loading
 * stack and the non-thread-safe legacy backend, while mu is needed only for
 * the final arena/registry publication. */
static bool load_legacy_pin(pl_thread* t, pl_store* s, const uint8_t hash[32],
                            pl_val* out, char* err, size_t err_cap) {
  pl_val hit = pl_store_intern_get(s, hash);
  if (hit != 0) {
    *out = hit;
    return true;
  }
  if (store_hash_loading(s, hash)) {
    (void)snprintf(err, err_cap, "cyclic Legacy PIN dependency");
    return false;
  }

  pl_hash loading;
  memcpy(loading.b, hash, sizeof(loading.b));
  ax_arrpush(s->loading, loading);

  uint8_t* bytes = NULL;
  size_t n = 0;
  pl_val* subs = NULL;
  bool compile = false;
  bool ok = false;

  if (!pl_store_backend_get(s, hash, &bytes, &n)) {
    (void)snprintf(err, err_cap, "missing pin");
    goto done;
  }

  deser_ctx d = {.b = bytes, .n = n, .t = t};
  uint64_t ver = dget(&d, 1);
  ax_assume(ver == PL_CANON_VERSION, "bad pin version %u", (unsigned)ver);
  d.nsub = dget(&d, 8);
  if (d.nsub > PL_HDR_META_MAX) {
    (void)snprintf(err, err_cap, "PIN exceeds the direct PIN-table limit");
    goto done;
  }
  for (size_t i = 0; i < d.nsub; i++) {
    uint8_t sub[32];
    ax_assume(d.off + sizeof(sub) <= d.n, "pin bytes truncated");
    memcpy(sub, d.b + d.off, sizeof(sub));
    d.off += sizeof(sub);
    pl_val child = 0;
    if (!load_legacy_pin(t, s, sub, &child, err, err_cap))
      goto done;
    ax_arrpush(subs, child);
  }
  d.subpins = subs;

  /* A direct internal registration can race while backend I/O is in flight.
   * Recheck under mu before constructing a second representative. */
  pl_store_lock(s);
  hit = pl_store_intern_get(s, hash);
  if (hit != 0) {
    *out = hit;
  } else {
    pl_store_profile_scope profile = pl_store_profile_begin(
        "store.deserialize", sizeof("store.deserialize") - 1);
    pl_val body = deser(s, &d);
    *out = pl_store_mk_pin(s, hash, body, (uint32_t)d.nsub, subs);
    compile = pl_tag(body) == PL_TAG_LAW;
    pl_store_profile_end(&profile);
  }
  pl_store_unlock(s);
  ok = true;

done:
  ax_arrfree(subs);
  free(bytes);
  ax_assume(ax_arrlen(s->loading) > 0, "Legacy loading stack underflow");
  ax_assume(memcmp(stbds_arrlast(s->loading).b, hash, 32) == 0,
            "Legacy loading stack order changed");
  (void)stbds_arrpop(s->loading);
  if (ok && compile)
    pl_store_put_code(s, hash);
  return ok;
}

pl_val pl_store_load(pl_thread* t, const uint8_t hash[32]) {
  pl_store* s = pl_heap_store(t->heap);
  ax_assume(s != NULL, "store_load requires a store");
  pl_store_save_lock(s);
  char err[192] = {0};
  pl_val pin = 0;
  bool ok;
  if (s->format == PL_STORE_FORMAT_SILO_V1) {
    /* Silo builds directly into the arena and rolls the whole build back on
     * validation failure, so retain mu across its mark/build/release region. */
    pl_intern_entry* compile = NULL;
    pl_store_lock(s);
    ok = load_silo_pin(t, s, hash, &pin, &compile, err, sizeof(err));
    pl_store_unlock(s);
    /* Loading needs one arena rollback region, but PLAN compilation does not.
     * Run every newly registered LAW only after releasing the general mutex;
     * save_mu still serializes the compiler machine and this load closure. */
    for (ptrdiff_t i = 0; i < ax_hmlen(compile); i++)
      pl_store_put_code(s, compile[i].key.b);
    ax_hmfree(compile);
  } else {
    ok = load_legacy_pin(t, s, hash, &pin, err, sizeof(err));
  }
  pl_store_save_unlock(s);
  if (!ok)
    pl_raise_msgf(t, "store_load: %s",
                  err[0] != '\0' ? err : "backend load failed");
  return pin;
}
