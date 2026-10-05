#include "silo_internal.h"

#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include <openssl/evp.h>

#include "axsys/assume.h"
#include "axsys/ds.h"
#include "axsys/sha256.h"
#include "plan/build.h"
#include "plan/nat.h"
#include "store_internal.h"

static const uint8_t silo_magic[5] = {'S', 'I', 'L', 'O', 1};
static const uint8_t silo_leaf_domain[] = "SILO-NAT-LEAF-v1";
static const uint8_t silo_node_domain[] = "SILO-NAT-NODE-v1";
static const uint8_t silo_root_domain[] = "SILO-NAT-ROOT-v1";

static bool silo_error(char* err, size_t cap, const char* fmt, ...) {
  if (err != NULL && cap != 0) {
    va_list ap;
    va_start(ap, fmt);
    (void)vsnprintf(err, cap, fmt, ap);
    va_end(ap);
  }
  return false;
}

static void put16le(uint8_t out[2], uint16_t v) {
  out[0] = (uint8_t)v;
  out[1] = (uint8_t)(v >> 8);
}

static void put32le(uint8_t out[4], uint32_t v) {
  for (unsigned i = 0; i < 4; i++)
    out[i] = (uint8_t)(v >> (8u * i));
}

static void put64le(uint8_t out[8], uint64_t v) {
  for (unsigned i = 0; i < 8; i++)
    out[i] = (uint8_t)(v >> (8u * i));
}

static uint64_t getle(const uint8_t* in, size_t n) {
  uint64_t v = 0;
  size_t take = n < 8 ? n : 8;
  for (size_t i = 0; i < take; i++)
    v |= (uint64_t)in[i] << (8u * i);
  return v;
}

static uint8_t width_u64(uint64_t v) {
  uint8_t n = 0;
  do {
    n++;
    v >>= 8;
  } while (v != 0);
  return n;
}

static uint64_t split_power(uint64_t n) {
  ax_assume(n > 1, "split_power");
  uint64_t k = 1;
  while (k <= (n - 1) / 2)
    k <<= 1;
  return k;
}

static uint32_t crc32c_update(uint32_t crc, const uint8_t* p, size_t n) {
  while (n-- != 0) {
    crc ^= *p++;
    for (unsigned k = 0; k < 8; k++)
      crc = (crc >> 1) ^ (UINT32_C(0x82f63b78) & (0u - (crc & 1u)));
  }
  return crc;
}

static void silo_leaf_hash(uint64_t index, const uint8_t* bytes, uint16_t len,
                           uint8_t out[32]) {
  uint8_t buf[sizeof(silo_leaf_domain) + 8 + 2 + PL_SILO_LEAF_BYTES];
  size_t off = 0;
  memcpy(buf + off, silo_leaf_domain, sizeof(silo_leaf_domain));
  off += sizeof(silo_leaf_domain);
  put64le(buf + off, index);
  off += 8;
  put16le(buf + off, len);
  off += 2;
  memcpy(buf + off, bytes, len);
  off += len;
  ax_sha256(buf, off, out);
}

static void silo_node_hash(uint64_t start, uint64_t count,
                           const uint8_t left[32], const uint8_t right[32],
                           uint8_t out[32]) {
  uint8_t buf[sizeof(silo_node_domain) + 8 + 8 + 32 + 32];
  size_t off = 0;
  memcpy(buf + off, silo_node_domain, sizeof(silo_node_domain));
  off += sizeof(silo_node_domain);
  put64le(buf + off, start);
  off += 8;
  put64le(buf + off, count);
  off += 8;
  memcpy(buf + off, left, 32);
  off += 32;
  memcpy(buf + off, right, 32);
  off += 32;
  ax_sha256(buf, off, out);
}

static void silo_nat_root_hash(uint64_t bit_length, const uint8_t tree[32],
                               uint8_t out[32]) {
  uint8_t buf[sizeof(silo_root_domain) + 8 + 32];
  size_t off = 0;
  memcpy(buf + off, silo_root_domain, sizeof(silo_root_domain));
  off += sizeof(silo_root_domain);
  put64le(buf + off, bit_length);
  off += 8;
  memcpy(buf + off, tree, 32);
  off += 32;
  ax_sha256(buf, off, out);
}

static bool swrite(pl_silo_writer* w, const void* bytes, size_t len, char* err,
                   size_t cap) {
  if (len > UINT64_MAX - w->pos)
    return silo_error(err, cap, "Silo output length overflow");
  if (len != 0 && !w->write(w->ctx, bytes, len))
    return silo_error(err, cap, "Silo output write failed");
  w->pos += len;
  return true;
}

static bool swrite_u8(pl_silo_writer* w, uint8_t v, char* err, size_t cap) {
  return swrite(w, &v, 1, err, cap);
}

static bool swrite_le(pl_silo_writer* w, uint64_t v, uint8_t width, char* err,
                      size_t cap) {
  uint8_t b[8];
  put64le(b, v);
  return swrite(w, b, width, err, cap);
}

static bool swrite_varnat(pl_silo_writer* w, uint64_t v, char* err,
                          size_t cap) {
  uint8_t width = v == 0 ? 0 : width_u64(v);
  return swrite_u8(w, width, err, cap) && swrite_le(w, v, width, err, cap);
}

static bool sread(pl_silo_reader* r, void* bytes, size_t len, char* err,
                  size_t cap) {
  if (r->pos > r->len || len > r->len - r->pos)
    return silo_error(err, cap, "truncated Silo stream at byte %llu",
                      (unsigned long long)r->pos);
  if (len != 0 && !r->read(r->ctx, bytes, len))
    return silo_error(err, cap, "Silo input read failed at byte %llu",
                      (unsigned long long)r->pos);
  r->pos += len;
  return true;
}

static bool sread_crc(pl_silo_reader* r, void* bytes, size_t len, uint32_t* crc,
                      char* err, size_t cap) {
  if (!sread(r, bytes, len, err, cap))
    return false;
  *crc = crc32c_update(*crc, bytes, len);
  return true;
}

static bool srewind(pl_silo_reader* r, char* err, size_t cap) {
  if (!r->rewind(r->ctx))
    return silo_error(err, cap, "Silo input rewind failed");
  r->pos = 0;
  return true;
}

/* ----------------------------------------------------------------------- */
/* Canonical encoder                                                        */

typedef struct enc_pin_idx {
  pl_hash key;
  uint32_t value;
} enc_pin_idx;

typedef struct silo_enc {
  pl_silo_writer* w;
  enc_pin_idx* pin_idx;
  pl_silo_pin_hash_fn pin_hash;
  void* pin_hash_ctx;
  char* err;
  size_t err_cap;
} silo_enc;

static const uint8_t* encode_pin_hash(silo_enc* e, pl_val pin) {
  return e->pin_hash != NULL ? e->pin_hash(e->pin_hash_ctx, pin)
                             : pl_pin_hash(pin);
}

typedef struct mnat_node {
  uint64_t start;
  uint64_t count;
  uint32_t left;
  uint32_t right;
  uint8_t hash[32];
} mnat_node;

typedef struct mnat_tree {
  mnat_node* nodes;
  pl_val nat;
  uint64_t byte_length;
} mnat_tree;

static uint64_t nat_bit_length(pl_val v, uint64_t byte_length) {
  if (byte_length == 0)
    return 0;
  uint8_t top = pl_nat_byte_at(v, (size_t)byte_length - 1);
  unsigned bits = 0;
  while (top != 0) {
    bits++;
    top >>= 1;
  }
  return (byte_length - 1) * 8 + bits;
}

static bool encode_nat_bytes(silo_enc* e, pl_val v, uint64_t len) {
  uint8_t buf[4096];
  uint64_t off = 0;
  while (off < len) {
    size_t n = (size_t)(len - off);
    if (n > sizeof(buf))
      n = sizeof(buf);
    for (size_t i = 0; i < n; i++)
      buf[i] = pl_nat_byte_at(v, (size_t)off + i);
    if (!swrite(e->w, buf, n, e->err, e->err_cap))
      return false;
    off += n;
  }
  return true;
}

static uint32_t mnat_build(mnat_tree* t, uint64_t start, uint64_t count) {
  mnat_node node = {
      .start = start, .count = count, .left = UINT32_MAX, .right = UINT32_MAX};
  if (count == 1) {
    uint8_t bytes[PL_SILO_LEAF_BYTES];
    uint64_t off = start * PL_SILO_LEAF_BYTES;
    uint64_t remaining = t->byte_length - off;
    uint16_t len = remaining > PL_SILO_LEAF_BYTES ? PL_SILO_LEAF_BYTES
                                                  : (uint16_t)remaining;
    for (uint16_t i = 0; i < len; i++)
      bytes[i] = pl_nat_byte_at(t->nat, (size_t)off + i);
    silo_leaf_hash(start, bytes, len, node.hash);
  } else {
    uint64_t k = split_power(count);
    node.left = mnat_build(t, start, k);
    node.right = mnat_build(t, start + k, count - k);
    silo_node_hash(start, count, t->nodes[node.left].hash,
                   t->nodes[node.right].hash, node.hash);
  }
  ax_arrpush(t->nodes, node);
  return (uint32_t)(ax_arrlen(t->nodes) - 1);
}

static void node_queue_insert(uint32_t** queue, const mnat_node* nodes,
                              uint32_t idx) {
  ptrdiff_t n = ax_arrlen(*queue);
  ptrdiff_t at = 0;
  while (at < n && nodes[(*queue)[at]].start < nodes[idx].start)
    at++;
  stbds_arrins(*queue, at, idx);
}

static bool encode_mnat(silo_enc* e, pl_val v, uint64_t byte_length) {
  uint64_t bit_length = nat_bit_length(v, byte_length);
  uint64_t leaf_count =
      (byte_length + PL_SILO_LEAF_BYTES - 1) / PL_SILO_LEAF_BYTES;
  mnat_tree tree = {.nat = v, .byte_length = byte_length};
  uint32_t root = mnat_build(&tree, 0, leaf_count);
  uint8_t root_hash[32];
  silo_nat_root_hash(bit_length, tree.nodes[root].hash, root_hash);

  uint8_t length_width = width_u64(bit_length);
  uint64_t max_page =
      byte_length < PL_SILO_PAGE_BYTES ? byte_length : PL_SILO_PAGE_BYTES;
  uint8_t page_width = width_u64(max_page);
  if (!swrite_u8(e->w, 0xf9, e->err, e->err_cap) ||
      !swrite_u8(e->w, 0, e->err, e->err_cap) ||
      !swrite_u8(e->w, (uint8_t)(length_width - 1), e->err, e->err_cap) ||
      !swrite_u8(e->w, (uint8_t)(page_width - 1), e->err, e->err_cap) ||
      !swrite_le(e->w, bit_length, length_width, e->err, e->err_cap) ||
      !swrite(e->w, root_hash, 32, e->err, e->err_cap))
    goto fail;

  /* Initial proof and initial unopened-node queue. */
  if (!swrite(e->w, tree.nodes[0].hash, 32, e->err, e->err_cap))
    goto fail;
  uint32_t* frontier = NULL;
  uint32_t cur = root;
  while (tree.nodes[cur].count > 1) {
    uint32_t right = tree.nodes[cur].right;
    if (!swrite(e->w, tree.nodes[right].hash, 32, e->err, e->err_cap)) {
      ax_arrfree(frontier);
      goto fail;
    }
    if (tree.nodes[right].count > 1)
      node_queue_insert(&frontier, tree.nodes, right);
    cur = tree.nodes[cur].left;
  }

  uint64_t payload_off = 0;
  uint64_t leaf_off = 0;
  uint8_t payload[4096];
  while (payload_off < byte_length) {
    uint64_t page_len = byte_length - payload_off;
    if (page_len > PL_SILO_PAGE_BYTES)
      page_len = PL_SILO_PAGE_BYTES;
    if (!swrite_le(e->w, page_len, page_width, e->err, e->err_cap)) {
      ax_arrfree(frontier);
      goto fail;
    }
    uint64_t in_page = 0;
    while (in_page < page_len) {
      uint64_t leaf_rem = PL_SILO_LEAF_BYTES - leaf_off;
      uint64_t seg = page_len - in_page;
      if (seg > leaf_rem)
        seg = leaf_rem;
      uint64_t done = 0;
      while (done < seg) {
        size_t n = (size_t)(seg - done);
        if (n > sizeof(payload))
          n = sizeof(payload);
        for (size_t i = 0; i < n; i++)
          payload[i] = pl_nat_byte_at(v, (size_t)(payload_off + done + i));
        if (!swrite(e->w, payload, n, e->err, e->err_cap)) {
          ax_arrfree(frontier);
          goto fail;
        }
        done += n;
      }
      payload_off += seg;
      in_page += seg;
      leaf_off += seg;
      bool leaf_done =
          leaf_off == PL_SILO_LEAF_BYTES || payload_off == byte_length;
      if (leaf_done) {
        leaf_off = 0;
        if (ax_arrlen(frontier) != 0) {
          uint32_t opening = frontier[0];
          stbds_arrdel(frontier, 0);
          mnat_node* p = &tree.nodes[opening];
          if (!swrite(e->w, tree.nodes[p->left].hash, 32, e->err, e->err_cap) ||
              !swrite(e->w, tree.nodes[p->right].hash, 32, e->err,
                      e->err_cap)) {
            ax_arrfree(frontier);
            goto fail;
          }
          if (tree.nodes[p->left].count > 1)
            node_queue_insert(&frontier, tree.nodes, p->left);
          if (tree.nodes[p->right].count > 1)
            node_queue_insert(&frontier, tree.nodes, p->right);
        }
      }
    }
  }
  if (ax_arrlen(frontier) != 0) {
    ax_arrfree(frontier);
    silo_error(e->err, e->err_cap, "internal MNAT frontier did not close");
    goto fail;
  }
  ax_arrfree(frontier);
  ax_arrfree(tree.nodes);
  return true;

fail:
  ax_arrfree(tree.nodes);
  return false;
}

static bool encode_node(silo_enc* e, pl_val v, uint32_t depth);

static bool encode_u64_nat(silo_enc* e, uint64_t v) {
  if (v <= 63)
    return swrite_u8(e->w, (uint8_t)(0x80u + v), e->err, e->err_cap);
  uint8_t width = width_u64(v);
  return swrite_u8(e->w, (uint8_t)(0xc0u | width), e->err, e->err_cap) &&
         swrite_le(e->w, v, width, e->err, e->err_cap);
}

static bool encode_app_range(silo_enc* e, pl_val head, const pl_val* args,
                             uint32_t n, uint32_t depth) {
  if (depth > PL_SILO_MAX_DEPTH)
    return silo_error(e->err, e->err_cap, "Silo nesting exceeds %u",
                      PL_SILO_MAX_DEPTH);
  uint32_t outer = n <= 15 ? n : n % 15;
  if (outer == 0)
    outer = 15;
  uint32_t inner = n - outer;
  if (!swrite_u8(e->w, (uint8_t)(outer << 3), e->err, e->err_cap))
    return false;
  if (inner != 0) {
    if (!encode_app_range(e, head, args, inner, depth + 1))
      return false;
  } else if (!encode_node(e, head, depth + 1)) {
    return false;
  }
  for (uint32_t i = inner; i < n; i++)
    if (!encode_node(e, args[i], depth + 1))
      return false;
  return true;
}

static bool encode_node(silo_enc* e, pl_val v, uint32_t depth) {
  if (depth > PL_SILO_MAX_DEPTH)
    return silo_error(e->err, e->err_cap, "Silo nesting exceeds %u",
                      PL_SILO_MAX_DEPTH);
  if (pl_is_nat(v)) {
    uint64_t len = pl_nat_byte_len(v);
    if (len == 0)
      return swrite_u8(e->w, 0x80, e->err, e->err_cap);
    if (len == 1) {
      uint8_t b = pl_nat_byte_at(v, 0);
      if (b <= 63)
        return swrite_u8(e->w, (uint8_t)(0x80u + b), e->err, e->err_cap);
    }
    if (len <= 31)
      return swrite_u8(e->w, (uint8_t)(0xc0u | len), e->err, e->err_cap) &&
             encode_nat_bytes(e, v, len);
    if (len <= PL_SILO_NAT_CUTOVER) {
      uint8_t lw = width_u64(len);
      return swrite_u8(e->w, (uint8_t)(0xe0u | lw), e->err, e->err_cap) &&
             swrite_le(e->w, len, lw, e->err, e->err_cap) &&
             encode_nat_bytes(e, v, len);
    }
    return encode_mnat(e, v, len);
  }

  pl_cell* p = pl_ptr(v);
  switch (pl_tag(v)) {
  case PL_TAG_PIN: {
    const uint8_t* bytes = encode_pin_hash(e, v);
    if (bytes == NULL)
      return silo_error(e->err, e->err_cap,
                        "cannot encode a provisional PIN reference");
    pl_hash hash;
    memcpy(hash.b, bytes, sizeof(hash.b));
    ptrdiff_t at = ax_hmgeti(e->pin_idx, hash);
    if (at < 0)
      return silo_error(e->err, e->err_cap,
                        "PIN missing from canonical Silo table");
    uint64_t index = e->pin_idx[at].value;
    uint8_t width = width_u64(index);
    if (!swrite_u8(e->w, (uint8_t)(0xf0u + width), e->err, e->err_cap))
      return false;
    return swrite_le(e->w, index, width, e->err, e->err_cap);
  }
  case PL_TAG_LAW:
    if (pl_law_arity(p) == 0 || pl_law_arity(p) > PL_NAT63_MAX)
      return silo_error(e->err, e->err_cap,
                        "LAW arity is not a direct nonzero runtime natural");
    return swrite_u8(e->w, 0xf0, e->err, e->err_cap) &&
           encode_node(e, pl_law_name(p), depth + 1) &&
           encode_u64_nat(e, pl_law_arity(p)) &&
           encode_node(e, pl_law_body(p), depth + 1);
  case PL_TAG_APP: {
    uint32_t n = pl_app_n(p);
    if (n == 0)
      return silo_error(e->err, e->err_cap, "cannot encode empty APP");
    return encode_app_range(e, pl_app_head(p), pl_app_args(p), n, depth);
  }
  default:
    return silo_error(e->err, e->err_cap,
                      "cannot encode non-normal PLAN tag 0x%llx",
                      (unsigned long long)pl_tag(v));
  }
}

bool pl_silo_encode_resolved(pl_silo_writer* w, pl_val root,
                             const pl_val* subpins, size_t nsub,
                             pl_silo_pin_hash_fn pin_hash, void* pin_hash_ctx,
                             char* err, size_t err_cap) {
  if (w == NULL || w->write == NULL)
    return silo_error(err, err_cap, "invalid Silo writer");
  if (nsub > PL_SILO_MAX_PIN_COUNT)
    return silo_error(err, err_cap, "too many Silo pins");
  silo_enc e = {.w = w,
                .pin_hash = pin_hash,
                .pin_hash_ctx = pin_hash_ctx,
                .err = err,
                .err_cap = err_cap};
  for (size_t i = 0; i < nsub; i++) {
    if (pl_tag(subpins[i]) != PL_TAG_PIN) {
      ax_hmfree(e.pin_idx);
      return silo_error(err, err_cap, "non-PIN in Silo pin table");
    }
    const uint8_t* bytes = encode_pin_hash(&e, subpins[i]);
    if (bytes == NULL) {
      ax_hmfree(e.pin_idx);
      return silo_error(err, err_cap, "provisional PIN in Silo pin table");
    }
    pl_hash hash;
    memcpy(hash.b, bytes, sizeof(hash.b));
    if (ax_hmgeti(e.pin_idx, hash) >= 0) {
      ax_hmfree(e.pin_idx);
      return silo_error(err, err_cap, "duplicate Silo pin table hash");
    }
    ax_hmput(e.pin_idx, hash, (uint32_t)i);
  }
  bool ok = swrite(w, silo_magic, sizeof(silo_magic), err, err_cap) &&
            swrite_varnat(w, nsub, err, err_cap);
  for (size_t i = 0; ok && i < nsub; i++) {
    const uint8_t* hash = encode_pin_hash(&e, subpins[i]);
    ok = hash != NULL && swrite(w, hash, 32, err, err_cap);
  }
  if (ok)
    ok = encode_node(&e, root, 0);
  ax_hmfree(e.pin_idx);
  return ok;
}

bool pl_silo_encode(pl_silo_writer* w, pl_val root, const pl_val* subpins,
                    size_t nsub, char* err, size_t err_cap) {
  return pl_silo_encode_resolved(w, root, subpins, nsub, NULL, NULL, err,
                                 err_cap);
}

typedef struct silo_buffer_sink {
  uint8_t* bytes;
} silo_buffer_sink;

static bool silo_buffer_write(void* ctx, const uint8_t* bytes, size_t len) {
  silo_buffer_sink* sink = ctx;
  if (len > (size_t)PTRDIFF_MAX ||
      ax_arrlen(sink->bytes) > PTRDIFF_MAX - (ptrdiff_t)len)
    return false;
  memcpy(ax_arraddn(sink->bytes, (ptrdiff_t)len), bytes, len);
  return true;
}

bool pl_silo_encode_buffer(pl_val root, const pl_val* subpins, size_t nsub,
                           pl_silo_pin_hash_fn pin_hash, void* pin_hash_ctx,
                           uint8_t** out_bytes, size_t* out_len,
                           uint8_t out_hash[32], char* err, size_t err_cap) {
  if (out_bytes == NULL || out_len == NULL || out_hash == NULL)
    return silo_error(err, err_cap, "invalid Silo buffer output");
  *out_bytes = NULL;
  *out_len = 0;
  silo_buffer_sink sink = {0};
  pl_silo_writer writer = {.ctx = &sink, .write = silo_buffer_write};
  if (!pl_silo_encode_resolved(&writer, root, subpins, nsub, pin_hash,
                               pin_hash_ctx, err, err_cap)) {
    ax_arrfree(sink.bytes);
    return false;
  }
  if (writer.pos != (uint64_t)ax_arrlen(sink.bytes)) {
    ax_arrfree(sink.bytes);
    return silo_error(err, err_cap, "Silo buffer length mismatch");
  }
  ax_sha256(sink.bytes, (size_t)ax_arrlen(sink.bytes), out_hash);
  *out_len = (size_t)ax_arrlen(sink.bytes);
  *out_bytes = sink.bytes;
  return true;
}

typedef struct silo_hash_sink {
  EVP_MD_CTX* digest;
} silo_hash_sink;

static bool silo_hash_write(void* ctx, const uint8_t* bytes, size_t len) {
  silo_hash_sink* sink = ctx;
  return EVP_DigestUpdate(sink->digest, bytes, len) == 1;
}

bool pl_silo_hash(pl_val root, const pl_val* subpins, size_t nsub,
                  uint8_t out[32], char* err, size_t err_cap) {
  if (out == NULL)
    return silo_error(err, err_cap, "invalid Silo hash output");
  EVP_MD_CTX* digest = EVP_MD_CTX_new();
  if (digest == NULL)
    return silo_error(err, err_cap, "cannot allocate Silo hash context");
  if (EVP_DigestInit_ex(digest, EVP_sha256(), NULL) != 1) {
    EVP_MD_CTX_free(digest);
    return silo_error(err, err_cap, "cannot initialize Silo hash");
  }

  silo_hash_sink sink = {.digest = digest};
  pl_silo_writer writer = {.ctx = &sink, .write = silo_hash_write};
  bool ok = pl_silo_encode(&writer, root, subpins, nsub, err, err_cap);
  unsigned int hash_len = 0;
  if (ok && (EVP_DigestFinal_ex(digest, out, &hash_len) != 1 || hash_len != 32))
    ok = silo_error(err, err_cap, "cannot finalize Silo hash");
  EVP_MD_CTX_free(digest);
  return ok;
}

/* ----------------------------------------------------------------------- */
/* General decoder and canonical validator                                 */

typedef enum silo_node_kind {
  SILO_NODE_NAT,
  SILO_NODE_PIN,
  SILO_NODE_LAW,
  SILO_NODE_APP,
} silo_node_kind;

typedef struct silo_node_info {
  silo_node_kind kind;
  uint8_t wire_app_n;
  bool nat_fits;
  uint64_t nat_u64;
} silo_node_info;

typedef struct scan_pin_entry {
  pl_hash key;
  uint8_t value;
} scan_pin_entry;

typedef struct silo_dec {
  pl_silo_reader* r;
  pl_store* store;
  pl_silo_scan* scan;
  const pl_val* resolved;
  bool build;
  bool canonical;
  bool capture_header;
  bool* used;
  size_t next_canonical_pin;
  char* err;
  size_t err_cap;
} silo_dec;

static pl_cell* decode_alloc(silo_dec* d, uint64_t cells) {
  if (cells == 0 || cells > UINT32_MAX || cells > SIZE_MAX / sizeof(pl_cell)) {
    silo_error(d->err, d->err_cap, "decoded object cell count overflow");
    return NULL;
  }
  size_t bytes = (size_t)cells * sizeof(pl_cell);
  size_t mark = pl_store_mark(d->store);
  if (mark > d->store->region->cap_s ||
      bytes > d->store->region->cap_s - mark) {
    silo_error(d->err, d->err_cap,
               "decoded object exceeds remaining store-region capacity");
    return NULL;
  }
  return pl_store_alloc(d->store, (size_t)cells);
}

static bool dread(silo_dec* d, void* bytes, size_t len) {
  return sread(d->r, bytes, len, d->err, d->err_cap);
}

static bool decode_varnat(silo_dec* d, uint64_t* out) {
  uint8_t width;
  uint8_t b[8] = {0};
  if (!dread(d, &width, 1))
    return false;
  if (width > 8)
    return silo_error(d->err, d->err_cap, "varnat width %u exceeds 8", width);
  if (!dread(d, b, width))
    return false;
  uint64_t v = getle(b, width);
  if ((v == 0 && width != 0) || (v != 0 && width != width_u64(v)))
    return silo_error(d->err, d->err_cap, "nonminimal varnat");
  *out = v;
  return true;
}

static bool decode_header(silo_dec* d) {
  uint8_t magic[5];
  uint64_t count = 0;
  if (!dread(d, magic, sizeof(magic)) ||
      memcmp(magic, silo_magic, sizeof(magic)) != 0)
    return silo_error(d->err, d->err_cap, "bad Silo magic or version");
  if (!decode_varnat(d, &count))
    return false;
  if (count > PL_SILO_MAX_PIN_COUNT || count > SIZE_MAX / sizeof(pl_hash))
    return silo_error(d->err, d->err_cap, "Silo pin count exceeds limit");
  if (d->capture_header) {
    d->scan->pins =
        calloc((size_t)count ? (size_t)count : 1, sizeof(*d->scan->pins));
    if (d->scan->pins == NULL)
      return silo_error(d->err, d->err_cap, "out of memory for Silo pins");
    d->scan->pin_count = (size_t)count;
    d->used = calloc((size_t)count ? (size_t)count : 1, sizeof(bool));
    if (d->used == NULL)
      return silo_error(d->err, d->err_cap, "out of memory for Silo pins");
  } else if (count != d->scan->pin_count) {
    return silo_error(d->err, d->err_cap, "Silo pin table changed on rewind");
  }

  scan_pin_entry* unique = NULL;
  for (size_t i = 0; i < (size_t)count; i++) {
    pl_hash hash;
    if (!dread(d, hash.b, sizeof(hash.b))) {
      ax_hmfree(unique);
      return false;
    }
    if (d->capture_header) {
      if (ax_hmgeti(unique, hash) >= 0) {
        ax_hmfree(unique);
        return silo_error(d->err, d->err_cap, "duplicate Silo pin-table hash");
      }
      ax_hmput(unique, hash, 1);
      d->scan->pins[i] = hash;
    } else if (memcmp(hash.b, d->scan->pins[i].b, 32) != 0) {
      ax_hmfree(unique);
      return silo_error(d->err, d->err_cap, "Silo pin table changed on rewind");
    }
  }
  ax_hmfree(unique);
  return true;
}

typedef struct nat_accum {
  uint64_t len;
  uint64_t low;
  uint8_t last;
  pl_cell* cells;
  size_t limbs;
} nat_accum;

static bool nat_accum_init(silo_dec* d, nat_accum* a, uint64_t len) {
  memset(a, 0, sizeof(*a));
  a->len = len;
  if (len > PL_SILO_MAX_NAT_BYTES)
    return silo_error(d->err, d->err_cap,
                      "natural byte length exceeds runtime limit");
  if (d->build && len > 8) {
    uint64_t limbs64 = (len + 7) / 8;
    if (limbs64 == 0 || limbs64 > PL_SILO_MAX_PIN_COUNT)
      return silo_error(d->err, d->err_cap, "natural limb count overflow");
    a->limbs = (size_t)limbs64;
    a->cells = decode_alloc(d, PL_NAT_CELLS(a->limbs));
    if (a->cells == NULL)
      return false;
    a->cells[0] = pl_hdr_make(PL_K_NAT, PL_F_NORMAL, (uint32_t)a->limbs,
                              PL_NAT_CELLS(a->limbs));
    memset(a->cells + 1, 0, a->limbs * sizeof(pl_cell));
  }
  return true;
}

static void nat_accum_bytes(nat_accum* a, uint64_t off, const uint8_t* bytes,
                            size_t len) {
  for (size_t i = 0; i < len; i++) {
    uint64_t at = off + i;
    if (at < 8)
      a->low |= (uint64_t)bytes[i] << (8u * at);
  }
  if (len != 0)
    a->last = bytes[len - 1];
  if (a->cells != NULL)
    memcpy((uint8_t*)(a->cells + 1) + off, bytes, len);
}

static bool nat_accum_finish(silo_dec* d, nat_accum* a, pl_val* out,
                             silo_node_info* info) {
  if (a->len != 0 && a->last == 0)
    return silo_error(d->err, d->err_cap, "natural has a trailing zero byte");
  info->kind = SILO_NODE_NAT;
  info->nat_fits = a->len <= 8;
  info->nat_u64 = a->low;
  if (!d->build)
    return true;
  if (a->len == 0 || (a->len <= 8 && a->low <= PL_NAT63_MAX)) {
    *out = a->low;
    return true;
  }
  if (a->cells == NULL) {
    a->limbs = 1;
    a->cells = decode_alloc(d, PL_NAT_CELLS(1));
    if (a->cells == NULL)
      return false;
    a->cells[0] = pl_hdr_make(PL_K_NAT, PL_F_NORMAL, 1, PL_NAT_CELLS(1));
    a->cells[1] = a->low;
  }
  *out = pl_make(PL_TAG_NAT, a->cells);
  return true;
}

static bool decode_contiguous_nat(silo_dec* d, uint64_t len, pl_val* out,
                                  silo_node_info* info) {
  nat_accum a;
  if (len == 0)
    return silo_error(d->err, d->err_cap, "zero-length natural payload");
  if (!nat_accum_init(d, &a, len))
    return false;
  uint8_t buf[4096];
  uint64_t off = 0;
  while (off < len) {
    size_t n = (size_t)(len - off);
    if (n > sizeof(buf))
      n = sizeof(buf);
    if (!dread(d, buf, n))
      return false;
    nat_accum_bytes(&a, off, buf, n);
    off += n;
  }
  return nat_accum_finish(d, &a, out, info);
}

static bool decode_node(silo_dec* d, uint32_t depth, pl_val* out,
                        silo_node_info* info);

static bool decode_medium(silo_dec* d, uint8_t width, pl_val* out,
                          silo_node_info* info) {
  if (width == 0 || width > 31)
    return silo_error(d->err, d->err_cap, "invalid MEDIUM width");
  if (!decode_contiguous_nat(d, width, out, info))
    return false;
  if (d->canonical && info->nat_fits && info->nat_u64 <= 63)
    return silo_error(d->err, d->err_cap,
                      "canonical small natural must use SMOL");
  return true;
}

static bool decode_big(silo_dec* d, uint8_t length_width, pl_val* out,
                       silo_node_info* info) {
  if (length_width == 0 || length_width > 15)
    return silo_error(d->err, d->err_cap, "invalid BIG length width");
  uint8_t b[15] = {0};
  if (!dread(d, b, length_width))
    return false;
  for (uint8_t i = 8; i < length_width; i++)
    if (b[i] != 0)
      return silo_error(d->err, d->err_cap,
                        "BIG length exceeds implementation range");
  uint64_t len = getle(b, length_width);
  if (len == 0)
    return silo_error(d->err, d->err_cap, "zero-length BIG");
  if (d->canonical && length_width != width_u64(len))
    return silo_error(d->err, d->err_cap,
                      "nonminimal canonical BIG length width");
  if (d->canonical && (len < 32 || len > PL_SILO_NAT_CUTOVER))
    return silo_error(d->err, d->err_cap,
                      "canonical natural uses the wrong BIG opcode");
  return decode_contiguous_nat(d, len, out, info);
}

typedef struct proof_sibling {
  uint64_t start;
  uint64_t count;
  uint64_t parent_count;
  uint8_t hash[32];
} proof_sibling;

typedef struct unopened_node {
  uint64_t start;
  uint64_t count;
  uint8_t hash[32];
} unopened_node;

typedef struct expected_leaf {
  uint64_t index;
  uint8_t hash[32];
} expected_leaf;

static bool unopened_insert(unopened_node** list, unopened_node node) {
  ptrdiff_t n = ax_arrlen(*list);
  ptrdiff_t at = 0;
  while (at < n && (*list)[at].start < node.start)
    at++;
  if (at < n && (*list)[at].start == node.start)
    return false;
  stbds_arrins(*list, at, node);
  return true;
}

static bool expected_insert(expected_leaf** list, expected_leaf leaf) {
  ptrdiff_t n = ax_arrlen(*list);
  ptrdiff_t at = 0;
  while (at < n && (*list)[at].index < leaf.index)
    at++;
  if (at < n && (*list)[at].index == leaf.index)
    return false;
  stbds_arrins(*list, at, leaf);
  return true;
}

static bool expected_take(expected_leaf** list, uint64_t index,
                          uint8_t out[32]) {
  ptrdiff_t n = ax_arrlen(*list);
  for (ptrdiff_t i = 0; i < n; i++) {
    if ((*list)[i].index == index) {
      memcpy(out, (*list)[i].hash, 32);
      stbds_arrdel(*list, i);
      return true;
    }
    if ((*list)[i].index > index)
      break;
  }
  return false;
}

static bool decode_mnat(silo_dec* d, pl_val* out, silo_node_info* info) {
  uint8_t fixed[3];
  if (!dread(d, fixed, sizeof(fixed)))
    return false;
  uint8_t flags = fixed[0];
  uint8_t length_width = (uint8_t)(fixed[1] + 1u);
  uint8_t page_width = (uint8_t)(fixed[2] + 1u);
  if ((flags & 0xfeu) != 0)
    return silo_error(d->err, d->err_cap, "reserved MNAT flag is set");
  if (length_width > 8 || page_width > 8)
    return silo_error(d->err, d->err_cap, "invalid MNAT scalar width");
  if (d->canonical && flags != 0)
    return silo_error(d->err, d->err_cap,
                      "canonical MNAT must not carry page CRCs");

  uint8_t lenbuf[8] = {0};
  uint8_t declared_root[32];
  if (!dread(d, lenbuf, length_width) || !dread(d, declared_root, 32))
    return false;
  uint64_t bit_length = getle(lenbuf, length_width);
  if (bit_length == 0)
    return silo_error(d->err, d->err_cap, "MNAT cannot encode zero");
  if (length_width != width_u64(bit_length))
    return silo_error(d->err, d->err_cap, "nonminimal MNAT bit-length width");
  uint64_t byte_length = bit_length / 8 + (bit_length % 8 != 0);
  if (byte_length > PL_SILO_MAX_NAT_BYTES)
    return silo_error(d->err, d->err_cap, "MNAT natural exceeds runtime limit");
  if (d->canonical && byte_length <= PL_SILO_NAT_CUTOVER)
    return silo_error(d->err, d->err_cap,
                      "canonical small natural must not use MNAT");
  uint64_t leaf_count =
      (byte_length + PL_SILO_LEAF_BYTES - 1) / PL_SILO_LEAF_BYTES;

  uint8_t first_hash[32];
  if (!dread(d, first_hash, 32))
    return false;
  proof_sibling* path = NULL;
  uint64_t count = leaf_count;
  while (count > 1) {
    uint64_t k = split_power(count);
    proof_sibling sibling = {
        .start = k, .count = count - k, .parent_count = count};
    if (!dread(d, sibling.hash, 32)) {
      ax_arrfree(path);
      return false;
    }
    ax_arrpush(path, sibling);
    count = k;
  }

  uint8_t folded[32];
  memcpy(folded, first_hash, 32);
  for (ptrdiff_t i = ax_arrlen(path); i-- > 0;) {
    uint8_t parent[32];
    silo_node_hash(0, path[i].parent_count, folded, path[i].hash, parent);
    memcpy(folded, parent, 32);
  }
  uint8_t proof_root[32];
  silo_nat_root_hash(bit_length, folded, proof_root);
  if (memcmp(proof_root, declared_root, 32) != 0) {
    ax_arrfree(path);
    return silo_error(d->err, d->err_cap,
                      "MNAT initial proof does not match root hash");
  }

  unopened_node* unopened = NULL;
  expected_leaf* expected = NULL;
  expected_leaf first = {.index = 0};
  memcpy(first.hash, first_hash, 32);
  (void)expected_insert(&expected, first);
  for (ptrdiff_t i = 0; i < ax_arrlen(path); i++) {
    if (path[i].count == 1) {
      expected_leaf leaf = {.index = path[i].start};
      memcpy(leaf.hash, path[i].hash, 32);
      if (!expected_insert(&expected, leaf))
        goto frontier_bad;
    } else {
      unopened_node node = {.start = path[i].start, .count = path[i].count};
      memcpy(node.hash, path[i].hash, 32);
      if (!unopened_insert(&unopened, node))
        goto frontier_bad;
    }
  }
  ax_arrfree(path);
  path = NULL;

  nat_accum accum;
  if (!nat_accum_init(d, &accum, byte_length))
    goto fail;
  uint8_t leafbuf[PL_SILO_LEAF_BYTES];
  uint64_t payload_off = 0;
  uint64_t leaf_index = 0;
  size_t leaf_len = 0;
  uint64_t max_page = 0;
  while (payload_off < byte_length) {
    uint8_t pbuf[8] = {0};
    uint32_t crc = UINT32_MAX;
    if (!sread_crc(d->r, pbuf, page_width, &crc, d->err, d->err_cap))
      goto fail;
    uint64_t page_len = getle(pbuf, page_width);
    if (page_len == 0 || page_len > PL_SILO_MAX_NAT_BYTES ||
        page_len > byte_length - payload_off) {
      silo_error(d->err, d->err_cap, "invalid MNAT page payload length");
      goto fail;
    }
    if (page_len > max_page)
      max_page = page_len;
    uint64_t canonical_page = byte_length - payload_off;
    if (canonical_page > PL_SILO_PAGE_BYTES)
      canonical_page = PL_SILO_PAGE_BYTES;
    if (d->canonical && page_len != canonical_page) {
      silo_error(d->err, d->err_cap, "noncanonical MNAT page payload length");
      goto fail;
    }

    uint64_t page_done = 0;
    while (page_done < page_len) {
      uint64_t leaf_total = byte_length - leaf_index * PL_SILO_LEAF_BYTES;
      if (leaf_total > PL_SILO_LEAF_BYTES)
        leaf_total = PL_SILO_LEAF_BYTES;
      size_t leaf_rem = (size_t)leaf_total - leaf_len;
      size_t n = (size_t)(page_len - page_done);
      if (n > leaf_rem)
        n = leaf_rem;
      if (!sread_crc(d->r, leafbuf + leaf_len, n, &crc, d->err, d->err_cap))
        goto fail;
      nat_accum_bytes(&accum, payload_off, leafbuf + leaf_len, n);
      leaf_len += n;
      payload_off += n;
      page_done += n;

      if (leaf_len == (size_t)leaf_total) {
        uint8_t actual[32], wanted[32];
        silo_leaf_hash(leaf_index, leafbuf, (uint16_t)leaf_len, actual);
        if (!expected_take(&expected, leaf_index, wanted)) {
          silo_error(d->err, d->err_cap,
                     "MNAT leaf completed without an expected hash");
          goto fail;
        }
        if (memcmp(actual, wanted, 32) != 0) {
          silo_error(d->err, d->err_cap, "MNAT leaf %llu hash mismatch",
                     (unsigned long long)leaf_index);
          goto fail;
        }

        if (ax_arrlen(unopened) != 0) {
          unopened_node parent = unopened[0];
          stbds_arrdel(unopened, 0);
          uint8_t children[64], actual_parent[32];
          if (!sread_crc(d->r, children, sizeof(children), &crc, d->err,
                         d->err_cap))
            goto fail;
          silo_node_hash(parent.start, parent.count, children, children + 32,
                         actual_parent);
          if (memcmp(actual_parent, parent.hash, 32) != 0) {
            silo_error(d->err, d->err_cap,
                       "MNAT expansion does not match parent hash");
            goto fail;
          }
          uint64_t k = split_power(parent.count);
          unopened_node child[2] = {
              {.start = parent.start, .count = k},
              {.start = parent.start + k, .count = parent.count - k},
          };
          memcpy(child[0].hash, children, 32);
          memcpy(child[1].hash, children + 32, 32);
          for (unsigned j = 0; j < 2; j++) {
            if (child[j].start <= leaf_index) {
              silo_error(d->err, d->err_cap,
                         "MNAT expansion points behind completed leaf");
              goto fail;
            }
            if (child[j].count == 1) {
              expected_leaf leaf = {.index = child[j].start};
              memcpy(leaf.hash, child[j].hash, 32);
              if (!expected_insert(&expected, leaf)) {
                silo_error(d->err, d->err_cap, "duplicate MNAT expected leaf");
                goto fail;
              }
            } else if (!unopened_insert(&unopened, child[j])) {
              silo_error(d->err, d->err_cap,
                         "duplicate MNAT unopened interval");
              goto fail;
            }
          }
        }
        leaf_index++;
        leaf_len = 0;
      }
    }
    if ((flags & 1u) != 0) {
      uint8_t crcbuf[4];
      if (!dread(d, crcbuf, sizeof(crcbuf)))
        goto fail;
      uint32_t expected_crc = (uint32_t)getle(crcbuf, sizeof(crcbuf));
      if ((~crc) != expected_crc) {
        silo_error(d->err, d->err_cap, "MNAT page CRC32C mismatch");
        goto fail;
      }
    }
  }

  if (leaf_len != 0 || leaf_index != leaf_count || ax_arrlen(unopened) != 0 ||
      ax_arrlen(expected) != 0) {
    silo_error(d->err, d->err_cap, "MNAT traversal did not close");
    goto fail;
  }
  unsigned top_bit = (unsigned)((bit_length - 1) & 7u);
  uint8_t top_mask = (uint8_t)((1u << (top_bit + 1)) - 1u);
  if ((accum.last & (uint8_t)~top_mask) != 0 ||
      (accum.last & (uint8_t)(1u << top_bit)) == 0) {
    silo_error(d->err, d->err_cap, "MNAT final byte disagrees with bit length");
    goto fail;
  }
  if (d->canonical) {
    uint64_t canonical_max =
        byte_length < PL_SILO_PAGE_BYTES ? byte_length : PL_SILO_PAGE_BYTES;
    if (page_width != width_u64(canonical_max) || max_page != canonical_max) {
      silo_error(d->err, d->err_cap, "noncanonical MNAT page-length width");
      goto fail;
    }
  }
  ax_arrfree(unopened);
  ax_arrfree(expected);
  return nat_accum_finish(d, &accum, out, info);

frontier_bad:
  silo_error(d->err, d->err_cap, "inconsistent MNAT initial frontier");
fail:
  ax_arrfree(path);
  ax_arrfree(unopened);
  ax_arrfree(expected);
  return false;
}

static bool decode_node_opcode(silo_dec* d, uint32_t depth, uint8_t opcode,
                               pl_val* out, silo_node_info* info);

static bool decode_node(silo_dec* d, uint32_t depth, pl_val* out,
                        silo_node_info* info) {
  if (depth > PL_SILO_MAX_DEPTH)
    return silo_error(d->err, d->err_cap, "Silo nesting exceeds %u",
                      PL_SILO_MAX_DEPTH);
  uint8_t opcode;
  if (!dread(d, &opcode, 1)) return false;
  return decode_node_opcode(d, depth, opcode, out, info);
}

static bool decode_node_body(silo_dec* d, uint32_t depth, uint8_t opcode,
                             pl_val* out, silo_node_info* info);

static bool decode_node_opcode(silo_dec* d, uint32_t depth, uint8_t opcode,
                               pl_val* out, silo_node_info* info) {
  bool ok = decode_node_body(d, depth, opcode, out, info);
  if (ok && d->build) *out = pl_store_reuse_decoded(d->store, *out);
  return ok;
}

static bool decode_node_body(silo_dec* d, uint32_t depth, uint8_t opcode,
                             pl_val* out, silo_node_info* info) {
  memset(info, 0, sizeof(*info));

  if (opcode >= 0x80 && opcode <= 0xbf) {
    info->kind = SILO_NODE_NAT;
    info->nat_fits = true;
    info->nat_u64 = opcode & 0x3fu;
    if (d->build)
      *out = info->nat_u64;
    return true;
  }
  if (opcode >= 0xc1 && opcode <= 0xdf)
    return decode_medium(d, opcode & 0x1fu, out, info);
  if (opcode >= 0xe1 && opcode <= 0xef)
    return decode_big(d, opcode & 0x0fu, out, info);
  if (opcode == 0xf9)
    return decode_mnat(d, out, info);

  if (opcode >= 0x08 && opcode <= 0x78 && (opcode & 7u) == 0) {
    /* The wire splits one flat APP into 15-argument head chunks. Retaining
     * every growing prefix in the store arena is quadratic. Accumulate the
     * chunk widths, decode their arguments, then allocate only the final APP.
     * Depth and canonical validation still follow the original wire tree. */
    uint8_t* widths = NULL;
    pl_val* args = NULL;
    uint64_t total = 0;
    uint32_t head_depth = depth;
    do {
      uint8_t n = opcode >> 3;
      if (d->canonical && ax_arrlen(widths) != 0 && n != 15) {
        silo_error(d->err, d->err_cap, "noncanonical APP spine flattening");
        goto app_fail;
      }
      ax_arrpush(widths, n);
      total += n;
      if (++head_depth > PL_SILO_MAX_DEPTH || total > UINT32_MAX - 2u) {
        silo_error(d->err, d->err_cap, "decoded APP exceeds depth or size limit");
        goto app_fail;
      }
      if (!dread(d, &opcode, 1)) goto app_fail;
    } while (opcode >= 0x08 && opcode <= 0x78 && (opcode & 7u) == 0);
    pl_val head = 0;
    silo_node_info head_info;
    if (!decode_node_opcode(d, head_depth, opcode, &head, &head_info))
      goto app_fail;
    if (d->build) {
      args = malloc((size_t)total * sizeof(*args));
      if (args == NULL) {
        silo_error(d->err, d->err_cap, "out of memory for APP args");
        goto app_fail;
      }
    }
    size_t at = 0;
    for (size_t chunk = (size_t)ax_arrlen(widths); chunk > 0; chunk--) {
      for (uint8_t i = 0; i < widths[chunk - 1]; i++) {
        pl_val arg = 0;
        silo_node_info arg_info;
        if (!decode_node(d, depth + (uint32_t)chunk, &arg, &arg_info))
          goto app_fail;
        if (d->build) args[at++] = arg;
      }
    }
    info->kind = SILO_NODE_APP;
    info->wire_app_n = widths[0];
    if (d->build) {
      uint64_t arity = pl_arity(head);
      uint64_t need = (arity == 0 || arity <= total) ? 0 : arity - total;
      if (need >= (UINT64_C(1) << 20)) {
        silo_error(d->err, d->err_cap, "decoded APP need exceeds runtime limit");
        goto app_fail;
      }
      pl_cell* p = decode_alloc(d, PL_APP_CELLS((uint32_t)total));
      if (p == NULL) goto app_fail;
      p[0] = pl_hdr_make(PL_K_APP, PL_F_NORMAL, (uint32_t)need,
                         PL_APP_CELLS((uint32_t)total));
      p[1] = head;
      memcpy(p + 2, args, (size_t)total * sizeof(pl_val));
      *out = pl_make(PL_TAG_APP, p);
    }
    free(args);
    ax_arrfree(widths);
    return true;
app_fail:
    free(args);
    ax_arrfree(widths);
    return false;
  }

  if (opcode == 0xf0) {
    pl_val name = 0, arity_value = 0, body = 0;
    silo_node_info name_info, arity_info, body_info;
    if (!decode_node(d, depth + 1, &name, &name_info) ||
        !decode_node(d, depth + 1, &arity_value, &arity_info))
      return false;
    if (arity_info.kind != SILO_NODE_NAT || !arity_info.nat_fits ||
        arity_info.nat_u64 == 0 || arity_info.nat_u64 > PL_NAT63_MAX)
      return silo_error(d->err, d->err_cap,
                        "LAW arity is not a direct nonzero runtime natural");
    if (!decode_node(d, depth + 1, &body, &body_info))
      return false;
    info->kind = SILO_NODE_LAW;
    if (d->build) {
      pl_cell* p = decode_alloc(d, PL_LAW_CELLS);
      if (p == NULL)
        return false;
      p[0] = pl_hdr_make(PL_K_LAW, PL_F_NORMAL, 0, PL_LAW_CELLS);
      p[1] = arity_info.nat_u64;
      p[2] = name;
      p[3] = body;
      *out = pl_make(PL_TAG_LAW, p);
    }
    return true;
  }

  if (opcode >= 0xf1 && opcode <= 0xf8) {
    uint8_t width = (uint8_t)(opcode - 0xf0u);
    uint8_t b[8] = {0};
    if (!dread(d, b, width))
      return false;
    uint64_t index = getle(b, width);
    if (width != width_u64(index))
      return silo_error(d->err, d->err_cap, "nonminimal PIN index width");
    if (index >= d->scan->pin_count)
      return silo_error(d->err, d->err_cap, "PIN index is out of range");
    info->kind = SILO_NODE_PIN;
    if (d->capture_header && !d->used[index]) {
      if (d->canonical && index != d->next_canonical_pin)
        return silo_error(d->err, d->err_cap,
                          "canonical PIN table is not first-occurrence order");
      d->used[index] = true;
      d->next_canonical_pin++;
      ax_arrpush(d->scan->used, (uint32_t)index);
      d->scan->used_count = (size_t)ax_arrlen(d->scan->used);
    }
    if (d->build) {
      pl_val pin = d->resolved[index];
      if (pl_tag(pin) != PL_TAG_PIN)
        return silo_error(d->err, d->err_cap,
                          "Silo PIN referent was not resolved");
      *out = pin;
    }
    return true;
  }

  return silo_error(d->err, d->err_cap, "invalid Silo opcode 0x%02x", opcode);
}

void pl_silo_scan_free(pl_silo_scan* scan) {
  if (scan == NULL)
    return;
  free(scan->pins);
  ax_arrfree(scan->used);
  memset(scan, 0, sizeof(*scan));
}

bool pl_silo_scan_stream(pl_silo_reader* r, bool canonical, pl_silo_scan* scan,
                         char* err, size_t err_cap) {
  if (r == NULL || r->read == NULL || r->rewind == NULL || scan == NULL)
    return silo_error(err, err_cap, "invalid Silo reader");
  memset(scan, 0, sizeof(*scan));
  if (!srewind(r, err, err_cap))
    return false;
  silo_dec d = {.r = r,
                .scan = scan,
                .canonical = canonical,
                .capture_header = true,
                .err = err,
                .err_cap = err_cap};
  pl_val ignored = 0;
  silo_node_info info;
  bool ok = decode_header(&d) && decode_node(&d, 0, &ignored, &info);
  if (ok && r->pos != r->len)
    ok = silo_error(err, err_cap, "trailing bytes after Silo root node");
  if (ok && canonical && d.next_canonical_pin != scan->pin_count)
    ok = silo_error(err, err_cap,
                    "canonical Silo pin table contains unused entries");
  free(d.used);
  if (!ok)
    pl_silo_scan_free(scan);
  return ok;
}

bool pl_silo_build_stream(pl_silo_reader* r, pl_store* store,
                          const pl_silo_scan* accepted, const pl_val* resolved,
                          pl_val* out, char* err, size_t err_cap) {
  if (r == NULL || store == NULL || accepted == NULL || out == NULL ||
      (accepted->pin_count != 0 && resolved == NULL))
    return silo_error(err, err_cap, "invalid Silo build arguments");
  if (!srewind(r, err, err_cap))
    return false;
  /* Header parsing is shared with validation.  It only mutates a scan when
   * capture_header is set, so casting away const here is read-only. */
  silo_dec d = {.r = r,
                .store = store,
                .scan = (pl_silo_scan*)accepted,
                .resolved = resolved,
                .build = true,
                .err = err,
                .err_cap = err_cap};
  silo_node_info info;
  bool ok = decode_header(&d) && decode_node(&d, 0, out, &info);
  if (ok && r->pos != r->len)
    ok = silo_error(err, err_cap, "trailing bytes after Silo root node");
  return ok;
}
