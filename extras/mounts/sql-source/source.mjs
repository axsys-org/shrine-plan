import http from 'node:http';
import {readFile} from 'node:fs/promises';
import {createHash, timingSafeEqual} from 'node:crypto';
import {dirname, resolve} from 'node:path';
import {pathToFileURL} from 'node:url';
import sql from 'mssql';

export const MAX_BYTES = 131072; // Existing native HTTP source limit.
export class SourceError extends Error {
  constructor(status, message) { super(message); this.status = status; }
}
export function parameters(search, declarations = {}) {
  const values = {};
  for (const key of search.keys()) {
    if (!Object.hasOwn(declarations, key) || search.getAll(key).length !== 1)
      throw new SourceError(400, 'Unknown or repeated query parameter');
  }
  for (const [name, spec] of Object.entries(declarations)) {
    const text = search.get(name);
    if (text === null || !/^-?(0|[1-9][0-9]*)$/.test(text))
      throw new SourceError(400, `Integer parameter required: ${name}`);
    const value = Number(text);
    if (!Number.isSafeInteger(value) || value < spec.min || value > spec.max)
      throw new SourceError(400, `Parameter outside declared range: ${name}`);
    values[name] = value;
  }
  return values;
}
export async function loadConfig(filename) {
  const config = JSON.parse(await readFile(filename, 'utf8'));
  if (typeof config.token !== 'string' || !/^[a-zA-Z0-9_-]{32,}$/.test(config.token))
    throw new Error('A persistent random capability token is required');
  if (!Number.isInteger(config.port) || config.port < 0 || config.port > 65535)
    throw new Error('Invalid HTTP port');
  const queries = {};
  for (const [name, spec] of Object.entries(config.queries ?? {})) {
    if (!/^[a-z][a-z0-9_-]*$/.test(name)) throw new Error('Invalid query name');
    for (const [parameter, range] of Object.entries(spec.parameters ?? {})) {
      if (!/^[A-Za-z][A-Za-z0-9_]*$/.test(parameter) ||
          !Number.isInteger(range.min) || !Number.isInteger(range.max) ||
          range.min < -2147483648 || range.max > 2147483647 || range.min > range.max)
        throw new Error('Only declared SQL int parameter ranges are supported');
    }
    const text = await readFile(resolve(dirname(filename), spec.file), 'utf8');
    queries[name] = {...spec, text, sha256: createHash('sha256').update(text).digest('hex')};
  }
  if (!Object.keys(queries).length) throw new Error('At least one query is required');
  return {...config, queries};
}

// SQL Server serializes the result. Preserve that JSON text, including exact
// decimal and bigint spellings; parsing below only checks syntax, never rewrites it.
export function readJson(request, text, signal) {
  return new Promise((resolve, reject) => {
    let chunks = [], bytes = 0, recordsets = 0, settled = false;
    const fail = error => {
      if (settled) return;
      settled = true;
      signal?.removeEventListener('abort', abort);
      request.cancel();
      reject(error);
    };
    const abort = () => fail(new SourceError(499, 'Capture disconnected'));
    request.stream = true;
    request.on('recordset', columns => {
      if (++recordsets !== 1 || Object.keys(columns).length !== 1)
        fail(new SourceError(502, 'Query must return one JSON result column'));
    });
    request.on('row', row => {
      if (settled) return;
      const values = Object.values(row);
      if (values.length !== 1 || typeof values[0] !== 'string')
        return fail(new SourceError(502, 'Query must return SQL-generated JSON text'));
      bytes += Buffer.byteLength(values[0]);
      if (bytes > MAX_BYTES) return fail(new SourceError(413, 'Capture too large; narrow the query'));
      chunks.push(values[0]);
    });
    request.on('error', fail);
    request.on('done', () => {
      if (settled) return;
      const body = chunks.join('');
      try { JSON.parse(body); }
      catch { return fail(new SourceError(502, 'Query returned invalid or empty JSON')); }
      settled = true;
      signal?.removeEventListener('abort', abort);
      resolve(body);
    });
    signal?.addEventListener('abort', abort, {once: true});
    if (signal?.aborted) return abort();
    request.query(text).catch(fail);
  });
}
export function capture(pool) {
  return async (query, args, signal) => {
    const tx = new sql.Transaction(pool);
    let rolledBack = false;
    tx.on('rollback', () => { rolledBack = true; });
    await tx.begin(sql.ISOLATION_LEVEL.SNAPSHOT);
    try {
      const request = new sql.Request(tx);
      for (const [name, value] of Object.entries(args)) request.input(name, sql.Int, value);
      const body = await readJson(request, query.text, signal);
      if (signal?.aborted) throw new SourceError(499, 'Capture disconnected');
      await tx.commit();
      return body;
    } catch (error) {
      if (!rolledBack) await tx.rollback().catch(() => {});
      throw error;
    }
  };
}
export function createServer(config, execute) {
  return http.createServer(async (req, res) => {
    const abort = new AbortController();
    res.on('close', () => { if (!res.writableEnded) abort.abort(); });
    const send = (status, body) => {
      if (res.destroyed) return;
      res.writeHead(status, {'Content-Type': 'application/json', 'Cache-Control': 'no-store',
        'Content-Length': Buffer.byteLength(body)});
      res.end(body);
    };
    try {
      const url = new URL(req.url, 'http://localhost');
      const parts = url.pathname.split('/');
      const token = Buffer.from(parts[1] ?? '');
      const expected = Buffer.from(config.token);
      if (token.length !== expected.length || !timingSafeEqual(token, expected))
        throw new SourceError(404, 'Not found');
      if (req.method !== 'GET') throw new SourceError(405, 'Read-only source');
      if (parts.length !== 3 || !Object.hasOwn(config.queries, parts[2]))
        throw new SourceError(404, 'Unknown capture');
      const name = parts[2], query = config.queries[name];
      const args = parameters(url.searchParams, query.parameters);
      const startedAt = new Date().toISOString();
      const data = await execute(query, args, abort.signal);
      // Validate injected adapters too; retain the original numeric lexemes.
      JSON.parse(data);
      const source = JSON.stringify({database: config.connection.database, query: name,
        querySha256: query.sha256, queryText: query.text, parameters: args, isolation: 'snapshot',
        startedAt, finishedAt: new Date().toISOString()});
      const body = `{"source":${source},"data":${data}}`;
      if (Buffer.byteLength(body) > MAX_BYTES)
        throw new SourceError(413, 'Capture too large; narrow the query');
      send(200, body);
    } catch (error) {
      const known = error instanceof SourceError;
      send(known ? error.status : 503, JSON.stringify({error: known ? error.message : 'SQL source unavailable'}));
    }
  });
}
export async function main(filename) {
  const config = await loadConfig(filename);
  const pool = new sql.ConnectionPool({...config.connection, connectionTimeout: 10000,
    requestTimeout: 15000, pool: {max: 2, min: 0, idleTimeoutMillis: 30000},
    options: {encrypt: true, trustServerCertificate: false, ...config.connection.options,
      enableArithAbort: true, abortTransactionOnError: true, parseJSON: false}});
  pool.on('error', () => {}); // Request failures are returned to native work.
  await pool.connect();
  const server = createServer(config, capture(pool));
  server.requestTimeout = 20000;
  server.headersTimeout = 10000;
  await new Promise((resolve, reject) => {
    server.once('error', reject);
    server.listen(config.port, '127.0.0.1', resolve);
  });
  process.stdout.write(JSON.stringify({port: server.address().port}) + '\n');
  const close = () => {
    server.closeAllConnections();
    server.close(() => pool.close().finally(() => process.exit(0)));
  };
  process.once('SIGTERM', close);
  process.once('SIGINT', close);
}
if (process.argv[1] && import.meta.url === pathToFileURL(resolve(process.argv[1])).href) {
  main(process.argv[2]).catch(() => { console.error('SQL source startup failed; check configuration and database availability'); process.exitCode = 1; });
}
