#include <blake3.h>
#include <sodium.h>
#include <pthread.h>
#include <errno.h>
#include <fcntl.h>
#include <libgen.h>
#include <inttypes.h>
#include <dirent.h>
#include <netinet/in.h>
#include <stdlib.h>
#include <string.h>
#include <sys/socket.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <netdb.h>
#include <arpa/inet.h>
#include <time.h>
#include <unistd.h>

#include "axsys/allocator.h"
#include "axsys/fd.h"
#include "axsys/util.h"
#include "internal.h"
#include "plan/nat.h"
#include "plan/rplan.h"
#include "plan/xtract.h"

/*
 * op 82: rplan I/O, gated on RPLAN mode (checked in eval.c before
 * dispatch).  Sockets live in a process-global fd handle table; the
 * byte conventions follow the Haskell reference, which the reaver
 * sources rely on:
 *
 *   - Input / ReadFile / Read return "bars": the data bytes followed by
 *     a 0x01 terminator byte (bytesBar), so the consumer can recover
 *     the length (reaver: bytes-size = Dec (Bytes b)).
 *   - Output / Warn / Write take bars and strip the top byte (natBytes).
 *   - Print takes a plain string nat and writes every byte (natStr).
 *
 * Actor ops (Spawn/Send/SendCaps/Recv/CloseHandle) are coordination
 * effects: their bodies below only validate the forced args and rebuild
 * the request spine [OpName, args…]; the machine parks it in
 * t->blocked_on and suspends with PL_RUN_BLOCKED (eval.c op_body).
 * Servicing — mailboxes, handle tables, spawning — belongs to the
 * executor, which deposits the response with pl_thread_deposit.
 */

#define ARG(i) (t->vstack[ab + (i)])

static int rp_write_all(int fd, const uint8_t* bytes, size_t len) {
  size_t off = 0;
  while (off < len) {
    ssize_t r = write(fd, bytes + off, len - off);
    if (r < 0) {
      if (errno == EINTR)
        continue;
      return -1;
    }
    if (r == 0) {
      errno = EIO;
      return -1;
    }
    off += (size_t)r;
  }
  return 0;
}

static int rp_read_all(int fd, uint8_t* buf, size_t len) {
  size_t off = 0;
  while (off < len) {
    ssize_t r = read(fd, buf + off, len - off);
    if (r < 0) {
      if (errno == EINTR)
        continue;
      return -1;
    }
    if (r == 0)
      break;
    off += (size_t)r;
  }
  return 0;
}

/* Materialize a nat's bytes (malloc'd; caller frees).  drop_top drops
 * the highest byte — the reference natBytes, inverse of bytesBar. */
static uint8_t* rp_nat_bytes(pl_val v, bool drop_top, size_t* out_n) {
  size_t n = pl_nat_byte_len(v);
  if (drop_top && n > 0)
    n -= 1;
  uint8_t* b = malloc(n ? n : 1);
  ax_assume(b != NULL, "oom");
  for (size_t i = 0; i < n; i++)
    b[i] = pl_nat_byte_at(v, i);
  *out_n = n;
  return b;
}

/* NUL-terminated path string from a nat (malloc'd). */
static char* rp_nat_path(pl_val v) {
  size_t n = pl_nat_byte_len(v);
  char* p = malloc(n + 1);
  ax_assume(p != NULL, "oom");
  for (size_t i = 0; i < n; i++)
    p[i] = (char)pl_nat_byte_at(v, i);
  p[n] = '\0';
  return p;
}

static char* rp_strdup(const char* s) {
  size_t n = strlen(s);
  char* out = malloc(n + 1);
  ax_assume(out != NULL, "oom");
  memcpy(out, s, n + 1);
  return out;
}

static char* rp_join_path(const char* root, const char* path) {
  size_t rn = strlen(root);
  size_t pn = strlen(path);
  bool slash = rn > 0 && root[rn - 1] == '/';
  char* out = malloc(rn + (slash ? 0 : 1) + pn + 1);
  ax_assume(out != NULL, "oom");
  memcpy(out, root, rn);
  size_t off = rn;
  if (!slash)
    out[off++] = '/';
  memcpy(out + off, path, pn + 1);
  return out;
}

static bool rp_path_under_root(const char* root, const char* path) {
  if (strcmp(root, "/") == 0)
    return true;
  size_t rn = strlen(root);
  return strncmp(path, root, rn) == 0 && (path[rn] == '\0' || path[rn] == '/');
}

static bool rp_resolve_read_path(pl_thread* t, const char* arg_path,
                                 char** out_path) {
  if (t->rplan_file_root_c == NULL || t->rplan_file_root_c[0] == '\0') {
    *out_path = rp_strdup(arg_path);
    return true;
  }

  char* root = realpath(t->rplan_file_root_c, NULL);
  if (root == NULL)
    return false;

  char* joined = rp_join_path(root, arg_path);
  char* resolved = realpath(joined, NULL);
  free(joined);
  if (resolved == NULL || !rp_path_under_root(root, resolved)) {
    free(root);
    free(resolved);
    return false;
  }

  free(root);
  *out_path = resolved;
  return true;
}

static bool rp_split_write_path(const char* arg_path, char** out_dir,
                                char** out_base) {
  char* dir_buf = rp_strdup(arg_path);
  char* base_buf = rp_strdup(arg_path);
  const char* dir_part = dirname(dir_buf);
  const char* base_part = basename(base_buf);
  bool ok = base_part[0] != '\0' && strcmp(base_part, ".") != 0 &&
            strcmp(base_part, "..") != 0;
  if (ok) {
    *out_dir = rp_strdup(dir_part);
    *out_base = rp_strdup(base_part);
  }
  free(dir_buf);
  free(base_buf);
  return ok;
}

static bool rp_resolve_write_path(pl_thread* t, const char* arg_path,
                                  char** out_path) {
  char* dir_path = NULL;
  char* base_path = NULL;
  char* resolved_dir = NULL;
  char* candidate = NULL;
  char* resolved_target = NULL;
  char* root = NULL;
  bool res = false;

  if (!rp_split_write_path(arg_path, &dir_path, &base_path))
    goto cleanup;

  if (!rp_resolve_read_path(t, dir_path, &resolved_dir))
    goto cleanup;

  candidate = rp_join_path(resolved_dir, base_path);
  if (t->rplan_file_root_c == NULL || t->rplan_file_root_c[0] == '\0') {
    *out_path = candidate;
    candidate = NULL;
    res = true;
    goto cleanup;
  }

  root = realpath(t->rplan_file_root_c, NULL);
  if (root == NULL)
    goto cleanup;

  errno = 0;
  resolved_target = realpath(candidate, NULL);
  if (resolved_target != NULL) {
    if (!rp_path_under_root(root, resolved_target))
      goto cleanup;
    *out_path = resolved_target;
    resolved_target = NULL;
    res = true;
    goto cleanup;
  }

  if (errno == ENOENT) {
    struct stat st;
    if (lstat(candidate, &st) < 0 && errno == ENOENT) {
      *out_path = candidate;
      candidate = NULL;
      res = true;
    }
  }

cleanup:
  free(dir_path);
  free(base_path);
  free(resolved_dir);
  free(candidate);
  free(resolved_target);
  free(root);
  return res;
}

/* bytesBar: the data bytes followed by a 0x01 terminator. */
static pl_val rp_bar(pl_thread* t, const uint8_t* b, size_t n) {
  uint8_t* bar = malloc(n + 1);
  ax_assume(bar != NULL, "oom");
  memcpy(bar, b, n);
  bar[n] = 0x01;
  pl_val out = pl_nat_from_bytes(t, bar, n + 1);
  free(bar);
  return out;
}

/* Pattern `N x`: the reference rplan errors on non-nat where it
 * pattern-matches a nat constructor. */
static pl_val rp_want_nat(pl_thread* t, pl_val v) {
  if (!pl_is_nat(v))
    pl_raise_msg(t, "unknown actor/net op");
  return v;
}

/* ── Console ───────────────────────────────────────────────────────────── */

pl_val pl_op82_input(pl_thread* t, size_t ab) {
  uint64_t n = pl_nat_u64_clamp(pl_nat_coerce(ARG(0)));
  if (n > (1u << 26))
    n = 1u << 26;
  uint8_t* buf = malloc(n ? n : 1);
  ax_assume(buf != NULL, "oom");
  int fd;
  if (ax_fd_acquire(STDIN_FILENO, &fd) < 0) {
    free(buf);
    pl_raise_msg(t, "Input: closed");
  }
  ssize_t r;
  do {
    r = read(fd, buf, n);
  } while (r < 0 && errno == EINTR);
  int read_errno = errno;
  (void)ax_fd_release(STDIN_FILENO);
  errno = read_errno;
  if (r < 0) {
    free(buf);
    pl_raise_msg(t, "Input: read failed");
  }
  pl_val out = rp_bar(t, buf, (size_t)r);
  free(buf);
  return out;
}

static pl_val rp_output_fd(pl_thread* t, size_t ab, size_t handle) {
  size_t n;
  uint8_t* b = rp_nat_bytes(pl_nat_coerce(ARG(0)), true, &n);
  int fd;
  if (ax_fd_acquire(handle, &fd) < 0) {
    free(b);
    pl_raise_msg(t, "Output: closed");
  }
  int rc = rp_write_all(fd, b, n);
  int write_errno = errno;
  (void)ax_fd_release(handle);
  errno = write_errno;
  free(b);
  if (rc < 0)
    pl_raise_msg(t, "Output: write failed");
  return 0;
}

pl_val pl_op82_output(pl_thread* t, size_t ab) {
  return rp_output_fd(t, ab, (size_t)STDOUT_FILENO);
}

pl_val pl_op82_warn(pl_thread* t, size_t ab) {
  return rp_output_fd(t, ab, (size_t)STDERR_FILENO);
}

pl_val pl_op82_print(pl_thread* t, size_t ab) {
  size_t n;
  uint8_t* b = rp_nat_bytes(rp_want_nat(t, ARG(0)), false, &n);
  int fd;
  if (ax_fd_acquire(STDOUT_FILENO, &fd) < 0) {
    free(b);
    pl_raise_msg(t, "Print: closed");
  }
  int rc = rp_write_all(fd, b, n);
  int write_errno = errno;
  (void)ax_fd_release(STDOUT_FILENO);
  errno = write_errno;
  free(b);
  if (rc < 0)
    pl_raise_msg(t, "Print: write failed");
  return 0;
}

/* ── Files ─────────────────────────────────────────────────────────────── */

pl_val pl_op82_read_file(pl_thread* t, size_t ab) {
  char* arg_path = rp_nat_path(rp_want_nat(t, ARG(0)));
  char* path = NULL;
  if (!rp_resolve_read_path(t, arg_path, &path)) {
    free(arg_path);
    return 0;
  }
  free(arg_path);
  int fd = open(path, O_RDONLY);
  free(path);
  if (fd < 0)
    return 0;
  struct stat st;
  if (fstat(fd, &st) < 0 || st.st_size < 0) {
    close(fd);
    return 0;
  }
  size_t size = (size_t)st.st_size;
  uint8_t* buf = malloc(size ? size : 1);
  ax_assume(buf != NULL, "oom");
  if (rp_read_all(fd, buf, size) < 0) {
    close(fd);
    free(buf);
    return 0;
  }
  close(fd);
  pl_val out = rp_bar(t, buf, size);
  free(buf);
  return out;
}

typedef struct rp_folder_item {
  char* name;
  bool is_folder;
} rp_folder_item;

static void rp_folder_items_free(rp_folder_item* items, size_t n) {
  for (size_t i = 0; i < n; i++)
    free(items[i].name);
  free(items);
}

/* List names first, keeping the directory stream out of the PLAN allocation
 * window.  fstatat follows symlinks, matching doesDirectoryExist in the
 * reference implementation. */
static bool rp_folder_items_read(const char* path, rp_folder_item** out_items,
                                 size_t* out_n) {
  DIR* dir = opendir(path);
  if (dir == NULL)
    return false;

  rp_folder_item* items = NULL;
  size_t n = 0, cap = 0;
  int fd = dirfd(dir);
  bool ok = true;
  for (;;) {
    errno = 0;
    struct dirent* ent = readdir(dir);
    if (ent == NULL) {
      if (errno != 0)
        ok = false;
      break;
    }
    if (strcmp(ent->d_name, ".") == 0 || strcmp(ent->d_name, "..") == 0)
      continue;
    if (n >= UINT32_MAX - 2) {
      ok = false; /* the enclosing PLAN row would not fit */
      break;
    }
    if (n == cap) {
      size_t next = cap == 0 ? 16 : cap * 2;
      if (next < cap || next > SIZE_MAX / sizeof(*items)) {
        ok = false;
        break;
      }
      rp_folder_item* grown = realloc(items, next * sizeof(*items));
      ax_assume(grown != NULL, "oom");
      items = grown;
      cap = next;
    }
    struct stat st;
    items[n].is_folder =
        fd >= 0 && fstatat(fd, ent->d_name, &st, 0) == 0 && S_ISDIR(st.st_mode);
    items[n].name = rp_strdup(ent->d_name);
    n++;
  }
  if (closedir(dir) != 0)
    ok = false;
  if (!ok) {
    rp_folder_items_free(items, n);
    return false;
  }
  *out_items = items;
  *out_n = n;
  return true;
}

/* Build the row with every intermediate rooted on the value stack: both
 * pl_nat_from_bytes and the APP constructors may collect. */
static pl_val rp_folder_row(pl_thread* t, const rp_folder_item* items,
                            uint32_t n) {
  if (n == 0)
    return 0;
  size_t base = t->vsp;
  for (uint32_t i = 0; i < n; i++) {
    pl_vpush(t, items[i].is_folder ? 1 : 0);
    pl_vpush(t, pl_nat_from_bytes(t, (const uint8_t*)items[i].name,
                                  strlen(items[i].name)));
    pl_gc_reserve(t, PL_APP_CELLS(2));
    PL_GC_FORBID(t);
    pl_val item = pl_mk_app_from(t, 0, 2, &t->vstack[t->vsp - 2]);
    PL_GC_ALLOW(t);
    t->vsp -= 2;
    pl_vpush(t, item);
  }
  pl_gc_reserve(t, PL_APP_CELLS(n));
  PL_GC_FORBID(t);
  pl_val row = pl_mk_app_from(t, 0, n, &t->vstack[base]);
  PL_GC_ALLOW(t);
  t->vsp = base;
  return row;
}

pl_val pl_rplan_read_folder(pl_thread* t, pl_val path_v) {
  char* arg_path = rp_nat_path(rp_want_nat(t, path_v));
  char* path = NULL;
  if (!rp_resolve_read_path(t, arg_path, &path)) {
    free(arg_path);
    return 0;
  }
  free(arg_path);

  rp_folder_item* items = NULL;
  size_t n = 0;
  bool ok = rp_folder_items_read(path, &items, &n);
  free(path);
  if (!ok)
    return 0;
  pl_val out = rp_folder_row(t, items, (uint32_t)n);
  rp_folder_items_free(items, n);
  return out;
}

pl_val pl_op82_write_file(pl_thread* t, size_t ab) {
  char* arg_path = rp_nat_path(rp_want_nat(t, ARG(0)));
  char* path = NULL;
  bool res = rp_resolve_write_path(t, arg_path, &path);
  if (!res) {
    fprintf(stderr, "Failed to canonise %s\n", arg_path);
    free(arg_path);
    return 0;
  }
  free(arg_path);
  int fd = open(path, O_WRONLY | O_CREAT | O_TRUNC, 0644);
  if (fd < 0) {
    perror("WriteFile: open");
    free(path);
    return 0;
  }
  free(path);
  size_t n;
  uint8_t* b = rp_nat_bytes(rp_want_nat(t, ARG(1)), true, &n);
  int rc = rp_write_all(fd, b, n);
  free(b);
  if (rc < 0) {
    perror("failed to write file");
    pl_raise_msg(t, "WriteFile: failed to write file");
  }
  ax_assume(0 == close(fd), "failed to close file");
  return 1;
}

pl_val pl_op82_stamp(pl_thread* t, size_t ab) {
  char* arg_path = rp_nat_path(rp_want_nat(t, ARG(0)));
  char* path;
  bool resolved = rp_resolve_read_path(t, arg_path, &path);
  free(arg_path);
  if (!resolved) {
    return 0;
  }
  struct stat st;
  int rc = stat(path, &st);

  free(path);
  if (rc < 0) {
    perror("stamp");
    return 0;
  }
  return (pl_val)(uint64_t)st.st_mtime;
}

pl_val pl_op82_now(pl_thread* t, size_t ab) {
  AX_UNUSED(ab);
  struct timespec now;
  if (clock_gettime(CLOCK_REALTIME, &now) != 0)
    pl_raise_msg(t, "Now: clock failed");

  uint64_t sec = (uint64_t)now.tv_sec;
  uint64_t nsec = (uint64_t)now.tv_nsec;
  if (sec > (UINT64_MAX - nsec) / UINT64_C(1000000000))
    pl_raise_msg(t, "Now: timestamp overflow");

  uint64_t instant = sec * UINT64_C(1000000000) + nsec;
  pl_gc_reserve(t, PL_NAT_CELLS(1));
  return pl_mk_nat_u64(t, instant);
}

/* ── Sockets / descriptors (handles via the global fd table) ───────────── */

pl_val pl_op82_closefd(pl_thread* t, size_t ab) {
  uint64_t h = pl_nat_u64_clamp(rp_want_nat(t, ARG(0)));
  int rc = ax_fd_close((size_t)h);
  if (rc < 0) {
    perror("bad handle");
    pl_raise_msg(t, "CloseFd: bad handle");
  }
  return 0;
}

static void* get_in_addr(struct sockaddr* sa) {
  if (sa->sa_family == AF_INET) {
    return &(((struct sockaddr_in*)sa)->sin_addr);
  }

  return &(((struct sockaddr_in6*)sa)->sin6_addr);
}

pl_val pl_op82_connect(pl_thread* t, size_t ab) {
  int fd = -1;
  const char* err_reason = NULL;
  char s[INET6_ADDRSTRLEN];
  struct addrinfo hints, *servinfo, *cur;

  bool is_dns = rp_want_nat(t, ARG(0)) == 1 ? true : false;
  uint64_t port = pl_nat_u64_clamp(rp_want_nat(t, ARG(2)));
  char* host = pl_nat_to_cstr(ax_allocator_system(), rp_want_nat(t, ARG(1)));

  servinfo = NULL;
  memset(&hints, 0, sizeof(hints));
  hints.ai_family = AF_INET;
  hints.ai_socktype = SOCK_STREAM;
  if (!is_dns)
    hints.ai_flags = AI_NUMERICHOST;
  char port_c[20];
  snprintf(port_c, sizeof(port_c), "%" PRIu64, port);
  int rc = getaddrinfo(host, port_c, &hints, &servinfo);
  if (rc != 0) {
    err_reason = gai_strerror(rc);
    goto cleanup;
  }
  for (cur = servinfo; cur != NULL; cur = cur->ai_next) {
    if ((fd = socket(cur->ai_family, cur->ai_socktype, cur->ai_protocol)) ==
        -1) {
      perror("connect: socket");
      continue;
    }

    inet_ntop(cur->ai_family, get_in_addr((struct sockaddr*)cur->ai_addr), s,
              sizeof(s));

    if (connect(fd, cur->ai_addr, cur->ai_addrlen) == -1) {
      perror("connect: syscall");
      close(fd);
      continue;
    }

    break;
  }
  if (cur == NULL) {
    err_reason = "connect: failed";
    goto cleanup;
  }

cleanup:
  freeaddrinfo(servinfo);
  ax_free(ax_allocator_system(), host);
  if (err_reason) {
    if (fd >= 0)
      close(fd);
    pl_raise_msg(t, err_reason);
  } else if (fd >= 0) {
    size_t h = ax_fd_add(fd);
    if (h == AX_FD_INVALID) {
      close(fd);
      pl_raise_msg(t, "Connect: fd table full");
    }
    return (pl_val)h;
  } else {
    pl_raise_msg(t, "Connect: bad fd");
  }
}

pl_val pl_op82_listen(pl_thread* t, size_t ab) {
  uint64_t port = pl_nat_u64_clamp(rp_want_nat(t, ARG(0)));
  int fd = socket(AF_INET, SOCK_STREAM, 0);
  if (fd < 0) {
    perror("socket failed");
    pl_raise_msg(t, "Listen: socket failed");
  }
  int yes = 1;
  if (setsockopt(fd, SOL_SOCKET, SO_REUSEADDR, &yes, sizeof(yes)) < 0) {
    close(fd);
    perror("setsockopt failed");
    pl_raise_msg(t, "Listen: setsockopt failed");
  }
  struct sockaddr_in addr = {0};
  addr.sin_family = AF_INET;
  addr.sin_addr.s_addr = htonl(INADDR_ANY);
  addr.sin_port = htons((uint16_t)port);
  if (bind(fd, (struct sockaddr*)&addr, sizeof(addr)) < 0 ||
      listen(fd, 128) < 0) {
    close(fd);
    perror("bind/listen failed");
    pl_raise_msg(t, "Listen: bind/listen failed");
  }
  size_t h = ax_fd_add(fd);
  if (h == AX_FD_INVALID) {
    close(fd);
    pl_raise_msg(t, "Listen: fd table full");
  }
  return (pl_val)h;
}

pl_val pl_op82_accept(pl_thread* t, size_t ab) {
  uint64_t h = pl_nat_u64_clamp(rp_want_nat(t, ARG(0)));
  int listen_fd;
  if (ax_fd_acquire((size_t)h, &listen_fd) < 0)
    pl_raise_msg(t, "Accept: bad handle");
  int client_fd = accept(listen_fd, NULL, NULL);
  int accept_errno = errno;
  (void)ax_fd_release((size_t)h);
  errno = accept_errno;
  if (client_fd < 0)
    pl_raise_msg(t, "Accept: accept failed");
  size_t ch = ax_fd_add(client_fd);
  if (ch == AX_FD_INVALID) {
    close(client_fd);
    pl_raise_msg(t, "Accept: fd table full");
  }
  return (pl_val)ch;
}

pl_val pl_op82_read(pl_thread* t, size_t ab) {
  uint64_t h = pl_nat_u64_clamp(rp_want_nat(t, ARG(0)));
  uint64_t n = pl_nat_u64_clamp(rp_want_nat(t, ARG(1)));
  if (n > (1u << 26))
    n = 1u << 26;
  int fd;
  if (ax_fd_acquire((size_t)h, &fd) < 0)
    pl_raise_msg(t, "Read: bad handle");
  uint8_t* buf = malloc(n ? n : 1);
  ax_assume(buf != NULL, "oom");
  ssize_t r;
  do {
    r = read(fd, buf, n);
  } while (r < 0 && errno == EINTR);
  int read_errno = errno;
  (void)ax_fd_release((size_t)h);
  errno = read_errno;
  if (r < 0) {
    free(buf);
    pl_raise_msg(t, "Read: read failed");
  }
  if (r == 0) {
    free(buf);
    return 0; /* reference: empty read is N 0, not an empty bar */
  }
  pl_val out = rp_bar(t, buf, (size_t)r);
  free(buf);
  return out;
}

pl_val pl_op82_write(pl_thread* t, size_t ab) {
  uint64_t h = pl_nat_u64_clamp(rp_want_nat(t, ARG(0)));
  rp_want_nat(t, ARG(1));
  int fd;
  if (ax_fd_acquire((size_t)h, &fd) < 0)
    pl_raise_msg(t, "Write: bad handle");
  size_t n;
  uint8_t* b = rp_nat_bytes(ARG(1), true, &n);
  int rc = rp_write_all(fd, b, n);
  int write_errno = errno;
  (void)ax_fd_release((size_t)h);
  errno = write_errno;
  free(b);
  if (rc < 0)
    pl_raise_msg(t, "Write: write failed");
  return 0;
}

/* ── Actors: coordination effects (see header comment) ─────────────────── */

/* Rebuild the request spine [OpName, args…] from the unapp'd op row on
 * the value stack (name at ab-1, argc args from ab).  Strict args are
 * already forced; the rest stay lazy until the executor services them. */
static pl_val rp_request(pl_thread* t, size_t ab, uint32_t argc) {
  pl_gc_reserve(t, PL_APP_CELLS(argc));
  PL_GC_FORBID(t);
  pl_val r = pl_mk_app_from(t, t->vstack[ab - 1], argc, &t->vstack[ab]);
  PL_GC_ALLOW(t);
  return r;
}

pl_val pl_op82_spawn(pl_thread* t, size_t ab) {
  return rp_request(t, ab, 1); /* fn is taken unevaluated */
}

pl_val pl_op82_send(pl_thread* t, size_t ab) {
  rp_want_nat(t, ARG(0)); /* handle; the message stays lazy */
  return rp_request(t, ab, 2);
}

pl_val pl_op82_send_caps(pl_thread* t, size_t ab) {
  rp_want_nat(t, ARG(0));
  return rp_request(t, ab, 3);
}

pl_val pl_op82_recv(pl_thread* t, size_t ab) {
  if (ARG(0) != 0) /* the reference accepts only the literal nat 0 */
    pl_raise_msg(t, "unknown actor/net op");
  return rp_request(t, ab, 1);
}

pl_val pl_op82_close_handle(pl_thread* t, size_t ab) {
  rp_want_nat(t, ARG(0));
  return rp_request(t, ab, 1);
}

/* ── op 83: structured drivers ─────────────────────────────────────────── */

pl_val pl_op83_read_folder(pl_thread* t, size_t ab) {
  rp_want_nat(t, ARG(0));
  return rp_request(t, ab, 1);
}

pl_val pl_op83_fetch(pl_thread* t, size_t ab) {
  /* req and cfg are deep-normalized by the machine before the body runs;
   * all shape/URL validation happens at service time in pkg/enki (libcurl
   * stays out of the plan layer). */
  return rp_request(t, ab, 2);
}

pl_val pl_op83_sleep(pl_thread* t, size_t ab) {
  /* Seconds in arg 0; the wait happens at service time in pkg/enki.  Here we
   * only validate the (forced) arg and park as a coordination request. */
  rp_want_nat(t, ARG(0));
  return rp_request(t, ab, 1);
}

/* ── op 83: deterministic cryptography ────────────────────────────────── */

/* All byte strings are canonical bars (payload followed by 0x01).  Unlike
 * the permissive I/O decoder, crypto rejects missing/incorrect terminators.
 * In particular, 1 is the empty message and 0 is not a valid bar. */
static bool rp_crypto_bar_size(pl_val v, size_t* len) {
  if (!pl_is_nat(v))
    return false;
  size_t n = pl_nat_byte_len(v);
  if (n == 0 || pl_nat_byte_at(v, n - 1) != 1)
    return false;
  *len = n - 1;
  return true;
}

static void rp_crypto_copy(pl_val v, uint8_t* out, size_t n) {
  for (size_t i = 0; i < n; i++)
    out[i] = pl_nat_byte_at(v, i);
}

static pthread_once_t rp_sodium_once = PTHREAD_ONCE_INIT;
static int rp_sodium_status = -1;

static void rp_sodium_init(void) {
  rp_sodium_status = sodium_init();
}

static void rp_crypto_init(pl_thread* t) {
  if (pthread_once(&rp_sodium_once, rp_sodium_init) != 0 ||
      rp_sodium_status < 0)
    pl_raise_msg(t, "crypto: sodium initialization failed");
}

pl_val pl_op83_blake3(pl_thread* t, size_t ab) {
  size_t n;
  if (!rp_crypto_bar_size(ARG(0), &n))
    pl_raise_msg(t, "Blake3: expected a byte bar");
  uint8_t* message = rp_nat_bytes(ARG(0), true, &n);
  uint8_t digest[BLAKE3_OUT_LEN];
  blake3_hasher hasher;
  blake3_hasher_init(&hasher);
  blake3_hasher_update(&hasher, message, n);
  blake3_hasher_finalize(&hasher, digest, sizeof(digest));
  free(message);
  return rp_bar(t, digest, sizeof(digest));
}

pl_val pl_op83_sha256(pl_thread* t, size_t ab) {
  size_t n;
  if (!rp_crypto_bar_size(ARG(0), &n))
    pl_raise_msg(t, "Sha256: expected a byte bar");
  rp_crypto_init(t);
  uint8_t* message = rp_nat_bytes(ARG(0), true, &n);
  uint8_t digest[crypto_hash_sha256_BYTES];
  crypto_hash_sha256(digest, message, (unsigned long long)n);
  free(message);
  return rp_bar(t, digest, sizeof(digest));
}

/* Blake3Keyed key message -> 32-byte MAC bar, using BLAKE3's native
 * keyed mode.  This is not the HMAC construction. */
pl_val pl_op83_blake3_keyed(pl_thread* t, size_t ab) {
  size_t key_n, n;
  if (!rp_crypto_bar_size(ARG(0), &key_n) || key_n != BLAKE3_KEY_LEN ||
      !rp_crypto_bar_size(ARG(1), &n))
    pl_raise_msg(t, "Blake3Keyed: expected a 32-byte key bar and message bar");
  uint8_t* message = rp_nat_bytes(ARG(1), true, &n);
  uint8_t key[BLAKE3_KEY_LEN];
  uint8_t digest[BLAKE3_OUT_LEN];
  blake3_hasher hasher;
  rp_crypto_copy(ARG(0), key, sizeof(key));
  blake3_hasher_init_keyed(&hasher, key);
  sodium_memzero(key, sizeof(key));
  blake3_hasher_update(&hasher, message, n);
  blake3_hasher_finalize(&hasher, digest, sizeof(digest));
  sodium_memzero(&hasher, sizeof(hasher));
  free(message);
  return rp_bar(t, digest, sizeof(digest));
}

/* HmacSha256 key message -> 32-byte MAC bar.  The incremental API accepts
 * arbitrary key lengths (including empty and longer than one hash block). */
pl_val pl_op83_hmac_sha256(pl_thread* t, size_t ab) {
  size_t key_n, n;
  if (!rp_crypto_bar_size(ARG(0), &key_n) || !rp_crypto_bar_size(ARG(1), &n))
    pl_raise_msg(t, "HmacSha256: expected key and message byte bars");
  rp_crypto_init(t);
  uint8_t* message = rp_nat_bytes(ARG(1), true, &n);
  uint8_t* key = rp_nat_bytes(ARG(0), true, &key_n);
  uint8_t digest[crypto_auth_hmacsha256_BYTES];
  crypto_auth_hmacsha256_state state;
  crypto_auth_hmacsha256_init(&state, key, key_n);
  sodium_memzero(key, key_n);
  free(key);
  crypto_auth_hmacsha256_update(&state, message, (unsigned long long)n);
  crypto_auth_hmacsha256_final(&state, digest);
  sodium_memzero(&state, sizeof(state));
  free(message);
  return rp_bar(t, digest, sizeof(digest));
}

/* Derive from a 32-byte seed instead of accepting libsodium's expanded
 * secret key, which includes a public key that must agree with the seed. */
static void rp_ed25519_keypair(pl_val seed_bar, uint8_t* pk, uint8_t* sk) {
  uint8_t seed[crypto_sign_ed25519_SEEDBYTES];
  rp_crypto_copy(seed_bar, seed, sizeof(seed));
  crypto_sign_ed25519_seed_keypair(pk, sk, seed);
  sodium_memzero(seed, sizeof(seed));
}

pl_val pl_op83_ed25519_public_key(pl_thread* t, size_t ab) {
  size_t n;
  if (!rp_crypto_bar_size(ARG(0), &n) || n != crypto_sign_ed25519_SEEDBYTES)
    pl_raise_msg(t, "Ed25519PublicKey: expected a 32-byte seed bar");
  rp_crypto_init(t);
  uint8_t pk[crypto_sign_ed25519_PUBLICKEYBYTES];
  uint8_t sk[crypto_sign_ed25519_SECRETKEYBYTES];
  rp_ed25519_keypair(ARG(0), pk, sk);
  sodium_memzero(sk, sizeof(sk));
  return rp_bar(t, pk, sizeof(pk));
}

/* Ed25519Sign seed message -> detached signature bar. */
pl_val pl_op83_ed25519_sign(pl_thread* t, size_t ab) {
  size_t seed_n, n;
  if (!rp_crypto_bar_size(ARG(0), &seed_n) ||
      seed_n != crypto_sign_ed25519_SEEDBYTES ||
      !rp_crypto_bar_size(ARG(1), &n))
    pl_raise_msg(t, "Ed25519Sign: expected a 32-byte seed bar and message bar");
  rp_crypto_init(t);
  uint8_t* message = rp_nat_bytes(ARG(1), true, &n);
  uint8_t pk[crypto_sign_ed25519_PUBLICKEYBYTES];
  uint8_t sk[crypto_sign_ed25519_SECRETKEYBYTES];
  uint8_t signature[crypto_sign_ed25519_BYTES];
  rp_ed25519_keypair(ARG(0), pk, sk);
  int rc = crypto_sign_ed25519_detached(signature, NULL, message,
                                        (unsigned long long)n, sk);
  sodium_memzero(sk, sizeof(sk));
  free(message);
  if (rc != 0)
    pl_raise_msg(t, "Ed25519Sign: signing failed");
  return rp_bar(t, signature, sizeof(signature));
}

/* Ed25519Verify public-key message signature -> 1 or 0.  Malformed input
 * is a verification failure too.  Validate all arguments before allocating. */
pl_val pl_op83_ed25519_verify(pl_thread* t, size_t ab) {
  size_t pk_n, n, sig_n;
  if (!rp_crypto_bar_size(ARG(0), &pk_n) ||
      pk_n != crypto_sign_ed25519_PUBLICKEYBYTES ||
      !rp_crypto_bar_size(ARG(1), &n) || !rp_crypto_bar_size(ARG(2), &sig_n) ||
      sig_n != crypto_sign_ed25519_BYTES)
    return 0;
  rp_crypto_init(t);
  uint8_t pk[crypto_sign_ed25519_PUBLICKEYBYTES];
  uint8_t signature[crypto_sign_ed25519_BYTES];
  rp_crypto_copy(ARG(0), pk, sizeof(pk));
  rp_crypto_copy(ARG(2), signature, sizeof(signature));
  uint8_t* message = rp_nat_bytes(ARG(1), true, &n);
  int rc = crypto_sign_ed25519_verify_detached(signature, message,
                                               (unsigned long long)n, pk);
  free(message);
  return rc == 0 ? 1 : 0;
}
