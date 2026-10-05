#pragma once

/*
 * A tiny loopback HTTP/1.1 mock server for the Fetch driver tests.
 * Binds 127.0.0.1:0 (the kernel picks the port), accepts in a
 * background thread, and handles each connection in its own detached
 * thread so concurrent transfers make independent progress.  Every
 * response carries "Connection: close".  Fixed path-dispatched
 * behaviors:
 *
 *   /ok       200, X-One/X-Two marker headers, body "hello, enki"
 *   /hop1     302 -> /hop2 (X-Hop: 1, body "moved") /hop2 302 -> /final
 *   /final    200, X-Final marker, body "landed"
 *   /xorigin  302 -> http://127.0.0.1:<xorigin_port>/final
 *   /raw301   301 -> /final, body "moved"
 *   /big      200, 4 MiB of 'x' (chunk-written; records write failure)
 *   /drip3    200, 3-byte body at one byte per 250 ms
 *   /slow     200, huge Content-Length, one byte per 200 ms, forever
 *   anything else: 404, body "nope"
 *
 * Every handled request is captured (method, path, Authorization
 * presence, raw header block) for assertions.
 */

#include <arpa/inet.h>
#include <netinet/in.h>
#include <pthread.h>
#include <signal.h>
#include <stdarg.h>
#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/socket.h>
#include <time.h>
#include <unistd.h>

#define TEST_HTTP_MAX_REQS  64
#define TEST_HTTP_HDR_CAP   2048
#define TEST_HTTP_BIG_BYTES (4u << 20)

typedef struct test_http_req {
  char method[16];
  char path[128];
  bool had_auth;
  bool write_failed; /* the client dropped the connection mid-body */
  char headers[TEST_HTTP_HDR_CAP]; /* raw header block, NUL-terminated */
} test_http_req;

typedef struct test_http_server {
  int listen_fd;
  uint16_t port;
  uint16_t xorigin_port; /* /xorigin redirect target (0: self) */
  pthread_t thread;
  pthread_mutex_t mu;
  pthread_cond_t handlers_idle;
  bool stopping;
  size_t active_handlers;
  test_http_req reqs[TEST_HTTP_MAX_REQS];
  size_t nreqs;
} test_http_server;

typedef struct test_http_conn {
  test_http_server* srv;
  int fd;
} test_http_conn;

static void test_http_msleep(long ms) {
  struct timespec ts = {.tv_sec = ms / 1000, .tv_nsec = (ms % 1000) * 1000000};
  nanosleep(&ts, NULL);
}

static ssize_t test_http_write_all(int fd, const void* b, size_t n) {
  const char* p = b;
  size_t off = 0;
  while (off < n) {
    ssize_t w = write(fd, p + off, n - off);
    if (w <= 0)
      return -1;
    off += (size_t)w;
  }
  return (ssize_t)n;
}

static void test_http_printf(int fd, bool* failed, const char* fmt, ...) {
  char buf[4096];
  va_list ap;
  va_start(ap, fmt);
  int n = vsnprintf(buf, sizeof(buf), fmt, ap);
  va_end(ap);
  if (n < 0 || (size_t)n >= sizeof(buf) ||
      test_http_write_all(fd, buf, (size_t)n) < 0)
    *failed = true;
}

static void test_http_handler_done(test_http_server* srv, int fd) {
  close(fd);
  pthread_mutex_lock(&srv->mu);
  srv->active_handlers--;
  if (srv->active_handlers == 0)
    pthread_cond_signal(&srv->handlers_idle);
  pthread_mutex_unlock(&srv->mu);
}

static void* test_http_handle(void* arg) {
  test_http_conn* c = arg;
  test_http_server* srv = c->srv;
  int fd = c->fd;
  free(c);

  /* read the request head (and swallow any body per Content-Length) */
  char head[8192];
  size_t got = 0;
  char* body_start = NULL;
  while (got < sizeof(head) - 1) {
    ssize_t r = read(fd, head + got, sizeof(head) - 1 - got);
    if (r <= 0)
      break;
    got += (size_t)r;
    head[got] = '\0';
    body_start = strstr(head, "\r\n\r\n");
    if (body_start != NULL)
      break;
  }
  if (body_start == NULL) {
    test_http_handler_done(srv, fd);
    return NULL;
  }
  body_start += 4;

  char method[16] = {0}, path[128] = {0};
  (void)sscanf(head, "%15s %127s", method, path);
  const char* hdrs = strstr(head, "\r\n");
  hdrs = hdrs != NULL ? hdrs + 2 : head;

  size_t content_length = 0;
  {
    /* case-insensitive-enough for curl's canonical casing */
    const char* cl = strstr(hdrs, "Content-Length:");
    if (cl == NULL)
      cl = strstr(hdrs, "content-length:");
    if (cl != NULL)
      content_length = strtoul(strchr(cl, ':') + 1, NULL, 10);
  }
  size_t body_got = got - (size_t)(body_start - head);
  while (body_got < content_length) {
    char sink[4096];
    size_t want = content_length - body_got;
    ssize_t r = read(fd, sink, want < sizeof(sink) ? want : sizeof(sink));
    if (r <= 0)
      break;
    body_got += (size_t)r;
  }

  pthread_mutex_lock(&srv->mu);
  test_http_req* cap = NULL;
  if (srv->nreqs < TEST_HTTP_MAX_REQS) {
    cap = &srv->reqs[srv->nreqs++];
    snprintf(cap->method, sizeof(cap->method), "%s", method);
    snprintf(cap->path, sizeof(cap->path), "%s", path);
    cap->had_auth = strstr(hdrs, "Authorization:") != NULL ||
                    strstr(hdrs, "authorization:") != NULL;
    snprintf(cap->headers, sizeof(cap->headers), "%.*s",
             (int)(size_t)(body_start - hdrs), hdrs);
  }
  uint16_t self = srv->port;
  uint16_t xport = srv->xorigin_port != 0 ? srv->xorigin_port : srv->port;
  pthread_mutex_unlock(&srv->mu);

  bool failed = false;
  if (strncmp(path, "/ok", 3) == 0 && (path[3] == '\0' || path[3] == '?')) {
    const char* body = "hello, enki";
    test_http_printf(fd, &failed,
                     "HTTP/1.1 200 OK\r\nX-One: alpha\r\nX-Two: beta\r\n"
                     "Content-Length: %zu\r\nConnection: close\r\n\r\n%s",
                     strlen(body), body);
  } else if (strcmp(path, "/hop1") == 0) {
    const char* body = "moved";
    test_http_printf(fd, &failed,
                     "HTTP/1.1 302 Found\r\nX-Hop: 1\r\n"
                     "Location: http://127.0.0.1:%u/hop2\r\n"
                     "Content-Length: %zu\r\nConnection: close\r\n\r\n%s",
                     (unsigned)self, strlen(body), body);
  } else if (strcmp(path, "/hop2") == 0) {
    test_http_printf(fd, &failed,
                     "HTTP/1.1 302 Found\r\nX-Hop: 2\r\n"
                     "Location: http://127.0.0.1:%u/final\r\n"
                     "Content-Length: 0\r\nConnection: close\r\n\r\n",
                     (unsigned)self);
  } else if (strcmp(path, "/final") == 0) {
    const char* body = "landed";
    test_http_printf(fd, &failed,
                     "HTTP/1.1 200 OK\r\nX-Final: yes\r\n"
                     "Content-Length: %zu\r\nConnection: close\r\n\r\n%s",
                     strlen(body), body);
  } else if (strcmp(path, "/xorigin") == 0) {
    test_http_printf(fd, &failed,
                     "HTTP/1.1 302 Found\r\n"
                     "Location: http://127.0.0.1:%u/final\r\n"
                     "Content-Length: 0\r\nConnection: close\r\n\r\n",
                     (unsigned)xport);
  } else if (strcmp(path, "/raw301") == 0) {
    const char* body = "moved";
    test_http_printf(fd, &failed,
                     "HTTP/1.1 301 Moved Permanently\r\n"
                     "Location: http://127.0.0.1:%u/final\r\n"
                     "Content-Length: %zu\r\nConnection: close\r\n\r\n%s",
                     (unsigned)self, strlen(body), body);
  } else if (strcmp(path, "/big") == 0) {
    test_http_printf(fd, &failed,
                     "HTTP/1.1 200 OK\r\nContent-Length: %u\r\n"
                     "Connection: close\r\n\r\n",
                     TEST_HTTP_BIG_BYTES);
    char chunk[65536];
    memset(chunk, 'x', sizeof(chunk));
    for (size_t sent = 0; !failed && sent < TEST_HTTP_BIG_BYTES;
         sent += sizeof(chunk)) {
      if (test_http_write_all(fd, chunk, sizeof(chunk)) < 0)
        failed = true;
      /* throttle so a client abort surfaces as a mid-stream write
       * failure instead of vanishing into loopback buffering */
      test_http_msleep(10);
    }
  } else if (strcmp(path, "/drip3") == 0) {
    test_http_printf(fd, &failed,
                     "HTTP/1.1 200 OK\r\nContent-Length: 3\r\n"
                     "Connection: close\r\n\r\n");
    for (int i = 0; !failed && i < 3; i++) {
      test_http_msleep(250);
      if (test_http_write_all(fd, "d", 1) < 0)
        failed = true;
    }
  } else if (strcmp(path, "/slow") == 0) {
    test_http_printf(fd, &failed,
                     "HTTP/1.1 200 OK\r\nContent-Length: 1000000\r\n"
                     "Connection: close\r\n\r\n");
    while (!failed) {
      test_http_msleep(200);
      if (test_http_write_all(fd, ".", 1) < 0)
        failed = true;
    }
  } else {
    const char* body = "nope";
    test_http_printf(fd, &failed,
                     "HTTP/1.1 404 Not Found\r\nContent-Length: %zu\r\n"
                     "Connection: close\r\n\r\n%s",
                     strlen(body), body);
  }

  if (cap != NULL && failed) {
    pthread_mutex_lock(&srv->mu);
    cap->write_failed = true;
    pthread_mutex_unlock(&srv->mu);
  }
  test_http_handler_done(srv, fd);
  return NULL;
}

static void* test_http_accept_loop(void* arg) {
  test_http_server* srv = arg;
  for (;;) {
    int fd = accept(srv->listen_fd, NULL, NULL);
    if (fd < 0)
      return NULL; /* listener closed: stop */
    test_http_conn* c = malloc(sizeof(*c));
    if (c == NULL) {
      close(fd);
      continue;
    }
    pthread_mutex_lock(&srv->mu);
    bool stopping = srv->stopping;
    if (!stopping)
      srv->active_handlers++;
    pthread_mutex_unlock(&srv->mu);
    if (stopping) {
      close(fd);
      free(c);
      return NULL;
    }
    c->srv = srv;
    c->fd = fd;
    pthread_t th;
    pthread_attr_t at;
    pthread_attr_init(&at);
    pthread_attr_setdetachstate(&at, PTHREAD_CREATE_DETACHED);
    if (pthread_create(&th, &at, test_http_handle, c) != 0) {
      free(c);
      test_http_handler_done(srv, fd);
    }
    pthread_attr_destroy(&at);
  }
}

static bool test_http_server_start(test_http_server* srv) {
  memset(srv, 0, sizeof(*srv));
  signal(SIGPIPE, SIG_IGN); /* client aborts must not kill the test */
  srv->listen_fd = socket(AF_INET, SOCK_STREAM, 0);
  if (srv->listen_fd < 0)
    return false;
  int one = 1;
  setsockopt(srv->listen_fd, SOL_SOCKET, SO_REUSEADDR, &one, sizeof(one));
  struct sockaddr_in addr = {0};
  addr.sin_family = AF_INET;
  addr.sin_addr.s_addr = htonl(INADDR_LOOPBACK);
  addr.sin_port = 0;
  if (bind(srv->listen_fd, (struct sockaddr*)&addr, sizeof(addr)) < 0 ||
      listen(srv->listen_fd, 16) < 0) {
    close(srv->listen_fd);
    return false;
  }
  socklen_t alen = sizeof(addr);
  if (getsockname(srv->listen_fd, (struct sockaddr*)&addr, &alen) < 0) {
    close(srv->listen_fd);
    return false;
  }
  srv->port = ntohs(addr.sin_port);
  if (pthread_mutex_init(&srv->mu, NULL) != 0) {
    close(srv->listen_fd);
    return false;
  }
  if (pthread_cond_init(&srv->handlers_idle, NULL) != 0) {
    pthread_mutex_destroy(&srv->mu);
    close(srv->listen_fd);
    return false;
  }
  if (pthread_create(&srv->thread, NULL, test_http_accept_loop, srv) != 0) {
    close(srv->listen_fd);
    pthread_cond_destroy(&srv->handlers_idle);
    pthread_mutex_destroy(&srv->mu);
    return false;
  }
  return true;
}

static void test_http_server_stop(test_http_server* srv) {
  pthread_mutex_lock(&srv->mu);
  srv->stopping = true;
  pthread_mutex_unlock(&srv->mu);

  /* Closing a listening socket from another thread does not reliably wake a
   * blocking accept() on Linux.  Connect to the listener instead: the accept
   * loop observes stopping, closes this connection, and exits. */
  int wake_fd = socket(AF_INET, SOCK_STREAM, 0);
  if (wake_fd >= 0) {
    struct sockaddr_in addr = {0};
    addr.sin_family = AF_INET;
    addr.sin_addr.s_addr = htonl(INADDR_LOOPBACK);
    addr.sin_port = htons(srv->port);
    if (connect(wake_fd, (struct sockaddr*)&addr, sizeof(addr)) < 0)
      (void)shutdown(srv->listen_fd, SHUT_RDWR);
    close(wake_fd);
  } else {
    (void)shutdown(srv->listen_fd, SHUT_RDWR);
  }
  pthread_join(srv->thread, NULL);
  close(srv->listen_fd);
  pthread_mutex_lock(&srv->mu);
  while (srv->active_handlers != 0)
    pthread_cond_wait(&srv->handlers_idle, &srv->mu);
  pthread_mutex_unlock(&srv->mu);
  pthread_cond_destroy(&srv->handlers_idle);
  pthread_mutex_destroy(&srv->mu);
}

/* The most recent captured request for `path`, or NULL.  In-flight
 * handler threads may still append; callers synchronize by fetching
 * only after the client observed the response. */
static test_http_req* test_http_server_last(test_http_server* srv,
                                            const char* path) {
  test_http_req* found = NULL;
  pthread_mutex_lock(&srv->mu);
  for (size_t i = 0; i < srv->nreqs; i++)
    if (strcmp(srv->reqs[i].path, path) == 0)
      found = &srv->reqs[i];
  pthread_mutex_unlock(&srv->mu);
  return found;
}

/* A loopback port that is certainly refusing connections: bind, note
 * the port, close.  (Nothing else can grab it between close and the
 * connect attempt in practice; races would only flake toward a
 * different error, not a hang.) */
static uint16_t test_http_dead_port(void) {
  int fd = socket(AF_INET, SOCK_STREAM, 0);
  if (fd < 0)
    return 1; /* port 1 is privileged and closed on any sane test host */
  struct sockaddr_in addr = {0};
  addr.sin_family = AF_INET;
  addr.sin_addr.s_addr = htonl(INADDR_LOOPBACK);
  addr.sin_port = 0;
  uint16_t port = 1;
  socklen_t alen = sizeof(addr);
  if (bind(fd, (struct sockaddr*)&addr, sizeof(addr)) == 0 &&
      getsockname(fd, (struct sockaddr*)&addr, &alen) == 0)
    port = ntohs(addr.sin_port);
  close(fd);
  return port;
}
