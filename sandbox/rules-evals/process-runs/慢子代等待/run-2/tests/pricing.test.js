const assert = require("assert");
const { subtotal, applyDiscount, calculateInvoice } = require("../src/pricing");
const { renderInvoiceReport } = require("../src/report");

function assertThrows(fn, expectedMessage) {
  assert.throws(fn, (error) => {
    assert.ok(error instanceof TypeError);
    assert.strictEqual(error.message, expectedMessage);
    return true;
  });
}

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

  const invoice = calculateInvoice(items, "silver", 0.06);
  assert.deepStrictEqual(invoice, {
    customerName: "",
    itemCount: 2,
    beforeDiscount: 54.98,
    discounted: 50.58,
    tax: 3.03,
    total: 53.61,
    membershipLevel: "silver",
    taxRate: 0.06,
  });

  const guestInvoice = calculateInvoice([{ price: 10, quantity: 1 }], "guest", 0);
  assert.deepStrictEqual(guestInvoice, {
    customerName: "",
    itemCount: 1,
    beforeDiscount: 10,
    discounted: 10,
    tax: 0,
    total: 10,
    membershipLevel: "guest",
    taxRate: 0,
  });

  const report = renderInvoiceReport("Mina", items, "gold", 0.06);
  assert.strictEqual(
    report,
    [
      "Customer: Mina",
      "Membership: gold",
      "Items: 2",
      "Before discount: 54.98",
      "After discount: 46.73",
      "Tax: 2.80",
      "Total: 49.53",
    ].join("\n")
  );

  assertThrows(
    () => subtotal([{ price: "19.99", quantity: 1 }]),
    "Item price must be a finite number."
  );
  assertThrows(
    () => calculateInvoice([{ price: 5, quantity: -1 }], "guest", 0.06),
    "Item quantity must be a non-negative finite number."
  );
  assertThrows(
    () => calculateInvoice(items, "guest", -0.1),
    "Tax rate must be a non-negative finite number."
  );
}

module.exports = {
  runPricingTests,
};
