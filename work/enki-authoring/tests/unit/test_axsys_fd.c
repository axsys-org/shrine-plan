#include "test.h"

#include <stdint.h>
#include <unistd.h>

#include "axsys/fd.h"

TEST(axsys_fd, close_defers_until_blocking_borrow_finishes) {
  int pipe_fd[2];
  ASSERT_EQ(pipe(pipe_fd), 0);
  size_t handle = ax_fd_add(pipe_fd[0]);
  ASSERT_NEQ(handle, AX_FD_INVALID);

  int borrowed = -1;
  ASSERT_EQ(ax_fd_acquire(handle, &borrowed), 0);
  ASSERT_EQ(borrowed, pipe_fd[0]);
  ASSERT_EQ(ax_fd_close(handle), 0);
  ASSERT_EQ(ax_fd_get(handle), -1); /* new effects see a closed handle */

  uint8_t sent = 42, received = 0;
  ASSERT_EQ(write(pipe_fd[1], &sent, 1), 1);
  ASSERT_EQ(read(borrowed, &received, 1), 1);
  ASSERT_EQ(received, sent); /* the in-flight effect retained the fd */
  ASSERT_EQ(ax_fd_release(handle), 0);
  ASSERT_EQ(close(pipe_fd[1]), 0);
}
