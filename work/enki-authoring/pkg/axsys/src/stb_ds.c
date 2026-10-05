#include <assert.h>
#include <stdlib.h>

#include "axsys/assume.h"

/* Vendor configuration for the single implementation unit.  The stb_ds
 * defaults leave its internal invariant checks off in every build and do
 * not check realloc: on OOM stbds_arrgrowf would write through a near-null
 * header pointer.  Abort like the rest of the tree does instead. */
static void* ax_stbds_realloc(void* p, size_t n) {
  void* q = realloc(p, n);
  ax_assume(q != NULL || n == 0, "stb_ds: out of memory");
  return q;
}
#define STBDS_REALLOC(c, p, s) ax_stbds_realloc((p), (s))
#define STBDS_FREE(c, p)       free(p)
#define STBDS_ASSERT(x)        assert(x)

#pragma GCC diagnostic push
#pragma GCC diagnostic ignored "-Wconversion"
#pragma GCC diagnostic ignored "-Wsign-conversion"
#define STB_DS_IMPLEMENTATION
#define STBDS_NO_SHORT_NAMES
#include "axsys/stb_ds.h"
#undef STB_DS_IMPLEMENTATION
#pragma GCC diagnostic pop
