#include "axsys/vector.h"
#include "theft.h"

#include <inttypes.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define PROPERTY_TRIALS  250u
#define MAX_SEQUENCE_LEN 64u

typedef struct allocation_header {
  size_t size_s;
} allocation_header;

typedef struct accounting_allocator {
  size_t live_allocations;
  size_t live_bytes;
} accounting_allocator;

typedef struct sequence_case {
  size_t len_s;
  uintptr_t values[MAX_SEQUENCE_LEN];
  size_t reserve;
} sequence_case;

static void* checked_malloc(size_t size_s) {
  void* ptr = malloc(size_s);
  if (ptr == NULL) {
    abort();
  }

  return ptr;
}

static void* accounting_alloc(void* ctx, size_t size_s) {
  accounting_allocator* account = ctx;
  allocation_header* header = malloc(sizeof(*header) + size_s);
  if (header == NULL) {
    return NULL;
  }

  header->size_s = size_s;
  account->live_allocations += 1;
  account->live_bytes += size_s;
  return header + 1;
}

static void* accounting_realloc(void* ctx, void* ptr, size_t size_s) {
  if (ptr == NULL) {
    return accounting_alloc(ctx, size_s);
  }

  accounting_allocator* account = ctx;
  allocation_header* old_header = ((allocation_header*)ptr) - 1;
  size_t old_size = old_header->size_s;
  allocation_header* new_header =
      realloc(old_header, sizeof(*new_header) + size_s);
  if (new_header == NULL) {
    return NULL;
  }

  new_header->size_s = size_s;
  account->live_bytes = (account->live_bytes - old_size) + size_s;
  return new_header + 1;
}

static void accounting_free(void* ctx, void* ptr) {
  if (ptr == NULL) {
    return;
  }

  accounting_allocator* account = ctx;
  allocation_header* header = ((allocation_header*)ptr) - 1;
  account->live_allocations -= 1;
  account->live_bytes -= header->size_s;
  free(header);
}

static void make_accounting_allocator(accounting_allocator* account,
                                      ax_allocator* allocator_a) {
  *account = (accounting_allocator){0};
  *allocator_a = (ax_allocator){
      .ctx = account,
      .alloc = accounting_alloc,
      .realloc = accounting_realloc,
      .free = accounting_free,
  };
}

static void* generate_sequence(theft_rng* rng, void* ctx) {
  (void)ctx;
  sequence_case* generated = checked_malloc(sizeof(*generated));
  generated->len_s = theft_rng_range(rng, MAX_SEQUENCE_LEN + 1u);
  generated->reserve = theft_rng_range(rng, MAX_SEQUENCE_LEN * 2u);

  for (size_t i = 0; i < MAX_SEQUENCE_LEN; i += 1) {
    generated->values[i] = (uintptr_t)(theft_rng_next_u64(rng) | UINT64_C(1));
  }

  return generated;
}

static bool shrink_sequence(void** generated, void* ctx) {
  (void)ctx;
  sequence_case* sequence = *generated;
  if (sequence->len_s > 0) {
    sequence->len_s /= 2u;
    return true;
  }

  if (sequence->reserve > 0) {
    sequence->reserve /= 2u;
    return true;
  }

  for (size_t i = 0; i < MAX_SEQUENCE_LEN; i += 1) {
    if (sequence->values[i] > 1u) {
      sequence->values[i] /= 2u;
      return true;
    }
  }

  return false;
}

static void free_sequence(void* generated, void* ctx) {
  (void)ctx;
  free(generated);
}

static void message(char* out, size_t out_len, const char* text) {
  if (out_len == 0) {
    return;
  }

  (void)snprintf(out, out_len, "%s", text);
}

static bool property_push_increases_len(const void* generated, void* ctx,
                                        char* out, size_t out_len) {
  (void)ctx;
  const sequence_case* sequence = generated;
  accounting_allocator account;
  ax_allocator allocator_a;
  make_accounting_allocator(&account, &allocator_a);
  ax_vector* vector = ax_vector_create(&allocator_a);
  if (vector == NULL) {
    message(out, out_len, "vector creation failed");
    return false;
  }

  for (size_t i = 0; i < sequence->len_s; i += 1) {
    if (ax_vector_push(vector, (void*)sequence->values[i]) != AX_OK) {
      ax_vector_destroy(vector);
      message(out, out_len, "initial push failed");
      return false;
    }
  }

  size_t before = ax_vector_len(vector);
  bool ok = ax_vector_push(vector, (void*)sequence->values[0]) == AX_OK &&
            ax_vector_len(vector) == before + 1u;

  ax_vector_destroy(vector);
  if (!ok || account.live_allocations != 0 || account.live_bytes != 0) {
    message(out, out_len,
            "push did not increase length by exactly one or leaked");
    return false;
  }

  return true;
}

static bool property_get_pushed_item(const void* generated, void* ctx,
                                     char* out, size_t out_len) {
  (void)ctx;
  const sequence_case* sequence = generated;
  accounting_allocator account;
  ax_allocator allocator_a;
  make_accounting_allocator(&account, &allocator_a);
  ax_vector* vector = ax_vector_create(&allocator_a);
  if (vector == NULL) {
    message(out, out_len, "vector creation failed");
    return false;
  }

  for (size_t i = 0; i < sequence->len_s; i += 1) {
    if (ax_vector_push(vector, (void*)sequence->values[i]) != AX_OK) {
      ax_vector_destroy(vector);
      message(out, out_len, "initial push failed");
      return false;
    }
  }

  size_t index_i = ax_vector_len(vector);
  void* value_v = (void*)sequence->values[0];
  bool ok = ax_vector_push(vector, value_v) == AX_OK &&
            ax_vector_get(vector, index_i) == value_v;

  ax_vector_destroy(vector);
  if (!ok || account.live_allocations != 0 || account.live_bytes != 0) {
    message(out, out_len,
            "pushed item_v was not retrievable at old_o length or leaked");
    return false;
  }

  return true;
}

static bool property_pushes_then_pops_empty(const void* generated, void* ctx,
                                            char* out, size_t out_len) {
  (void)ctx;
  const sequence_case* sequence = generated;
  accounting_allocator account;
  ax_allocator allocator_a;
  make_accounting_allocator(&account, &allocator_a);
  ax_vector* vector = ax_vector_create(&allocator_a);
  if (vector == NULL) {
    message(out, out_len, "vector creation failed");
    return false;
  }

  for (size_t i = 0; i < sequence->len_s; i += 1) {
    if (ax_vector_push(vector, (void*)sequence->values[i]) != AX_OK) {
      ax_vector_destroy(vector);
      message(out, out_len, "push failed");
      return false;
    }
  }

  for (size_t i = sequence->len_s; i > 0; i -= 1) {
    void* popped = ax_vector_pop(vector);
    if (popped != (void*)sequence->values[i - 1u]) {
      ax_vector_destroy(vector);
      message(out, out_len, "pop order changed");
      return false;
    }
  }

  bool ok = ax_vector_len(vector) == 0;
  ax_vector_destroy(vector);
  if (!ok || account.live_allocations != 0 || account.live_bytes != 0) {
    message(out, out_len, "pop sequence did not return to empty or leaked");
    return false;
  }

  return true;
}

static bool property_reserve_keeps_len_and_capacity(const void* generated,
                                                    void* ctx, char* out,
                                                    size_t out_len) {
  (void)ctx;
  const sequence_case* sequence = generated;
  accounting_allocator account;
  ax_allocator allocator_a;
  make_accounting_allocator(&account, &allocator_a);
  ax_vector* vector = ax_vector_create(&allocator_a);
  if (vector == NULL) {
    message(out, out_len, "vector creation failed");
    return false;
  }

  for (size_t i = 0; i < sequence->len_s; i += 1) {
    if (ax_vector_push(vector, (void*)sequence->values[i]) != AX_OK) {
      ax_vector_destroy(vector);
      message(out, out_len, "push failed");
      return false;
    }
  }

  size_t before_len = ax_vector_len(vector);
  size_t before_capacity = ax_vector_capacity(vector);
  bool ok = ax_vector_reserve(vector, sequence->reserve) == AX_OK &&
            ax_vector_len(vector) == before_len &&
            ax_vector_capacity(vector) >= before_capacity;

  ax_vector_destroy(vector);
  if (!ok || account.live_allocations != 0 || account.live_bytes != 0) {
    message(out, out_len,
            "reserve changed length, decreased capacity_s, or leaked");
    return false;
  }

  return true;
}

static int run_one(const char* name_v, theft_check_fn check, uint64_t seed) {
  theft_property property = {
      .name_v = name_v,
      .trials = PROPERTY_TRIALS,
      .generate = generate_sequence,
      .check = check,
      .shrink = shrink_sequence,
      .free = free_sequence,
      .ctx = NULL,
  };

  return theft_run_property(&property, seed);
}

int main(void) {
  uint64_t seed = theft_seed_from_env("THEFT_SEED", UINT64_C(0x5eed1234c0ffee));
  int failures = 0;

  failures += run_one("len_s(push(v, x)) == len_s(v) + 1",
                      property_push_increases_len, seed ^ UINT64_C(0x101));
  failures += run_one("get(push(v, x), len_s(v)) == x",
                      property_get_pushed_item, seed ^ UINT64_C(0x202));
  failures += run_one("push sequence then equal pops returns empty",
                      property_pushes_then_pops_empty, seed ^ UINT64_C(0x303));
  failures +=
      run_one("reserve never decreases capacity_s or changes len_s",
              property_reserve_keeps_len_and_capacity, seed ^ UINT64_C(0x404));

  return failures == 0 ? EXIT_SUCCESS : EXIT_FAILURE;
}
