#include <stdint.h>
#include <stdlib.h>
#include <string.h>

#include "../../pkg/plan/src/silo_internal.h"

typedef struct fuzz_input {
  const uint8_t* bytes;
  size_t len;
  size_t pos;
} fuzz_input;

static bool fuzz_read(void* ctx, uint8_t* bytes, size_t len) {
  fuzz_input* in = ctx;
  if (in->pos > in->len || len > in->len - in->pos)
    return false;
  memcpy(bytes, in->bytes + in->pos, len);
  in->pos += len;
  return true;
}

static bool fuzz_rewind(void* ctx) {
  ((fuzz_input*)ctx)->pos = 0;
  return true;
}

int LLVMFuzzerTestOneInput(const uint8_t* data, size_t size);

int LLVMFuzzerTestOneInput(const uint8_t* data, size_t size) {
  fuzz_input in = {.bytes = data, .len = size};
  pl_silo_reader reader = {
      .ctx = &in,
      .read = fuzz_read,
      .rewind = fuzz_rewind,
      .len = size,
  };
  char err[192];
  pl_silo_scan scan = {0};
  (void)pl_silo_scan_stream(&reader, false, &scan, err, sizeof(err));
  pl_silo_scan_free(&scan);
  (void)pl_silo_scan_stream(&reader, true, &scan, err, sizeof(err));
  pl_silo_scan_free(&scan);
  return 0;
}
