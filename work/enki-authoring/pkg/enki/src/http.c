/*
 * The HTTP driver: op 83 Fetch, backed by libcurl.
 *
 * A Fetch is a coordination effect with req/res semantics: the calling
 * actor parks (er_actor.http != NULL distinguishes it from a Recv
 * park), the transfer runs on the scheduler's CURLM multi handle while
 * other actors execute, and completion deposits a Result value built in
 * the caller's heap.  There is no request id and no cancel: the parked
 * suspension is the identity of the request, and scheduler teardown
 * aborts whatever is still in flight.
 *
 * Result   = (0 response) | (1 errCode)
 * Response = [status urlBar headersRow bodyBar]   (final response only)
 * Request  = [methodBar urlBar headersRow bodyMaybe]
 * Config   = [connectMsMaybe deadlineMs redirects bodyMode]
 *   where Maybe x = 0 | [x], headersRow = 0 | [[nameBar valBar]…],
 *   bodyMode = [maxBytes] (Buffered) | 1 (Spooled — reserved, rejected)
 *
 * Record/replay.  The completion order of concurrent transfers is the
 * only nondeterminism; the log captures it and replay reproduces it
 * without linking a single curl call:
 *   - RECORD deposits completions only at empty-run-queue points,
 *     exactly one per point ("FetchV" validation failures deposit at
 *     their service point instead), appending the ER_EV_HTTP event
 *     immediately before the deposit.
 *   - REPLAY never creates a CURLM or easy handle.  A Fetch service
 *     consumes a "FetchV" event if one is next in the log (validation
 *     failed on the recording — validation is NOT re-run), else parks a
 *     stub; each empty-queue point consumes exactly one "Fetch" event,
 *     verifies (actor, args-hash), and deposits the logged result.
 *   Record and replay build the deposited value through the same
 *   decoder (er_http_result_build), so the values match by construction.
 *
 * Compression caveat: transfers are made with ACCEPT_ENCODING "" (all
 * curl built-ins), so the delivered body is decoded while Content-Length
 * and Content-Encoding response headers still describe the wire form.
 */

#include <curl/curl.h>
#include <limits.h>
#include <pthread.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "actor_internal.h"
#include "axsys/assume.h"
#include "axsys/ds.h"
#include "axsys/sha256.h"
#include "plan/build.h"
#include "plan/nat.h"

#if LIBCURL_VERSION_NUM < 0x074400 /* 7.68.0 */
#error "the enki HTTP driver requires libcurl >= 7.68 (curl_multi_poll/wakeup)"
#endif

#define ER_HTTP_CONNECT_DEFAULT_MS 10000

#define ER_CURL_EASY(expr)                                                     \
  do {                                                                         \
    CURLcode rc_ = (expr);                                                     \
    ax_assume(rc_ == CURLE_OK, "curl_easy_setopt");                            \
  } while (0)

/* Err codes (the userland taxonomy; stable ABI). */
enum {
  ER_HTTP_BAD_URL = 0,
  ER_HTTP_DNS = 1,
  ER_HTTP_CONNECT = 2,
  ER_HTTP_TLS = 3,
  ER_HTTP_DEADLINE = 4,
  ER_HTTP_REDIRECTS = 5,
  ER_HTTP_TOO_LARGE = 6,
  ER_HTTP_PROTOCOL = 7,
};

typedef struct er_http_hdr {
  uint8_t* name;
  size_t name_n;
  uint8_t* value;
  size_t value_n;
} er_http_hdr;

struct er_http_xfer {
  er_actor* actor;
  CURL* easy; /* NULL: replay stub (args_hash only) */
  struct curl_slist* req_headers;
  char* method_c; /* stable C copies; curl never sees the moving heap */
  char* url_c;
  uint8_t* body; /* CURLOPT_POSTFIELDS storage */
  size_t body_n;
  uint64_t max_body;
  bool body_overflow; /* Buffered cap tripped in the write callback */
  CURLcode result;
  long resp_status;
  char* effective_url;       /* strdup'd at DONE, before cleanup */
  bool connected;            /* CONNECT_TIME_T > 0 at DONE */
  uint8_t* resp_body;        /* stb_ds byte array */
  er_http_hdr* resp_headers; /* stb_ds; reset at each new status line */
  uint8_t args_hash[32];
  struct er_http_xfer* next_inflight;
  struct er_http_xfer* next_done;
};

/* ── curl bootstrap ────────────────────────────────────────────────────── */

static pthread_once_t er_http_once = PTHREAD_ONCE_INIT;

static void er_http_global_init(void) {
  ax_assume(curl_global_init(CURL_GLOBAL_DEFAULT) == 0, "curl_global_init");
}

static CURLM* er_curlm(er_scheduler* sys) {
  ax_assume(sys->mode != ER_MODE_REPLAY,
            "er_http: no curl handles may exist in replay mode");
  if (sys->curlm == NULL) {
    pthread_once(&er_http_once, er_http_global_init);
    CURLM* m = curl_multi_init();
    ax_assume(m != NULL, "curl_multi_init");
    if (sys->cfg.http_max_total_connections > 0) {
      CURLMcode rc = curl_multi_setopt(m, CURLMOPT_MAX_TOTAL_CONNECTIONS,
                                       sys->cfg.http_max_total_connections);
      ax_assume(rc == CURLM_OK, "curl_multi_setopt");
    }
    sys->curlm = m;
  }
  return sys->curlm;
}

/* ── Request parsing (deep-normalized PLAN rows → C) ───────────────────── */

typedef struct er_http_parsed {
  uint8_t* method;
  size_t method_n;
  uint8_t* url;
  size_t url_n;
  er_http_hdr* hdrs; /* stb_ds */
  bool has_body;
  uint8_t* body;
  size_t body_n;
  bool has_connect_ms;
  uint64_t connect_ms;
  uint64_t deadline_ms;
  uint64_t redirects;
  int body_mode; /* 0 = Buffered, 1 = Spooled (reserved) */
  uint64_t max_body;
} er_http_parsed;

static void er_http_parsed_free(er_http_parsed* p) {
  free(p->method);
  free(p->url);
  for (ptrdiff_t i = 0; i < ax_arrlen(p->hdrs); i++) {
    free(p->hdrs[i].name);
    free(p->hdrs[i].value);
  }
  ax_arrfree(p->hdrs);
  free(p->body);
  memset(p, 0, sizeof(*p));
}

/* A bar is a byte string as a nat: data bytes then a 0x01 terminator
 * (rp_bar).  Strict here: the terminator must be present. */
static bool er_bar(pl_val v, uint8_t** out, size_t* out_n) {
  if (!pl_is_nat(v))
    return false;
  size_t n = pl_nat_byte_len(v);
  if (n < 1 || pl_nat_byte_at(v, n - 1) != 0x01)
    return false;
  uint8_t* b = malloc(n > 1 ? n - 1 : 1);
  ax_assume(b != NULL, "oom");
  for (size_t i = 0; i + 1 < n; i++)
    b[i] = pl_nat_byte_at(v, i);
  *out = b;
  *out_n = n - 1;
  return true;
}

/* A row is an APP with head nat 0; fields arrive deep-normalized. */
static pl_cell* er_row(pl_val v) {
  pl_cell* p = pl_as(PL_TAG_APP, v);
  if (p == NULL || pl_app_head(p) != 0)
    return NULL;
  return p;
}

static bool er_http_parse(pl_val reqv, pl_val cfgv, er_http_parsed* p) {
  memset(p, 0, sizeof(*p));

  pl_cell* req = er_row(reqv);
  if (req == NULL || pl_app_n(req) != 4)
    return false;
  pl_val* rf = pl_app_args(req);
  if (!er_bar(rf[0], &p->method, &p->method_n))
    return false;
  if (!er_bar(rf[1], &p->url, &p->url_n))
    return false;

  if (rf[2] != 0) { /* headers: 0 = none */
    pl_cell* hs = er_row(rf[2]);
    if (hs == NULL)
      return false;
    uint32_t nh = pl_app_n(hs);
    for (uint32_t i = 0; i < nh; i++) {
      pl_cell* h = er_row(pl_app_args(hs)[i]);
      if (h == NULL || pl_app_n(h) != 2)
        return false;
      er_http_hdr hdr = {0};
      if (!er_bar(pl_app_args(h)[0], &hdr.name, &hdr.name_n))
        return false;
      if (!er_bar(pl_app_args(h)[1], &hdr.value, &hdr.value_n)) {
        free(hdr.name);
        return false;
      }
      ax_arrpush(p->hdrs, hdr);
    }
  }

  if (rf[3] != 0) { /* body: Maybe */
    pl_cell* some = er_row(rf[3]);
    if (some == NULL || pl_app_n(some) != 1)
      return false;
    if (!er_bar(pl_app_args(some)[0], &p->body, &p->body_n))
      return false;
    p->has_body = true;
  }

  pl_cell* cfg = er_row(cfgv);
  if (cfg == NULL || pl_app_n(cfg) != 4)
    return false;
  pl_val* cf = pl_app_args(cfg);

  if (cf[0] != 0) { /* connectMs: Maybe Nat */
    pl_cell* some = er_row(cf[0]);
    if (some == NULL || pl_app_n(some) != 1 || !pl_is_nat(pl_app_args(some)[0]))
      return false;
    p->has_connect_ms = true;
    p->connect_ms = pl_nat_u64_clamp(pl_app_args(some)[0]);
  }
  if (!pl_is_nat(cf[1]) || !pl_is_nat(cf[2]))
    return false;
  p->deadline_ms = pl_nat_u64_clamp(cf[1]);
  p->redirects = pl_nat_u64_clamp(cf[2]);

  if (cf[3] == 1) { /* Spooled: reserved */
    p->body_mode = 1;
  } else {
    pl_cell* buffered = er_row(cf[3]);
    if (buffered == NULL || pl_app_n(buffered) != 1 ||
        !pl_is_nat(pl_app_args(buffered)[0]))
      return false;
    p->body_mode = 0;
    p->max_body = pl_nat_u64_clamp(pl_app_args(buffered)[0]);
  }
  return true;
}

/* ── Site identity: SHA-256 over the parsed request+config ─────────────── */

static void er_hash_u64(uint8_t** buf, uint64_t v) {
  uint8_t* dst = ax_arraddn(*buf, 8);
  for (int i = 0; i < 8; i++)
    dst[i] = (uint8_t)(v >> (8 * i));
}

static void er_hash_bytes(uint8_t** buf, const uint8_t* b, size_t n) {
  er_hash_u64(buf, (uint64_t)n);
  if (n > 0)
    memcpy(ax_arraddn(*buf, (ptrdiff_t)n), b, n);
}

static void er_http_args_hash(const er_http_parsed* p, uint8_t out[32]) {
  uint8_t* buf = NULL;
  er_hash_bytes(&buf, p->method, p->method_n);
  er_hash_bytes(&buf, p->url, p->url_n);
  er_hash_u64(&buf, (uint64_t)ax_arrlen(p->hdrs));
  for (ptrdiff_t i = 0; i < ax_arrlen(p->hdrs); i++) {
    er_hash_bytes(&buf, p->hdrs[i].name, p->hdrs[i].name_n);
    er_hash_bytes(&buf, p->hdrs[i].value, p->hdrs[i].value_n);
  }
  er_hash_u64(&buf, p->has_body ? 1 : 0);
  if (p->has_body)
    er_hash_bytes(&buf, p->body, p->body_n);
  er_hash_u64(&buf, p->has_connect_ms ? 1 : 0);
  er_hash_u64(&buf, p->connect_ms);
  er_hash_u64(&buf, p->deadline_ms);
  er_hash_u64(&buf, p->redirects);
  er_hash_u64(&buf, (uint64_t)p->body_mode);
  er_hash_u64(&buf, p->max_body);
  ax_sha256(buf, (size_t)ax_arrlen(buf), out);
  ax_arrfree(buf);
}

/* ── Validation (live/record only; replay reads the log instead) ───────── */

/* -1 = valid; else the Err code to deliver without any transfer. */
static bool er_http_is_token(const uint8_t* b, size_t n) {
  if (n == 0)
    return false;
  for (size_t i = 0; i < n; i++) {
    uint8_t c = b[i];
    if ((c >= '0' && c <= '9') || (c >= 'A' && c <= 'Z') ||
        (c >= 'a' && c <= 'z'))
      continue;
    switch (c) {
    case '!':
    case '#':
    case '$':
    case '%':
    case '&':
    case '\'':
    case '*':
    case '+':
    case '-':
    case '.':
    case '^':
    case '_':
    case '`':
    case '|':
    case '~':
      continue;
    default:
      return false;
    }
  }
  return true;
}

/* curl_slist_append takes C strings and sends them verbatim: reject the
 * bytes that could truncate or split a caller-supplied header line. */
static bool er_http_header_value_ok(const uint8_t* b, size_t n) {
  return memchr(b, '\0', n) == NULL && memchr(b, '\r', n) == NULL &&
         memchr(b, '\n', n) == NULL;
}

static int er_http_validate(const er_scheduler* sys, const er_http_parsed* p) {
  if (p->deadline_ms == 0)
    return ER_HTTP_BAD_URL; /* unbounded suspension: rejected */
  if (p->body_mode == 1)
    return ER_HTTP_BAD_URL; /* Spooled is reserved in v1 */
  if (memchr(p->url, '\0', p->url_n) != NULL ||
      !er_http_is_token(p->method, p->method_n))
    return ER_HTTP_BAD_URL; /* embedded NUL would truncate at curl */
  for (ptrdiff_t i = 0; i < ax_arrlen(p->hdrs); i++)
    if (!er_http_is_token(p->hdrs[i].name, p->hdrs[i].name_n) ||
        !er_http_header_value_ok(p->hdrs[i].value, p->hdrs[i].value_n))
      return ER_HTTP_BAD_URL;

  uint64_t connect_ms = p->has_connect_ms ? p->connect_ms
                        : sys->cfg.http_connect_default_ms > 0
                            ? sys->cfg.http_connect_default_ms
                            : ER_HTTP_CONNECT_DEFAULT_MS;
  if (connect_ms > LONG_MAX || p->deadline_ms > LONG_MAX ||
      p->redirects > LONG_MAX)
    return ER_HTTP_BAD_URL;

  /* curl_url is a libcurl API too; initialize before calling it. */
  pthread_once(&er_http_once, er_http_global_init);

  char* url_c = malloc(p->url_n + 1);
  ax_assume(url_c != NULL, "oom");
  memcpy(url_c, p->url, p->url_n);
  url_c[p->url_n] = '\0';

  int err = -1;
  CURLU* u = curl_url();
  ax_assume(u != NULL, "curl_url");
  /* no CURLU_DEFAULT_SCHEME / CURLU_GUESS_SCHEME: relative URLs fail */
  if (curl_url_set(u, CURLUPART_URL, url_c, 0) != CURLUE_OK) {
    err = ER_HTTP_BAD_URL;
  } else {
    char* scheme = NULL;
    if (curl_url_get(u, CURLUPART_SCHEME, &scheme, 0) != CURLUE_OK ||
        (strcmp(scheme, "http") != 0 && strcmp(scheme, "https") != 0))
      err = ER_HTTP_BAD_URL;
    curl_free(scheme);
  }
  curl_url_cleanup(u);
  free(url_c);
  return err;
}

/* ── curl callbacks ────────────────────────────────────────────────────── */

static size_t er_http_write_cb(char* ptr, size_t size, size_t nmemb, void* ud) {
  er_http_xfer* x = ud;
  size_t n = size * nmemb;
  if ((uint64_t)ax_arrlen(x->resp_body) + n > x->max_body) {
    x->body_overflow = true;
    return 0; /* short count aborts the transfer (CURLE_WRITE_ERROR) */
  }
  if (n > 0)
    memcpy(ax_arraddn(x->resp_body, (ptrdiff_t)n), ptr, n);
  return n;
}

static void er_http_headers_reset(er_http_xfer* x) {
  for (ptrdiff_t i = 0; i < ax_arrlen(x->resp_headers); i++) {
    free(x->resp_headers[i].name);
    free(x->resp_headers[i].value);
  }
  ax_arrfree(x->resp_headers);
  x->resp_headers = NULL;
}

static void er_http_body_reset(er_http_xfer* x) {
  ax_arrfree(x->resp_body);
  x->resp_body = NULL;
}

static uint8_t* er_memdup(const char* b, size_t n) {
  uint8_t* d = malloc(n > 0 ? n : 1);
  ax_assume(d != NULL, "oom");
  memcpy(d, b, n);
  return d;
}

/* Fires once per header line of EVERY response on a redirect chain; a
 * line starting "HTTP/" is a new status line and resets the accumulators
 * so the final Response carries only the final response's headers/body. */
static size_t er_http_header_cb(char* buf, size_t size, size_t nitems,
                                void* ud) {
  er_http_xfer* x = ud;
  size_t n = size * nitems;
  size_t len = n;
  while (len > 0 && (buf[len - 1] == '\r' || buf[len - 1] == '\n'))
    len--;
  if (len >= 5 && memcmp(buf, "HTTP/", 5) == 0) {
    er_http_headers_reset(x);
    er_http_body_reset(x);
    return n;
  }
  if (len == 0)
    return n; /* the blank end-of-headers line */
  if (buf[0] == ' ' || buf[0] == '\t') {
    /* obs-fold: continuation of the previous value */
    ptrdiff_t last = ax_arrlen(x->resp_headers) - 1;
    if (last < 0)
      return n; /* fold with no previous header: drop */
    size_t s = 0;
    while (s < len && (buf[s] == ' ' || buf[s] == '\t'))
      s++;
    er_http_hdr* h = &x->resp_headers[last];
    uint8_t* merged = malloc(h->value_n + 1 + (len - s) + 1);
    ax_assume(merged != NULL, "oom");
    memcpy(merged, h->value, h->value_n);
    merged[h->value_n] = ' ';
    memcpy(merged + h->value_n + 1, buf + s, len - s);
    free(h->value);
    h->value = merged;
    h->value_n = h->value_n + 1 + (len - s);
    return n;
  }
  char* colon = memchr(buf, ':', len);
  if (colon == NULL)
    return n; /* not a header line; ignore */
  size_t name_n = (size_t)(colon - buf);
  size_t vs = name_n + 1;
  while (vs < len && (buf[vs] == ' ' || buf[vs] == '\t'))
    vs++;
  er_http_hdr h = {.name = er_memdup(buf, name_n),
                   .name_n = name_n,
                   .value = er_memdup(buf + vs, len - vs),
                   .value_n = len - vs};
  ax_arrpush(x->resp_headers, h);
  return n;
}

/* ── Error mapping (exhaustive over what HTTP(S) transfers return) ─────── */

static uint8_t er_http_map_err(const er_http_xfer* x) {
  if (x->body_overflow)
    return ER_HTTP_TOO_LARGE; /* the short write count aborted it */
  switch (x->result) {
  case CURLE_COULDNT_RESOLVE_HOST:
  case CURLE_COULDNT_RESOLVE_PROXY:
    return ER_HTTP_DNS;
  case CURLE_COULDNT_CONNECT:
    return ER_HTTP_CONNECT;
  case CURLE_OPERATION_TIMEDOUT:
    return x->connected ? ER_HTTP_DEADLINE : ER_HTTP_CONNECT;
  case CURLE_TOO_MANY_REDIRECTS:
    return ER_HTTP_REDIRECTS;
  case CURLE_PEER_FAILED_VERIFICATION:
  case CURLE_SSL_CONNECT_ERROR:
  case CURLE_SSL_CERTPROBLEM:
  case CURLE_SSL_CIPHER:
  case CURLE_SSL_CACERT_BADFILE:
  case CURLE_SSL_ISSUER_ERROR:
  case CURLE_SSL_INVALIDCERTSTATUS:
  case CURLE_SSL_PINNEDPUBKEYNOTMATCH:
  case CURLE_SSL_ENGINE_NOTFOUND:
  case CURLE_SSL_ENGINE_SETFAILED:
  case CURLE_SSL_ENGINE_INITFAILED:
  case CURLE_SSL_SHUTDOWN_FAILED:
  case CURLE_SSL_CLIENTCERT:
  case CURLE_USE_SSL_FAILED:
    return ER_HTTP_TLS;
  default:
    return ER_HTTP_PROTOCOL;
  }
}

/* ── Result encoding (the log format; also the build input) ────────────── */

static void er_enc_u64(uint8_t** buf, uint64_t v) {
  er_hash_u64(buf, v);
}

static void er_enc_bytes(uint8_t** buf, const uint8_t* b, size_t n) {
  er_hash_bytes(&*buf, b, n);
}

/* err: [0x01 code]
 * ok:  [0x00][status][urlLen url][nHeaders (nameLen name valLen val)…]
 *      [bodyLen body]                                (u64s LE) */
static uint8_t* er_http_result_encode(const er_http_xfer* x, uint64_t* out_n) {
  uint8_t* buf = NULL;
  if (x->result != CURLE_OK) {
    ax_arrpush(buf, 1);
    ax_arrpush(buf, er_http_map_err(x));
  } else {
    ax_arrpush(buf, 0);
    er_enc_u64(&buf, (uint64_t)x->resp_status);
    const char* eu = x->effective_url != NULL ? x->effective_url : "";
    er_enc_bytes(&buf, (const uint8_t*)eu, strlen(eu));
    er_enc_u64(&buf, (uint64_t)ax_arrlen(x->resp_headers));
    for (ptrdiff_t i = 0; i < ax_arrlen(x->resp_headers); i++) {
      er_enc_bytes(&buf, x->resp_headers[i].name, x->resp_headers[i].name_n);
      er_enc_bytes(&buf, x->resp_headers[i].value, x->resp_headers[i].value_n);
    }
    er_enc_bytes(&buf, x->resp_body, (size_t)ax_arrlen(x->resp_body));
  }
  *out_n = (uint64_t)ax_arrlen(buf);
  uint8_t* out = malloc((size_t)*out_n);
  ax_assume(out != NULL, "oom");
  memcpy(out, buf, (size_t)*out_n);
  ax_arrfree(buf);
  return out;
}

/* ── Result value construction (in the caller's heap) ──────────────────── */

/* Build a row from the top n vstack slots (popped), push the result. */
static void er_push_app(pl_thread* t, pl_val head, uint32_t n) {
  pl_gc_reserve(t, PL_APP_CELLS(n));
  PL_GC_FORBID(t);
  pl_val r = pl_mk_app_from(t, head, n, &t->vstack[t->vsp - n]);
  PL_GC_ALLOW(t);
  t->vsp -= n;
  pl_vpush(t, r);
}

static void er_push_bar(pl_thread* t, const uint8_t* b, uint64_t n) {
  uint8_t* buf = malloc((size_t)n + 1);
  ax_assume(buf != NULL, "oom");
  if (n > 0)
    memcpy(buf, b, (size_t)n);
  buf[n] = 0x01;
  pl_val v = pl_nat_from_bytes(t, buf, (size_t)n + 1);
  free(buf);
  pl_vpush(t, v);
}

typedef struct er_dec {
  const uint8_t* d;
  uint64_t n;
  uint64_t at;
} er_dec;

static uint64_t er_dec_u64(er_dec* c) {
  ax_assume(c->at + 8 <= c->n, "er_http: truncated result encoding");
  uint64_t v = 0;
  for (int i = 0; i < 8; i++)
    v |= (uint64_t)c->d[c->at + (uint64_t)i] << (8 * i);
  c->at += 8;
  return v;
}

static const uint8_t* er_dec_bytes(er_dec* c, uint64_t* out_n) {
  *out_n = er_dec_u64(c);
  ax_assume(c->at + *out_n <= c->n, "er_http: truncated result encoding");
  const uint8_t* b = c->d + c->at;
  c->at += *out_n;
  return b;
}

/* Decode the flat encoding into the Result value.  Record, replay and
 * live all pass through here, so the deposited value is identical by
 * construction. */
static pl_val er_http_result_build(pl_thread* t, const uint8_t* d, uint64_t n) {
  ax_assume(n >= 1, "er_http: empty result encoding");
  size_t base = t->vsp;
  if (d[0] == 1) {
    ax_assume(n == 2, "er_http: malformed err encoding");
    pl_vpush(t, d[1]);
    er_push_app(t, 1, 1); /* (1 errCode) */
  } else {
    er_dec c = {.d = d, .n = n, .at = 1};
    uint64_t status = er_dec_u64(&c);
    uint64_t url_n;
    const uint8_t* url = er_dec_bytes(&c, &url_n);
    pl_vpush(t, 0); /* status slot; nat63 (status fits trivially) */
    t->vstack[base] = status;
    er_push_bar(t, url, url_n);
    uint64_t nh = er_dec_u64(&c);
    for (uint64_t i = 0; i < nh; i++) {
      uint64_t name_n, val_n;
      const uint8_t* name = er_dec_bytes(&c, &name_n);
      const uint8_t* val = er_dec_bytes(&c, &val_n);
      er_push_bar(t, name, name_n);
      er_push_bar(t, val, val_n);
      er_push_app(t, 0, 2); /* [name value] */
    }
    if (nh > 0)
      er_push_app(t, 0, (uint32_t)nh);
    else
      pl_vpush(t, 0); /* the empty row is nat 0 */
    uint64_t body_n;
    const uint8_t* body = er_dec_bytes(&c, &body_n);
    ax_assume(c.at == c.n, "er_http: trailing bytes in result encoding");
    er_push_bar(t, body, body_n);
    er_push_app(t, 0, 4); /* [status url headers body] */
    er_push_app(t, 0, 1); /* (0 response) */
  }
  pl_val res = t->vstack[t->vsp - 1];
  t->vsp = base;
  return res;
}

/* ── Bookkeeping ───────────────────────────────────────────────────────── */

static void er_http_xfer_free(er_scheduler* sys, er_http_xfer* x) {
  if (x->easy != NULL) {
    /* teardown order: remove from the multi first, then cleanup */
    curl_multi_remove_handle(sys->curlm, x->easy);
    curl_easy_cleanup(x->easy);
  }
  curl_slist_free_all(x->req_headers);
  free(x->method_c);
  free(x->url_c);
  free(x->body);
  free(x->effective_url);
  ax_arrfree(x->resp_body);
  er_http_headers_reset(x);
  free(x);
}

static void er_http_unlink_inflight(er_scheduler* sys, er_http_xfer* x) {
  er_http_xfer** at = &sys->http_inflight;
  while (*at != NULL && *at != x)
    at = &(*at)->next_inflight;
  ax_assume(*at == x, "er_http: transfer not in flight");
  *at = x->next_inflight;
  x->next_inflight = NULL;
  sys->http_inflight_n--;
}

static void er_http_park(er_scheduler* sys, er_actor* a, er_http_xfer* x) {
  a->http = x;
  a->status = ER_ACTOR_BLOCKED;
  x->next_inflight = sys->http_inflight;
  sys->http_inflight = x;
  sys->http_inflight_n++;
  sys->http_parked_n++;
}

/* Deposit `data` into the parked actor and make it runnable. */
static void er_http_resume(er_scheduler* sys, er_actor* a, const uint8_t* data,
                           uint64_t n) {
  pl_val res = er_http_result_build(a->t, data, n);
  pl_thread_deposit(a->t, res);
  if (a->http != NULL) {
    a->http = NULL;
    sys->http_parked_n--;
  }
  a->status = ER_ACTOR_RUNNABLE;
  er_enqueue(a);
}

static void er_http_record_event(er_scheduler* sys, uint64_t actor,
                                 const char* op, const uint8_t hash[32],
                                 const uint8_t* data, uint64_t n) {
  er_event e = {.kind = ER_EV_HTTP, .actor = actor, .op = er_mote(op)};
  memcpy(e.args_hash, hash, 32);
  e.data = malloc(n > 0 ? (size_t)n : 1);
  ax_assume(e.data != NULL, "oom");
  memcpy(e.data, data, (size_t)n);
  e.data_n = n;
  ax_arrpush(sys->rec->ev, e);
}

/* ── Dispatch (live/record) ────────────────────────────────────────────── */

static char* er_cstr(const uint8_t* b, size_t n) {
  char* s = malloc(n + 1);
  ax_assume(s != NULL, "oom");
  memcpy(s, b, n);
  s[n] = '\0';
  return s;
}

/* MT executors drop sys->mu around the curl wait; every other CURLM
 * access holds mu AND sees http_pumping == false.  Callers already
 * hold mu (or are the only thread).  Waits out an in-progress poll. */
static void er_http_curlm_settle(er_scheduler* sys) {
  while (sys->http_pumping) {
    curl_multi_wakeup(sys->curlm); // LCOV_EXCL_LINE: scheduling-dependent
    pthread_cond_wait(&sys->cv,
                      &sys->mu); // LCOV_EXCL_LINE: scheduling-dependent
  }
}

static void er_http_dispatch(er_scheduler* sys, er_actor* a, er_http_parsed* p,
                             const uint8_t hash[32]) {
  CURLM* m = er_curlm(sys);
  er_http_curlm_settle(sys);
  er_http_xfer* x = calloc(1, sizeof(*x));
  ax_assume(x != NULL, "oom");
  x->actor = a;
  memcpy(x->args_hash, hash, 32);
  x->max_body = p->max_body;
  x->method_c = er_cstr(p->method, p->method_n);
  x->url_c = er_cstr(p->url, p->url_n);
  if (p->has_body) { /* steal the parsed body as POSTFIELDS storage */
    x->body = p->body;
    x->body_n = p->body_n;
    p->body = NULL;
    p->body_n = 0;
  }

  for (ptrdiff_t i = 0; i < ax_arrlen(p->hdrs); i++) {
    const er_http_hdr* h = &p->hdrs[i];
    /* "Name: value"; an empty value needs curl's "Name;" form ("Name:"
     * alone would DELETE a curl default header instead) */
    size_t line_n = h->name_n + 2 + h->value_n + 1;
    char* line = malloc(line_n + 1);
    ax_assume(line != NULL, "oom");
    if (h->value_n == 0) {
      memcpy(line, h->name, h->name_n);
      memcpy(line + h->name_n, ";", 2);
    } else {
      memcpy(line, h->name, h->name_n);
      memcpy(line + h->name_n, ": ", 2);
      memcpy(line + h->name_n + 2, h->value, h->value_n);
      line[h->name_n + 2 + h->value_n] = '\0';
    }
    struct curl_slist* nl = curl_slist_append(x->req_headers, line);
    ax_assume(nl != NULL, "curl_slist_append");
    x->req_headers = nl;
    free(line);
  }

  CURL* e = curl_easy_init();
  ax_assume(e != NULL, "curl_easy_init");
  x->easy = e;
  ER_CURL_EASY(curl_easy_setopt(e, CURLOPT_URL, x->url_c));
  ER_CURL_EASY(curl_easy_setopt(e, CURLOPT_CUSTOMREQUEST, x->method_c));
  if (strcmp(x->method_c, "HEAD") == 0)
    ER_CURL_EASY(curl_easy_setopt(e, CURLOPT_NOBODY, 1L));
  if (x->body != NULL) {
    ER_CURL_EASY(curl_easy_setopt(e, CURLOPT_POSTFIELDS, x->body));
    ER_CURL_EASY(curl_easy_setopt(e, CURLOPT_POSTFIELDSIZE_LARGE,
                                  (curl_off_t)x->body_n));
  }
  if (x->req_headers != NULL)
    ER_CURL_EASY(curl_easy_setopt(e, CURLOPT_HTTPHEADER, x->req_headers));
  uint64_t connect_ms = p->has_connect_ms ? p->connect_ms
                        : sys->cfg.http_connect_default_ms > 0
                            ? sys->cfg.http_connect_default_ms
                            : ER_HTTP_CONNECT_DEFAULT_MS;
  /* er_http_validate has checked the three user-facing long options. */
  ER_CURL_EASY(
      curl_easy_setopt(e, CURLOPT_CONNECTTIMEOUT_MS, (long)connect_ms));
  ER_CURL_EASY(curl_easy_setopt(e, CURLOPT_TIMEOUT_MS, (long)p->deadline_ms));
  ER_CURL_EASY(
      curl_easy_setopt(e, CURLOPT_FOLLOWLOCATION, p->redirects > 0 ? 1L : 0L));
  ER_CURL_EASY(curl_easy_setopt(e, CURLOPT_MAXREDIRS, (long)p->redirects));
  /* CURLOPT_UNRESTRICTED_AUTH stays unset: curl strips Authorization on
   * cross-origin redirects by default, and that is the contract */
  ER_CURL_EASY(curl_easy_setopt(e, CURLOPT_NOSIGNAL, 1L));
  ER_CURL_EASY(curl_easy_setopt(e, CURLOPT_ACCEPT_ENCODING, ""));
  ER_CURL_EASY(curl_easy_setopt(e, CURLOPT_PIPEWAIT, 1L));
  ER_CURL_EASY(curl_easy_setopt(e, CURLOPT_WRITEFUNCTION, er_http_write_cb));
  ER_CURL_EASY(curl_easy_setopt(e, CURLOPT_WRITEDATA, x));
  ER_CURL_EASY(curl_easy_setopt(e, CURLOPT_HEADERFUNCTION, er_http_header_cb));
  ER_CURL_EASY(curl_easy_setopt(e, CURLOPT_HEADERDATA, x));
  ER_CURL_EASY(curl_easy_setopt(e, CURLOPT_PRIVATE, x));
  /* the cookie engine stays off, always */

  ax_assume(curl_multi_add_handle(m, e) == CURLM_OK, "curl_multi_add_handle");
  er_http_park(sys, a, x);
  /* In er_mt_executor_drive, the adopted root is the first actor that
   * can dispatch a Fetch.  Its workers may all be sleeping before this
   * transition, so wake one to take ownership of the CURLM pump. */
  pthread_cond_broadcast(&sys->cv);
}

/* ── The service entry (the Fetch branch of er_service) ────────────────── */

void er_http_service(er_scheduler* sys, er_actor* a, uint32_t argc,
                     pl_val* args) {
  ax_assume(argc == 2, "Fetch arity");

  if (sys->mode == ER_MODE_REPLAY) {
    /* Validation is not re-run on replay (a different curl could judge
     * differently); the log knows.  A "FetchV" event next in the log is
     * this fetch's validation failure, deposited at this same service
     * point on the recording; anything else means it dispatched. */
    er_http_parsed p;
    if (!er_http_parse(args[0], args[1], &p)) {
      er_http_parsed_free(&p);
      er_crash_msg(a, "malformed Fetch request");
      return;
    }
    uint8_t hash[32];
    er_http_args_hash(&p, hash);
    er_http_parsed_free(&p);
    if (sys->cursor < er_log_events(sys->play)) {
      const er_event* e = &sys->play->ev[sys->cursor];
      if (e->kind == ER_EV_HTTP && e->op == er_mote("FetchV") &&
          e->actor == a->id) {
        ax_assume(memcmp(e->args_hash, hash, 32) == 0,
                  "er_log: replay divergence at a Fetch validation");
        sys->cursor++;
        er_http_resume(sys, a, e->data, e->data_n);
        return;
      }
    }
    er_http_xfer* stub = calloc(1, sizeof(*stub));
    ax_assume(stub != NULL, "oom");
    stub->actor = a;
    memcpy(stub->args_hash, hash, 32);
    er_http_park(sys, a, stub);
    return;
  }

  er_http_parsed p;
  if (!er_http_parse(args[0], args[1], &p)) {
    er_http_parsed_free(&p);
    er_crash_msg(a, "malformed Fetch request");
    return;
  }
  uint8_t hash[32] = {0};
  if (sys->mode != ER_MODE_LIVE) /* only the event log reads the hash */
    er_http_args_hash(&p, hash);

  int verr = er_http_validate(sys, &p);
  if (verr >= 0) {
    /* even an immediately-failing fetch is an oracle: log and replay it
     * rather than re-validating against a possibly-different curl */
    uint8_t data[2] = {1, (uint8_t)verr};
    if (sys->mode == ER_MODE_RECORD)
      er_http_record_event(sys, a->id, "FetchV", hash, data, 2);
    er_http_parsed_free(&p);
    er_http_resume(sys, a, data, 2);
    return;
  }

  er_http_dispatch(sys, a, &p, hash);
  er_http_parsed_free(&p);
}

/* ── Progress: pump, harvest, idle ─────────────────────────────────────── */

/* Move DONE transfers off the multi handle into the completion FIFO,
 * in curl_multi_info_read order (never from inside a callback). */
static void er_http_harvest(er_scheduler* sys) {
  CURLM* m = sys->curlm;
  CURLMsg* msg;
  int left;
  while ((msg = curl_multi_info_read(m, &left)) != NULL) {
    if (msg->msg != CURLMSG_DONE)
      continue;
    CURL* e = msg->easy_handle;
    er_http_xfer* x = NULL;
    curl_easy_getinfo(e, CURLINFO_PRIVATE, &x);
    ax_assume(x != NULL, "er_http: DONE easy handle without a transfer");
    x->result = msg->data.result;
    long status = 0;
    curl_easy_getinfo(e, CURLINFO_RESPONSE_CODE, &status);
    x->resp_status = status;
    char* eu = NULL;
    curl_easy_getinfo(e, CURLINFO_EFFECTIVE_URL, &eu);
    x->effective_url = eu != NULL ? strdup(eu) : NULL;
    curl_off_t ct = 0;
    curl_easy_getinfo(e, CURLINFO_CONNECT_TIME_T, &ct);
    x->connected = ct > 0;
    curl_multi_remove_handle(m, e);
    er_http_unlink_inflight(sys, x);
    x->next_done = NULL;
    if (sys->http_done_tail != NULL)
      sys->http_done_tail->next_done = x;
    else
      sys->http_done_head = x;
    sys->http_done_tail = x;
  }
}

/* Pop the completion FIFO head, log it (record mode), resume its actor. */
static void er_http_deposit_head(er_scheduler* sys) {
  er_http_xfer* x = sys->http_done_head;
  ax_assume(x != NULL, "er_http: no completion to deposit");
  sys->http_done_head = x->next_done;
  if (sys->http_done_head == NULL)
    sys->http_done_tail = NULL;
  uint64_t n;
  uint8_t* data = er_http_result_encode(x, &n);
  if (sys->mode == ER_MODE_RECORD)
    er_http_record_event(sys, x->actor->id, "Fetch", x->args_hash, data, n);
  er_http_resume(sys, x->actor, data, n);
  free(data);
  er_http_xfer_free(sys, x);
}

void er_http_pump(er_scheduler* sys) {
  if (sys->curlm == NULL)
    return;
  int running = 0;
  curl_multi_perform(sys->curlm, &running);
  er_http_harvest(sys);
  if (sys->mode == ER_MODE_LIVE) /* record: one deposit per idle point */
    while (sys->http_done_head != NULL)
      er_http_deposit_head(sys);
}

bool er_http_outstanding(const er_scheduler* sys) {
  return sys->http_inflight_n > 0 || sys->http_done_head != NULL ||
         sys->http_parked_n > 0;
}

size_t er_http_inflight_count(const er_scheduler* sys) {
  return sys->http_inflight_n;
}

/*
 * MT executors (LIVE only): one worker at a time owns the CURLM,
 * releases sys->mu around a bounded curl_multi_poll, then harvests and
 * deposits every completion under mu.  Returns true when this call
 * owned the pump — the caller should re-check the run queue and call
 * again; false when another worker owns it or no http work exists
 * (then cond_wait is correct: the owner broadcasts on completion).
 */
bool er_http_mt_pump(er_scheduler* sys) {
  if (sys->curlm == NULL || sys->http_pumping || !er_http_outstanding(sys))
    return false;
  sys->http_pumping = true;
  pthread_mutex_unlock(&sys->mu);
  int running = 0;
  curl_multi_perform(sys->curlm, &running);
  curl_multi_poll(sys->curlm, NULL, 0, 100, NULL); /* bounded: stay stealable */
  curl_multi_perform(sys->curlm, &running);
  pthread_mutex_lock(&sys->mu);
  sys->http_pumping = false;
  er_http_harvest(sys);
  while (sys->http_done_head != NULL)
    er_http_deposit_head(sys);      /* er_enqueue signals the cv per actor */
  pthread_cond_broadcast(&sys->cv); /* dispatchers may wait in settle */
  return true;
}

/* Block in curl_multi_poll until at least one completion is harvested.
 * curl computes its own timers (deadlines, connect timeouts), so the
 * outer timeout is just a backstop. */
static void er_http_wait_for_done(er_scheduler* sys) {
  while (sys->http_done_head == NULL && sys->http_inflight_n > 0) {
    int running = 0;
    curl_multi_perform(sys->curlm, &running);
    er_http_harvest(sys);
    if (sys->http_done_head != NULL)
      break;
    curl_multi_poll(sys->curlm, NULL, 0, 1000, NULL);
  }
}

bool er_http_idle(er_scheduler* sys) {
  switch (sys->mode) {
  case ER_MODE_LIVE:
  case ER_MODE_RECORD:
    if (sys->http_inflight_n == 0 && sys->http_done_head == NULL)
      return false;
    er_http_wait_for_done(sys);
    if (sys->http_done_head == NULL)
      return false;
    if (sys->mode == ER_MODE_LIVE) {
      while (sys->http_done_head != NULL)
        er_http_deposit_head(sys);
    } else {
      /* exactly ONE deposit per empty-queue point: replay reaches the
       * same points in the same order, so log order alone reproduces
       * the resumption schedule */
      er_http_deposit_head(sys);
    }
    return true;

  case ER_MODE_REPLAY: {
    if (sys->http_parked_n == 0)
      return false;
    const er_event* e = er_replay_next(sys);
    ax_assume(e->kind == ER_EV_HTTP && e->op == er_mote("Fetch"),
              "er_log: replay divergence at a Fetch completion");
    er_actor* a = NULL;
    for (er_actor* it = sys->all_head; it != NULL; it = it->all_next)
      if (it->http != NULL && it->id == e->actor) {
        a = it;
        break;
      }
    ax_assume(a != NULL, "er_log: replayed Fetch completion for an actor "
                         "that is not fetch-parked");
    ax_assume(memcmp(e->args_hash, a->http->args_hash, 32) == 0,
              "er_log: replay divergence at a Fetch completion");
    er_http_xfer* stub = a->http;
    er_http_resume(sys, a, e->data, e->data_n);
    er_http_unlink_inflight(sys, stub);
    er_http_xfer_free(sys, stub);
    return true;
  }
  }
  return false;
}

/* ── Teardown (scheduler free): abort in-flight, log nothing ───────────── */

void er_http_teardown(er_scheduler* sys) {
  for (er_http_xfer* x = sys->http_inflight; x != NULL;) {
    er_http_xfer* next = x->next_inflight;
    if (x->actor != NULL && x->actor->http == x)
      x->actor->http = NULL;
    er_http_xfer_free(sys, x);
    x = next;
  }
  sys->http_inflight = NULL;
  sys->http_inflight_n = 0;
  for (er_http_xfer* x = sys->http_done_head; x != NULL;) {
    er_http_xfer* next = x->next_done;
    if (x->actor != NULL && x->actor->http == x)
      x->actor->http = NULL;
    er_http_xfer_free(sys, x);
    x = next;
  }
  sys->http_done_head = sys->http_done_tail = NULL;
  sys->http_parked_n = 0;
  if (sys->curlm != NULL) {
    curl_multi_cleanup(sys->curlm);
    sys->curlm = NULL;
  }
}
