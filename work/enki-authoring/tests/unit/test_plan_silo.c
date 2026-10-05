#include "test.h"
#include <stdlib.h>
#include <string.h>

#include "../../pkg/plan/src/silo_internal.h"
#include "../../pkg/plan/src/store_internal.h"
#include "axsys/sha256.h"
#include "test_plan.h"

typedef struct mem_stream {
  uint8_t* bytes;
  size_t len;
  size_t cap;
  size_t pos;
} mem_stream;

static bool mem_write(void* ctx, const uint8_t* bytes, size_t len) {
  mem_stream* m = ctx;
  if (len > SIZE_MAX - m->len)
    return false;
  size_t need = m->len + len;
  if (need > m->cap) {
    size_t cap = m->cap ? m->cap : 64;
    while (cap < need) {
      if (cap > SIZE_MAX / 2)
        return false;
      cap *= 2;
    }
    uint8_t* next = realloc(m->bytes, cap);
    if (next == NULL)
      return false;
    m->bytes = next;
    m->cap = cap;
  }
  memcpy(m->bytes + m->len, bytes, len);
  m->len += len;
  return true;
}

static bool mem_read(void* ctx, uint8_t* bytes, size_t len) {
  mem_stream* m = ctx;
  if (len > m->len - m->pos)
    return false;
  memcpy(bytes, m->bytes + m->pos, len);
  m->pos += len;
  return true;
}

static bool mem_rewind(void* ctx) {
  ((mem_stream*)ctx)->pos = 0;
  return true;
}

static void mem_reset(mem_stream* m) {
  m->len = 0;
  m->pos = 0;
}

static uint64_t test_getle(const uint8_t* bytes, size_t n) {
  uint64_t value = 0;
  for (size_t i = 0; i < n; i++)
    value |= (uint64_t)bytes[i] << (8u * i);
  return value;
}

static void test_putle(uint8_t* bytes, uint64_t value, size_t n) {
  for (size_t i = 0; i < n; i++)
    bytes[i] = (uint8_t)(value >> (8u * i));
}

static uint64_t test_split_power(uint64_t n) {
  uint64_t k = 1;
  while (k <= (n - 1) / 2)
    k <<= 1;
  return k;
}

static uint32_t test_crc32c(const uint8_t* bytes, size_t n) {
  uint32_t crc = UINT32_MAX;
  while (n-- != 0) {
    crc ^= *bytes++;
    for (unsigned k = 0; k < 8; k++)
      crc = (crc >> 1) ^ (UINT32_C(0x82f63b78) & (0u - (crc & 1u)));
  }
  return ~crc;
}

/* Return the offset of the first MNAT page-length field. */
static size_t first_page(const mem_stream* m) {
  ASSERT_GT(m->len, 10);
  ASSERT_EQ(m->bytes[6], 0xf9);
  size_t length_width = (size_t)m->bytes[8] + 1;
  uint64_t bit_length = test_getle(m->bytes + 10, length_width);
  uint64_t byte_length = bit_length / 8 + (bit_length % 8 != 0);
  uint64_t leaves = (byte_length + PL_SILO_LEAF_BYTES - 1) / PL_SILO_LEAF_BYTES;
  size_t siblings = 0;
  while (leaves > 1) {
    leaves = test_split_power(leaves);
    siblings++;
  }
  return 10 + length_width + 32 + 32 + siblings * 32;
}

static void encode(mem_stream* m, pl_val root, const pl_val* pins, size_t n) {
  char err[192] = {0};
  pl_silo_writer w = {.ctx = m, .write = mem_write};
  ASSERT(pl_silo_encode(&w, root, pins, n, err, sizeof(err)), "%s", err);
  ASSERT_EQ(w.pos, m->len);
}

static bool scan(mem_stream* m, bool canonical, pl_silo_scan* out,
                 char err[192]) {
  pl_silo_reader r = {
      .ctx = m, .read = mem_read, .rewind = mem_rewind, .len = m->len};
  return pl_silo_scan_stream(&r, canonical, out, err, 192);
}

static pl_val mk_nat_bytes(pl_thread* t, size_t bytes) {
  size_t limbs = (bytes + 7) / 8;
  pl_gc_reserve(t, PL_NAT_CELLS(limbs));
  PL_GC_FORBID(t);
  uint64_t* out;
  pl_val v = pl_mk_nat_limbs(t, limbs, &out);
  memset(out, 0, limbs * sizeof(*out));
  uint8_t* raw = (uint8_t*)out;
  for (size_t i = 0; i + 1 < bytes; i++)
    raw[i] = (uint8_t)(i * 29u + 7u);
  raw[bytes - 1] = 1;
  PL_GC_ALLOW(t);
  return v;
}

TEST(silo, scalar_golden_bytes) {
  mem_stream m = {0};
  static const uint8_t prefix[] = {'S', 'I', 'L', 'O', 1, 0};

  encode(&m, 0, NULL, 0);
  ASSERT_EQ(m.len, sizeof(prefix) + 1);
  ASSERT_EQ(memcmp(m.bytes, prefix, sizeof(prefix)), 0);
  ASSERT_EQ(m.bytes[sizeof(prefix)], 0x80);

  mem_reset(&m);
  encode(&m, 63, NULL, 0);
  ASSERT_EQ(m.bytes[sizeof(prefix)], 0xbf);

  mem_reset(&m);
  encode(&m, 64, NULL, 0);
  ASSERT_EQ(m.len, sizeof(prefix) + 2);
  ASSERT_EQ(m.bytes[sizeof(prefix)], 0xc1);
  ASSERT_EQ(m.bytes[sizeof(prefix) + 1], 0x40);

  mem_reset(&m);
  encode(&m, 256, NULL, 0);
  ASSERT_EQ(m.bytes[sizeof(prefix)], 0xc2);
  ASSERT_EQ(m.bytes[sizeof(prefix) + 1], 0);
  ASSERT_EQ(m.bytes[sizeof(prefix) + 2], 1);
  free(m.bytes);
}

TEST(silo, identity_is_sha256_of_canonical_stream) {
  mem_stream m = {0};
  encode(&m, 64, NULL, 0);
  uint8_t expected[32], actual[32];
  ax_sha256(m.bytes, m.len, expected);
  char err[192] = {0};
  ASSERT(pl_silo_hash(64, NULL, 0, actual, err, sizeof(err)), "%s", err);
  ASSERT_EQ(memcmp(actual, expected, sizeof(actual)), 0);
  free(m.bytes);
}

TEST(silo, opcode_and_width_boundaries) {
  test_rt rt = test_rt_new();
  pl_thread* t = rt.t;
  mem_stream m = {0};
  char err[192] = {0};
  pl_silo_scan accepted = {0};

  const size_t widths[] = {31, 32, 255, 256};
  const uint8_t opcodes[] = {0xdf, 0xe1, 0xe1, 0xe2};
  for (size_t i = 0; i < sizeof(widths) / sizeof(widths[0]); i++) {
    pl_val value = mk_nat_bytes(t, widths[i]);
    pl_vpush(t, value);
    mem_reset(&m);
    encode(&m, value, NULL, 0);
    ASSERT_EQ(m.bytes[6], opcodes[i]);
    ASSERT(scan(&m, true, &accepted, err), "%s", err);
    pl_silo_scan_free(&accepted);
  }

  pl_val args[16];
  for (uint32_t i = 0; i < 16; i++)
    args[i] = i;
  pl_gc_reserve(t, PL_APP_CELLS(15) + PL_APP_CELLS(16));
  PL_GC_FORBID(t);
  pl_val app15 = pl_mk_app_from(t, 0, 15, args);
  pl_val app16 = pl_mk_app_from(t, 0, 16, args);
  PL_GC_ALLOW(t);
  pl_vpush(t, app15);
  pl_vpush(t, app16);
  mem_reset(&m);
  encode(&m, app15, NULL, 0);
  ASSERT_EQ(m.bytes[6], 0x78);
  mem_reset(&m);
  encode(&m, app16, NULL, 0);
  ASSERT_EQ(m.bytes[6], 0x08);
  ASSERT_EQ(m.bytes[7], 0x78);

  /* General PIN indices switch from f1 to f2 at 256. */
  for (uint64_t index = 255; index <= 256; index++) {
    size_t count = (size_t)index + 1;
    size_t header = 5 + 3 + count * 32;
    size_t pin_width = index == 255 ? 1 : 2;
    uint8_t* bytes = calloc(1, header + 1 + pin_width);
    ASSERT_NOT_NULL(bytes);
    memcpy(bytes, "SILO\1", 5);
    bytes[5] = 2;
    bytes[6] = (uint8_t)count;
    bytes[7] = (uint8_t)(count >> 8);
    for (size_t i = 0; i < count; i++) {
      bytes[8 + i * 32] = (uint8_t)i;
      bytes[8 + i * 32 + 1] = (uint8_t)(i >> 8);
    }
    bytes[header] = index == 255 ? 0xf1 : 0xf2;
    bytes[header + 1] = (uint8_t)index;
    if (pin_width == 2)
      bytes[header + 2] = 1;
    mem_stream indexed = {.bytes = bytes,
                          .len = header + 1 + pin_width,
                          .cap = header + 1 + pin_width};
    ASSERT(scan(&indexed, false, &accepted, err), "%s", err);
    pl_silo_scan_free(&accepted);
    free(bytes);
  }

  free(m.bytes);
  test_rt_free(&rt);
}

TEST(silo, canonical_app_chunks_and_law_order) {
  test_rt rt = test_rt_new();
  pl_thread* t = rt.t;
  mem_stream m = {0};
  pl_val args[16];
  for (uint32_t i = 0; i < 16; i++)
    args[i] = i + 1;
  pl_gc_reserve(t, PL_APP_CELLS(16) + PL_LAW_CELLS);
  PL_GC_FORBID(t);
  pl_val app = pl_mk_app_from(t, 0, 16, args);
  pl_val law = pl_mk_law(t, 2, 1, 3);
  PL_GC_ALLOW(t);

  encode(&m, app, NULL, 0);
  ASSERT_EQ(m.bytes[6], 0x08); /* outer one argument */
  ASSERT_EQ(m.bytes[7], 0x78); /* saturated inner 15 */
  pl_silo_scan accepted = {0};
  char err[192] = {0};
  ASSERT(scan(&m, true, &accepted, err), "%s", err);
  pl_silo_scan_free(&accepted);

  mem_reset(&m);
  encode(&m, law, NULL, 0);
  static const uint8_t suffix[] = {0xf0, 0x81, 0x82, 0x83};
  ASSERT_EQ(memcmp(m.bytes + 6, suffix, sizeof(suffix)), 0);
  free(m.bytes);
  test_rt_free(&rt);
}

TEST(silo, direct_pin_table_is_canonical) {
  test_rt rt = test_rt_new();
  pl_thread* t = rt.t;
  size_t base = t->vsp;
  pl_vpush(t, 42);
  t->vstack[base] = pl_pin(t, t->vstack[base]);
  char save_err[192] = {0};
  ASSERT(pl_store_save_root(rt.store, t->vstack[base], NULL, save_err,
                            sizeof(save_err)),
         "%s", save_err);
  pl_val pin = pl_pin_proxy_target(pl_ptr(t->vstack[base]));
  ASSERT_NEQ(pin, 0);
  pl_val args[2] = {pin, pin};
  pl_gc_reserve(t, PL_APP_CELLS(2));
  PL_GC_FORBID(t);
  pl_val app = pl_mk_app_from(t, 0, 2, args);
  PL_GC_ALLOW(t);
  mem_stream m = {0};
  encode(&m, app, &pin, 1);

  ASSERT_EQ(m.bytes[5], 1); /* pin-count varnat width */
  ASSERT_EQ(m.bytes[6], 1);
  ASSERT_EQ(memcmp(m.bytes + 7, pl_pin_hash(pin), 32), 0);
  ASSERT_EQ(m.bytes[39], 0x10);
  ASSERT_EQ(m.bytes[41], 0xf1);
  ASSERT_EQ(m.bytes[42], 0);
  ASSERT_EQ(m.bytes[43], 0xf1);
  ASSERT_EQ(m.bytes[44], 0);

  pl_silo_scan accepted = {0};
  char err[192] = {0};
  ASSERT(scan(&m, true, &accepted, err), "%s", err);
  ASSERT_EQ(accepted.pin_count, 1);
  ASSERT_EQ(accepted.used_count, 1);
  pl_silo_scan_free(&accepted);
  free(m.bytes);
  test_rt_free(&rt);
}

TEST(silo, general_pin_table_order_is_referent_independent) {
  uint8_t bytes[5 + 2 + 64 + 7] = {'S', 'I', 'L', 'O', 1, 1, 2};
  bytes[7] = 1;
  bytes[39] = 2;
  size_t root = 7 + 64;
  bytes[root] = 0x10;
  bytes[root + 1] = 0x80;
  bytes[root + 2] = 0xf1;
  bytes[root + 3] = 1;
  bytes[root + 4] = 0xf1;
  bytes[root + 5] = 0;
  mem_stream m = {.bytes = bytes, .len = root + 6, .cap = sizeof(bytes)};
  pl_silo_scan accepted = {0};
  char err[192] = {0};
  ASSERT(scan(&m, false, &accepted, err), "%s", err);
  ASSERT_EQ(accepted.used_count, 2);
  ASSERT_EQ(accepted.used[0], 1);
  ASSERT_EQ(accepted.used[1], 0);
  pl_silo_scan_free(&accepted);
  ASSERT_FALSE(scan(&m, true, &accepted, err));
}

TEST(silo, general_reader_accepts_noncanonical_natural_choices) {
  uint8_t medium[] = {'S', 'I', 'L', 'O', 1, 0, 0xc1, 1};
  mem_stream m = {
      .bytes = medium, .len = sizeof(medium), .cap = sizeof(medium)};
  pl_silo_scan accepted = {0};
  char err[192] = {0};
  ASSERT(scan(&m, false, &accepted, err), "%s", err);
  pl_silo_scan_free(&accepted);
  ASSERT_FALSE(scan(&m, true, &accepted, err));

  uint8_t big[] = {'S', 'I', 'L', 'O', 1, 0, 0xe2, 1, 0, 1};
  m = (mem_stream){.bytes = big, .len = sizeof(big), .cap = sizeof(big)};
  memset(err, 0, sizeof(err));
  ASSERT(scan(&m, false, &accepted, err), "%s", err);
  pl_silo_scan_free(&accepted);
  ASSERT_FALSE(scan(&m, true, &accepted, err));
}

TEST(silo, big_and_mnat_round_trip_at_cutover) {
  test_rt rt = test_rt_new();
  pl_thread* t = rt.t;
  mem_stream m = {0};

  pl_val big = mk_nat_bytes(t, PL_SILO_NAT_CUTOVER);
  pl_vpush(t, big);
  encode(&m, big, NULL, 0);
  ASSERT((m.bytes[6] & 0xf0u) == 0xe0u);
  pl_silo_scan accepted = {0};
  char err[192] = {0};
  ASSERT(scan(&m, true, &accepted, err), "%s", err);
  pl_silo_scan_free(&accepted);

  mem_reset(&m);
  pl_val mnat = mk_nat_bytes(t, PL_SILO_NAT_CUTOVER + 1);
  pl_vpush(t, mnat);
  encode(&m, mnat, NULL, 0);
  ASSERT_EQ(m.bytes[6], 0xf9);
  ASSERT(scan(&m, true, &accepted, err), "%s", err);

  pl_silo_reader reader = {
      .ctx = &m, .read = mem_read, .rewind = mem_rewind, .len = m.len};
  pl_val decoded = 0;
  ASSERT(pl_silo_build_stream(&reader, rt.store, &accepted, NULL, &decoded, err,
                              sizeof(err)),
         "%s", err);
  ASSERT(pl_nat_eq(decoded, mnat));
  pl_silo_scan_free(&accepted);

  mem_reset(&m);
  pl_val balanced = mk_nat_bytes(t, 16 * PL_SILO_LEAF_BYTES);
  pl_vpush(t, balanced);
  encode(&m, balanced, NULL, 0);
  ASSERT(scan(&m, true, &accepted, err), "%s", err);
  pl_silo_scan_free(&accepted);
  free(m.bytes);
  test_rt_free(&rt);
}

TEST(silo, corruption_and_trailing_bytes_are_rejected) {
  mem_stream m = {0};
  encode(&m, 42, NULL, 0);
  pl_silo_scan accepted = {0};
  char err[192] = {0};
  m.bytes[0] ^= 1;
  ASSERT_FALSE(scan(&m, false, &accepted, err));
  m.bytes[0] ^= 1;
  ASSERT(mem_write(&m, (const uint8_t[]){0}, 1));
  ASSERT_FALSE(scan(&m, false, &accepted, err));
  free(m.bytes);
}

TEST(silo, general_mnat_repages_and_checks_crc32c) {
  test_rt rt = test_rt_new();
  pl_thread* t = rt.t;
  mem_stream m = {0};
  pl_val value = mk_nat_bytes(t, PL_SILO_NAT_CUTOVER + 1);
  pl_vpush(t, value);
  encode(&m, value, NULL, 0);

  size_t page = first_page(&m);
  size_t page_width = (size_t)m.bytes[9] + 1;
  ASSERT_EQ(test_getle(m.bytes + page, page_width), PL_SILO_NAT_CUTOVER + 1);

  /* A 9-leaf tree has four Blackman expansions, all funded by the first
   * four leaves. Split immediately after those leaves and their proofs. */
  size_t first_payload = 4 * PL_SILO_LEAF_BYTES;
  size_t first_physical = first_payload + 4 * 64;
  size_t old_body = page + page_width;
  size_t physical = m.len - old_body;
  ASSERT_GT(physical, first_physical);
  uint8_t* repaged = malloc(m.len + page_width);
  ASSERT_NOT_NULL(repaged);
  memcpy(repaged, m.bytes, page);
  test_putle(repaged + page, first_payload, page_width);
  memcpy(repaged + page + page_width, m.bytes + old_body, first_physical);
  size_t second = page + page_width + first_physical;
  test_putle(repaged + second, PL_SILO_NAT_CUTOVER + 1 - first_payload,
             page_width);
  memcpy(repaged + second + page_width, m.bytes + old_body + first_physical,
         physical - first_physical);
  free(m.bytes);
  m.bytes = repaged;
  m.len += page_width;
  m.cap = m.len;
  m.pos = 0;

  pl_silo_scan accepted = {0};
  char err[192] = {0};
  ASSERT(scan(&m, false, &accepted, err), "%s", err);
  pl_silo_scan_free(&accepted);
  ASSERT_FALSE(scan(&m, true, &accepted, err));

  /* Add a standard CRC32C trailer to each independently framed page. */
  size_t first_end = second;
  size_t second_end = m.len;
  uint32_t crc1 = test_crc32c(m.bytes + page, first_end - page);
  uint32_t crc2 = test_crc32c(m.bytes + second, second_end - second);
  uint8_t* checked = malloc(m.len + 8);
  ASSERT_NOT_NULL(checked);
  memcpy(checked, m.bytes, first_end);
  test_putle(checked + first_end, crc1, 4);
  memcpy(checked + first_end + 4, m.bytes + second, second_end - second);
  test_putle(checked + m.len + 4, crc2, 4);
  free(m.bytes);
  m.bytes = checked;
  m.len += 8;
  m.cap = m.len;
  m.pos = 0;
  m.bytes[7] = 1;

  memset(err, 0, sizeof(err));
  ASSERT(scan(&m, false, &accepted, err), "%s", err);
  pl_silo_scan_free(&accepted);
  ASSERT_FALSE(scan(&m, true, &accepted, err));
  m.bytes[m.len - 1] ^= 1;
  ASSERT_FALSE(scan(&m, false, &accepted, err));
  free(m.bytes);
  test_rt_free(&rt);
}

TEST(silo, canonical_mnat_uses_64k_pages_and_funding_page_expansions) {
  test_rt rt = test_rt_new();
  pl_thread* t = rt.t;
  mem_stream m = {0};
  pl_val value = mk_nat_bytes(t, PL_SILO_PAGE_BYTES + 1);
  pl_vpush(t, value);
  encode(&m, value, NULL, 0);

  size_t page = first_page(&m);
  size_t width = (size_t)m.bytes[9] + 1;
  ASSERT_EQ(test_getle(m.bytes + page, width), PL_SILO_PAGE_BYTES);
  pl_silo_scan accepted = {0};
  char err[192] = {0};
  ASSERT(scan(&m, true, &accepted, err), "%s", err);
  pl_silo_scan_free(&accepted);

  /* The encoder puts every expansion funded by the 64th leaf before the
   * next page header; moving the last proof behind it must be rejected. */
  ASSERT_GT(m.len, page + width + PL_SILO_PAGE_BYTES + 64);
  m.bytes[page + width + PL_SILO_PAGE_BYTES] ^= 1;
  ASSERT_FALSE(scan(&m, false, &accepted, err));
  free(m.bytes);
  test_rt_free(&rt);
}

TEST(silo, malformed_headers_nodes_and_authentication_are_rejected) {
  char err[192] = {0};
  pl_silo_scan accepted = {0};

  uint8_t nonminimal_count[] = {'S', 'I', 'L', 'O', 1, 1, 0, 0x80};
  mem_stream m = {.bytes = nonminimal_count,
                  .len = sizeof(nonminimal_count),
                  .cap = sizeof(nonminimal_count)};
  ASSERT_FALSE(scan(&m, false, &accepted, err));

  uint8_t bad_opcode[] = {'S', 'I', 'L', 'O', 1, 0, 0xff};
  m = (mem_stream){.bytes = bad_opcode,
                   .len = sizeof(bad_opcode),
                   .cap = sizeof(bad_opcode)};
  ASSERT_FALSE(scan(&m, false, &accepted, err));

  uint8_t zero_law[] = {'S', 'I', 'L', 'O', 1, 0, 0xf0, 0x80, 0x80, 0x80};
  m = (mem_stream){
      .bytes = zero_law, .len = sizeof(zero_law), .cap = sizeof(zero_law)};
  ASSERT_FALSE(scan(&m, false, &accepted, err));

  uint8_t nested_app[] = {'S',  'I',  'L',  'O',  1,   0,
                          0x08, 0x08, 0x80, 0x81, 0x82};
  m = (mem_stream){.bytes = nested_app,
                   .len = sizeof(nested_app),
                   .cap = sizeof(nested_app)};
  ASSERT(scan(&m, false, &accepted, err), "%s", err);
  pl_silo_scan_free(&accepted);
  ASSERT_FALSE(scan(&m, true, &accepted, err));

  uint8_t duplicate_pins[5 + 2 + 64 + 2] = {'S', 'I', 'L', 'O', 1, 1, 2};
  duplicate_pins[5 + 2 + 64] = 0xf1;
  duplicate_pins[5 + 2 + 64 + 1] = 0;
  m = (mem_stream){.bytes = duplicate_pins,
                   .len = sizeof(duplicate_pins),
                   .cap = sizeof(duplicate_pins)};
  ASSERT_FALSE(scan(&m, false, &accepted, err));

  test_rt rt = test_rt_new();
  pl_val value = mk_nat_bytes(rt.t, PL_SILO_NAT_CUTOVER + 1);
  pl_vpush(rt.t, value);
  mem_stream encoded = {0};
  encode(&encoded, value, NULL, 0);
  size_t length_width = (size_t)encoded.bytes[8] + 1;
  size_t first_hash = 10 + length_width + 32;
  encoded.bytes[first_hash] ^= 1;
  ASSERT_FALSE(scan(&encoded, false, &accepted, err));
  free(encoded.bytes);
  test_rt_free(&rt);
}

/* A long row is encoded in 15-argument chunks. Loading must not retain
 * each flattened prefix in the permanent store arena. */
TEST(silo, wide_application_decode_uses_linear_store_space) {
  test_rt rt = test_rt_new();
  const uint32_t n = 6000;
  pl_val* args = malloc(n * sizeof(*args));
  ASSERT_NOT_NULL(args);
  for (uint32_t i = 0; i < n; i++) args[i] = i % 61;
  pl_val row = test_app(rt.t, 0, n, args);
  pl_vpush(rt.t, row);
  mem_stream encoded = {0}, roundtrip = {0};
  encode(&encoded, row, NULL, 0);
  char err[192] = {0};
  pl_silo_scan shape = {0};
  ASSERT(scan(&encoded, true, &shape, err), "%s", err);
  pl_silo_reader reader = {.ctx = &encoded, .read = mem_read,
      .rewind = mem_rewind, .len = encoded.len};
  size_t before = pl_store_mark(rt.store);
  pl_val decoded;
  ASSERT(pl_silo_build_stream(&reader, rt.store, &shape, NULL,
                              &decoded, err, sizeof(err)), "%s", err);
  size_t allocated = pl_store_mark(rt.store) - before;
  encode(&roundtrip, decoded, NULL, 0);
  ASSERT_EQ(encoded.len, roundtrip.len);
  ASSERT_EQ(memcmp(encoded.bytes, roundtrip.bytes, encoded.len), 0);
  ASSERT(allocated <= 2 * PL_APP_CELLS(n) * sizeof(pl_cell),
         "wide row allocated %zu bytes for %u fields", allocated, n);
  pl_silo_scan_free(&shape);
  free(args); free(encoded.bytes); free(roundtrip.bytes);
  test_rt_free(&rt);
}

TEST(silo, decoded_sharing_is_exact_and_rollback_drops_cache) {
  test_rt rt = test_rt_new();
  pl_val args[3] = {11, 22, 33};
  pl_val row = test_app(rt.t, 0, 3, args);
  pl_vpush(rt.t, row);
  mem_stream encoded = {0}; encode(&encoded, row, NULL, 0);
  char err[192] = {0}; pl_silo_scan shape = {0};
  ASSERT(scan(&encoded, true, &shape, err), "%s", err);
  pl_silo_reader reader = {.ctx=&encoded, .read=mem_read,
      .rewind=mem_rewind, .len=encoded.len};
  size_t start = pl_store_mark(rt.store);
  pl_val first, second, third;
  ASSERT(pl_silo_build_stream(&reader, rt.store, &shape, NULL, &first, err, sizeof(err)), "%s", err);
  size_t once = pl_store_mark(rt.store);
  ASSERT(pl_silo_build_stream(&reader, rt.store, &shape, NULL, &second, err, sizeof(err)), "%s", err);
  ASSERT_EQ(first, second);
  ASSERT_EQ(pl_store_mark(rt.store), once);
  pl_store_release(rt.store, start);
  ASSERT(pl_silo_build_stream(&reader, rt.store, &shape, NULL, &third, err, sizeof(err)), "%s", err);
  ASSERT_EQ(pl_store_mark(rt.store), once);
  mem_stream again = {0}; encode(&again, third, NULL, 0);
  ASSERT_EQ(again.len, encoded.len);
  ASSERT_EQ(memcmp(again.bytes, encoded.bytes, again.len), 0);
  pl_silo_scan_free(&shape); free(again.bytes); free(encoded.bytes); test_rt_free(&rt);
}
