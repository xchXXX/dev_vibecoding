const assert = require("assert");
const { subtotal, applyDiscount, calculateInvoice } = require("../src/pricing");
const { renderInvoiceReport } = require("../src/report");

function runPricingTests() {
  const items = [
    { price: 19.99, quantity: 2 },
    { price: 5.0, quantity: 3 },
  ];

  assert.strictEqual(subtotal(items), 54.98);
  assert.strictEqual(subtotal([]), 0);
  assert.strictEqual(applyDiscount(100, "gold"), 85);
  assert.strictEqual(applyDiscount(100, "silver"), 92);
  assert.strictEqual(applyDiscount(100, "guest"), 100);
  assert.strictEqual(applyDiscount(100, undefined), 100);

  const invoice = calculateInvoice(items, "silver", 0.06);
  assert.deepStrictEqual(invoice, {
    beforeDiscount: 54.98,
    discounted: 50.58,
    tax: 3.03,
    total: 53.61,
  });

  const roundedInvoice = calculateInvoice(
    [{ price: 0.335, quantity: 3 }],
    "guest",
    0.05
  );
  assert.deepStrictEqual(roundedInvoice, {
    beforeDiscount: 1.01,
    discounted: 1.01,
    tax: 0.05,
    total: 1.06,
  });

  const emptyInvoice = calculateInvoice([], "gold", 0.2);
  assert.deepStrictEqual(emptyInvoice, {
    beforeDiscount: 0,
    discounted: 0,
    tax: 0,
    total: 0,
  });

  const report = renderInvoiceReport("Mina", items, "gold", 0.06);
  const lines = report.split("\n");
  assert.deepStrictEqual(lines, [
    "Customer: Mina",
    "Items: 2",
    "Before discount: 54.98",
    "After discount: 46.73",
    "Tax: 2.80",
    "Total: 49.53",
  ]);
}

module.exports = {
  runPricingTests,
};
