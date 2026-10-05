#include <errno.h>
#include <setjmp.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/types.h>

#include "axsys/allocator.h"
#include "enki/wisp.h"
#include "plan/heap.h"
#include "plan/store.h"

/* A tiny PLAN-assembly REPL over stdin. */

static ssize_t repl_line(char** out_c, size_t* cap_s) {
  fputs("> ", stdout);
  fflush(stdout);
  ssize_t len_s = getline(out_c, cap_s, stdin);
  if (len_s < 0) {
    if (feof(stdin))
      return -1;
    if (errno == EINTR) {
      clearerr(stdin);
      return 0;
    }
    perror("getline");
    return -1;
  }
  if (len_s > 0 && (*out_c)[len_s - 1] == '\n')
    (*out_c)[--len_s] = '\0';
  return len_s;
}

int main(void) {
  const ax_allocator* loc_a = ax_allocator_system();
  pl_store* store = pl_store_new_mem();
  pl_heap* heap = pl_heap_new((size_t)1 << 21, store);
  en_wisp* w = en_wisp_new(heap);
  if (w == NULL) {
    fputs("failed to allocate wisp runtime\n", stderr);
    return 1;
  }

  char* inp_c = NULL;
  size_t cap_s = 0;
  ssize_t inp_s;
  w->err_f = true;
  while (inp_s = repl_line(&inp_c, &cap_s), inp_s >= 0) {
    if (inp_s == 0)
      continue;
    char* txt_c = inp_c;
    if (setjmp(w->errjmp)) {
      printf("Failed to evaluate: %s\n",
             w->msg_c == NULL ? "Unknown Error" : w->msg_c);
      continue;
    }
    pl_val val_v = en_wisp_parse(w, &txt_c);
    pl_val eve_v = en_wisp_eval(w, val_v);
    char* out_c = en_wisp_print(w, eve_v, NULL);
    printf(">> %s\n", out_c);
    ax_free(loc_a, out_c);
  }
  free(inp_c);
  en_wisp_free(w);
  pl_heap_free(heap);
  pl_store_free(store);
  return 0;
}
