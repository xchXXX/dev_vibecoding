const assert = require("assert");
const { createInvoiceReportModel } = require("../src/invoice");

function runInvoiceTests() {
  const items = [
    { price: 12.5, quantity: 1 },
    { price: 3.25, quantity: 4 },
  ];

  assert.deepStrictEqual(
    createInvoiceReportModel("Mina", items, "gold", 0.06),
    {
      customerName: "Mina",
      itemCount: 2,
      beforeDiscount: 25.5,
      discounted: 21.68,
      tax: 1.3,
      total: 22.98,
    }
  );
}

module.exports = {
  runInvoiceTests,
};
