#include <pthread.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <unistd.h>

#include "axsys/fd.h"
#include "test.h"

typedef struct fd_worker {
  bool ok;
} fd_worker;

static void* fd_worker_main(void* arg) {
  fd_worker* worker = arg;
  for (int i = 0; i < 500; i++) {
    int pipe_fd[2];
    if (pipe(pipe_fd) != 0) {
      worker->ok = false;
      break;
    }
    size_t handle = ax_fd_add(pipe_fd[0]);
    int borrowed = -1;
    uint8_t sent = 42, received = 0;
    if (handle == AX_FD_INVALID || ax_fd_acquire(handle, &borrowed) != 0 ||
        ax_fd_close(handle) != 0 || write(pipe_fd[1], &sent, 1) != 1 ||
        read(borrowed, &received, 1) != 1 || received != sent ||
        ax_fd_release(handle) != 0 || close(pipe_fd[1]) != 0) {
      worker->ok = false;
      break;
    }
  }
  return NULL;
}

static int run_fd_stress(void) {
  enum { NTHREADS = 4 };
  fd_worker workers[NTHREADS];
  pthread_t threads[NTHREADS];
  bool started[NTHREADS] = {0};
  int status = 0;

  for (size_t i = 0; i < NTHREADS; i++) {
    workers[i].ok = true;
    int err = pthread_create(&threads[i], NULL, fd_worker_main, &workers[i]);
    if (err != 0) {
      fprintf(stderr, "pthread_create(%zu) failed: %d\n", i, err);
      status = 1;
      break;
    }
    started[i] = true;
  }
  for (size_t i = 0; i < NTHREADS; i++) {
    if (!started[i])
      continue;
    int err = pthread_join(threads[i], NULL);
    if (err != 0 || !workers[i].ok) {
      fprintf(stderr, "fd worker %zu failed (join=%d)\n", i, err);
      status = 1;
    }
  }
  return status;
}

TEST(axsys_fd_tsan, concurrent_borrow_and_close) {
  ASSERT_EQ(run_fd_stress(), 0);
}
