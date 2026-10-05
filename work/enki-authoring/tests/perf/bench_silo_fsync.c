/*
 * bench_silo_fsync — what the pins.pack durability barrier costs.
 *
 * Phase 1 times the raw primitives on the target filesystem: a small pwrite
 * followed by fcntl(F_FULLFSYNC), by fsync, or by nothing.  On Darwin only
 * the first flushes the drive's own write cache, so the gap between the
 * first two is the price of surviving power loss.
 *
 * Phase 2 times whole Silo commits (pl_store_save_root: pack append, sync,
 * LMDB root publish) under the PL_SILO_FSYNC mode this process inherited,
 * which is what the gap is worth end to end.
 *
 *   bench_silo_fsync [--dir DIR] [--iters N] [--bytes N] [--warmup N]
 */

#include <errno.h>
#include <fcntl.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <time.h>
#include <unistd.h>

#include "plan/heap.h"
#include "plan/store.h"

typedef struct sample_set {
  double* us;
  size_t n;
} sample_set;

static double now_us(void) {
  struct timespec ts;
  clock_gettime(CLOCK_MONOTONIC, &ts);
  return (double)ts.tv_sec * 1e6 + (double)ts.tv_nsec / 1e3;
}

static int cmp_double(const void* a, const void* b) {
  double x = *(const double*)a, y = *(const double*)b;
  return x < y ? -1 : (x > y ? 1 : 0);
}

static double pct(const sample_set* s, double p) {
  if (s->n == 0)
    return 0.0;
  size_t i = (size_t)(p * (double)(s->n - 1) + 0.5);
  return s->us[i];
}

/* Destructive: sorts the samples in place. */
static void report(const char* label, sample_set* s) {
  if (s->n == 0) {
    printf("  %-22s (no samples)\n", label);
    return;
  }
  double total = 0.0;
  for (size_t i = 0; i < s->n; i++)
    total += s->us[i];
  qsort(s->us, s->n, sizeof(double), cmp_double);
  double mean = total / (double)s->n;
  printf("  %-22s n=%-6zu mean %9.1f  p50 %9.1f  p90 %9.1f  p99 %9.1f  "
         "min %8.1f  max %9.1f  %9.1f ops/s\n",
         label, s->n, mean, pct(s, 0.50), pct(s, 0.90), pct(s, 0.99), s->us[0],
         s->us[s->n - 1], 1e6 / mean);
}

/* ── Phase 1: the primitives ───────────────────────────────────────────── */

enum raw_mode { RAW_FULL, RAW_DATA, RAW_NONE };

static void bench_raw(const char* dir, enum raw_mode mode, const char* label,
                      size_t iters, size_t warmup, size_t bytes) {
  char path[512];
  snprintf(path, sizeof(path), "%s/raw.bin", dir);
  int fd = open(path, O_RDWR | O_CREAT | O_TRUNC, 0644);
  if (fd < 0) {
    fprintf(stderr, "open %s: %s\n", path, strerror(errno));
    exit(1);
  }
  uint8_t* buf = malloc(bytes);
  memset(buf, 0xa5, bytes);

  double* us = malloc(iters * sizeof(double));
  size_t kept = 0;
  for (size_t i = 0; i < warmup + iters; i++) {
    off_t off = (off_t)(i * bytes);
    double t0 = now_us();
    if (pwrite(fd, buf, bytes, off) != (ssize_t)bytes) {
      fprintf(stderr, "pwrite: %s\n", strerror(errno));
      exit(1);
    }
    int rc = 0;
    if (mode == RAW_FULL)
      rc = fcntl(fd, F_FULLFSYNC, 0);
    else if (mode == RAW_DATA)
      rc = fsync(fd);
    if (rc != 0) {
      fprintf(stderr, "sync: %s\n", strerror(errno));
      exit(1);
    }
    double dt = now_us() - t0;
    if (i >= warmup)
      us[kept++] = dt;
  }
  sample_set s = {.us = us, .n = kept};
  report(label, &s);
  free(us);
  free(buf);
  close(fd);
  (void)unlink(path);
}

/* ── Phase 2: whole Silo commits ───────────────────────────────────────── */

static void rm_store(const char* dir) {
  char path[512];
  snprintf(path, sizeof(path), "%s/pins.pack", dir);
  (void)unlink(path);
  snprintf(path, sizeof(path), "%s/data.mdb", dir);
  (void)unlink(path);
  snprintf(path, sizeof(path), "%s/lock.mdb", dir);
  (void)unlink(path);
}

static void bench_store(const char* dir, const char* label, size_t iters,
                        size_t warmup) {
  rm_store(dir);
  pl_store* s = pl_store_new_silo(dir, (size_t)256 << 20);
  if (s == NULL) {
    fprintf(stderr, "pl_store_new_silo(%s) failed\n", dir);
    exit(1);
  }
  pl_heap* h = pl_heap_new(1 << 16, s);
  pl_thread* t = pl_thread_new(h);

  double* us = malloc(iters * sizeof(double));
  size_t kept = 0;
  char err[256] = {0};
  for (size_t i = 0; i < warmup + iters; i++) {
    /* A fresh nat per iteration: distinct hash, so every commit really
     * appends to the pack and republishes the root. */
    size_t base = t->vsp;
    pl_vpush(t, (pl_val)(i + 1));
    double t0 = now_us();
    t->vstack[base] = pl_pin(t, t->vstack[base]);
    if (!pl_store_save_root(s, t->vstack[base], NULL, err, sizeof(err))) {
      fprintf(stderr, "save_root: %s\n", err);
      exit(1);
    }
    double dt = now_us() - t0;
    t->vsp = base;
    if (i >= warmup)
      us[kept++] = dt;
  }
  sample_set set = {.us = us, .n = kept};
  report(label, &set);
  free(us);

  pl_thread_free(t);
  pl_heap_free(h);
  pl_store_free(s);
  rm_store(dir);
}

int main(int argc, char** argv) {
  const char* dir = "build/bench-silo";
  size_t iters = 300, warmup = 20, bytes = 4096;
  for (int i = 1; i < argc; i++) {
    if (strcmp(argv[i], "--dir") == 0 && i + 1 < argc)
      dir = argv[++i];
    else if (strcmp(argv[i], "--iters") == 0 && i + 1 < argc)
      iters = (size_t)strtoul(argv[++i], NULL, 10);
    else if (strcmp(argv[i], "--warmup") == 0 && i + 1 < argc)
      warmup = (size_t)strtoul(argv[++i], NULL, 10);
    else if (strcmp(argv[i], "--bytes") == 0 && i + 1 < argc)
      bytes = (size_t)strtoul(argv[++i], NULL, 10);
    else {
      fprintf(stderr,
              "usage: %s [--dir D] [--iters N] [--warmup N] "
              "[--bytes N]\n",
              argv[0]);
      return 2;
    }
  }
  (void)mkdir(dir, 0755);

  const char* mode = getenv("PL_SILO_FSYNC");
  printf("dir=%s iters=%zu warmup=%zu bytes=%zu PL_SILO_FSYNC=%s\n", dir, iters,
         warmup, bytes, mode == NULL ? "(unset -> full)" : mode);

  printf("phase 1: pwrite(%zu B) + barrier, microseconds\n", bytes);
  bench_raw(dir, RAW_FULL, "fcntl(F_FULLFSYNC)", iters, warmup, bytes);
  bench_raw(dir, RAW_DATA, "fsync", iters, warmup, bytes);
  bench_raw(dir, RAW_NONE, "write only", iters, warmup, bytes);

  printf("phase 2: pl_store_save_root, microseconds\n");
  bench_store(dir, "silo commit", iters, warmup);
  (void)rmdir(dir);
  return 0;
}
