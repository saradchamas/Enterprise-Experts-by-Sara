// Deliberately insecure fixture. Do not copy.
const express = require('express');
const { Pool } = require('pg');
const app = express();
const pool = new Pool({ connectionString: process.env.DATABASE_URL });
app.get('/orders/:id', async (req, res) => {
  const r = await pool.query('SELECT * FROM orders WHERE id = ' + req.params.id);
  res.json(r.rows[0]);
});
exports.total = (items) => items.reduce((s, i) => s + i.price * i.qty, 0);
if (require.main === module) app.listen(3000);
