import test from 'node:test';
import assert from 'node:assert/strict';
import {EventEmitter} from 'node:events';
import {createServer, parameters, readJson, MAX_BYTES, SourceError} from './source.mjs';

const config = {token: 'a'.repeat(40), connection: {database: 'sample'},
  queries: {orders: {text: 'SELECT', sha256: 'hash', parameters: {id: {min: 1, max: 10}}}}};
async function serve(t, execute) {
  const server = createServer(config, execute);
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  t.after(() => { server.closeAllConnections(); server.close(); });
  return `http://127.0.0.1:${server.address().port}/${config.token}/orders`;
}
test('only declared bounded integers reach SQL parameters', () => {
  assert.deepEqual(parameters(new URLSearchParams('id=7'), config.queries.orders.parameters), {id: 7});
  for (const text of ['', 'id=0', 'id=11', 'id=1&id=2', 'id=1&sql=DROP', 'id=1.0', 'id=1%3BDELETE'])
    assert.throws(() => parameters(new URLSearchParams(text), config.queries.orders.parameters));
});
test('raw decimal and bigint JSON remains exact, with query provenance', async t => {
  const url = await serve(t, async (_q, args) => { assert.equal(args.id, 7); return '[{"amount":12.50,"id":9007199254740993,"empty":null}]'; });
  const response = await fetch(url + '?id=7');
  const text = await response.text();
  assert.equal(response.status, 200);
  assert.match(text, /12\.50/); assert.match(text, /9007199254740993/);
  const value = JSON.parse(text);
  assert.equal(value.source.querySha256, 'hash'); assert.deepEqual(value.source.parameters, {id: 7});
  assert.equal(value.source.queryText, 'SELECT');
  assert.equal(response.headers.get('cache-control'), 'no-store');
});
test('unavailable source returns failure, never cached evidence; restoration works', async t => {
  let available = true;
  const url = await serve(t, async () => { if (!available) throw new Error('private SQL details'); return '[]'; });
  assert.equal((await fetch(url + '?id=1')).status, 200);
  available = false;
  const failed = await fetch(url + '?id=1');
  assert.equal(failed.status, 503); assert.equal(await failed.text(), '{"error":"SQL source unavailable"}');
  available = true; assert.equal((await fetch(url + '?id=1')).status, 200);
});
test('capability, method, parameter and size refusal', async t => {
  let calls = 0;
  const url = await serve(t, async () => { calls++; return JSON.stringify('x'.repeat(MAX_BYTES)); });
  assert.equal((await fetch(url.replace(config.token, 'wrong') + '?id=1')).status, 404);
  assert.equal((await fetch(url + '?id=1', {method: 'POST'})).status, 405);
  assert.equal((await fetch(url + '?id=20')).status, 400);
  assert.equal(calls, 0);
  assert.equal((await fetch(url + '?id=1')).status, 413);
});
test('disconnect cancels the in-flight request', async t => {
  let started, cancelled;
  const began = new Promise(resolve => { started = resolve; });
  const stopped = new Promise(resolve => { cancelled = resolve; });
  const url = await serve(t, (_q, _a, signal) => new Promise((_resolve, reject) => {
    signal.addEventListener('abort', () => { cancelled(); reject(new SourceError(499, 'gone')); }); started();
  }));
  const abort = new AbortController();
  const request = fetch(url + '?id=1', {signal: abort.signal}).catch(() => {});
  await began; abort.abort(); await request;
  await Promise.race([stopped, new Promise((_r, reject) => { const timer = setTimeout(() => reject(new Error('not cancelled')), 2000); timer.unref(); })]);
});
test('stream rejects multiple recordsets and cancels oversized results', async () => {
  for (const multiple of [true, false]) {
    const request = new EventEmitter(); let cancelled = false;
    request.cancel = () => { cancelled = true; };
    request.query = async () => {
      request.emit('recordset', {json: {}});
      if (multiple) request.emit('recordset', {json: {}});
      else request.emit('row', {json: 'x'.repeat(MAX_BYTES + 1)});
      request.emit('done');
    };
    await assert.rejects(readJson(request, 'query'), error => error.status === (multiple ? 502 : 413));
    assert.equal(cancelled, true);
  }
});
