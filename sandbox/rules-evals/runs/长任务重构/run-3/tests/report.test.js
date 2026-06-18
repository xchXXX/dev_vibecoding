const assert = require("assert");
const { formatInvoiceReport, renderInvoiceReport } = require("../src/report");

function runReportTests() {
  assert.strictEqual(
    formatInvoiceReport({
      customerName: "Ava",
      itemCount: 0,
      beforeDiscount: 0,
      discounted: 0,
      tax: 0,
      total: 0,
    }),
    [
      "Customer: Ava",
      "Items: 0",
      "Before discount: 0.00",
      "After discount: 0.00",
      "Tax: 0.00",
      "Total: 0.00",
    ].join("\n")
  );

  const report = renderInvoiceReport(
    "Mina",
    [
      { price: 19.99, quantity: 2 },
      { price: 5.0, quantity: 3 },
    ],
    "gold",
    0.06
  );

  assert.ok(report.includes("Customer: Mina"));
  assert.ok(report.includes("Items: 2"));
  assert.ok(report.includes("Total: 49.53"));
}

module.exports = {
  runReportTests,
};
