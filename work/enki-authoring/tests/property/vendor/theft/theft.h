#ifndef ENKI_VENDOR_THEFT_H
#define ENKI_VENDOR_THEFT_H

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

typedef struct theft_rng {
  uint64_t state_b;
} theft_rng;

typedef void* (*theft_generate_fn)(theft_rng* rng, void* ctx);
typedef bool (*theft_check_fn)(const void* generated, void* ctx, char* message,
                               size_t message_len);
typedef bool (*theft_shrink_fn)(void** generated, void* ctx);
typedef void (*theft_free_fn)(void* generated, void* ctx);

typedef struct theft_property {
  const char* name_v;
  size_t trials;
  theft_generate_fn generate;
  theft_check_fn check;
  theft_shrink_fn shrink;
  theft_free_fn free;
  void* ctx;
} theft_property;

void theft_rng_seed(theft_rng* rng, uint64_t seed);
uint64_t theft_rng_next_u64(theft_rng* rng);
size_t theft_rng_range(theft_rng* rng, size_t exclusive_max);
uint64_t theft_seed_from_env(const char* name_v, uint64_t fallback_v);
int theft_run_property(const theft_property* property, uint64_t seed);

#endif
