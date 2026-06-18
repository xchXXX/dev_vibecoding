const assert = require("assert");
const {
  roundMoney,
  subtotal,
  getDiscountRate,
  applyDiscount,
  calculateInvoice,
} = require("../src/pricing");

function runPricingTests() {
  const items = [
    { price: 19.99, quantity: 2 },
    { price: 5.0, quantity: 3 },
  ];

  assert.strictEqual(roundMoney(10.235), 10.24);
  assert.strictEqual(subtotal(items), 54.98);
  assert.strictEqual(subtotal([]), 0);

  assert.strictEqual(getDiscountRate("gold"), 0.15);
  assert.strictEqual(getDiscountRate("silver"), 0.08);
  assert.strictEqual(getDiscountRate("guest"), 0);

  assert.strictEqual(applyDiscount(100, "gold"), 85);
  assert.strictEqual(applyDiscount(100, "silver"), 92);
  assert.strictEqual(applyDiscount(100, "guest"), 100);

  const invoice = calculateInvoice(items, "silver", 0.06);
  assert.deepStrictEqual(invoice, {
    beforeDiscount: 54.98,
    discounted: 50.58,
    tax: 3.03,
    total: 53.61,
  });

  const emptyInvoice = calculateInvoice([], "guest", 0.06);
  assert.deepStrictEqual(emptyInvoice, {
    beforeDiscount: 0,
    discounted: 0,
    tax: 0,
    total: 0,
  });
}

module.exports = {
  runPricingTests,
};
