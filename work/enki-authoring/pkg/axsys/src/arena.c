#include "axsys/arena.h"

#include <stdint.h>
#include <sys/mman.h>

#ifndef MAP_ANONYMOUS
#define MAP_ANONYMOUS MAP_ANON
#endif

ax_arena* ax_arena_create(const ax_allocator* loc_a, size_t cap_s) {
  if (!loc_a)
    return NULL;
  if (cap_s > SIZE_MAX - sizeof(ax_arena))
    return NULL;
  size_t siz_s = sizeof(ax_arena) + cap_s;
  ax_arena* a = (ax_arena*)loc_a->alloc(loc_a->ctx, siz_s);
  if (!a) {
    return NULL;
  }
  a->off_o = sizeof(ax_arena);
  a->ptr = (unsigned char*)a;
  a->cap_s = siz_s;
  a->our_a = *loc_a;
  a->mmap_f = false;
  a->allocator_a = (ax_allocator){
      .ctx = a,
      .alloc = ax_arena_alloc,
      .realloc = NULL,
      .free = ax_arena_free,
  };
  return a;
}

/** TODO: added MAP_NORESERVE which will create a SIGBUS at fault time instead
 * of failing at allocation time on OOM. ADD SIGNAL HANDLING!!*/
ax_arena* ax_arena_create_overcommit(size_t cap_s) {
  if (cap_s > SIZE_MAX - sizeof(ax_arena))
    return NULL;
  size_t siz_s = sizeof(ax_arena) + cap_s;
  void* mem = mmap(NULL, siz_s, PROT_READ | PROT_WRITE,
                   MAP_PRIVATE | MAP_ANONYMOUS | MAP_NORESERVE, -1, 0);
  if (mem == MAP_FAILED)
    return NULL;
  ax_arena* a = mem;
  a->off_o = sizeof(ax_arena);
  a->ptr = (unsigned char*)a;
  a->cap_s = siz_s;
  a->our_a = (ax_allocator){0};
  a->mmap_f = true;
  a->allocator_a = (ax_allocator){
      .ctx = a,
      .alloc = ax_arena_alloc,
      .realloc = NULL,
      .free = ax_arena_free,
  };
  return a;
}

void ax_arena_destroy(ax_arena* a) {
  if (!a)
    return;
  if (a->mmap_f) {
    (void)munmap(a, a->cap_s);
    return;
  }
  a->our_a.free(a->our_a.ctx, a);
}
void* ax_arena_alloc(void* ctx, size_t size_s) {
  ax_arena* a = ctx;
  if (!a)
    return NULL;
  size_t align_s = _Alignof(max_align_t);
  size_t old_o = (a->off_o + align_s - 1) & ~(align_s - 1);
  if (old_o > a->cap_s || size_s > a->cap_s - old_o) {
    return NULL;
  }
  a->off_o = old_o + size_s;
  return (void*)(a->ptr + old_o);
}
void* ax_arena_alloc_aligned(void* ctx, size_t size_s, size_t align_s) {
  ax_arena* a = ctx;
  if (!a || align_s == 0 || (align_s & (align_s - 1)) != 0)
    return NULL; /* alignment must be a power of two for the mask below */
  size_t old_o = (a->off_o + align_s - 1) & ~(align_s - 1);
  if (old_o > a->cap_s || size_s > a->cap_s - old_o) {
    return NULL;
  }
  a->off_o = old_o + size_s;
  return (void*)(a->ptr + old_o);
}
void ax_arena_free(void* ctx, void* ptr) {
  (void)ctx;
  (void)ptr;
  return;
}
void ax_arena_reset(ax_arena* a) {
  if (!a)
    return;
  a->off_o = sizeof(ax_arena);
}
const ax_allocator* ax_arena_as_allocator(ax_arena* a) {
  if (!a)
    return NULL;
  return &a->allocator_a;
}
void* ax_arena_start(ax_arena* a) {
  if (!a)
    return NULL;
  return (void*)(a->ptr + sizeof(ax_arena));
}
void* ax_arena_end(ax_arena* a) {
  if (!a)
    return NULL;
  return (void*)(a->ptr + a->cap_s);
}
