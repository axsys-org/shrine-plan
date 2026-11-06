import test from 'node:test';
import assert from 'node:assert/strict';
import sql from 'mssql';
import {loadConfig, capture} from './source.mjs';

test('WWI live SQL captures, structural evidence and read-only permissions',
  {skip: !process.env.SHRINE_SQL_CONFIG}, async () => {
    const config = await loadConfig(process.env.SHRINE_SQL_CONFIG);
    const pool = await new sql.ConnectionPool({...config.connection,
      options: {...config.connection.options, parseJSON: false}}).connect();
    try {
      const execute = capture(pool);
      const catalog = JSON.parse(await execute(config.queries.catalog, {}));
      const ordersTable = catalog.find(t => t.SchemaName === 'Sales' && t.TableName === 'Orders');
      assert.ok(ordersTable);
      const schema = JSON.parse(await execute(config.queries.schema, {object: ordersTable.ObjectId}))[0];
      assert.ok(schema.Columns.length); assert.ok(schema.PrimaryKey.length); assert.ok(schema.ForeignKeys.length);
      const first = JSON.parse(await execute(config.queries.orders, {after: 0, limit: 3}));
      assert.equal(first.length, 3);
      const next = JSON.parse(await execute(config.queries.orders, {after: first[2].OrderID, limit: 3}));
      assert.ok(next.every(row => row.OrderID > first[2].OrderID));
      const detail = JSON.parse(await execute(config.queries.order, {id: first[0].OrderID}))[0];
      assert.equal(detail.OrderID, first[0].OrderID); assert.ok(detail.Lines.length);
      assert.deepEqual(JSON.parse(await execute(config.queries.order, {id: 2147483647})), []);
      await assert.rejects(pool.request().query('UPDATE Sales.Orders SET CustomerID=CustomerID WHERE 1=0'),
        error => error.number === 229);
    } finally { await pool.close(); }
  });
