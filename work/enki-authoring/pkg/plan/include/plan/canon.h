#ifndef PL_CANON_H
#define PL_CANON_H

/*
 * Canonical text rendering of normalized PLAN values, a faithful port of
 * the reference Print.hs.  These are the legacy snapshot bytes: legacy
 * stores hash pl_canonize with SHA-256, and text-mode Save writes that same
 * text to snap/<base58>.plan, where any PLAN assembler can reload it.  Silo
 * identity instead hashes the complete canonical Silo stream.
 *
 * Inputs must be deeply normal (no thunks); both functions are pure
 * reads of the graph and allocate only through the given allocator.
 */

#include <stddef.h>

#include "axsys/allocator.h"
#include "plan/value.h"

/* The reference showVal (prettyValMulti 50): NUL-terminated, caller frees. */
char* pl_show_val(const ax_allocator* a, pl_val v, size_t* out_s);

/* The reference canonize: the full snapshot module text for the pin of v
 * (v may be the pin itself or the value being pinned). */
char* pl_canonize(const ax_allocator* a, pl_val v, size_t* out_s);

#endif
