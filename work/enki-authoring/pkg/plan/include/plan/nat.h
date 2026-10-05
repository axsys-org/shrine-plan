#ifndef PL_NAT_H
#define PL_NAT_H

/*
 * Nat arithmetic (mpn, never mpz, on the heap representation).
 *
 * Allocating helpers take rooted slots (pointers into the value stack or
 * another registered root) rather than bare values: they reserve
 * internally, which may move every heap object, and re-fetch operands
 * through the slot (I4 by construction).
 */

#include "plan/heap.h"
#include "plan/value.h"

/* Reads (no allocation). */
int pl_nat_cmp(pl_val a, pl_val b);
bool pl_nat_eq(pl_val a, pl_val b);
bool pl_nat_is_zero(pl_val v);
size_t pl_nat_byte_len(pl_val v);
uint64_t pl_nat_u64_clamp(pl_val v); /* min(v, UINT64_MAX) */
size_t pl_nat_bit_len(pl_val v);
uint8_t pl_nat_byte_at(pl_val v, size_t i);
uint64_t pl_nat_limb_at(pl_val v, size_t i);
size_t pl_nat_limb_len(pl_val v);

/* `nat` coercion from the reference: non-nat values become 0. */
static inline pl_val pl_nat_coerce(pl_val v) {
  return pl_is_nat(v) ? v : 0;
}

/* Allocating: slots must be rooted. */
pl_val pl_nat_inc(pl_thread* t, pl_val* a);
pl_val pl_nat_dec(pl_thread* t, pl_val* a);
pl_val pl_nat_add(pl_thread* t, pl_val* a, pl_val* b);
pl_val pl_nat_sub(pl_thread* t, pl_val* a, pl_val* b); /* floored at 0 */
pl_val pl_nat_mul(pl_thread* t, pl_val* a, pl_val* b);
pl_val pl_nat_div(pl_thread* t, pl_val* a, pl_val* b); /* b==0: raises */
pl_val pl_nat_mod(pl_thread* t, pl_val* a, pl_val* b); /* b==0: raises */
pl_val pl_nat_lsh(pl_thread* t, pl_val* a, pl_val* sh);
pl_val pl_nat_rsh(pl_thread* t, pl_val* a, pl_val* sh);
pl_val pl_nat_bex(pl_thread* t, pl_val* bits);
pl_val pl_nat_set_bit(pl_thread* t, pl_val* bit, pl_val* a);
pl_val pl_nat_clear_bit(pl_thread* t, pl_val* bit, pl_val* a);
bool pl_nat_test_bit(pl_val bit, pl_val a);
pl_val pl_nat_trunc(pl_thread* t, pl_val* width, pl_val* a);
pl_val pl_nat_load_var(pl_thread* t, pl_val* off, pl_val* width, pl_val* a);
pl_val pl_nat_store_byte(pl_thread* t, pl_val* idx, pl_val* byte, pl_val* a);

/* Construction from raw bytes / decimal text (no rooted inputs needed). */
pl_val pl_nat_from_bytes(pl_thread* t, const uint8_t* b, size_t n);
pl_val pl_nat_from_decimal(pl_thread* t, const char* s, size_t n, bool* ok);

#endif
