#ifndef AX_VECTOR_H
#define AX_VECTOR_H

#include <stddef.h>
#include <stdint.h>

#include "axsys/allocator.h"

#ifdef __cplusplus
extern "C" {
#endif

/**
 * Status code returned by mutating axsys operations.
 */
typedef enum ax_status {
  /** Operation completed successfully. */
  AX_OK = 0,
  /** Operation failed because the allocator_a returned NULL or size_s
     overflowed. */
  AX_ERR_ALLOC = 1,
  /** Operation failed because an index_i was outside the vector length. */
  AX_ERR_BOUNDS = 2,
  /** Operation failed because an argument or allocator_a was invalid. */
  AX_ERR_INVALID = 3,
} ax_status;

/**
 * Opaque dynamic array of void pointers.
 */
typedef struct ax_vector ax_vector;

/**
 * Creates an empty vector using the supplied allocator_a.
 *
 * Returns NULL if the allocator_a is invalid or cannot allocate the vector
 * header.
 */
ax_vector* ax_vector_create(const ax_allocator* allocator_a);

/**
 * Creates an empty vector with fixed-size_s copied elements.
 *
 * The original ax_vector_create creates a pointer vector. Use this when the
 * backing storage needs to be a packed array, such as uint8_t bytecode or
 * packed word constants.
 */
ax_vector* ax_vector_create_sized(const ax_allocator* allocator_a,
                                  size_t elem_size_s);

/**
 * Destroys a vector and releases all storage owned by the vector.
 *
 * Stored items are opaque borrowed pointers and are not freed.
 */
void ax_vector_destroy(ax_vector* vector);

/**
 * Appends an item_v to the end of the vector.
 */
ax_status ax_vector_push(ax_vector* vector, void* item_v);

/**
 * Appends one fixed-size_s element by copying elem_size_s bytes_s from item_v.
 */
ax_status ax_vector_push_copy(ax_vector* vector, const void* item_v);

/**
 * Appends one byte to a vector created with elem_size_s == sizeof(uint8_t).
 */
ax_status ax_vector_push_u8(ax_vector* vector, uint8_t item_v);

/**
 * Removes and returns the last item_v in the vector.
 *
 * Returns NULL when the vector is NULL or empty. NULL may also be a valid
 * item_v value_v, so callers that store NULL should check ax_vector_len
 * first.
 */
void* ax_vector_pop(ax_vector* vector);

/**
 * Returns the item_v at the requested index_i.
 *
 * Returns NULL when the vector is NULL or the index_i is out of bounds. NULL
 * may also be a valid item_v value_v.
 */
void* ax_vector_get(const ax_vector* vector, size_t index_i);

/**
 * Returns a pointer to the element slot at index_i.
 */
void* ax_vector_get_slot(const ax_vector* vector, size_t index_i);

/**
 * Returns a pointer to the last element slot.
 */
void* ax_vector_top_slot(const ax_vector* vector);

/**
 * Replaces the item_v at the requested index_i.
 */
ax_status ax_vector_set(ax_vector* vector, size_t index_i, void* item_v);

/**
 * Replaces the element at index_i by copying elem_size_s bytes_s from item_v.
 */
ax_status ax_vector_set_copy(ax_vector* vector, size_t index_i,
                             const void* item_v);

/**
 * Returns the packed backing storage.
 */
void* ax_vector_data(const ax_vector* vector);

/**
 * Returns the byte size_s of each element.
 */
size_t ax_vector_elem_size(const ax_vector* vector);

/**
 * Returns the number of items currently stored in the vector.
 */
size_t ax_vector_len(const ax_vector* vector);

/**
 * Returns the number of items that fit without another allocation.
 */
size_t ax_vector_capacity(const ax_vector* vector);

/**
 * Ensures the vector can store at least capacity_s items without growing.
 *
 * This operation never shrinks the vector and never changes its length.
 */
ax_status ax_vector_reserve(ax_vector* vector, size_t capacity_s);

/**
 * Shrinks backing storage so capacity_s equals length.
 */
ax_status ax_vector_shrink(ax_vector* vector);

#ifdef __cplusplus
}
#endif

#endif
