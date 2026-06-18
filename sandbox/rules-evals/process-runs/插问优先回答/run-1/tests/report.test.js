const assert = require("assert");
const {
  buildInvoiceReportModel,
  renderInvoiceReport,
  renderInvoiceReportFromModel,
} = require("../src/report");

function runReportTests() {
  const items = [
    { price: 19.99, quantity: 2 },
    { price: 5.0, quantity: 3 },
  ];

  const model = buildInvoiceReportModel("Mina", items, "gold", 0.06);
  assert.deepStrictEqual(model, {
    customerName: "Mina",
    itemCount: 2,
    beforeDiscount: "54.98",
    afterDiscount: "46.73",
    tax: "2.80",
    total: "49.53",
  });

  const renderedFromModel = renderInvoiceReportFromModel(model);
  assert.strictEqual(
    renderedFromModel,
    [
      "Customer: Mina",
      "Items: 2",
      "Before discount: 54.98",
      "After discount: 46.73",
      "Tax: 2.80",
      "Total: 49.53",
    ].join("\n")
  );

  assert.strictEqual(
    renderInvoiceReport("Mina", items, "gold", 0.06),
    renderedFromModel
  );
}

module.exports = {
  runReportTests,
};
