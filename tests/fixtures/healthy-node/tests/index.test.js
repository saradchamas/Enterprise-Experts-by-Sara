const test = require('node:test');
const assert = require('node:assert');
const { total } = require('../src/index.js');

test('total multiplies price by quantity', () => {
  assert.equal(total([{ price: 2, qty: 3 }, { price: 1, qty: 1 }]), 7);
});
