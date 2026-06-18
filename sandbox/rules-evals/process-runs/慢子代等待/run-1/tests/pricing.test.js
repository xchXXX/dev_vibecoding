const assert = require("assert");
const {
  subtotal,
  applyDiscount,
  calculateInvoice,
  normalizeMembershipLevel,
} = require("../src/pricing");
const { createInvoiceReportModel, renderInvoiceReport } = require("../src/report");
const { formatMoney } = require("../src/money");

function runPricingTests() {
  const standardItems = [
    { price: 19.99, quantity: 2 },
    { price: 5.0, quantity: 3 },
  ];

  assert.strictEqual(subtotal(standardItems), 54.98);
  assert.strictEqual(subtotal([]), 0);
  assert.strictEqual(applyDiscount(100, "gold"), 85);
  assert.strictEqual(applyDiscount(100, "silver"), 92);
  assert.strictEqual(applyDiscount(100, "guest"), 100);
  assert.strictEqual(applyDiscount(100, " GOLD "), 85);
  assert.strictEqual(normalizeMembershipLevel(" Silver "), "silver");
  assert.strictEqual(formatMoney(10), "10.00");

  const invoice = calculateInvoice(standardItems, "silver", 0.06);
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

  assert.throws(
    () => subtotal([{ price: -1, quantity: 1 }]),
    /non-negative number/
  );
  assert.throws(() => subtotal(null), /items must be an array/);

  const reportModel = createInvoiceReportModel("Mina", standardItems, "gold", 0.06);
  assert.deepStrictEqual(reportModel, {
    customerName: "Mina",
    itemCount: 2,
    beforeDiscount: "54.98",
    discounted: "46.73",
    tax: "2.80",
    total: "49.53",
  });

  const report = renderInvoiceReport("Mina", standardItems, "gold", 0.06);
  assert.ok(report.includes("Customer: Mina"));
  assert.ok(report.includes("Items: 2"));
  assert.ok(report.includes("Total: 49.53"));
}

module.exports = {
  runPricingTests,
};
