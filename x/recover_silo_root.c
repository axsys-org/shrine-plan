/* Offline recovery into a NEW store; never edits the source store.
 * Uses Enki's Silo closure/index/transaction APIs. Historical root journals
 * remain in the original world; this is not in-place garbage collection.
 * Link with the libraries corresponding to the preserved world engine.
 */
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>
#include <sys/stat.h>
#include <openssl/sha.h>
#include "axsys/ds.h"
#include "plan/store.h"
#include "store_internal.h"

typedef struct entry { pl_hash key; uint64_t value; } entry;
static void fail(const char *message) {
  fprintf(stderr, "recovery refused: %s\n", message);
  exit(1);
}
static void hex(const uint8_t *bytes, char *out) {
  for (size_t i=0; i<32; i++) sprintf(out+2*i, "%02x", bytes[i]);
}
static bool exact(pl_store *s, pl_hash hash, uint64_t length, uint8_t **bytes) {
  pl_silo_reader reader={0}; char error[256]={0}; uint8_t digest[32];
  if (!pl_store_silo_open(s,hash.b,&reader,error,sizeof(error))) return false;
  if (reader.len!=length || !(*bytes=malloc((size_t)length))) {
    pl_store_silo_close_reader(&reader); return false;
  }
  bool ok=reader.read(reader.ctx,*bytes,(size_t)length);
  pl_store_silo_close_reader(&reader);
  SHA256(*bytes,(size_t)length,digest);
  return ok && memcmp(digest,hash.b,32)==0;
}
int main(int argc, char **argv) {
  if (argc!=4) fail("usage: recover_silo_root SOURCE NEW_DEST EXPECTED_ROOT_HASH");
  pl_store *source=pl_store_new_silo_ro(argv[1], (size_t)1<<30);
  if (!source) fail("cannot open source read-only");
  pl_hash root; char roothex[65];
  if (!pl_store_get_root(source,root.b)) fail("source has no committed root");
  hex(root.b,roothex);
  if (strcmp(roothex,argv[3])) fail("source root differs from inspected basis");
  uint64_t source_sequence=pl_store_root_log_head(source);
  entry *seen=NULL; pl_hash *pending=NULL; uint64_t total=0;
  ax_arrpush(pending,root);
  while (ax_arrlen(pending)>0) {
    pl_hash h=stbds_arrpop(pending);
    if (ax_hmgeti(seen,h)>=0) continue;
    uint64_t length=0; pl_hash *children=NULL; size_t n=0; char error[256]={0};
    if (!pl_store_silo_object_info(source,h.b,&length,&children,&n,error,sizeof(error))) fail(error);
    if (length>128*1024*1024 || total+length>1024ULL*1024*1024 || ax_hmlen(seen)>=1000000 || n>1000000) fail("closure exceeds recovery bound");
    total+=length; ax_hmput(seen,h,length);
    for (size_t i=0;i<n;i++) {
      if (ax_arrlen(pending)>=2000000) fail("pending closure exceeds recovery bound");
      ax_arrpush(pending,children[i]);
    }
    free(children);
  }
  ax_arrfree(pending);
  /* mkdir is exclusive: an existing, linked or partial destination is refused. */
  if (mkdir(argv[2],0700)!=0) fail("destination must not exist");
  pl_store *dest=pl_store_new_silo(argv[2],(size_t)1<<30);
  if (!dest) fail("cannot create destination store");
  pl_silo_batch *batch=NULL; char error[256]={0};
  if (!pl_store_silo_batch_begin(dest,&batch,error,sizeof(error))) fail(error);
  for (ptrdiff_t i=0;i<ax_hmlen(seen);i++) {
    uint8_t *bytes=NULL;
    if (!exact(source,seen[i].key,seen[i].value,&bytes)) fail("source stream hash/length mismatch");
    if (!pl_store_silo_batch_put(batch,seen[i].key.b,bytes,(size_t)seen[i].value,error,sizeof(error))) fail(error);
    free(bytes);
  }
  uint8_t latest[32];
  if (!pl_store_get_root(source,latest) || memcmp(latest,root.b,32) || pl_store_root_log_head(source)!=source_sequence) fail("source advanced during copy");
  if (!pl_store_silo_batch_commit(batch,root.b,error,sizeof(error))) fail(error);
  pl_store_free(dest);
  /* Cold reopen and byte-identity verification of EVERY reachable object. */
  dest=pl_store_new_silo_ro(argv[2],(size_t)1<<30);
  if (!dest || !pl_store_get_root(dest,latest) || memcmp(latest,root.b,32)) fail("cold root verification failed");
  for (ptrdiff_t i=0;i<ax_hmlen(seen);i++) {
    uint8_t *bytes=NULL;
    if (!exact(dest,seen[i].key,seen[i].value,&bytes)) fail("cold stream verification failed");
    free(bytes);
  }
  printf("{\"root\":\"%s\",\"source_sequence\":%llu,\"objects\":%td,\"bytes\":%llu,\"cold_verified\":true,\"historical_journal\":\"retained in source world\"}\n",roothex,(unsigned long long)source_sequence,ax_hmlen(seen),(unsigned long long)total);
  ax_hmfree(seen); pl_store_free(dest); pl_store_free(source);
  return 0;
}
