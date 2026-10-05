#ifndef AX_FD_H
#define AX_FD_H

/*
 * Process-global file-descriptor handle table (from the io-work branch).
 * PLAN code addresses descriptors through small-nat handles; slots 0-2
 * are prewired to stdin/stdout/stderr.
 */

#include <stdbool.h>
#include <stddef.h>

#define AX_FD_MAX     1024
#define AX_FD_INVALID ((size_t)-1)

typedef struct ax_fd_slot {
  bool live;
  bool closing;
  int fd;
  size_t refs;
} ax_fd_slot;

typedef struct ax_fd_table {
  size_t next;
  ax_fd_slot slots[AX_FD_MAX];
} ax_fd_table;

extern ax_fd_table ax_global_fd_table;

size_t ax_fd_add(int fd);
int ax_fd_get(size_t hdl);
/* Atomically borrow a live descriptor until the matching ax_fd_release.
 * CloseFd invalidates the handle immediately but defers the OS close while
 * an in-flight blocking operation holds a borrow. */
int ax_fd_acquire(size_t hdl, int* out_fd);
int ax_fd_close(size_t hdl);
int ax_fd_retain(size_t hdl);
int ax_fd_release(size_t hdl);

#endif
