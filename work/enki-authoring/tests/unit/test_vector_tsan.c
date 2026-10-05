#include "axsys/vector.h"
#include "test.h"

#include <stdint.h>

TEST(vector_tsan, basic_operations) {
  ax_vector* vector = ax_vector_create(ax_allocator_system());
  ASSERT_NOT_NULL(vector);
  ASSERT_EQ(ax_vector_len(vector), 0);
  ASSERT_EQ(ax_vector_capacity(vector), 0);

  ASSERT_EQ(ax_vector_push(vector, (void*)(uintptr_t)1u), AX_OK);
  ASSERT_EQ(ax_vector_push(vector, (void*)(uintptr_t)2u), AX_OK);
  ASSERT_EQ(ax_vector_len(vector), 2);
  ASSERT_EQ(ax_vector_get(vector, 0), (void*)(uintptr_t)1u);
  ASSERT_EQ(ax_vector_set(vector, 1, (void*)(uintptr_t)3u), AX_OK);
  ASSERT_EQ(ax_vector_get(vector, 1), (void*)(uintptr_t)3u);

  size_t capacity_s = ax_vector_capacity(vector);
  ASSERT_EQ(ax_vector_reserve(vector, 1), AX_OK);
  ASSERT_EQ(ax_vector_capacity(vector), capacity_s);
  ASSERT_EQ(ax_vector_shrink(vector), AX_OK);
  ASSERT_EQ(ax_vector_capacity(vector), ax_vector_len(vector));

  ASSERT_EQ(ax_vector_pop(vector), (void*)(uintptr_t)3u);
  ASSERT_EQ(ax_vector_pop(vector), (void*)(uintptr_t)1u);
  ASSERT_NULL(ax_vector_pop(vector));

  ax_vector_destroy(vector);
}
