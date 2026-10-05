#ifndef PL_STORE_INTERNAL_H
#define PL_STORE_INTERNAL_H

/* Shared between store.c (region, backends) and pin.c (canonize, copy). */

#include "plan/store.h"
#include "plan/value.h"
#include "silo_internal.h"

typedef struct pl_store_profile_scope {
  uint64_t lane;
  uint64_t span;
  const uint8_t* name;
  size_t name_n;
  bool active;
} pl_store_profile_scope;

/* Chrome Trace span shared by store.c and the serializer in pin.c. */
pl_store_profile_scope pl_store_profile_begin(const char* name, size_t name_n);
void pl_store_profile_end(pl_store_profile_scope* scope);

pl_cell* pl_store_alloc(pl_store* s, size_t cells);
size_t pl_store_mark(pl_store* s);
void pl_store_release(pl_store* s, size_t mark);
pl_val pl_store_reuse_decoded(pl_store* s, pl_val value);

void pl_store_lock(pl_store* s);
void pl_store_unlock(pl_store* s);
void pl_store_save_lock(pl_store* s);
void pl_store_save_unlock(pl_store* s);

pl_val pl_store_intern_get(pl_store* s, const uint8_t hash[32]);
void pl_store_intern_put(pl_store* s, const uint8_t hash[32], pl_val pin);

bool pl_store_backend_put(pl_store* s, const uint8_t hash[32], const uint8_t* b,
                          size_t n);
bool pl_store_backend_get(pl_store* s, const uint8_t hash[32], uint8_t** out_b,
                          size_t* out_s);

typedef struct pl_silo_batch pl_silo_batch;

/* Store-local (or separately locked global-cache) writes awaiting Save. */
typedef struct pl_staged_blob {
  pl_hash key;
  struct {
    uint8_t* bytes;
    size_t len;
  } value;
} pl_staged_blob;

bool pl_staged_put(pl_staged_blob** staged, const uint8_t hash[32],
                   const uint8_t* bytes, size_t len);
bool pl_staged_get(pl_staged_blob* staged, const uint8_t hash[32],
                   uint8_t** out, size_t* len);
void pl_staged_clear(pl_staged_blob** staged);
void pl_store_cache_checkpoint(void);

bool pl_store_silo_batch_begin(pl_store* s, pl_silo_batch** out, char* err,
                               size_t err_cap);
bool pl_store_silo_batch_contains(pl_silo_batch* batch, const uint8_t hash[32],
                                  bool* out, char* err, size_t err_cap);
bool pl_store_silo_batch_put(pl_silo_batch* batch, const uint8_t hash[32],
                             const uint8_t* bytes, size_t len, char* err,
                             size_t err_cap);
/* With no root, stage the batch locally without committing LMDB or syncing.
 * With a root, commit all staged objects/cache entries and the root together.
 * Consumes batch on both success and failure. */
bool pl_store_silo_batch_commit(pl_silo_batch* batch,
                                const uint8_t root_hash[32], char* err,
                                size_t err_cap);
void pl_store_silo_batch_abort(pl_silo_batch* batch);
bool pl_store_silo_open(pl_store* s, const uint8_t hash[32],
                        pl_silo_reader* out, char* err, size_t err_cap);
void pl_store_silo_close_reader(pl_silo_reader* r);
bool pl_store_load_silo_stream(pl_thread* t, pl_store* s, const uint8_t* bytes,
                               size_t len, pl_val* out, char* err,
                               size_t err_cap);

pl_val pl_store_mk_pin(pl_store* s, const uint8_t* hash, pl_val body,
                       uint32_t npins, const pl_val* subpins);

/* Fixed-size, closed, non-persistent PIN proxy.  Store proxies are deliberately
 * absent from the intern table, canonical PIN list, and code indexes. */
pl_val pl_store_mk_proxy(pl_store* s, pl_val body);

/* Publish a fully initialized canonical store PIN in the runtime indexes. */
void pl_store_register_canonical(pl_store* s, pl_val pin);

/* Intern the pin of a small nat (used for the op-66 row exprs). */
pl_val pl_store_pin_of_nat(pl_store* s, uint64_t n);

#endif
