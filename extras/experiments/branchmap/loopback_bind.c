/* Experiment-local macOS bind adapter: constrain only this world's port. */
#include <sys/socket.h>
#include <netinet/in.h>
#include <string.h>
static int local_bind(int fd, const struct sockaddr *address, socklen_t length) {
  if (address && address->sa_family == AF_INET && length >= sizeof(struct sockaddr_in)) {
    struct sockaddr_in local;
    memcpy(&local,address,sizeof(local));
    if (ntohs(local.sin_port)==8148 && local.sin_addr.s_addr==htonl(INADDR_ANY)) {
      local.sin_addr.s_addr=htonl(INADDR_LOOPBACK);
      return bind(fd,(const struct sockaddr *)&local,length);
    }
  }
  return bind(fd,address,length);
}
__attribute__((used)) static struct { const void *replacement; const void *replacee; } bindings
__attribute__((section("__DATA,__interpose"))) = {(const void *)local_bind,(const void *)bind};
