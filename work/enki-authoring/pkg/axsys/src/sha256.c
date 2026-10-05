#include "axsys/sha256.h"

#include <openssl/sha.h>

void ax_sha256(const uint8_t* data_b, size_t len_s, uint8_t out_b[32]) {
  SHA256(data_b, len_s, out_b);
}
