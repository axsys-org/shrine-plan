#ifndef PL_NATIVE_WIRE_H
#define PL_NATIVE_WIRE_H
#include "plan/heap.h"

/* Bounded transport of normal native values. Returns (0 value) or (1 error).
 * Neither operation evaluates decoded values or publishes a store root. */
pl_val pl_native_pack(pl_thread* t, size_t ab);
pl_val pl_native_unpack(pl_thread* t, size_t ab);
#endif
