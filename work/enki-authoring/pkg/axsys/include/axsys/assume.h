#ifndef AX_ASSUME_H
#define AX_ASSUME_H

#include <limits.h>
#include <stdint.h>

#include "axsys/util.h"

static_assert(CHAR_BIT == 8, "byte must be 8 bits");
static_assert(sizeof(void*) == 8, "tagged pointer scheme assumes 64-bit");
static_assert(sizeof(size_t) == sizeof(uintptr_t),
              "size_t must match pointer width");

/*
 * ax_assume is the hard assert: it stays on in release builds. It is the
 * corruption firewall for invariants that must never be violated (heap
 * headroom, collection points). Use plain assert() for debug-only checks.
 */
#define ax_assume(cond, ...) ax_assertf(cond, __VA_ARGS__)

#endif
