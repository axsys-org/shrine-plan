#pragma once
#include <stdbool.h>
#include <stddef.h>

#include "axsys/allocator.h"

typedef struct ax_arena {
  unsigned char* ptr;
  size_t cap_s;
  size_t off_o;
  ax_allocator our_a;
  ax_allocator allocator_a;
  bool mmap_f;
} ax_arena;

ax_arena* ax_arena_create(const ax_allocator* parent_a, size_t cap_s);
ax_arena* ax_arena_create_overcommit(size_t cap_s);
void ax_arena_destroy(ax_arena* a);
void* ax_arena_alloc(void* ctx, size_t size_s);
void ax_arena_free(void* ctx, void* ptr); // no-op_b
void ax_arena_reset(ax_arena* a);
const ax_allocator* ax_arena_as_allocator(ax_arena* a);
void* ax_arena_start(ax_arena* a);
void* ax_arena_end(ax_arena* a);
void* ax_arena_alloc_aligned(void* ctx, size_t size_s, size_t align_s);
