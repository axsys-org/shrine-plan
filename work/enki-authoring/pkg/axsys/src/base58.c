#include "axsys/base58.h"

#include <string.h>

#include "axsys/assume.h"

static const char ax_b58_alphabet[] =
    "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz";

size_t ax_base58(const uint8_t* b, size_t n, char* out) {
  ax_assume(n <= 64, "ax_base58: input too large");
  size_t zeros = 0;
  while (zeros < n && b[zeros] == 0)
    zeros++;

  /* big-endian base-256 -> base-58 by repeated division */
  uint8_t digits[AX_BASE58_CAP(64)];
  size_t ndigits = 0;
  for (size_t i = zeros; i < n; i++) {
    unsigned carry = b[i];
    for (size_t j = 0; j < ndigits; j++) {
      carry += (unsigned)digits[j] << 8;
      digits[j] = (uint8_t)(carry % 58);
      carry /= 58;
    }
    while (carry > 0) {
      digits[ndigits++] = (uint8_t)(carry % 58);
      carry /= 58;
    }
  }

  size_t len = 0;
  for (size_t i = 0; i < zeros; i++)
    out[len++] = '1';
  for (size_t i = ndigits; i > 0; i--)
    out[len++] = ax_b58_alphabet[digits[i - 1]];
  out[len] = '\0';
  return len;
}
