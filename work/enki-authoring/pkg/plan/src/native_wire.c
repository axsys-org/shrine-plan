#include "native_wire.h"

#include <stdlib.h>
#include <string.h>

#include "axsys/ds.h"
#include "plan/build.h"
#include "plan/nat.h"
#include "plan/store.h"

/* SRNV3 is the existing graph codec. SRND4 additionally binds a delta to
 * the ordered hashes of its explicit seeds. No ambient store lookup is used
 * by decoding. Pointer memoization avoids walking shared compiler graphs
 * through repeated semantic comparisons; it changes no native value. */
/* The transport is one runtime natural, including its trailing bytebar bit. */
#define NW_BYTES ((size_t)PL_HDR_META_MAX * 8u - 1u)
#define NW_NODES 1000000u
#define NW_DEPTH 1024u
#define NW_CELLS (16u * 1024u * 1024u)

typedef struct nw_seen { pl_val key; uint32_t value; } nw_seen;
typedef struct nw_seed { pl_hash key; uint32_t value; } nw_seed;
typedef struct nw_path { uint32_t parent, step, seed, depth; pl_val value; } nw_path;
typedef struct nw_encoder {
  pl_thread* t;
  uint8_t* bytes;
  nw_seen* seen;
  nw_seen* basis;
  nw_path* paths;
  uint32_t nodes;
  uint32_t scanned;
  const char* error;
} nw_encoder;
static pl_val nw_key(pl_val value);

/* References into a seed carry selectors, not process-local table indices.
 * Thus independently loaded graphs may have different memory sharing without
 * changing what a delta denotes. Indexing is only an encoding optimization. */
static void nw_index_basis(nw_encoder* e, pl_val value, uint32_t parent,
                           uint32_t step, uint32_t seed, uint32_t depth) {
  if (++e->scanned > NW_NODES * 4u || depth > NW_DEPTH ||
      (size_t)ax_arrlen(e->paths) >= NW_NODES) return;
  value = nw_key(value);
  if (pl_is_nat(value) || ax_hmgeti(e->basis, value) >= 0) return;
  uint32_t here = (uint32_t)ax_arrlen(e->paths);
  nw_path path = {.parent = parent, .step = step, .seed = seed,
                  .depth = depth, .value = value};
  ax_arrpush(e->paths, path);
  ax_hmput(e->basis, value, here);
}

/* All roots enter before their descendants. Shared compiler artifacts can
 * also be reachable through hundreds of ancestors; depth-first traversal
 * retained those long selectors and exhausted the byte budget on references
 * alone. Breadth-first discovery chooses shortest selectors within the same
 * bounded domain and never changes which native value a reference denotes. */
static void nw_expand_basis(nw_encoder* e) {
  for (uint32_t here = 0; here < (uint32_t)ax_arrlen(e->paths); here++) {
    nw_path path = e->paths[here];
    pl_cell* p = pl_ptr(path.value);
    uint32_t depth = path.depth + 1u;
    if (pl_tag(path.value) == PL_TAG_PIN) {
      nw_index_basis(e, pl_pin_body(p), here, 0, path.seed, depth);
    } else if (pl_tag(path.value) == PL_TAG_LAW) {
      nw_index_basis(e, pl_law_name(p), here, 0, path.seed, depth);
      nw_index_basis(e, pl_law_body(p), here, 1, path.seed, depth);
    } else if (pl_tag(path.value) == PL_TAG_APP) {
      nw_index_basis(e, pl_app_head(p), here, 0, path.seed, depth);
      for (uint32_t i = 0; i < pl_app_n(p); i++)
        nw_index_basis(e, pl_app_args(p)[i], here, i + 1, path.seed, depth);
    }
  }
}

static bool nw_charge(pl_thread* t) {
  if (t->pure_depth == 0) return true;
  if (t->pure_remaining == 0) return false;
  t->pure_remaining--;
  return true;
}

static pl_val nw_key(pl_val value) {
  value = pl_resolve(value);
  if (pl_tag(value) == PL_TAG_PIN) {
    pl_val target = pl_pin_proxy_target(pl_ptr(value));
    if (target != 0) return target;
  }
  return value;
}

static pl_val nw_result(pl_thread* t, bool ok, pl_val value) {
  size_t root = t->vsp;
  pl_vpush(t, value);
  pl_gc_reserve(t, PL_APP_CELLS(1));
  PL_GC_FORBID(t);
  pl_val answer = pl_mk_app_from(t, ok ? 0 : 1, 1, &t->vstack[root]);
  PL_GC_ALLOW(t);
  t->vsp = root;
  return answer;
}

static pl_val nw_failure(pl_thread* t, const char* error) {
  return nw_result(t, false, pl_nat_from_bytes(t, (const uint8_t*)error, strlen(error)));
}

static bool nw_seeds(pl_thread* t, pl_val seeds, uint32_t* count,
                     uint8_t** hashes, const char** error) {
  if (seeds == 0) { *count = 0; return true; }
  if (pl_tag(seeds) != PL_TAG_APP || pl_app_head(pl_ptr(seeds)) != 0) {
    *error = "native-wire-seeds-must-be-row"; return false;
  }
  *count = pl_app_n(pl_ptr(seeds));
  if (*count > NW_NODES || *count > NW_BYTES / 32u) {
    *error = "native-wire-seed-limit"; return false;
  }
  nw_seed* seen = NULL;
  pl_val* values = pl_app_args(pl_ptr(seeds));
  for (uint32_t i = 0; i < *count; i++) {
    pl_val value = pl_resolve(values[i]);
    if (pl_tag(value) != PL_TAG_PIN) {
      *error = "native-wire-seeds-must-be-pins"; break;
    }
    /* Immutable pin interning is allowed by Pure, exactly as for Ice.
     * Existing worlds normally supply already canonical pins. */
    char detail[192] = {0};
    pl_hash hash;
    if (!pl_store_save_pin(pl_heap_store(t->heap), value, hash.b, detail, sizeof(detail))) {
      *error = "native-wire-seed-intern-failed"; break;
    }
    if (ax_hmgeti(seen, hash) >= 0) {
      *error = "native-wire-duplicate-seed"; break;
    }
    ax_hmput(seen, hash, i);
    memcpy(ax_arraddn(*hashes, 32), hash.b, 32);
  }
  ax_hmfree(seen);
  return *error == NULL;
}

static bool nw_put(nw_encoder* e, const void* bytes, size_t n) {
  if (n > NW_BYTES - (size_t)ax_arrlen(e->bytes)) {
    e->error = "native-wire-byte-limit"; return false;
  }
  if (n != 0) memcpy(ax_arraddn(e->bytes, (ptrdiff_t)n), bytes, n);
  return true;
}
static bool nw_uint(nw_encoder* e, uint32_t value, size_t n) {
  uint8_t b[4];
  for (size_t i = 0; i < n; i++) b[i] = (uint8_t)(value >> (i * 8));
  return nw_put(e, b, n);
}

static bool nw_pack_basis(nw_encoder* e, pl_val value, uint32_t path) {
      uint32_t steps[NW_DEPTH + 1u], n = 0, seed = e->paths[path].seed;
      while (e->paths[path].parent != UINT32_MAX) {
        steps[n++] = e->paths[path].step;
        path = e->paths[path].parent;
      }
      bool ok = nw_uint(e, 5, 1) && nw_uint(e, seed, 4) && nw_uint(e, n, 4);
      for (uint32_t i = n; ok && i > 0; i--) ok = nw_uint(e, steps[i - 1], 4);
      if (ok) {
        uint32_t index = (uint32_t)ax_hmlen(e->seen);
        ax_hmput(e->seen, value, index);
      }
      return ok;
}

static bool nw_pack_value(nw_encoder* e, pl_val value, uint32_t depth) {
  if (++e->nodes > NW_NODES || !nw_charge(e->t)) {
    e->error = "native-wire-node-limit"; return false;
  }
  if (depth > NW_DEPTH) { e->error = "native-wire-depth-limit"; return false; }
  value = nw_key(value);
  bool nat = pl_is_nat(value);
  if (!nat) {
    ptrdiff_t hit = ax_hmgeti(e->seen, value);
    if (hit >= 0)
      return nw_uint(e, 4, 1) && nw_uint(e, e->seen[hit].value, 4);
    hit = ax_hmgeti(e->basis, value);
    if (hit >= 0) {
      return nw_pack_basis(e, value, e->basis[hit].value);
    }
  }
  if (nat) {
    size_t n = pl_nat_byte_len(value);
    if (n > NW_BYTES || !nw_uint(e, 0, 1) || !nw_uint(e, (uint32_t)n, 4)) {
      e->error = "native-wire-byte-limit"; return false;
    }
    if (n > NW_BYTES - (size_t)ax_arrlen(e->bytes)) {
      e->error = "native-wire-byte-limit"; return false;
    }
    uint8_t* at = ax_arraddn(e->bytes, (ptrdiff_t)n);
    for (size_t i = 0; i < n; i++) at[i] = pl_nat_byte_at(value, i);
    return true;
  }
  pl_cell* p = pl_ptr(value);
  bool ok = false;
  switch (pl_tag(value)) {
  case PL_TAG_LAW:
    if (pl_law_arity(p) == 0 || pl_law_arity(p) > PL_HDR_META_MAX) {
      e->error = "native-wire-invalid-arity"; return false;
    }
    ok = nw_uint(e, 1, 1) && nw_pack_value(e, pl_law_arity(p), depth + 1) &&
         nw_pack_value(e, pl_law_name(p), depth + 1) &&
         nw_pack_value(e, pl_law_body(p), depth + 1);
    break;
  case PL_TAG_PIN:
    ok = nw_uint(e, 2, 1) && nw_pack_value(e, pl_pin_body(p), depth + 1);
    break;
  case PL_TAG_APP:
    ok = nw_uint(e, 3, 1) && nw_uint(e, pl_app_n(p), 4) &&
         nw_pack_value(e, pl_app_head(p), depth + 1);
    for (uint32_t i = 0; ok && i < pl_app_n(p); i++)
      ok = nw_pack_value(e, pl_app_args(p)[i], depth + 1);
    break;
  default: e->error = "native-wire-non-normal-value"; return false;
  }
  if (ok) {
    uint32_t index = (uint32_t)ax_hmlen(e->seen);
    ax_hmput(e->seen, value, index);
  }
  return ok;
}

pl_val pl_native_pack(pl_thread* t, size_t ab) {
  nw_encoder e = {.t = t};
  uint8_t* hashes = NULL;
  pl_val* origins = NULL;
  /* Interning a fresh seed can copy its body. Keep the pre-interning body
   * as an equivalent selector route, so values sharing that original graph
   * do not get serialized in full merely because the seed became canonical.
   * Inputs are already normalized, and pin interning does not move this heap. */
  pl_val seed_row = t->vstack[ab];
  if (pl_tag(seed_row) == PL_TAG_APP && pl_app_head(pl_ptr(seed_row)) == 0 &&
      pl_app_n(pl_ptr(seed_row)) <= NW_NODES) {
    for (uint32_t i = 0; i < pl_app_n(pl_ptr(seed_row)); i++) {
      pl_val seed = pl_resolve(pl_app_args(pl_ptr(seed_row))[i]);
      pl_val origin = 0;
      if (pl_tag(seed) == PL_TAG_PIN && pl_pin_is_proxy(pl_ptr(seed)) &&
          pl_pin_proxy_target(pl_ptr(seed)) == 0)
        origin = pl_pin_body(pl_ptr(seed));
      ax_arrpush(origins, origin);
    }
  }
  uint32_t nseeds = 0;
  bool ok = nw_seeds(t, t->vstack[ab], &nseeds, &hashes, &e.error);
  if (ok) {
    ok = nw_put(&e, nseeds ? "SRND4" : "SRNV3", 5);
    if (ok && nseeds) ok = nw_uint(&e, nseeds, 4) && nw_put(&e, hashes, (size_t)nseeds * 32u);
    if (ok && nseeds) {
      pl_val* seeds = pl_app_args(pl_ptr(t->vstack[ab]));
      for (uint32_t i = 0; i < nseeds; i++) ax_hmput(e.seen, nw_key(seeds[i]), i);
      /* Most specific explicit artifacts first; the namespace basis follows. */
      for (uint32_t i = nseeds; i > 0; i--)
        nw_index_basis(&e, seeds[i - 1], UINT32_MAX, 0, i - 1, 0);
      for (uint32_t i = nseeds; i > 0; i--) {
        ptrdiff_t root = ax_hmgeti(e.basis, nw_key(seeds[i - 1]));
        if (root >= 0 && origins[i - 1] != 0)
          nw_index_basis(&e, origins[i - 1], e.basis[root].value, 0, i - 1, 1);
      }
      nw_expand_basis(&e);
    }
    if (ok) ok = nw_pack_value(&e, t->vstack[ab + 1], 0);
  }
  ax_arrfree(hashes);
  ax_arrfree(origins);
  ax_hmfree(e.seen);
  ax_hmfree(e.basis);
  ax_arrfree(e.paths);
  pl_val answer;
  if (ok) {
    /* Bytebar sentinel is not part of the wire's 16 MiB payload budget. */
    ax_arrpush(e.bytes, 1);
    answer = nw_result(t, true, pl_nat_from_bytes(t, e.bytes, (size_t)ax_arrlen(e.bytes)));
  } else answer = nw_failure(t, e.error ? e.error : "native-wire-encode-failed");
  ax_arrfree(e.bytes);
  return answer;
}

/* First pass validates and measures the complete graph without constructing
 * executable runtime values. The second reserves once, then builds native
 * values in postorder in a no-collection window. */
typedef struct nw_node {
  uint8_t tag;
  uint8_t call_kind; /* 0 nat, 1 law, 2 pin-law, 3 other */
  uint32_t a, b, c;
  uint64_t arity;
} nw_node;
typedef struct nw_decoder {
  pl_thread* t;
  size_t ab;
  uint8_t* bytes;
  size_t len, pos, cells;
  uint32_t visits, nseeds;
  nw_node* nodes;
  uint32_t* refs;
  uint32_t* args;
  bool paths;
  const char* error;
} nw_decoder;

static bool nw_follow(nw_decoder* d, nw_node n, pl_val* out) {
  pl_val value = pl_app_args(pl_ptr(d->t->vstack[d->ab]))[n.a];
  for (uint32_t i = 0; i < n.c; i++) {
    uint32_t step = 0;
    for (uint32_t j = 0; j < 4; j++) step |= (uint32_t)d->bytes[n.b + i * 4u + j] << (j * 8);
    value = nw_key(value);
    if (pl_is_nat(value)) return false;
    pl_cell* p = pl_ptr(value);
    if (pl_tag(value) == PL_TAG_PIN && step == 0) value = pl_pin_body(p);
    else if (pl_tag(value) == PL_TAG_LAW && step < 2) value = step ? pl_law_body(p) : pl_law_name(p);
    else if (pl_tag(value) == PL_TAG_APP && step <= pl_app_n(p))
      value = step ? pl_app_args(p)[step - 1] : pl_app_head(p);
    else return false;
  }
  *out = nw_key(value); return true;
}

static void nw_describe(nw_node* n, pl_val value) {
  if (pl_is_nat(value)) n->call_kind = 0;
  else if (pl_tag(value) == PL_TAG_LAW) {
    n->call_kind = 1; n->arity = pl_law_arity(pl_ptr(value));
  } else if (pl_tag(value) == PL_TAG_PIN) {
    pl_val body = nw_key(pl_pin_body(pl_ptr(value)));
    if (pl_tag(body) == PL_TAG_LAW) { n->call_kind = 2; n->arity = pl_law_arity(pl_ptr(body)); }
  }
}

static bool nw_read(nw_decoder* d, uint32_t n, uint32_t* value) {
  if (n > d->len - d->pos) { d->error = "native-wire-truncated"; return false; }
  *value = 0;
  for (uint32_t i = 0; i < n; i++) *value |= (uint32_t)d->bytes[d->pos++] << (i * 8);
  return true;
}
static bool nw_parse(nw_decoder* d, uint32_t depth, uint32_t* out) {
  if (++d->visits > NW_NODES || !nw_charge(d->t)) {
    d->error = "native-wire-node-limit"; return false;
  }
  if (depth > NW_DEPTH) { d->error = "native-wire-depth-limit"; return false; }
  uint32_t tag;
  if (!nw_read(d, 1, &tag)) return false;
  nw_node n = {.tag = (uint8_t)tag, .call_kind = 3};
  size_t cells = 0;
  if (tag == 4) {
    uint32_t ref;
    if (!nw_read(d, 4, &ref)) return false;
    if (ref >= (uint32_t)ax_arrlen(d->refs)) {
      d->error = "native-wire-invalid-reference"; return false;
    }
    *out = d->refs[ref]; return true;
  }
  if (tag == 5 && d->paths) {
    if (!nw_read(d, 4, &n.a) || !nw_read(d, 4, &n.c)) return false;
    if (n.a >= d->nseeds || n.c > NW_DEPTH || n.c > NW_NODES - d->visits || (size_t)n.c * 4u > d->len - d->pos) {
      d->error = "native-wire-invalid-basis-path"; return false;
    }
    n.b = (uint32_t)d->pos; d->pos += (size_t)n.c * 4u; d->visits += n.c;
    pl_val value;
    if (!nw_follow(d, n, &value) || pl_is_nat(value)) {
      d->error = "native-wire-invalid-basis-path"; return false;
    }
    nw_describe(&n, value);
  } else if (tag == 0) {
    if (!nw_read(d, 4, &n.b)) return false;
    n.a = (uint32_t)d->pos;
    if (n.b > d->len - d->pos) { d->error = "native-wire-truncated"; return false; }
    if ((n.b + 7u) / 8u > PL_HDR_META_MAX) { d->error = "native-wire-natural-limit"; return false; }
    if (n.b && d->bytes[d->pos + n.b - 1] == 0) {
      d->error = "native-wire-noncanonical-natural"; return false;
    }
    d->pos += n.b;
    n.call_kind = 0;
    if (n.b > 7) cells = PL_NAT_CELLS((n.b + 7u) / 8u);
  } else if (tag == 1) {
    uint32_t arity;
    if (!nw_parse(d, depth + 1, &arity) || !nw_parse(d, depth + 1, &n.a) ||
        !nw_parse(d, depth + 1, &n.b)) return false;
    nw_node an = d->nodes[arity];
    if (an.tag != 0 || an.b == 0 || an.b > 3) {
      d->error = "native-wire-invalid-arity"; return false;
    }
    for (uint32_t i = 0; i < an.b; i++) n.arity |= (uint64_t)d->bytes[an.a + i] << (i * 8);
    if (n.arity > PL_HDR_META_MAX) { d->error = "native-wire-invalid-arity"; return false; }
    n.call_kind = 1; cells = PL_LAW_CELLS;
  } else if (tag == 2) {
    if (!nw_parse(d, depth + 1, &n.a)) return false;
    nw_node body = d->nodes[n.a];
    if (body.call_kind == 1) { n.call_kind = 2; n.arity = body.arity; }
    cells = PL_PIN_CELLS(0);
  } else if (tag == 3) {
    if (!nw_read(d, 4, &n.c)) return false;
    if (n.c == 0 || n.c > NW_NODES - d->visits) {
      d->error = "native-wire-invalid-row"; return false;
    }
    if (!nw_parse(d, depth + 1, &n.a)) return false;
    nw_node head = d->nodes[n.a];
    if (!(head.call_kind == 0 || ((head.call_kind == 1 || head.call_kind == 2) && head.arity > n.c))) {
      d->error = "native-wire-reducible-application"; return false;
    }
    n.b = (uint32_t)ax_arrlen(d->args);
    if ((size_t)n.c > NW_NODES - (size_t)ax_arrlen(d->args)) {
      d->error = "native-wire-node-limit"; return false;
    }
    ax_arraddn(d->args, n.c);
    for (uint32_t i = 0; i < n.c; i++) {
      uint32_t arg;
      if (!nw_parse(d, depth + 1, &arg)) return false;
      d->args[n.b + i] = arg;
    }
    cells = PL_APP_CELLS(n.c);
  } else { d->error = "native-wire-invalid-tag"; return false; }
  if (cells > NW_CELLS - d->cells || (size_t)ax_arrlen(d->nodes) >= NW_NODES) {
    d->error = "native-wire-allocation-limit"; return false;
  }
  d->cells += cells;
  *out = (uint32_t)ax_arrlen(d->nodes);
  ax_arrpush(d->nodes, n);
  if (tag != 0) ax_arrpush(d->refs, *out);
  return true;
}

static pl_val nw_build(pl_thread* t, size_t ab, nw_decoder* d, uint32_t root) {
  pl_val* values = calloc((size_t)ax_arrlen(d->nodes), sizeof(pl_val));
  pl_val* args = malloc(((size_t)ax_arrlen(d->args) + 1u) * sizeof(pl_val));
  if (!values || !args) {
    free(values); free(args); return nw_failure(t, "native-wire-allocation-failed");
  }
  pl_gc_reserve(t, d->cells);
  PL_GC_FORBID(t);
  if (d->nseeds) memcpy(values, pl_app_args(pl_ptr(t->vstack[ab])), d->nseeds * sizeof(pl_val));
  for (size_t i = d->nseeds; i < (size_t)ax_arrlen(d->nodes); i++) {
    nw_node n = d->nodes[i];
    if (n.tag == 5) {
      bool ok = nw_follow(d, n, &values[i]);
      ax_assume(ok, "validated native basis path changed");
    } else if (n.tag == 0) {
      if (n.b <= 7) {
        for (uint32_t j = 0; j < n.b; j++) values[i] |= (uint64_t)d->bytes[n.a + j] << (j * 8);
      } else {
        size_t limbs = (n.b + 7u) / 8u;
        uint64_t* data;
        values[i] = pl_mk_nat_limbs(t, limbs, &data);
        memset(data, 0, limbs * 8u);
        for (uint32_t j = 0; j < n.b; j++) data[j / 8u] |= (uint64_t)d->bytes[n.a + j] << ((j % 8u) * 8u);
        values[i] = pl_nat_trim(values[i]);
      }
    } else if (n.tag == 1) {
      values[i] = pl_mk_law(t, n.arity, values[n.a], values[n.b]);
    } else if (n.tag == 2) {
      pl_cell* p = pl_bump(t, PL_PIN_CELLS(0));
      p[0] = pl_hdr_make(PL_K_PIN, PL_F_PIN_PROXY | PL_F_NORMAL, 0, PL_PIN_CELLS(0));
      memset(p + 1, 0, 4 * sizeof(pl_cell));
      p[5] = values[n.a]; p[6] = 0;
      values[i] = pl_make(PL_TAG_PIN, p);
    } else {
      for (uint32_t j = 0; j < n.c; j++) args[j] = values[d->args[n.b + j]];
      values[i] = pl_mk_app_from(t, values[n.a], n.c, args);
    }
    if (n.tag != 5 && !pl_is_nat(values[i])) pl_ptr(values[i])[0] = pl_hdr_set_flag(pl_ptr(values[i])[0], PL_F_NORMAL);
  }
  pl_val answer = values[root];
  PL_GC_ALLOW(t);
  free(values); free(args);
  return nw_result(t, true, answer);
}

pl_val pl_native_unpack(pl_thread* t, size_t ab) {
  nw_decoder d = {.t = t, .ab = ab};
  uint8_t* hashes = NULL;
  pl_val bytes = t->vstack[ab + 1];
  if (!pl_is_nat(bytes)) return nw_failure(t, "native-wire-size");
  size_t len = pl_nat_byte_len(bytes);
  if (len < 7 || len > NW_BYTES + 1u || pl_nat_byte_at(bytes, len - 1) != 1)
    return nw_failure(t, "native-wire-size");
  d.len = len - 1;
  d.bytes = malloc(d.len);
  if (!d.bytes) return nw_failure(t, "native-wire-allocation-failed");
  for (size_t i = 0; i < d.len; i++) d.bytes[i] = pl_nat_byte_at(bytes, i);
  d.paths = memcmp(d.bytes, "SRND4", 5) == 0;
  bool delta = d.paths || memcmp(d.bytes, "SRND3", 5) == 0;
  bool ok = delta || memcmp(d.bytes, "SRNV3", 5) == 0;
  if (!ok) d.error = "native-wire-version";
  if (ok) ok = nw_seeds(t, t->vstack[ab], &d.nseeds, &hashes, &d.error);
  d.pos = 5;
  if (ok && delta) {
    uint32_t count;
    ok = nw_read(&d, 4, &count);
    if (ok && (count != d.nseeds || count == 0 || (size_t)count * 32u > d.len - d.pos ||
               memcmp(d.bytes + d.pos, hashes, (size_t)count * 32u) != 0)) {
      ok = false; d.error = "native-wire-basis-mismatch";
    }
    if (ok) d.pos += (size_t)count * 32u;
  } else if (ok && d.nseeds) { ok = false; d.error = "native-wire-basis-mismatch"; }
  if (ok && d.nseeds) {
    pl_val* seeds = pl_app_args(pl_ptr(t->vstack[ab]));
    for (uint32_t i = 0; i < d.nseeds; i++) {
      pl_val body = pl_resolve(pl_pin_body(pl_ptr(seeds[i])));
      nw_node n = {.tag = 2, .call_kind = 3};
      if (pl_tag(body) == PL_TAG_LAW) { n.call_kind = 2; n.arity = pl_law_arity(pl_ptr(body)); }
      ax_arrpush(d.nodes, n); ax_arrpush(d.refs, i);
    }
  }
  uint32_t root = 0;
  if (ok) ok = nw_parse(&d, 0, &root);
  if (ok && d.pos != d.len) { ok = false; d.error = "native-wire-trailing-data"; }
  pl_val answer = ok ? nw_build(t, ab, &d, root) : nw_failure(t, d.error);
  ax_arrfree(hashes); ax_arrfree(d.nodes); ax_arrfree(d.refs); ax_arrfree(d.args); free(d.bytes);
  return answer;
}
