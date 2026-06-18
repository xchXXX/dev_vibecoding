const assert = require("assert");
const {
  subtotal,
  applyDiscount,
  calculateInvoice,
  getDiscountRate,
  calculateTax,
} = require("../src/pricing");
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
  assert.strictEqual(getDiscountRate("gold"), 0.15);
  assert.strictEqual(getDiscountRate("silver"), 0.08);
  assert.strictEqual(getDiscountRate("guest"), 0);
  assert.strictEqual(calculateTax(50.58, 0.06), 3.03);

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

  const emptyInvoice = calculateInvoice([], "guest", 0.06);
  assert.deepStrictEqual(emptyInvoice, {
    beforeDiscount: 0,
    discounted: 0,
    tax: 0,
    total: 0,
  });

  const roundedInvoice = calculateInvoice(
    [
      { price: 1.005, quantity: 1 },
      { price: 2.335, quantity: 1 },
    ],
    "guest",
    0.07
  );
  assert.deepStrictEqual(roundedInvoice, {
    beforeDiscount: 3.34,
    discounted: 3.34,
    tax: 0.23,
    total: 3.57,
  });

  const exactReport = renderInvoiceReport("Alex", [], "guest", 0.05);
  assert.strictEqual(
    exactReport,
    [
      "Customer: Alex",
      "Items: 0",
      "Before discount: 0.00",
      "After discount: 0.00",
      "Tax: 0.00",
      "Total: 0.00",
    ].join("\n")
  );
}

module.exports = {
  runPricingTests,
};
