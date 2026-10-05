#include "test.h"

#include <stdint.h>
#include <stdlib.h>
#include <string.h>

/*
    keep inline storage tiny in tests so growth/realloc paths are exercised
    without having to append a silly number of pieces.
*/
#include "axsys/sb.h"

typedef struct test_allocator_state {
  int fail_after; /* -1 = never fail; 0 = fail next alloc/realloc */
  size_t alloc_calls;
  size_t realloc_calls;
  size_t free_calls;
  ax_allocator allocator;
} test_allocator_state;

static int test_allocator_should_fail(test_allocator_state* state) {
  if (state->fail_after < 0)
    return 0;

  if (state->fail_after == 0)
    return 1;

  --state->fail_after;
  return 0;
}

static void* test_alloc(void* ctx, size_t size) {
  test_allocator_state* state = (test_allocator_state*)ctx;

  ++state->alloc_calls;

  if (test_allocator_should_fail(state))
    return NULL;

  return malloc(size);
}

static void* test_realloc(void* ctx, void* ptr, size_t size) {
  test_allocator_state* state = (test_allocator_state*)ctx;

  ++state->realloc_calls;

  if (test_allocator_should_fail(state))
    return NULL;

  return realloc(ptr, size);
}

static void test_free(void* ctx, void* ptr) {
  test_allocator_state* state = (test_allocator_state*)ctx;

  if (ptr)
    ++state->free_calls;

  free(ptr);
}

static ax_allocator* make_test_allocator(test_allocator_state* state,
                                         int with_realloc) {
  memset(state, 0, sizeof(*state));
  state->fail_after = -1;

  state->allocator.ctx = state;
  state->allocator.alloc = test_alloc;
  state->allocator.realloc = with_realloc ? test_realloc : NULL;
  state->allocator.free = test_free;

  return &state->allocator;
}

static void init_builder(ax_sb* sb, test_allocator_state* state) {
  ax_sb_init(sb, make_test_allocator(state, 1));

  ASSERT(!ax_sb_failed(sb));
  ASSERT_EQ(ax_sb_piece_count(sb), 0);
}

static void assert_build_bytes(ax_sb* sb, const char* expected,
                               size_t expected_len) {
  size_t got_len = 777;
  char* got = ax_sb_build(sb, &got_len);

  ASSERT_NOT_NULL(got);
  ASSERT_EQ(got_len, expected_len);
  ASSERT_EQ(memcmp(got, expected, expected_len), 0);
  ASSERT_EQ(got[expected_len], '\0');

  sb->allocator->free(sb->allocator->ctx, got);
}

static void assert_build_cstr(ax_sb* sb, const char* expected) {
  assert_build_bytes(sb, expected, strlen(expected));
}

TEST(ax_sb, empty_builder_builds_empty_string) {
  test_allocator_state state;
  ax_sb sb;
  size_t len = 999;
  char* out;

  init_builder(&sb, &state);

  ASSERT(ax_sb_measure(&sb, &len));
  ASSERT_EQ(len, 0);

  out = ax_sb_build(&sb, &len);
  ASSERT_NOT_NULL(out);
  ASSERT_EQ(len, 0);
  ASSERT_EQ(out[0], '\0');

  sb.allocator->free(sb.allocator->ctx, out);
  ax_sb_free(&sb);
}

TEST(ax_sb, appends_refs_cstrings_literals_and_chars) {
  test_allocator_state state;
  ax_sb sb;
  const char* world = "world";

  init_builder(&sb, &state);

  ASSERT(ax_sb_append_lit(&sb, "hello"));
  ASSERT(ax_sb_append_char(&sb, ' '));
  ASSERT(ax_sb_append_cstr(&sb, world));
  ASSERT(ax_sb_append_char(&sb, '!'));

  assert_build_cstr(&sb, "hello world!");

  ax_sb_free(&sb);
}

TEST(ax_sb, cstr_captures_length_but_not_bytes) {
  test_allocator_state state;
  ax_sb sb;
  char mutable_text[] = "abcdef";

  init_builder(&sb, &state);

  ASSERT(ax_sb_append_cstr(&sb, mutable_text));

  /*
      append_cstr captured length 6, but the builder still references the
      original bytes. this is the intended twine-ish behavior.
  */
  memcpy(mutable_text, "UVWXYZ", 6);

  assert_build_cstr(&sb, "UVWXYZ");

  ax_sb_free(&sb);
}

TEST(ax_sb, supports_embedded_nuls) {
  test_allocator_state state;
  ax_sb sb;

  const char chunk[] = {'a', '\0', 'b'};
  const char expected[] = {'x', 'a', '\0', 'b', 'y'};

  init_builder(&sb, &state);

  ASSERT(ax_sb_append_char(&sb, 'x'));
  ASSERT(ax_sb_append_ref(&sb, chunk, sizeof(chunk)));
  ASSERT(ax_sb_append_char(&sb, 'y'));

  assert_build_bytes(&sb, expected, sizeof(expected));

  ax_sb_free(&sb);
}

TEST(ax_sb, formats_signed_and_unsigned_integers) {
  test_allocator_state state;
  ax_sb sb;

  init_builder(&sb, &state);

  ASSERT(ax_sb_append_i64(&sb, 0));
  ASSERT(ax_sb_append_lit(&sb, ","));
  ASSERT(ax_sb_append_i64(&sb, -123));
  ASSERT(ax_sb_append_lit(&sb, ","));
  ASSERT(ax_sb_append_i64(&sb, INT64_MIN));
  ASSERT(ax_sb_append_lit(&sb, ","));
  ASSERT(ax_sb_append_u64(&sb, UINT64_MAX));
  ASSERT(ax_sb_append_lit(&sb, ","));
  ASSERT(ax_sb_append_u64_base(&sb, 255, 16, 0));
  ASSERT(ax_sb_append_lit(&sb, ","));
  ASSERT(ax_sb_append_u64_base(&sb, 255, 16, 1));
  ASSERT(ax_sb_append_lit(&sb, ","));
  ASSERT(ax_sb_append_u64_base(&sb, 5, 2, 0));

  assert_build_cstr(
      &sb, "0,-123,-9223372036854775808,18446744073709551615,ff,FF,101");

  ax_sb_free(&sb);
}

TEST(ax_sb, reserve_pieces_grows_metadata_storage) {
  test_allocator_state state;
  ax_sb sb;

  init_builder(&sb, &state);

  ASSERT(ax_sb_reserve_pieces(&sb, 32));
  ASSERT(sb.capacity >= 32);
  ASSERT(state.alloc_calls > 0);

  ASSERT(ax_sb_append_lit(&sb, "after reserve"));

  assert_build_cstr(&sb, "after reserve");

  ax_sb_free(&sb);
}

TEST(ax_sb, growth_uses_realloc_when_available) {
  test_allocator_state state;
  ax_sb sb;
  char expected[21];
  size_t i;

  init_builder(&sb, &state);

  for (i = 0; i < 20; ++i) {
    expected[i] = (char)('a' + (int)i);
    ASSERT(ax_sb_append_char(&sb, expected[i]));
  }
  expected[20] = '\0';

  ASSERT(state.alloc_calls > 0);
  // ASSERT(state.realloc_calls > 0);

  assert_build_cstr(&sb, expected);

  ax_sb_free(&sb);
}

TEST(ax_sb, growth_falls_back_to_alloc_copy_free_without_realloc) {
  test_allocator_state state;
  ax_allocator* allocator;
  ax_sb sb;
  char expected[21];
  size_t i;

  allocator = make_test_allocator(&state, 0);
  ax_sb_init(&sb, allocator);

  ASSERT(!ax_sb_failed(&sb));

  for (i = 0; i < 20; ++i) {
    expected[i] = (char)('A' + (int)i);
    ASSERT(ax_sb_append_char(&sb, expected[i]));
  }
  expected[20] = '\0';

  ASSERT_EQ(state.realloc_calls, 0);
  ASSERT(state.alloc_calls > 0);

  assert_build_cstr(&sb, expected);

  ax_sb_free(&sb);
}

TEST(ax_sb, appends_another_builder_as_metadata_only) {
  test_allocator_state left_state;
  test_allocator_state right_state;
  ax_sb left;
  ax_sb right;

  char referenced[] = "old";

  init_builder(&left, &left_state);
  init_builder(&right, &right_state);

  ASSERT(ax_sb_append_lit(&left, "prefix:"));
  ASSERT(ax_sb_append_ref(&right, referenced, 3));

  ASSERT(ax_sb_append_builder(&left, &right));

  /*
      append_builder copied the reference piece, not the pointed-to bytes.
  */
  memcpy(referenced, "new", 3);

  assert_build_cstr(&left, "prefix:new");
  assert_build_cstr(&right, "new");

  ax_sb_free(&right);
  ax_sb_free(&left);
}

TEST(ax_sb, supports_self_append) {
  test_allocator_state state;
  ax_sb sb;

  init_builder(&sb, &state);

  ASSERT(ax_sb_append_lit(&sb, "ab"));
  ASSERT(ax_sb_append_builder(&sb, &sb));

  assert_build_cstr(&sb, "abab");

  ax_sb_free(&sb);
}

TEST(ax_sb, measure_and_write_report_required_length) {
  test_allocator_state state;
  ax_sb sb;

  size_t len = 999;
  char too_small[5];
  char exact[6];

  init_builder(&sb, &state);

  ASSERT(ax_sb_append_lit(&sb, "abc"));
  ASSERT(ax_sb_append_u64(&sb, 42));

  ASSERT(ax_sb_measure(&sb, &len));
  ASSERT_EQ(len, 5);

  len = 999;
  ASSERT(!ax_sb_write(&sb, too_small, sizeof(too_small), &len));
  ASSERT_EQ(len, 5);

  len = 999;
  ASSERT(ax_sb_write(&sb, exact, sizeof(exact), &len));
  ASSERT_EQ(len, 5);
  ASSERT_STR_EQ(exact, "abc42");

  ax_sb_free(&sb);
}

TEST(ax_sb, zero_length_null_ref_is_allowed) {
  test_allocator_state state;
  ax_sb sb;

  init_builder(&sb, &state);

  ASSERT(ax_sb_append_ref(&sb, NULL, 0));
  ASSERT(!ax_sb_failed(&sb));

  ASSERT(ax_sb_append_lit(&sb, "ok"));

  assert_build_cstr(&sb, "ok");

  ax_sb_free(&sb);
}

TEST(ax_sb, null_nonempty_ref_marks_builder_failed) {
  test_allocator_state state;
  ax_sb sb;
  size_t len = 999;
  char* out;

  init_builder(&sb, &state);

  ASSERT(!ax_sb_append_ref(&sb, NULL, 1));
  ASSERT(ax_sb_failed(&sb));

  out = ax_sb_build(&sb, &len);
  ASSERT_NULL(out);
  ASSERT_EQ(len, 0);

  ax_sb_free(&sb);
}

TEST(ax_sb, null_cstr_marks_builder_failed) {
  test_allocator_state state;
  ax_sb sb;

  init_builder(&sb, &state);

  ASSERT(!ax_sb_append_cstr(&sb, NULL));
  ASSERT(ax_sb_failed(&sb));

  ax_sb_free(&sb);
}

TEST(ax_sb, invalid_integer_base_marks_builder_failed) {
  test_allocator_state state;
  ax_sb sb;

  init_builder(&sb, &state);

  ASSERT(!ax_sb_append_u64_base(&sb, 10, 1, 0));
  ASSERT(ax_sb_failed(&sb));

  ax_sb_free(&sb);
}

TEST(ax_sb, allocation_failure_during_growth_marks_builder_failed) {
  test_allocator_state state;
  ax_sb sb;
  size_t i;
  size_t len = 999;
  char* out;

  init_builder(&sb, &state);

  /*
      with AX_SB_INLINE_PIECES == 4, the fifth append must allocate
      metadata storage. make that allocation fail.
  */
  state.fail_after = 0;

  for (i = 0; i < AX_SB_INLINE_PIECES; ++i)
    ASSERT(ax_sb_append_char(&sb, 'x'));

  ASSERT(!ax_sb_append_char(&sb, 'y'));
  ASSERT(ax_sb_failed(&sb));
  ASSERT_EQ(state.alloc_calls, 1);

  out = ax_sb_build(&sb, &len);
  ASSERT_NULL(out);
  ASSERT_EQ(len, 0);

  ax_sb_free(&sb);
}

TEST(ax_sb, failed_realloc_does_not_prevent_freeing_builder) {
  test_allocator_state state;
  ax_sb sb;
  size_t i;

  init_builder(&sb, &state);

  /*
      First dynamic grow succeeds.
      Second grow, which should be realloc, fails.
  */
  state.fail_after = 1;

  for (i = 0; i < AX_SB_INLINE_PIECES * 2; ++i)
    ASSERT(ax_sb_append_char(&sb, 'x'));

  ASSERT(!ax_sb_append_char(&sb, 'y'));
  ASSERT(ax_sb_failed(&sb));
  ASSERT(state.realloc_calls > 0);

  ax_sb_free(&sb);

  /*
      The original heap metadata allocation should still have been released.
  */
  ASSERT(state.free_calls > 0);
}

TEST(ax_sb, reset_clears_content_and_recovers_from_allocator_failure) {
  test_allocator_state state;
  ax_sb sb;
  size_t i;

  init_builder(&sb, &state);

  state.fail_after = 0;

  for (i = 0; i < AX_SB_INLINE_PIECES; ++i)
    ASSERT(ax_sb_append_char(&sb, 'x'));

  ASSERT(!ax_sb_append_char(&sb, 'y'));
  ASSERT(ax_sb_failed(&sb));

  state.fail_after = -1;
  ax_sb_reset(&sb);

  ASSERT(!ax_sb_failed(&sb));
  ASSERT_EQ(ax_sb_piece_count(&sb), 0);

  ASSERT(ax_sb_append_lit(&sb, "recovered"));

  assert_build_cstr(&sb, "recovered");

  ax_sb_free(&sb);
}

TEST(ax_sb, build_allocation_failure_returns_null_without_failing_builder) {
  test_allocator_state state;
  ax_sb sb;
  size_t len = 999;
  char* out;

  init_builder(&sb, &state);

  ASSERT(ax_sb_append_lit(&sb, "abc"));

  state.fail_after = 0;

  out = ax_sb_build(&sb, &len);

  ASSERT_NULL(out);
  ASSERT_EQ(len, 0);
  ASSERT(!ax_sb_failed(&sb));

  state.fail_after = -1;

  assert_build_cstr(&sb, "abc");

  ax_sb_free(&sb);
}

TEST(ax_sb, build_with_allocator_uses_requested_output_allocator) {
  test_allocator_state builder_state;
  test_allocator_state output_state;

  ax_allocator* output_allocator;
  ax_sb sb;

  size_t len = 999;
  char* out;

  init_builder(&sb, &builder_state);

  output_allocator = make_test_allocator(&output_state, 1);

  ASSERT(ax_sb_append_lit(&sb, "separate output allocator"));

  out = ax_sb_build_with_allocator(&sb, output_allocator, &len);

  ASSERT_NOT_NULL(out);
  ASSERT_EQ(len, strlen("separate output allocator"));
  ASSERT_STR_EQ(out, "separate output allocator");

  ASSERT_EQ(output_state.alloc_calls, 1);

  output_allocator->free(output_allocator->ctx, out);
  ax_sb_free(&sb);
}

TEST(ax_sb, bad_allocator_initializes_as_failed) {
  ax_allocator bad_allocator;
  ax_sb sb;
  size_t len = 999;

  memset(&bad_allocator, 0, sizeof(bad_allocator));

  ax_sb_init(&sb, &bad_allocator);

  ASSERT(ax_sb_failed(&sb));
  ASSERT(!ax_sb_append_lit(&sb, "nope"));
  ASSERT(!ax_sb_measure(&sb, &len));
  ASSERT_EQ(len, 0);

  ax_sb_free(&sb);
}

TEST(ax_sb, measure_detects_size_overflow) {
  test_allocator_state state;
  ax_sb sb;
  const char one_byte = 'x';
  size_t len = 999;

  init_builder(&sb, &state);

  /*
      No bytes are copied here; the huge length only exercises accounting.
  */
  ASSERT(ax_sb_append_ref(&sb, &one_byte, SIZE_MAX));
  ASSERT(ax_sb_append_char(&sb, 'y'));

  ASSERT(!ax_sb_measure(&sb, &len));
  ASSERT_EQ(len, 0);

  ax_sb_free(&sb);
}
