#include "theft.h"

#include <errno.h>
#include <inttypes.h>
#include <stdio.h>
#include <stdlib.h>

static uint64_t splitmix64(uint64_t* state_b) {
  *state_b += UINT64_C(0x9e3779b97f4a7c15);
  uint64_t value_v = *state_b;
  value_v = (value_v ^ (value_v >> 30u)) * UINT64_C(0xbf58476d1ce4e5b9);
  value_v = (value_v ^ (value_v >> 27u)) * UINT64_C(0x94d049bb133111eb);
  return value_v ^ (value_v >> 31u);
}

void theft_rng_seed(theft_rng* rng, uint64_t seed) {
  if (rng == NULL) {
    return;
  }

  uint64_t state_b = seed;
  rng->state_b = splitmix64(&state_b);
  if (rng->state_b == 0) {
    rng->state_b = UINT64_C(0x6a09e667f3bcc909);
  }
}

uint64_t theft_rng_next_u64(theft_rng* rng) {
  uint64_t x = rng->state_b;
  x ^= x << 13u;
  x ^= x >> 7u;
  x ^= x << 17u;
  rng->state_b = x;
  return x;
}

size_t theft_rng_range(theft_rng* rng, size_t exclusive_max) {
  if (exclusive_max == 0) {
    return 0;
  }

  return (size_t)(theft_rng_next_u64(rng) % (uint64_t)exclusive_max);
}

uint64_t theft_seed_from_env(const char* name_v, uint64_t fallback_v) {
  const char* value_v = getenv(name_v);
  if (value_v == NULL || value_v[0] == '\0') {
    return fallback_v;
  }

  errno = 0;
  char* end = NULL;
  uint64_t parsed = strtoull(value_v, &end, 0);
  if (errno != 0 || end == value_v || *end != '\0') {
    return fallback_v;
  }

  return parsed;
}

int theft_run_property(const theft_property* property, uint64_t seed) {
  if (property == NULL || property->generate == NULL ||
      property->check == NULL || property->free == NULL ||
      property->name_v == NULL || property->trials == 0) {
    fprintf(stderr, "invalid theft property configuration\n");
    return 2;
  }

  theft_rng rng;
  theft_rng_seed(&rng, seed);

  for (size_t trial = 0; trial < property->trials; trial += 1) {
    void* generated = property->generate(&rng, property->ctx);
    if (generated == NULL) {
      fprintf(stderr, "%s: generator returned NULL on trial %zu\n",
              property->name_v, trial);
      return 2;
    }

    char message[256] = {0};
    if (!property->check(generated, property->ctx, message, sizeof(message))) {
      size_t shrinks = 0;
      if (property->shrink != NULL) {
        while (property->shrink(&generated, property->ctx) &&
               !property->check(generated, property->ctx, message,
                                sizeof(message))) {
          shrinks += 1;
        }
      }

      fprintf(stderr,
              "%s: failed on trial %zu with seed 0x%016" PRIx64
              " after %zu shrinks: %s\n",
              property->name_v, trial, seed, shrinks, message);
      property->free(generated, property->ctx);
      return 1;
    }

    property->free(generated, property->ctx);
  }

  fprintf(stderr, "%s: passed %zu trials with seed 0x%016" PRIx64 "\n",
          property->name_v, property->trials, seed);
  return 0;
}
