#include "axsys/vector.h"
#include "fff.h"

#include "test.h"
#include <stdint.h>
#include <stdlib.h>

DEFINE_FFF_GLOBALS;

FAKE_VALUE_FUNC(void*, fake_alloc, void*, size_t);
FAKE_VALUE_FUNC(void*, fake_realloc, void*, void*, size_t);
FAKE_VOID_FUNC(fake_free, void*, void*);

static ax_vector* fixture_vector;

static void setup(void) {
  fixture_vector = ax_vector_create(ax_allocator_system());
  ASSERT_NOT_NULL(fixture_vector);
}

static void teardown(void) {
  ax_vector_destroy(fixture_vector);
  fixture_vector = NULL;
}

TEST_FIXTURE(vector, setup, teardown)

static const ax_allocator* fake_allocator(void) {
  static const ax_allocator allocator_a = {
      .ctx = NULL,
      .alloc = fake_alloc,
      .realloc = fake_realloc,
      .free = fake_free,
  };
  return &allocator_a;
}

static void reset_allocator_fakes(void) {
  RESET_FAKE(fake_alloc);
  RESET_FAKE(fake_realloc);
  RESET_FAKE(fake_free);
}

static void* malloc_fake(void* ctx, size_t size_s) {
  (void)ctx;
  return malloc(size_s);
}

static void* realloc_fake(void* ctx, void* ptr, size_t size_s) {
  (void)ctx;
  return realloc(ptr, size_s);
}

static void free_fake(void* ctx, void* ptr) {
  (void)ctx;
  free(ptr);
}

static void* fail_second_alloc(void* ctx, size_t size_s) {
  (void)ctx;
  if (fake_alloc_fake.call_count >= 2u) {
    (void)size_s;
    return NULL;
  }

  return malloc(size_s);
}

static void* always_fail_realloc(void* ctx, void* ptr, size_t size_s) {
  (void)ctx;
  (void)ptr;
  (void)size_s;
  return NULL;
}

TEST(vector, starts_empty) {
  ASSERT_EQ(ax_vector_len(fixture_vector), 0);
  ASSERT_EQ(ax_vector_capacity(fixture_vector), 0);
  ASSERT_NULL(ax_vector_pop(fixture_vector));
}

TEST(vector, pushes_gets_sets_and_pops) {
  uintptr_t one = (uintptr_t)0x1u;
  uintptr_t two = (uintptr_t)0x2u;
  uintptr_t three = (uintptr_t)0x3u;

  ASSERT_EQ(ax_vector_push(fixture_vector, (void*)one), AX_OK);
  ASSERT_EQ(ax_vector_push(fixture_vector, (void*)two), AX_OK);
  ASSERT_EQ(ax_vector_len(fixture_vector), 2);
  ASSERT_EQ(ax_vector_get(fixture_vector, 0), (void*)one);
  ASSERT_EQ(ax_vector_set(fixture_vector, 1, (void*)three), AX_OK);
  ASSERT_EQ(ax_vector_get(fixture_vector, 1), (void*)three);
  ASSERT_EQ(ax_vector_pop(fixture_vector), (void*)three);
  ASSERT_EQ(ax_vector_pop(fixture_vector), (void*)one);
  ASSERT_NULL(ax_vector_pop(fixture_vector));
}

TEST(vector, rejects_invalid_arguments) {
  ASSERT_NULL(ax_vector_create(&(const ax_allocator){0}));
  ASSERT_EQ(ax_vector_push(NULL, NULL), AX_ERR_INVALID);
  ASSERT_EQ(ax_vector_set(NULL, 0, NULL), AX_ERR_INVALID);
  ASSERT_EQ(ax_vector_reserve(NULL, 1), AX_ERR_INVALID);
  ASSERT_EQ(ax_vector_shrink(NULL), AX_ERR_INVALID);
  ASSERT_EQ(ax_vector_set(fixture_vector, 0, NULL), AX_ERR_BOUNDS);
  ASSERT_NULL(ax_vector_get(fixture_vector, 0));
}

TEST(vector, allocator_alloc_failure_is_reported_on_create_and_growth) {
  reset_allocator_fakes();
  fake_alloc_fake.return_val = NULL;

  ASSERT_NULL(ax_vector_create(fake_allocator()));
  ASSERT_EQ(fake_alloc_fake.call_count, 1);

  reset_allocator_fakes();
  fake_alloc_fake.custom_fake = fail_second_alloc;
  fake_free_fake.custom_fake = free_fake;

  ax_vector* vector = ax_vector_create(fake_allocator());
  ASSERT_NOT_NULL(vector);
  ASSERT_EQ(ax_vector_push(vector, (void*)(uintptr_t)1u), AX_ERR_ALLOC);
  ASSERT_EQ(ax_vector_len(vector), 0);

  ax_vector_destroy(vector);
  ASSERT_GTE(fake_free_fake.call_count, 1);
}

TEST(vector, allocator_realloc_failure_keeps_existing_storage) {
  reset_allocator_fakes();
  fake_alloc_fake.custom_fake = malloc_fake;
  fake_realloc_fake.custom_fake = realloc_fake;
  fake_free_fake.custom_fake = free_fake;

  ax_vector* vector = ax_vector_create(fake_allocator());
  ASSERT_NOT_NULL(vector);
  ASSERT_EQ(ax_vector_reserve(vector, 8), AX_OK);
  ASSERT_EQ(ax_vector_push(vector, (void*)(uintptr_t)1u), AX_OK);

  size_t capacity_s = ax_vector_capacity(vector);
  fake_realloc_fake.custom_fake = always_fail_realloc;

  ASSERT_EQ(ax_vector_shrink(vector), AX_ERR_ALLOC);
  ASSERT_EQ(ax_vector_len(vector), 1);
  ASSERT_EQ(ax_vector_capacity(vector), capacity_s);
  ASSERT_EQ(ax_vector_get(vector, 0), (void*)(uintptr_t)1u);

  fake_realloc_fake.custom_fake = realloc_fake;
  ax_vector_destroy(vector);
}

typedef struct reserve_case {
  size_t requested;
  size_t expected;
} reserve_case;

TEST(vector, reserve_tracks_capacity) {
  static const reserve_case cases[] = {
      {.requested = 0, .expected = 0},
      {.requested = 1, .expected = 1},
      {.requested = 8, .expected = 8},
      {.requested = 32, .expected = 32},
  };

  for (size_t i = 0; i < sizeof(cases) / sizeof(cases[0]); i++) {
    const reserve_case* param = &cases[i];
    ax_vector* vector = ax_vector_create(ax_allocator_system());
    ASSERT_NOT_NULL(vector);
    ASSERT_EQ(ax_vector_reserve(vector, param->requested), AX_OK);
    ASSERT_GTE(ax_vector_capacity(vector), param->expected);
    ASSERT_EQ(ax_vector_len(vector), 0);
    ax_vector_destroy(vector);
  }
}

TEST(vector, set_get_roundtrip) {
  static const uintptr_t data[] = {
      (uintptr_t)0u,
      (uintptr_t)1u,
      (uintptr_t)255u,
      UINTPTR_MAX,
  };

  for (size_t i = 0; i < sizeof(data) / sizeof(data[0]); i++) {
    uintptr_t raw = data[i];
    ax_vector* vector = ax_vector_create(ax_allocator_system());
    ASSERT_NOT_NULL(vector);
    ASSERT_EQ(ax_vector_push(vector, NULL), AX_OK);
    ASSERT_EQ(ax_vector_set(vector, 0, (void*)raw), AX_OK);
    ASSERT_EQ(ax_vector_get(vector, 0), (void*)raw);
    ax_vector_destroy(vector);
  }
}
