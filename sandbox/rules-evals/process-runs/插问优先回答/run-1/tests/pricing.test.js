const assert = require("assert");
const {
  subtotal,
  applyDiscount,
  calculateInvoice,
  getDiscountRate,
} = require("../src/pricing");

function runPricingTests() {
  const items = [
    { price: 19.99, quantity: 2 },
    { price: 5.0, quantity: 3 },
  ];

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
    itemCount: 2,
    membershipLevel: "silver",
    taxRate: 0.06,
    beforeDiscount: 54.98,
    discounted: 50.58,
    tax: 3.03,
    total: 53.61,
  });

  const zeroTaxInvoice = calculateInvoice(items, "guest", 0);
  assert.deepStrictEqual(zeroTaxInvoice, {
    itemCount: 2,
    membershipLevel: "guest",
    taxRate: 0,
    beforeDiscount: 54.98,
    discounted: 54.98,
    tax: 0,
    total: 54.98,
  });
}

module.exports = {
  runPricingTests,
};
