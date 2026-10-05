#ifndef PL_DEBUG_H
#define PL_DEBUG_H

/*
 * Value printer.  Pure read: never forces, never allocates on the plan
 * heap.  Unevaluated thunks print as <thk>, blackholes as <bh>.
 */

#include <stddef.h>

#include "axsys/allocator.h"
#include "axsys/sb.h"
#include "plan/value.h"

/* Append a rendering of v to sb. */
void pl_show_sb(ax_sb* sb, pl_val v);

/* Convenience: allocate and return a NUL-terminated rendering. */
char* pl_show(const ax_allocator* a, pl_val v, size_t* out_s);

/*
 * Bounded rendering for interactive inspection of arbitrarily large
 * values.  Recursion stops at max_depth ("…"), application spines elide
 * arguments beyond max_width ("…+N"), nats longer than 64 bytes render
 * as <nat:N bytes>, and a hashed PIN renders as its 8-hex-digit hash
 * prefix (<pin a1b2c3d4>) instead of its body.
 */
void pl_show_limited_sb(ax_sb* sb, pl_val v, size_t max_depth,
                        size_t max_width);

#endif
