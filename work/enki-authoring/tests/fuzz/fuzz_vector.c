#include "axsys/vector.h"

#include <stdint.h>
#include <stdlib.h>

int LLVMFuzzerTestOneInput(const uint8_t* data, size_t size);

static size_t bounded_index(uint8_t value, size_t len) {
  if (len == 0) {
    return 0;
  }

  return (size_t)value % len;
}

int LLVMFuzzerTestOneInput(const uint8_t* data, size_t size) {
  ax_vector* vector = ax_vector_create(ax_allocator_system());
  if (vector == NULL) {
    abort();
  }

  for (size_t offset = 0; offset < size; offset += 1) {
    uint8_t op = (uint8_t)(data[offset] % 6u);
    uint8_t value = data[offset];

    switch (op) {
    case 0:
      (void)ax_vector_push(vector, (void*)(uintptr_t)value);
      break;
    case 1:
      (void)ax_vector_pop(vector);
      break;
    case 2:
      (void)ax_vector_get(vector, bounded_index(value, ax_vector_len(vector)));
      break;
    case 3:
      if (ax_vector_len(vector) > 0) {
        (void)ax_vector_set(vector, bounded_index(value, ax_vector_len(vector)),
                            (void*)(uintptr_t)(value + 1u));
      }
      break;
    case 4:
      (void)ax_vector_reserve(vector, (size_t)value);
      break;
    case 5:
      (void)ax_vector_shrink(vector);
      break;
    default:
      break;
    }
  }

  ax_vector_destroy(vector);
  return 0;
}
