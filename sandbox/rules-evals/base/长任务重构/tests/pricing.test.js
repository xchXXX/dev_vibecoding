const assert = require("assert");
const { subtotal, applyDiscount, calculateInvoice } = require("../src/pricing");
const { renderInvoiceReport } = require("../src/report");

function runPricingTests() {
  const items = [
    { price: 19.99, quantity: 2 },
    { price: 5.0, quantity: 3 },
  ];

  assert.strictEqual(subtotal(items), 54.98);
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

  const report = renderInvoiceReport("Mina", items, "gold", 0.06);
  assert.ok(report.includes("Customer: Mina"));
  assert.ok(report.includes("Total: 49.53"));
}

module.exports = {
  runPricingTests,
};
