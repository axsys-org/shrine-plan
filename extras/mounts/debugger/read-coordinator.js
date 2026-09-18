// One transport budget for foreground navigation, tree, locator and previews.
// Share immutable wire text, not Documents (consumers move their DOM nodes).
export function createReadCoordinator({fetcher = globalThis.fetch, concurrency = 3,
  background = 2, timeout = 20000, maxBytes = 4 * 1024 * 1024} = {}) {
  const jobs = new Map();
  let active = 0, sequence = 0;
  function pump() {
    const queued = [...jobs.values()].filter(job => !job.started && job.clients.size)
      .sort((a, b) => b.priority - a.priority || a.sequence - b.sequence);
    for (const job of queued) {
      if (active >= concurrency || (job.priority < 1 && active >= background)) break;
      job.started = true; active++;
      void run(job);
    }
  }
  async function run(job) {
    const timer = setTimeout(() => job.controller.abort(new DOMException('Read timed out.', 'TimeoutError')), timeout);
    let value, failure;
    try {
      const response = await fetcher(job.url, {cache: 'no-store', signal: job.controller.signal});
      if (!response.ok) throw new Error('Read failed (HTTP ' + response.status + ').');
      if (!(response.headers.get('content-type') || '').includes('text/html'))
        throw new Error('The runtime did not return an HTML debug document.');
      if (Number(response.headers.get('content-length')) > maxBytes) throw new Error('Debug document exceeds the read budget.');
      const reader = response.body?.getReader();
      if (!reader) {
        value = await response.text();
        if (new TextEncoder().encode(value).byteLength > maxBytes) throw new Error('Debug document exceeds the read budget.');
      } else {
        const decoder = new TextDecoder();
        const parts = []; let bytes = 0;
        try {
          for (;;) {
            const {value: chunk, done} = await reader.read();
            if (done) break;
            bytes += chunk.byteLength;
            if (bytes > maxBytes) throw new Error('Debug document exceeds the read budget.');
            parts.push(decoder.decode(chunk, {stream: true}));
          }
          parts.push(decoder.decode()); value = parts.join('');
        } catch (error) { await reader.cancel().catch(() => {}); throw error; }
        finally { reader.releaseLock(); }
      }
      job.controller.signal.throwIfAborted();
    } catch (error) { failure = error; }
    finally {
      clearTimeout(timer); active--;
      if (jobs.get(job.url) === job) jobs.delete(job.url);
      for (const client of job.clients) {
        client.signal?.removeEventListener('abort', client.cancel);
        failure ? client.reject(failure) : client.resolve(value);
      }
      job.clients.clear(); pump();
    }
  }
  function read(url, {signal, priority = 0, alternatives = []} = {}) {
    return new Promise((resolve, reject) => {
      signal?.throwIfAborted();
      let job = jobs.get(url) || alternatives.map(key => jobs.get(key)).find(Boolean);
      if (!job) {
        job = {url, sequence: sequence++, priority, started: false, controller: new AbortController(), clients: new Set()};
        jobs.set(url, job);
      }
      job.priority = Math.max(job.priority, priority);
      const client = {signal, resolve, reject, cancel: null};
      client.cancel = () => {
        job.clients.delete(client);
        signal.removeEventListener('abort', client.cancel);
        reject(signal.reason);
        if (!job.clients.size) {
          // A new subscription must never attach to an aborted in-flight job.
          if (jobs.get(job.url) === job) jobs.delete(job.url);
          job.controller.abort(signal.reason);
        }
        pump();
      };
      job.clients.add(client);
      signal?.addEventListener('abort', client.cancel, {once: true});
      pump();
    });
  }
  return {read, get size() { return jobs.size; }, get active() { return active; }};
}

export const debugReads = createReadCoordinator();
