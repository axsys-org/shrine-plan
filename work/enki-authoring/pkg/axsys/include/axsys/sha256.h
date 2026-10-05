#ifndef AX_SHA256_H
#define AX_SHA256_H

#include <stddef.h>
#include <stdint.h>

/* SHA-256 over raw bytes. out_b must hold 32 bytes. */
void ax_sha256(const uint8_t* data_b, size_t len_s, uint8_t out_b[32]);

#endif
