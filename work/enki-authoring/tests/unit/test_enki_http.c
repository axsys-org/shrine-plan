#include "test.h"

#include <stdio.h>
#include <string.h>
#include <unistd.h>

#include "enki/actor.h"
#include "test_http_server.h"
#include "test_plan.h"

/*
 * op 83 Fetch: the libcurl-backed HTTP driver, against a loopback mock
 * server (no external network).  The reaver reference has no httpFetch
 * — like Connect, this is an enki extension, so there is no
 * differential oracle test; the mock server is the ground truth.
 *
 * Law-body code combinators as in test_enki_replay.c.
 */

#define FETCH ax_s5('F', 'e', 't', 'c', 'h')

/* Err codes (ABI mirror of http.c). */
enum {
  HTTP_BAD_URL = 0,
  HTTP_DNS = 1,
  HTTP_CONNECT = 2,
  HTTP_TLS = 3,
  HTTP_DEADLINE = 4,
  HTTP_REDIRECTS = 5,
  HTTP_TOO_LARGE = 6,
  HTTP_PROTOCOL = 7,
};

static pl_val code_lit(pl_thread* t, pl_val v) {
  return test_app1(t, 0, v);
}

static pl_val code_app(pl_thread* t, pl_val f, pl_val x) {
  return test_app2(t, 0, f, x);
}

static pl_val test_p83(pl_thread* t) {
  size_t base = t->vsp;
  pl_vpush(t, 83);
  pl_val pin = pl_pin(t, t->vstack[base]);
  t->vsp = base;
  return pin;
}

/* Law-body code performing (P83 % (Fetch req cfg)). */
static pl_val code_fetch(pl_thread* t, pl_val req, pl_val cfg) {
  size_t base = t->vsp;
  pl_vpush(t, req);
  pl_vpush(t, cfg);
  pl_vpush(t, code_lit(t, test_p83(t)));
  pl_val row_args[2] = {t->vstack[base], t->vstack[base + 1]};
  pl_vpush(t, code_lit(t, test_app(t, FETCH, 2, row_args)));
  pl_val out = code_app(t, t->vstack[base + 2], t->vstack[base + 3]);
  t->vsp = base;
  return out;
}

static pl_val actor_fn(pl_thread* t, pl_val body) {
  return test_law(t, 1, 0, body);
}

/* ── Request/Config value builders (bars, rows) ────────────────────────── */

static pl_val mk_bar_n(pl_thread* t, const uint8_t* b, size_t n) {
  uint8_t* buf = malloc(n + 1);
  ASSERT_NOT_NULL(buf);
  memcpy(buf, b, n);
  buf[n] = 0x01;
  pl_val v = pl_nat_from_bytes(t, buf, n + 1);
  free(buf);
  return v;
}

static pl_val mk_bar(pl_thread* t, const char* s) {
  return mk_bar_n(t, (const uint8_t*)s, strlen(s));
}

typedef struct test_hdr {
  const char* name;
  const char* value;
} test_hdr;

/* Request = [methodBar urlBar headersRow bodyMaybe] */
static pl_val mk_request(pl_thread* t, const char* method, const char* url,
                         size_t nh, const test_hdr* hdrs, const char* body) {
  size_t base = t->vsp;
  pl_vpush(t, mk_bar(t, method));
  pl_vpush(t, mk_bar(t, url));
  for (size_t i = 0; i < nh; i++) {
    size_t hb = t->vsp;
    pl_vpush(t, mk_bar(t, hdrs[i].name));
    pl_vpush(t, mk_bar(t, hdrs[i].value));
    pl_val pair[2] = {t->vstack[hb], t->vstack[hb + 1]};
    t->vsp = hb;
    pl_vpush(t, test_app(t, 0, 2, pair));
  }
  if (nh > 0) {
    pl_val row = test_app(t, 0, nh, &t->vstack[base + 2]);
    t->vsp = base + 2;
    pl_vpush(t, row);
  } else {
    pl_vpush(t, 0);
  }
  if (body != NULL) {
    size_t bb = t->vsp;
    pl_vpush(t, mk_bar(t, body));
    pl_val some[1] = {t->vstack[bb]};
    t->vsp = bb;
    pl_vpush(t, test_app(t, 0, 1, some));
  } else {
    pl_vpush(t, 0);
  }
  pl_val fields[4] = {t->vstack[base], t->vstack[base + 1], t->vstack[base + 2],
                      t->vstack[base + 3]};
  pl_val req = test_app(t, 0, 4, fields);
  t->vsp = base;
  return req;
}

/* Config = [connectMsMaybe deadlineMs redirects [maxBody]];
 * connect_ms < 0 = None, max_body = UINT64_MAX means Spooled (nat 1). */
static pl_val mk_config_ex(pl_thread* t, int64_t connect_ms,
                           uint64_t deadline_ms, uint64_t redirects,
                           uint64_t max_body, bool spooled) {
  size_t base = t->vsp;
  if (connect_ms >= 0) {
    pl_val some[1] = {(pl_val)connect_ms};
    pl_vpush(t, test_app(t, 0, 1, some));
  } else {
    pl_vpush(t, 0);
  }
  if (spooled) {
    pl_vpush(t, 1);
  } else {
    pl_val buffered[1] = {max_body};
    pl_vpush(t, test_app(t, 0, 1, buffered));
  }
  pl_val fields[4] = {t->vstack[base], deadline_ms, redirects,
                      t->vstack[base + 1]};
  pl_val cfg = test_app(t, 0, 4, fields);
  t->vsp = base;
  return cfg;
}

static pl_val mk_config(pl_thread* t, uint64_t deadline_ms, uint64_t redirects,
                        uint64_t max_body) {
  return mk_config_ex(t, -1, deadline_ms, redirects, max_body, false);
}

/* An actor whose result is the Fetch Result value. */
static er_actor* start_fetch_actor(er_scheduler* sys,
                                   pl_val (*mkreq)(pl_thread* t,
                                                   const void* env),
                                   const void* env, uint64_t deadline_ms,
                                   uint64_t redirects, uint64_t max_body) {
  er_actor* a = er_scheduler_actor(sys);
  pl_thread* t = er_actor_thread(a);
  size_t base = t->vsp;
  pl_vpush(t, mkreq(t, env));
  pl_vpush(t, mk_config(t, deadline_ms, redirects, max_body));
  pl_val body = code_fetch(t, t->vstack[base], t->vstack[base + 1]);
  t->vsp = base;
  er_actor_start(a, actor_fn(t, body));
  return a;
}

/* The common case: GET `url`, no headers, no body. */
static pl_val mk_get(pl_thread* t, const void* env) {
  return mk_request(t, "GET", (const char*)env, 0, NULL, NULL);
}

/* ── Result readers ────────────────────────────────────────────────────── */

/* Assert (0 resp) and return the Response cell [status url hdrs body]. */
static pl_cell* result_ok(pl_val res) {
  pl_cell* r = pl_as(PL_TAG_APP, res);
  ASSERT_NOT_NULL(r, "Result is not an app");
  ASSERT_EQ(pl_app_head(r), 0, "Result is an Err");
  ASSERT_EQ(pl_app_n(r), 1);
  pl_cell* resp = pl_as(PL_TAG_APP, pl_app_args(r)[0]);
  ASSERT_NOT_NULL(resp);
  ASSERT_EQ(pl_app_head(resp), 0);
  ASSERT_EQ(pl_app_n(resp), 4);
  return resp;
}

/* Assert (1 code) and return the code. */
static uint64_t result_err(pl_val res) {
  pl_cell* r = pl_as(PL_TAG_APP, res);
  ASSERT_NOT_NULL(r, "Result is not an app");
  ASSERT_EQ(pl_app_head(r), 1, "Result is not an Err");
  ASSERT_EQ(pl_app_n(r), 1);
  ASSERT(pl_is_nat63(pl_app_args(r)[0]));
  return pl_app_args(r)[0];
}

static void bar_cstr(pl_val v, char* out, size_t cap) {
  ASSERT(pl_is_nat(v), "expected a bar");
  size_t n = pl_nat_byte_len(v);
  ASSERT_GT(n, 0);
  ASSERT_EQ(pl_nat_byte_at(v, n - 1), 1, "missing bar terminator");
  ASSERT_LT(n, cap, "bar too long for the buffer");
  for (size_t i = 0; i + 1 < n; i++)
    out[i] = (char)pl_nat_byte_at(v, i);
  out[n - 1] = '\0';
}

static void assert_bar_eq(pl_val v, const char* s) {
  char buf[4096];
  bar_cstr(v, buf, sizeof(buf));
  ASSERT_STR_EQ(buf, s);
}

/* The index of header `name` in the headers row, or -1; checks the
 * value when expected_value is non-NULL. */
static int64_t header_find(pl_val hdrs, const char* name,
                           const char* expected_value) {
  if (hdrs == 0)
    return -1;
  pl_cell* h = pl_as(PL_TAG_APP, hdrs);
  ASSERT_NOT_NULL(h);
  for (uint32_t i = 0; i < pl_app_n(h); i++) {
    pl_cell* pair = pl_as(PL_TAG_APP, pl_app_args(h)[i]);
    ASSERT_NOT_NULL(pair);
    ASSERT_EQ(pl_app_n(pair), 2);
    char nbuf[256];
    bar_cstr(pl_app_args(pair)[0], nbuf, sizeof(nbuf));
    if (strcmp(nbuf, name) != 0)
      continue;
    if (expected_value != NULL) {
      char vbuf[1024];
      bar_cstr(pl_app_args(pair)[1], vbuf, sizeof(vbuf));
      ASSERT_STR_EQ(vbuf, expected_value);
    }
    return i;
  }
  return -1;
}

static void url_of(const test_http_server* srv, const char* path, char* out,
                   size_t cap) {
  (void)snprintf(out, cap, "http://127.0.0.1:%u%s", (unsigned)srv->port, path);
}

/* ── The matrix ────────────────────────────────────────────────────────── */

TEST(http, get_roundtrip_status_headers_body) {
  test_http_server srv;
  ASSERT(test_http_server_start(&srv));
  test_rt rt = test_rt_new();
  er_scheduler* sys = er_scheduler_new(rt.store, (er_config){0});

  char url[256];
  url_of(&srv, "/ok", url, sizeof(url));
  er_actor* a = er_scheduler_actor(sys);
  {
    pl_thread* t = er_actor_thread(a);
    size_t base = t->vsp;
    test_hdr hdrs[2] = {{"A-First", "1"}, {"A-Second", "2"}};
    pl_vpush(t, mk_request(t, "GET", url, 2, hdrs, NULL));
    pl_vpush(t, mk_config(t, 5000, 0, 1 << 20));
    pl_val body = code_fetch(t, t->vstack[base], t->vstack[base + 1]);
    t->vsp = base;
    er_actor_start(a, actor_fn(t, body));
  }
  ASSERT_EQ(er_scheduler_run(sys), ER_RUN_IDLE);
  ASSERT_EQ(er_actor_state(a), ER_ACTOR_HALTED);

  pl_cell* resp = result_ok(er_actor_result(a));
  ASSERT_EQ(pl_app_args(resp)[0], 200);
  assert_bar_eq(pl_app_args(resp)[1], url); /* effective URL, no redirect */
  pl_val hdrs = pl_app_args(resp)[2];
  int64_t one = header_find(hdrs, "X-One", "alpha");
  int64_t two = header_find(hdrs, "X-Two", "beta");
  ASSERT_GTE(one, 0);
  ASSERT_GT(two, one); /* wire order preserved */
  assert_bar_eq(pl_app_args(resp)[3], "hello, enki");

  /* server side: method verbatim, request headers sent in order */
  test_http_req* cap = test_http_server_last(&srv, "/ok");
  ASSERT_NOT_NULL(cap);
  ASSERT_STR_EQ(cap->method, "GET");
  char* first = strstr(cap->headers, "A-First: 1");
  char* second = strstr(cap->headers, "A-Second: 2");
  ASSERT_NOT_NULL(first);
  ASSERT_NOT_NULL(second);
  ASSERT(first < second, "request header order not preserved");

  er_scheduler_free(sys);
  test_rt_free(&rt);
  test_http_server_stop(&srv);
}

TEST(http, post_body_upload) {
  test_http_server srv;
  ASSERT(test_http_server_start(&srv));
  test_rt rt = test_rt_new();
  er_scheduler* sys = er_scheduler_new(rt.store, (er_config){0});

  char url[256];
  url_of(&srv, "/ok", url, sizeof(url));
  er_actor* a = er_scheduler_actor(sys);
  {
    pl_thread* t = er_actor_thread(a);
    size_t base = t->vsp;
    pl_vpush(t, mk_request(t, "POST", url, 0, NULL, "ping-body"));
    pl_vpush(t, mk_config(t, 5000, 0, 1 << 20));
    pl_val body = code_fetch(t, t->vstack[base], t->vstack[base + 1]);
    t->vsp = base;
    er_actor_start(a, actor_fn(t, body));
  }
  ASSERT_EQ(er_scheduler_run(sys), ER_RUN_IDLE);
  ASSERT_EQ(er_actor_state(a), ER_ACTOR_HALTED);
  pl_cell* resp = result_ok(er_actor_result(a));
  ASSERT_EQ(pl_app_args(resp)[0], 200);

  test_http_req* cap = test_http_server_last(&srv, "/ok");
  ASSERT_NOT_NULL(cap);
  ASSERT_STR_EQ(cap->method, "POST");
  ASSERT_NOT_NULL(strstr(cap->headers, "Content-Length: 9"));

  er_scheduler_free(sys);
  test_rt_free(&rt);
  test_http_server_stop(&srv);
}

TEST(http, redirect_chain_final_headers_only) {
  test_http_server srv;
  ASSERT(test_http_server_start(&srv));
  test_rt rt = test_rt_new();
  er_scheduler* sys = er_scheduler_new(rt.store, (er_config){0});

  char url[256], final_url[256];
  url_of(&srv, "/hop1", url, sizeof(url));
  url_of(&srv, "/final", final_url, sizeof(final_url));
  er_actor* a = er_scheduler_actor(sys);
  {
    pl_thread* t = er_actor_thread(a);
    size_t base = t->vsp;
    test_hdr hdrs[1] = {{"Authorization", "Bearer sesame"}};
    pl_vpush(t, mk_request(t, "GET", url, 1, hdrs, NULL));
    pl_vpush(t, mk_config(t, 5000, 5, 1 << 20));
    pl_val body = code_fetch(t, t->vstack[base], t->vstack[base + 1]);
    t->vsp = base;
    er_actor_start(a, actor_fn(t, body));
  }
  ASSERT_EQ(er_scheduler_run(sys), ER_RUN_IDLE);
  ASSERT_EQ(er_actor_state(a), ER_ACTOR_HALTED);

  pl_cell* resp = result_ok(er_actor_result(a));
  ASSERT_EQ(pl_app_args(resp)[0], 200);
  assert_bar_eq(pl_app_args(resp)[1], final_url); /* effective URL */
  pl_val hdrs = pl_app_args(resp)[2];
  ASSERT_GTE(header_find(hdrs, "X-Final", "yes"), 0);
  ASSERT_EQ(header_find(hdrs, "X-Hop", NULL), -1,
            "intermediate 3xx headers leaked into the Response");
  assert_bar_eq(pl_app_args(resp)[3], "landed"); /* not "movedlanded" */

  /* same-origin redirect: the Authorization header rides along */
  test_http_req* cap = test_http_server_last(&srv, "/final");
  ASSERT_NOT_NULL(cap);
  ASSERT(cap->had_auth);

  er_scheduler_free(sys);
  test_rt_free(&rt);
  test_http_server_stop(&srv);
}

TEST(http, cross_origin_redirect_strips_auth) {
  test_http_server srv_a, srv_b;
  ASSERT(test_http_server_start(&srv_a));
  ASSERT(test_http_server_start(&srv_b));
  srv_a.xorigin_port = srv_b.port; /* different port = different origin */

  test_rt rt = test_rt_new();
  er_scheduler* sys = er_scheduler_new(rt.store, (er_config){0});
  char url[256];
  url_of(&srv_a, "/xorigin", url, sizeof(url));
  er_actor* a = er_scheduler_actor(sys);
  {
    pl_thread* t = er_actor_thread(a);
    size_t base = t->vsp;
    test_hdr hdrs[1] = {{"Authorization", "Bearer sesame"}};
    pl_vpush(t, mk_request(t, "GET", url, 1, hdrs, NULL));
    pl_vpush(t, mk_config(t, 5000, 5, 1 << 20));
    pl_val body = code_fetch(t, t->vstack[base], t->vstack[base + 1]);
    t->vsp = base;
    er_actor_start(a, actor_fn(t, body));
  }
  ASSERT_EQ(er_scheduler_run(sys), ER_RUN_IDLE);
  ASSERT_EQ(er_actor_state(a), ER_ACTOR_HALTED);
  pl_cell* resp = result_ok(er_actor_result(a));
  ASSERT_EQ(pl_app_args(resp)[0], 200);

  test_http_req* at_a = test_http_server_last(&srv_a, "/xorigin");
  ASSERT_NOT_NULL(at_a);
  ASSERT(at_a->had_auth, "Authorization missing at the origin");
  test_http_req* at_b = test_http_server_last(&srv_b, "/final");
  ASSERT_NOT_NULL(at_b);
  ASSERT(!at_b->had_auth, "Authorization leaked cross-origin");

  er_scheduler_free(sys);
  test_rt_free(&rt);
  test_http_server_stop(&srv_a);
  test_http_server_stop(&srv_b);
}

TEST(http, zero_redirects_delivers_3xx_raw) {
  test_http_server srv;
  ASSERT(test_http_server_start(&srv));
  test_rt rt = test_rt_new();
  er_scheduler* sys = er_scheduler_new(rt.store, (er_config){0});
  char url[256];
  url_of(&srv, "/raw301", url, sizeof(url));
  er_actor* a =
      start_fetch_actor(sys, mk_get, url, 5000, /*redirects=*/0, 1 << 20);
  ASSERT_EQ(er_scheduler_run(sys), ER_RUN_IDLE);
  ASSERT_EQ(er_actor_state(a), ER_ACTOR_HALTED);

  pl_cell* resp = result_ok(er_actor_result(a));
  ASSERT_EQ(pl_app_args(resp)[0], 301);
  ASSERT_GTE(header_find(pl_app_args(resp)[2], "Location", NULL), 0);
  assert_bar_eq(pl_app_args(resp)[3], "moved");

  er_scheduler_free(sys);
  test_rt_free(&rt);
  test_http_server_stop(&srv);
}

TEST(http, too_many_redirects) {
  test_http_server srv;
  ASSERT(test_http_server_start(&srv));
  test_rt rt = test_rt_new();
  er_scheduler* sys = er_scheduler_new(rt.store, (er_config){0});
  char url[256];
  url_of(&srv, "/hop1", url, sizeof(url));
  /* the chain needs 2 hops; allow only 1 */
  er_actor* a = start_fetch_actor(sys, mk_get, url, 5000, 1, 1 << 20);
  ASSERT_EQ(er_scheduler_run(sys), ER_RUN_IDLE);
  ASSERT_EQ(er_actor_state(a), ER_ACTOR_HALTED);
  ASSERT_EQ(result_err(er_actor_result(a)), HTTP_REDIRECTS);
  er_scheduler_free(sys);
  test_rt_free(&rt);
  test_http_server_stop(&srv);
}

TEST(http, buffered_cap_exact_and_exceeded) {
  test_http_server srv;
  ASSERT(test_http_server_start(&srv));
  test_rt rt = test_rt_new();
  er_scheduler* sys = er_scheduler_new(rt.store, (er_config){0});
  char url[256];
  url_of(&srv, "/big", url, sizeof(url));

  /* exactly N bytes with cap N succeeds */
  er_actor* ok =
      start_fetch_actor(sys, mk_get, url, 30000, 0, TEST_HTTP_BIG_BYTES);
  ASSERT_EQ(er_scheduler_run(sys), ER_RUN_IDLE);
  ASSERT_EQ(er_actor_state(ok), ER_ACTOR_HALTED);
  pl_cell* resp = result_ok(er_actor_result(ok));
  ASSERT_EQ(pl_app_args(resp)[0], 200);
  ASSERT_EQ(pl_nat_byte_len(pl_app_args(resp)[3]),
            (size_t)TEST_HTTP_BIG_BYTES + 1); /* + bar terminator */

  /* cap N-1: the last body byte trips the cap — BodyTooLarge */
  er_actor* big =
      start_fetch_actor(sys, mk_get, url, 30000, 0, TEST_HTTP_BIG_BYTES - 1);
  ASSERT_EQ(er_scheduler_run(sys), ER_RUN_IDLE);
  ASSERT_EQ(er_actor_state(big), ER_ACTOR_HALTED);
  ASSERT_EQ(result_err(er_actor_result(big)), HTTP_TOO_LARGE);

  /* a small cap aborts early enough that the (throttled) server is
   * still mid-body and observes the connection drop */
  er_actor* tiny = start_fetch_actor(sys, mk_get, url, 30000, 0, 100000);
  ASSERT_EQ(er_scheduler_run(sys), ER_RUN_IDLE);
  ASSERT_EQ(er_actor_state(tiny), ER_ACTOR_HALTED);
  ASSERT_EQ(result_err(er_actor_result(tiny)), HTTP_TOO_LARGE);
  bool dropped = false;
  for (int i = 0; i < 100 && !dropped; i++) { /* the handler thread races */
    pthread_mutex_lock(&srv.mu);
    for (size_t j = 0; j < srv.nreqs; j++)
      if (strcmp(srv.reqs[j].path, "/big") == 0 && srv.reqs[j].write_failed)
        dropped = true;
    pthread_mutex_unlock(&srv.mu);
    if (!dropped)
      test_http_msleep(50);
  }
  ASSERT(dropped, "the aborted transfer was fully written server-side");

  er_scheduler_free(sys);
  test_rt_free(&rt);
  test_http_server_stop(&srv);
}

TEST(http, deadline_exceeded_on_slow_body) {
  test_http_server srv;
  ASSERT(test_http_server_start(&srv));
  test_rt rt = test_rt_new();
  er_scheduler* sys = er_scheduler_new(rt.store, (er_config){0});
  char url[256];
  url_of(&srv, "/slow", url, sizeof(url));
  er_actor* a =
      start_fetch_actor(sys, mk_get, url, /*deadline=*/600, 0, 1 << 20);
  ASSERT_EQ(er_scheduler_run(sys), ER_RUN_IDLE);
  ASSERT_EQ(er_actor_state(a), ER_ACTOR_HALTED);
  ASSERT_EQ(result_err(er_actor_result(a)), HTTP_DEADLINE);
  er_scheduler_free(sys);
  test_rt_free(&rt);
  test_http_server_stop(&srv);
}

TEST(http, connect_refused) {
  test_rt rt = test_rt_new();
  er_scheduler* sys = er_scheduler_new(rt.store, (er_config){0});
  char url[256];
  (void)snprintf(url, sizeof(url), "http://127.0.0.1:%u/ok",
                 (unsigned)test_http_dead_port());
  er_actor* a = start_fetch_actor(sys, mk_get, url, 5000, 0, 1 << 20);
  ASSERT_EQ(er_scheduler_run(sys), ER_RUN_IDLE);
  ASSERT_EQ(er_actor_state(a), ER_ACTOR_HALTED);
  ASSERT_EQ(result_err(er_actor_result(a)), HTTP_CONNECT);
  er_scheduler_free(sys);
  test_rt_free(&rt);
}

TEST(http, bad_url_rejections) {
  test_rt rt = test_rt_new();
  er_scheduler* sys = er_scheduler_new(rt.store, (er_config){0});
  const char* bad[] = {"/relative/path", "ftp://127.0.0.1/x",
                       "http//missing.colon", "not a url at all"};
  er_actor* actors[4];
  for (size_t i = 0; i < 4; i++)
    actors[i] = start_fetch_actor(sys, mk_get, bad[i], 5000, 0, 1 << 20);
  /* deadlineMs = 0 is BadUrl-class validation failure */
  er_actor* zero_deadline =
      start_fetch_actor(sys, mk_get, "http://127.0.0.1/ok", 0, 0, 1 << 20);
  /* Spooled bodyMode is reserved in v1 */
  er_actor* spooled = er_scheduler_actor(sys);
  {
    pl_thread* t = er_actor_thread(spooled);
    size_t base = t->vsp;
    pl_vpush(t, mk_request(t, "GET", "http://127.0.0.1/ok", 0, NULL, NULL));
    pl_vpush(t, mk_config_ex(t, -1, 5000, 0, 0, /*spooled=*/true));
    pl_val body = code_fetch(t, t->vstack[base], t->vstack[base + 1]);
    t->vsp = base;
    er_actor_start(spooled, actor_fn(t, body));
  }

  ASSERT_EQ(er_scheduler_run(sys), ER_RUN_IDLE);
  for (size_t i = 0; i < 4; i++) {
    ASSERT_EQ(er_actor_state(actors[i]), ER_ACTOR_HALTED);
    ASSERT_EQ(result_err(er_actor_result(actors[i])), HTTP_BAD_URL,
              "url %zu accepted: %s", i, bad[i]);
  }
  ASSERT_EQ(er_actor_state(zero_deadline), ER_ACTOR_HALTED);
  ASSERT_EQ(result_err(er_actor_result(zero_deadline)), HTTP_BAD_URL);
  ASSERT_EQ(er_actor_state(spooled), ER_ACTOR_HALTED);
  ASSERT_EQ(result_err(er_actor_result(spooled)), HTTP_BAD_URL);

  er_scheduler_free(sys);
  test_rt_free(&rt);
}

TEST(http, malformed_headers_and_oversized_timeouts_are_rejected) {
  test_rt rt = test_rt_new();
  er_scheduler* sys = er_scheduler_new(rt.store, (er_config){0});

  test_hdr injected[] = {{"X-Request", "ok\r\nInjected: yes"}};
  er_actor* bad_header = er_scheduler_actor(sys);
  {
    pl_thread* t = er_actor_thread(bad_header);
    size_t base = t->vsp;
    pl_vpush(t, mk_request(t, "GET", "http://127.0.0.1/ok", 1, injected, NULL));
    pl_vpush(t, mk_config(t, 5000, 0, 1 << 20));
    pl_val body = code_fetch(t, t->vstack[base], t->vstack[base + 1]);
    t->vsp = base;
    er_actor_start(bad_header, actor_fn(t, body));
  }

  er_actor* oversized_deadline = er_scheduler_actor(sys);
  {
    pl_thread* t = er_actor_thread(oversized_deadline);
    size_t base = t->vsp;
    pl_vpush(t, mk_request(t, "GET", "http://127.0.0.1/ok", 0, NULL, NULL));
    pl_vpush(t, 0); /* connectMs None */
    pl_vpush(t, pl_mk_nat_u64(t, UINT64_MAX));
    pl_vpush(t, 0); /* redirects */
    pl_val buffered[1] = {1 << 20};
    pl_vpush(t, test_app(t, 0, 1, buffered));
    pl_val cfg_fields[4] = {t->vstack[base + 1], t->vstack[base + 2],
                            t->vstack[base + 3], t->vstack[base + 4]};
    pl_val cfg = test_app(t, 0, 4, cfg_fields);
    t->vsp = base + 1;
    pl_vpush(t, cfg);
    pl_val body = code_fetch(t, t->vstack[base], t->vstack[base + 1]);
    t->vsp = base;
    er_actor_start(oversized_deadline, actor_fn(t, body));
  }

  ASSERT_EQ(er_scheduler_run(sys), ER_RUN_IDLE);
  ASSERT_EQ(result_err(er_actor_result(bad_header)), HTTP_BAD_URL);
  ASSERT_EQ(result_err(er_actor_result(oversized_deadline)), HTTP_BAD_URL);
  er_scheduler_free(sys);

  er_scheduler* bad_default = er_scheduler_new(
      rt.store, (er_config){.http_connect_default_ms = UINT64_MAX});
  er_actor* oversized_default = start_fetch_actor(
      bad_default, mk_get, "http://127.0.0.1/ok", 5000, 0, 1 << 20);
  ASSERT_EQ(er_scheduler_run(bad_default), ER_RUN_IDLE);
  ASSERT_EQ(result_err(er_actor_result(oversized_default)), HTTP_BAD_URL);
  er_scheduler_free(bad_default);
  test_rt_free(&rt);
}

TEST(http, malformed_request_shape_crashes_the_actor) {
  test_rt rt = test_rt_new();
  er_scheduler* sys = er_scheduler_new(rt.store, (er_config){0});
  er_actor* a = er_scheduler_actor(sys);
  {
    pl_thread* t = er_actor_thread(a);
    size_t base = t->vsp;
    pl_vpush(t, 5); /* req is not a row */
    pl_vpush(t, mk_config(t, 5000, 0, 1 << 20));
    pl_val body = code_fetch(t, t->vstack[base], t->vstack[base + 1]);
    t->vsp = base;
    er_actor_start(a, actor_fn(t, body));
  }
  ASSERT_EQ(er_scheduler_run(sys), ER_RUN_IDLE);
  ASSERT_EQ(er_actor_state(a), ER_ACTOR_CRASHED);
  er_scheduler_free(sys);
  test_rt_free(&rt);
}

TEST(http, teardown_aborts_inflight_transfers) {
  test_http_server srv;
  ASSERT(test_http_server_start(&srv));
  test_rt rt = test_rt_new();
  er_scheduler* sys = er_scheduler_new(rt.store, (er_config){0});
  char url[256];
  url_of(&srv, "/slow", url, sizeof(url));

  /* a spawned actor parks on a slow fetch; the adopted root's own
   * computation completes, so the drive returns with the transfer
   * still in flight — teardown must reap it (ASAN owns the proof) */
  (void)start_fetch_actor(sys, mk_get, url, /*deadline=*/60000, 0, 1 << 20);
  er_actor* root = er_scheduler_adopt(sys, rt.t);
  pl_thread_start(rt.t, 42);
  ASSERT_EQ(er_scheduler_drive(sys, root), ER_DRIVE_DONE);
  ASSERT_EQ(er_http_inflight_count(sys), 1);
  er_scheduler_free(sys); /* aborts the transfer, logs nothing */

  test_rt_free(&rt);
  test_http_server_stop(&srv);
}

/* ── Record / replay ───────────────────────────────────────────────────── */

typedef struct fetch_summary {
  bool ok;
  uint64_t err;
  uint64_t status;
  char url[256];
  char body[256];
} fetch_summary;

static fetch_summary summarize(pl_val res) {
  fetch_summary s = {0};
  pl_cell* r = pl_as(PL_TAG_APP, res);
  ASSERT_NOT_NULL(r);
  if (pl_app_head(r) == 1) {
    s.ok = false;
    s.err = pl_app_args(r)[0];
    return s;
  }
  pl_cell* resp = result_ok(res);
  s.ok = true;
  s.status = pl_app_args(resp)[0];
  bar_cstr(pl_app_args(resp)[1], s.url, sizeof(s.url));
  bar_cstr(pl_app_args(resp)[3], s.body, sizeof(s.body));
  return s;
}

static void assert_summary_eq(const fetch_summary* a, const fetch_summary* b) {
  ASSERT_EQ(a->ok, b->ok);
  ASSERT_EQ(a->err, b->err);
  ASSERT_EQ(a->status, b->status);
  ASSERT_STR_EQ(a->url, b->url);
  ASSERT_STR_EQ(a->body, b->body);
}

TEST(http, record_replay_single_fetch) {
  char dir[] = "/tmp/enki-http-replay-XXXXXX";
  ASSERT_NOT_NULL(mkdtemp(dir));
  char logpath[256];
  (void)snprintf(logpath, sizeof(logpath), "%s/run.enkilog", dir);

  test_http_server srv;
  ASSERT(test_http_server_start(&srv));
  char url[256];
  url_of(&srv, "/ok", url, sizeof(url));

  test_rt rt = test_rt_new();
  er_log* log = er_log_new();
  fetch_summary recorded;
  {
    er_scheduler* sys = er_scheduler_new(rt.store, (er_config){0});
    er_scheduler_record(sys, log);
    er_actor* a = start_fetch_actor(sys, mk_get, url, 5000, 0, 1 << 20);
    ASSERT_EQ(er_scheduler_run(sys), ER_RUN_IDLE);
    ASSERT_EQ(er_actor_state(a), ER_ACTOR_HALTED);
    recorded = summarize(er_actor_result(a));
    ASSERT(recorded.ok);
    ASSERT_EQ(recorded.status, 200);
    er_scheduler_free(sys);
  }
  ASSERT_EQ(er_log_events(log), 1);

  /* file round trip, then kill the server: only the log can answer */
  ASSERT(er_log_write_file(log, logpath));
  er_log_free(log);
  test_http_server_stop(&srv);
  er_log* loaded = er_log_read_file(logpath);
  ASSERT_NOT_NULL(loaded);
  ASSERT_EQ(er_log_events(loaded), 1);

  {
    er_scheduler* sys = er_scheduler_new(rt.store, (er_config){0});
    er_scheduler_replay(sys, loaded);
    er_actor* a = start_fetch_actor(sys, mk_get, url, 5000, 0, 1 << 20);
    ASSERT_EQ(er_scheduler_run(sys), ER_RUN_IDLE);
    ASSERT_EQ(er_actor_state(a), ER_ACTOR_HALTED);
    fetch_summary replayed = summarize(er_actor_result(a));
    assert_summary_eq(&replayed, &recorded);
    ASSERT_EQ(er_scheduler_log_cursor(sys), 1);
    ASSERT_EQ(er_http_inflight_count(sys), 0); /* zero network */
    er_scheduler_free(sys);
  }
  er_log_free(loaded);
  test_rt_free(&rt);
}

/* Three concurrent fetches (the first is slow, so completion order
 * differs from service order) recorded, then replayed with the server
 * down: identical per-actor results, resumption order from log order. */
TEST(http, record_replay_concurrent_fetches) {
  test_http_server srv;
  ASSERT(test_http_server_start(&srv));
  char slow_url[256], ok_url[256], final_url[256];
  url_of(&srv, "/drip3", slow_url, sizeof(slow_url));
  url_of(&srv, "/ok", ok_url, sizeof(ok_url));
  url_of(&srv, "/final", final_url, sizeof(final_url));

  test_rt rt = test_rt_new();
  er_log* log = er_log_new();
  fetch_summary rec[3];
  {
    er_scheduler* sys = er_scheduler_new(rt.store, (er_config){0});
    er_scheduler_record(sys, log);
    er_actor* a0 = start_fetch_actor(sys, mk_get, slow_url, 30000, 0, 1 << 20);
    er_actor* a1 = start_fetch_actor(sys, mk_get, ok_url, 30000, 0, 1 << 20);
    er_actor* a2 = start_fetch_actor(sys, mk_get, final_url, 30000, 0, 1 << 20);
    ASSERT_EQ(er_scheduler_run(sys), ER_RUN_IDLE);
    er_actor* as[3] = {a0, a1, a2};
    for (int i = 0; i < 3; i++) {
      ASSERT_EQ(er_actor_state(as[i]), ER_ACTOR_HALTED);
      rec[i] = summarize(er_actor_result(as[i]));
      ASSERT(rec[i].ok);
    }
    ASSERT_STR_EQ(rec[0].body, "ddd");
    ASSERT_STR_EQ(rec[1].body, "hello, enki");
    ASSERT_STR_EQ(rec[2].body, "landed");
    er_scheduler_free(sys);
  }
  ASSERT_EQ(er_log_events(log), 3);
  test_http_server_stop(&srv); /* replay must not need the network */

  {
    er_scheduler* sys = er_scheduler_new(rt.store, (er_config){0});
    er_scheduler_replay(sys, log);
    er_actor* a0 = start_fetch_actor(sys, mk_get, slow_url, 30000, 0, 1 << 20);
    er_actor* a1 = start_fetch_actor(sys, mk_get, ok_url, 30000, 0, 1 << 20);
    er_actor* a2 = start_fetch_actor(sys, mk_get, final_url, 30000, 0, 1 << 20);
    ASSERT_EQ(er_scheduler_run(sys), ER_RUN_IDLE);
    er_actor* as[3] = {a0, a1, a2};
    for (int i = 0; i < 3; i++) {
      ASSERT_EQ(er_actor_state(as[i]), ER_ACTOR_HALTED);
      fetch_summary s = summarize(er_actor_result(as[i]));
      assert_summary_eq(&s, &rec[i]);
    }
    ASSERT_EQ(er_scheduler_log_cursor(sys), 3);
    ASSERT_EQ(er_http_inflight_count(sys), 0);
    er_scheduler_free(sys);
  }
  er_log_free(log);
  test_rt_free(&rt);
}

/* Validation failures are oracles too: logged at the service point and
 * replayed from the log without re-running validation. */
TEST(http, record_replay_bad_url) {
  test_rt rt = test_rt_new();
  er_log* log = er_log_new();
  {
    er_scheduler* sys = er_scheduler_new(rt.store, (er_config){0});
    er_scheduler_record(sys, log);
    er_actor* a =
        start_fetch_actor(sys, mk_get, "ftp://127.0.0.1/x", 5000, 0, 1 << 20);
    ASSERT_EQ(er_scheduler_run(sys), ER_RUN_IDLE);
    ASSERT_EQ(er_actor_state(a), ER_ACTOR_HALTED);
    ASSERT_EQ(result_err(er_actor_result(a)), HTTP_BAD_URL);
    er_scheduler_free(sys);
  }
  ASSERT_EQ(er_log_events(log), 1);
  {
    er_scheduler* sys = er_scheduler_new(rt.store, (er_config){0});
    er_scheduler_replay(sys, log);
    er_actor* a =
        start_fetch_actor(sys, mk_get, "ftp://127.0.0.1/x", 5000, 0, 1 << 20);
    ASSERT_EQ(er_scheduler_run(sys), ER_RUN_IDLE);
    ASSERT_EQ(er_actor_state(a), ER_ACTOR_HALTED);
    ASSERT_EQ(result_err(er_actor_result(a)), HTTP_BAD_URL);
    ASSERT_EQ(er_scheduler_log_cursor(sys), 1);
    er_scheduler_free(sys);
  }
  er_log_free(log);
  test_rt_free(&rt);
}

/* A validation failure and a live fetch in one recording: the FetchV
 * event consumes at its service point, the completion at an idle
 * point, and replay interleaves both identically. */
TEST(http, record_replay_mixed_valid_and_invalid) {
  test_http_server srv;
  ASSERT(test_http_server_start(&srv));
  char url[256];
  url_of(&srv, "/ok", url, sizeof(url));

  test_rt rt = test_rt_new();
  er_log* log = er_log_new();
  fetch_summary rec_ok;
  {
    er_scheduler* sys = er_scheduler_new(rt.store, (er_config){0});
    er_scheduler_record(sys, log);
    er_actor* good = start_fetch_actor(sys, mk_get, url, 5000, 0, 1 << 20);
    er_actor* bad =
        start_fetch_actor(sys, mk_get, "/relative", 5000, 0, 1 << 20);
    ASSERT_EQ(er_scheduler_run(sys), ER_RUN_IDLE);
    ASSERT_EQ(er_actor_state(good), ER_ACTOR_HALTED);
    ASSERT_EQ(er_actor_state(bad), ER_ACTOR_HALTED);
    rec_ok = summarize(er_actor_result(good));
    ASSERT(rec_ok.ok);
    ASSERT_EQ(result_err(er_actor_result(bad)), HTTP_BAD_URL);
    er_scheduler_free(sys);
  }
  ASSERT_EQ(er_log_events(log), 2);
  test_http_server_stop(&srv);

  {
    er_scheduler* sys = er_scheduler_new(rt.store, (er_config){0});
    er_scheduler_replay(sys, log);
    er_actor* good = start_fetch_actor(sys, mk_get, url, 5000, 0, 1 << 20);
    er_actor* bad =
        start_fetch_actor(sys, mk_get, "/relative", 5000, 0, 1 << 20);
    ASSERT_EQ(er_scheduler_run(sys), ER_RUN_IDLE);
    fetch_summary s = summarize(er_actor_result(good));
    assert_summary_eq(&s, &rec_ok);
    ASSERT_EQ(result_err(er_actor_result(bad)), HTTP_BAD_URL);
    ASSERT_EQ(er_scheduler_log_cursor(sys), 2);
    er_scheduler_free(sys);
  }
  er_log_free(log);
  test_rt_free(&rt);
}

/* MT executor (LIVE only): several actors fetch concurrently; one
 * worker at a time owns the CURLM pump while the rest run actors. */
TEST(http, mt_executor_concurrent_fetches) {
  test_http_server srv;
  ASSERT(test_http_server_start(&srv));
  test_rt rt = test_rt_new();
  er_scheduler* sys = er_scheduler_new(rt.store, (er_config){0});
  er_mt_executor* ex = er_mt_executor_new(sys, (er_mt_config){.workers = 4});

  char ok_url[256], drip_url[256], final_url[256];
  url_of(&srv, "/ok", ok_url, sizeof(ok_url));
  url_of(&srv, "/drip3", drip_url, sizeof(drip_url));
  url_of(&srv, "/final", final_url, sizeof(final_url));
  er_actor* as[6];
  const char* urls[6] = {drip_url, ok_url, final_url,
                         ok_url,   ok_url, final_url};
  for (int i = 0; i < 6; i++)
    as[i] = start_fetch_actor(sys, mk_get, urls[i], 30000, 0, 1 << 20);

  ASSERT_EQ(er_mt_executor_run(ex), ER_RUN_IDLE);
  const char* bodies[6] = {"ddd",         "hello, enki", "landed",
                           "hello, enki", "hello, enki", "landed"};
  for (int i = 0; i < 6; i++) {
    ASSERT_EQ(er_actor_state(as[i]), ER_ACTOR_HALTED);
    fetch_summary s = summarize(er_actor_result(as[i]));
    ASSERT(s.ok);
    ASSERT_EQ(s.status, 200);
    ASSERT_STR_EQ(s.body, bodies[i]);
  }
  ASSERT_EQ(er_http_inflight_count(sys), 0);

  er_mt_executor_free(ex);
  er_scheduler_free(sys);
  test_rt_free(&rt);
  test_http_server_stop(&srv);
}

TEST(http, adopted_root_can_fetch) {
  test_http_server srv;
  ASSERT(test_http_server_start(&srv));
  test_rt rt = test_rt_new();
  rt.t->rplan_f = true;
  er_scheduler* sys = er_scheduler_new(rt.store, (er_config){0});
  er_actor* root = er_scheduler_adopt(sys, rt.t);

  char url[256];
  url_of(&srv, "/ok", url, sizeof(url));
  pl_thread* t = rt.t;
  size_t base = t->vsp;
  pl_vpush(t, mk_request(t, "GET", url, 0, NULL, NULL));
  pl_vpush(t, mk_config(t, 5000, 0, 1 << 20));
  pl_val body = code_fetch(t, t->vstack[base], t->vstack[base + 1]);
  t->vsp = base;
  /* arm (law 0) — run the fetch as the root's own computation */
  size_t lb = t->vsp;
  pl_vpush(t, actor_fn(t, body));
  pl_val law = t->vstack[lb];
  t->vsp = lb;
  pl_thread_start_call_nf(t, law, 0);

  ASSERT_EQ(er_scheduler_drive(sys, root), ER_DRIVE_DONE);
  pl_cell* resp = result_ok(pl_thread_result(t));
  ASSERT_EQ(pl_app_args(resp)[0], 200);
  assert_bar_eq(pl_app_args(resp)[3], "hello, enki");

  er_scheduler_free(sys);
  test_rt_free(&rt);
  test_http_server_stop(&srv);
}

TEST(http, mt_adopted_root_can_fetch) {
  test_http_server srv;
  ASSERT(test_http_server_start(&srv));
  test_rt rt = test_rt_new();
  rt.t->rplan_f = true;
  er_scheduler* sys = er_scheduler_new(rt.store, (er_config){0});
  er_mt_executor* ex = er_mt_executor_new(sys, (er_mt_config){.workers = 2});
  er_actor* root = er_scheduler_adopt(sys, rt.t);

  char url[256];
  url_of(&srv, "/ok", url, sizeof(url));
  pl_thread* t = rt.t;
  size_t base = t->vsp;
  pl_vpush(t, mk_request(t, "GET", url, 0, NULL, NULL));
  pl_vpush(t, mk_config(t, 5000, 0, 1 << 20));
  pl_val body = code_fetch(t, t->vstack[base], t->vstack[base + 1]);
  t->vsp = base;
  size_t lb = t->vsp;
  pl_vpush(t, actor_fn(t, body));
  pl_val law = t->vstack[lb];
  t->vsp = lb;
  pl_thread_start_call_nf(t, law, 0);

  ASSERT_EQ(er_mt_executor_drive(ex, root), ER_DRIVE_DONE);
  pl_cell* resp = result_ok(pl_thread_result(t));
  ASSERT_EQ(pl_app_args(resp)[0], 200);
  assert_bar_eq(pl_app_args(resp)[3], "hello, enki");

  er_mt_executor_free(ex);
  er_scheduler_free(sys);
  test_rt_free(&rt);
  test_http_server_stop(&srv);
}
