#ifndef PL_RPLAN_H
#define PL_RPLAN_H

/*
 * Helpers shared by rplan operation bodies and the actor executor.
 * ReadFolder currently lives in op 83, the staging area for provisional
 * primops whose PLAN-level semantics are not yet settled.  Its filesystem
 * work is performed by the executor because its result is a structured row.
 */

#include "plan/heap.h"
#include "plan/value.h"

/*
 * List a folder visible to `t`.  `path` must be a nat path.  The result is
 * zero on failure (and for an empty folder), otherwise
 *
 *   (0 (0 is-folder folder-name) ...)
 *
 * `is-folder` is 1 for directories and 0 for every other entry.  Path
 * resolution observes t->rplan_file_root_c exactly as ReadFile does.
 */
pl_val pl_rplan_read_folder(pl_thread* t, pl_val path);

#endif
