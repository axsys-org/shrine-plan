#ifndef AX_DS_H
#define AX_DS_H

/*
 * ax facade over the vendored stb_ds (axsys/stb_ds.h, upstream v0.67, with
 * local patches).  STBDS_NO_SHORT_NAMES stops the vendor header from spilling
 * unprefixed macros (arrput, hmget, …) into the global namespace; everything
 * callers touch is ax_-prefixed here. Include this header, never
 * axsys/stb_ds.h directly. Extend the mapping as more of the stb_ds API is
 * needed.
 */

#define STBDS_NO_SHORT_NAMES
#include "axsys/stb_ds.h"

/* dynamic arrays */
#define ax_arrlen  stbds_arrlen
#define ax_arrlenu stbds_arrlenu
#define ax_arrpush stbds_arrput
#define ax_arraddn stbds_arraddnptr
#define ax_arrfree stbds_arrfree

/* hash maps keyed by a value field named `key` */
#define ax_hmput  stbds_hmput
#define ax_dshead stbds_header
#define ax_hmgeti stbds_hmgeti
#define ax_hmlen  stbds_hmlen
#define ax_hmfree stbds_hmfree

#endif
