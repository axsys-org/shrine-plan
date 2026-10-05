#include "axsys/fd.h"

#include "axsys/assume.h"

#include <errno.h>
#include <pthread.h>
#include <stdint.h>
#include <unistd.h>

static pthread_mutex_t ax_fd_mu = PTHREAD_MUTEX_INITIALIZER;

ax_fd_table ax_global_fd_table = {
    .next = 3,
    .slots =
        {
            [0] = {.live = true, .fd = 0, .refs = 1},
            [1] = {.live = true, .fd = 1, .refs = 1},
            [2] = {.live = true, .fd = 2, .refs = 1},
        },
};

size_t ax_fd_add(int fd) {
  pthread_mutex_lock(&ax_fd_mu);
  if (ax_global_fd_table.next < AX_FD_MAX) {
    size_t hdl = ax_global_fd_table.next++;
    ax_global_fd_table.slots[hdl] =
        (ax_fd_slot){.live = true, .fd = fd, .refs = 1};
    pthread_mutex_unlock(&ax_fd_mu);
    return hdl;
  }
  for (size_t k = 0; k < AX_FD_MAX; k++) {
    ax_fd_slot* slot = &ax_global_fd_table.slots[k];
    if (!slot->live && !slot->closing && slot->refs == 0) {
      slot->fd = fd;
      slot->refs = 1;
      slot->live = true;
      pthread_mutex_unlock(&ax_fd_mu);
      return k;
    }
  }
  pthread_mutex_unlock(&ax_fd_mu);
  return AX_FD_INVALID;
}

int ax_fd_get(size_t hdl) {
  if (hdl >= AX_FD_MAX)
    return -1;
  pthread_mutex_lock(&ax_fd_mu);
  ax_fd_slot* slot = &ax_global_fd_table.slots[hdl];
  int fd = slot->live ? slot->fd : -1;
  pthread_mutex_unlock(&ax_fd_mu);
  return fd;
}

int ax_fd_acquire(size_t hdl, int* out_fd) {
  if (hdl >= AX_FD_MAX || out_fd == NULL)
    return -1;
  pthread_mutex_lock(&ax_fd_mu);
  ax_fd_slot* slot = &ax_global_fd_table.slots[hdl];
  if (!slot->live || slot->refs == SIZE_MAX) {
    pthread_mutex_unlock(&ax_fd_mu);
    return -1;
  }
  slot->refs++;
  *out_fd = slot->fd;
  pthread_mutex_unlock(&ax_fd_mu);
  return 0;
}

static int ax_fd_finish_close(size_t hdl, int fd) {
  int rc = close(fd);
  pthread_mutex_lock(&ax_fd_mu);
  ax_fd_slot* slot = &ax_global_fd_table.slots[hdl];
  slot->fd = -1;
  slot->closing = false;
  pthread_mutex_unlock(&ax_fd_mu);
  return rc;
}

int ax_fd_close(size_t hdl) {
  if (hdl >= AX_FD_MAX) {
    errno = EMFILE;
    return -1;
  }
  pthread_mutex_lock(&ax_fd_mu);
  ax_fd_slot* slot = &ax_global_fd_table.slots[hdl];
  if (!slot->live) {
    pthread_mutex_unlock(&ax_fd_mu);
    errno = EBADF;
    return -1;
  }
  slot->live = false;
  ax_assume(slot->refs > 0, "live fd slot has no owner reference");
  slot->refs--;
  if (slot->refs != 0) {
    pthread_mutex_unlock(&ax_fd_mu);
    return 0; /* an in-flight syscall owns the deferred close */
  }
  int fd = slot->fd;
  slot->closing = true;
  pthread_mutex_unlock(&ax_fd_mu);
  return ax_fd_finish_close(hdl, fd);
}

int ax_fd_retain(size_t hdl) {
  if (hdl >= AX_FD_MAX)
    return -1;
  pthread_mutex_lock(&ax_fd_mu);
  ax_fd_slot* slot = &ax_global_fd_table.slots[hdl];
  if (!slot->live || slot->refs == SIZE_MAX) {
    pthread_mutex_unlock(&ax_fd_mu);
    return -1;
  }
  slot->refs++;
  pthread_mutex_unlock(&ax_fd_mu);
  return 0;
}

int ax_fd_release(size_t hdl) {
  if (hdl >= AX_FD_MAX)
    return -1;
  pthread_mutex_lock(&ax_fd_mu);
  ax_fd_slot* slot = &ax_global_fd_table.slots[hdl];
  if (slot->refs == 0) {
    pthread_mutex_unlock(&ax_fd_mu);
    return -1;
  }
  slot->refs--;
  if (slot->refs != 0) {
    pthread_mutex_unlock(&ax_fd_mu);
    return 0;
  }
  slot->live = false;
  int fd = slot->fd;
  slot->closing = true;
  pthread_mutex_unlock(&ax_fd_mu);
  return ax_fd_finish_close(hdl, fd);
}
