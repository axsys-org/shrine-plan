#include "axsys/vector.h"

#include <stdbool.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>

struct ax_vector {
  ax_allocator allocator_a;
  uint8_t* data_b;
  size_t elem_size_s;
  size_t len_s;
  size_t capacity_s;
};

static void* system_alloc(void* ctx, size_t size_s) {
  (void)ctx;
  return malloc(size_s);
}

static void* system_realloc(void* ctx, void* ptr, size_t size_s) {
  (void)ctx;
  return realloc(ptr, size_s);
}

static void system_free(void* ctx, void* ptr) {
  (void)ctx;
  free(ptr);
}

static bool allocator_is_valid(const ax_allocator* allocator_a) {
  return allocator_a != NULL && allocator_a->alloc != NULL &&
         allocator_a->free != NULL;
}

static bool item_bytes(size_t capacity_s, size_t elem_size_s, size_t* bytes_s) {
  if (elem_size_s == 0 || capacity_s > (SIZE_MAX / elem_size_s)) {
    return false;
  }

  *bytes_s = capacity_s * elem_size_s;
  return true;
}

static ax_status resize_storage(ax_vector* vector, size_t capacity_s) {
  size_t bytes_s = 0;

  if (!item_bytes(capacity_s, vector->elem_size_s, &bytes_s)) {
    return AX_ERR_ALLOC;
  }

  if (vector->allocator_a.realloc != NULL) {
    void* resized = vector->allocator_a.realloc(vector->allocator_a.ctx,
                                                (void*)vector->data_b, bytes_s);
    if (resized == NULL) {
      return AX_ERR_ALLOC;
    }

    vector->data_b = (uint8_t*)resized;
    vector->capacity_s = capacity_s;
    return AX_OK;
  }

  uint8_t* next =
      (uint8_t*)vector->allocator_a.alloc(vector->allocator_a.ctx, bytes_s);
  if (next == NULL) {
    return AX_ERR_ALLOC;
  }

  if (vector->data_b != NULL && vector->len_s > 0) {
    memcpy((void*)next, (const void*)vector->data_b,
           vector->len_s * vector->elem_size_s);
  }

  vector->allocator_a.free(vector->allocator_a.ctx, (void*)vector->data_b);
  vector->data_b = next;
  vector->capacity_s = capacity_s;
  return AX_OK;
}

const ax_allocator ax_sys_a = {
    .ctx = NULL,
    .alloc = system_alloc,
    .realloc = system_realloc,
    .free = system_free,
};
const ax_allocator* ax_allocator_system(void) {

  return &ax_sys_a;
}

ax_vector* ax_vector_create(const ax_allocator* allocator_a) {
  return ax_vector_create_sized(allocator_a, sizeof(void*));
}

ax_vector* ax_vector_create_sized(const ax_allocator* allocator_a,
                                  size_t elem_size_s) {
  if (!allocator_is_valid(allocator_a)) {
    return NULL;
  }
  if (elem_size_s == 0) {
    return NULL;
  }

  ax_vector* vector = allocator_a->alloc(allocator_a->ctx, sizeof(*vector));
  if (vector == NULL) {
    return NULL;
  }

  vector->allocator_a = *allocator_a;
  vector->data_b = NULL;
  vector->elem_size_s = elem_size_s;
  vector->len_s = 0;
  vector->capacity_s = 0;

  return vector;
}

void ax_vector_destroy(ax_vector* vector) {
  if (vector == NULL) {
    return;
  }

  ax_allocator allocator_a = vector->allocator_a;
  allocator_a.free(allocator_a.ctx, (void*)vector->data_b);
  allocator_a.free(allocator_a.ctx, vector);
}

static ax_status ensure_push_capacity(ax_vector* vector) {
  if (vector == NULL) {
    return AX_ERR_INVALID;
  }

  if (vector->len_s == vector->capacity_s) {
    size_t next_capacity_s = 4;
    if (vector->capacity_s > 0) {
      if (vector->capacity_s > (SIZE_MAX / 2)) {
        return AX_ERR_ALLOC;
      }
      next_capacity_s = vector->capacity_s * 2;
    }

    ax_status status = ax_vector_reserve(vector, next_capacity_s);
    if (status != AX_OK) {
      return status;
    }
  }

  return AX_OK;
}

ax_status ax_vector_push(ax_vector* vector, void* item_v) {
  if (vector == NULL || vector->elem_size_s != sizeof(void*)) {
    return AX_ERR_INVALID;
  }

  ax_status status = ensure_push_capacity(vector);
  if (status != AX_OK) {
    return status;
  }

  memcpy((void*)(vector->data_b + vector->len_s * vector->elem_size_s), &item_v,
         sizeof(item_v));
  vector->len_s += 1;
  return AX_OK;
}

ax_status ax_vector_push_copy(ax_vector* vector, const void* item_v) {
  if (item_v == NULL) {
    return AX_ERR_INVALID;
  }

  ax_status status = ensure_push_capacity(vector);
  if (status != AX_OK) {
    return status;
  }

  memcpy((void*)(vector->data_b + vector->len_s * vector->elem_size_s), item_v,
         vector->elem_size_s);
  vector->len_s += 1;
  return AX_OK;
}

ax_status ax_vector_push_u8(ax_vector* vector, uint8_t item_v) {
  if (vector == NULL || vector->elem_size_s != sizeof(uint8_t)) {
    return AX_ERR_INVALID;
  }

  return ax_vector_push_copy(vector, &item_v);
}

static void* slot_at(const ax_vector* vector, size_t index_i) {
  return (void*)(vector->data_b + index_i * vector->elem_size_s);
}

void* ax_vector_pop(ax_vector* vector) {
  if (vector == NULL || vector->len_s == 0 ||
      vector->elem_size_s != sizeof(void*)) {
    return NULL;
  }

  vector->len_s -= 1;
  void* item_v = NULL;
  memcpy(&item_v, slot_at(vector, vector->len_s), sizeof(item_v));
  memset(slot_at(vector, vector->len_s), 0, sizeof(item_v));
  return item_v;
}

void* ax_vector_get(const ax_vector* vector, size_t index_i) {
  if (vector == NULL || index_i >= vector->len_s ||
      vector->elem_size_s != sizeof(void*)) {
    return NULL;
  }

  void* item_v = NULL;
  memcpy(&item_v, slot_at(vector, index_i), sizeof(item_v));
  return item_v;
}

void* ax_vector_get_slot(const ax_vector* vector, size_t index_i) {
  if (vector == NULL || index_i >= vector->len_s) {
    return NULL;
  }

  return slot_at(vector, index_i);
}

void* ax_vector_top_slot(const ax_vector* vector) {
  if (vector == NULL || vector->len_s == 0) {
    return NULL;
  }

  return slot_at(vector, vector->len_s - 1);
}

ax_status ax_vector_set(ax_vector* vector, size_t index_i, void* item_v) {
  if (vector == NULL) {
    return AX_ERR_INVALID;
  }

  if (index_i >= vector->len_s) {
    return AX_ERR_BOUNDS;
  }

  if (vector->elem_size_s != sizeof(void*)) {
    return AX_ERR_INVALID;
  }

  memcpy(slot_at(vector, index_i), &item_v, sizeof(item_v));
  return AX_OK;
}

ax_status ax_vector_set_copy(ax_vector* vector, size_t index_i,
                             const void* item_v) {
  if (vector == NULL || item_v == NULL) {
    return AX_ERR_INVALID;
  }

  if (index_i >= vector->len_s) {
    return AX_ERR_BOUNDS;
  }

  memcpy(slot_at(vector, index_i), item_v, vector->elem_size_s);
  return AX_OK;
}

void* ax_vector_data(const ax_vector* vector) {
  if (vector == NULL) {
    return NULL;
  }

  return vector->data_b;
}

size_t ax_vector_elem_size(const ax_vector* vector) {
  if (vector == NULL) {
    return 0;
  }

  return vector->elem_size_s;
}

size_t ax_vector_len(const ax_vector* vector) {
  if (vector == NULL) {
    return 0;
  }

  return vector->len_s;
}

size_t ax_vector_capacity(const ax_vector* vector) {
  if (vector == NULL) {
    return 0;
  }

  return vector->capacity_s;
}

ax_status ax_vector_reserve(ax_vector* vector, size_t capacity_s) {
  if (vector == NULL) {
    return AX_ERR_INVALID;
  }

  if (capacity_s <= vector->capacity_s) {
    return AX_OK;
  }

  return resize_storage(vector, capacity_s);
}

ax_status ax_vector_shrink(ax_vector* vector) {
  if (vector == NULL) {
    return AX_ERR_INVALID;
  }

  if (vector->len_s == vector->capacity_s) {
    return AX_OK;
  }

  if (vector->len_s == 0) {
    vector->allocator_a.free(vector->allocator_a.ctx, (void*)vector->data_b);
    vector->data_b = NULL;
    vector->capacity_s = 0;
    return AX_OK;
  }

  return resize_storage(vector, vector->len_s);
}
