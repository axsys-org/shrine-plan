#ifndef AX_BASE58_H
#define AX_BASE58_H

/* Base58 encoding (Bitcoin alphabet), used for content-hash filenames. */

#include <stddef.h>
#include <stdint.h>

/* Worst case for n input bytes: ceil(n * log(256)/log(58)) chars. */
#define AX_BASE58_CAP(n) ((n) * 137 / 100 + 2)

/* Encode b[0..n) into out (NUL-terminated); returns the string length.
 * out must have room for AX_BASE58_CAP(n) bytes. */
size_t ax_base58(const uint8_t* b, size_t n, char* out);

#endif
