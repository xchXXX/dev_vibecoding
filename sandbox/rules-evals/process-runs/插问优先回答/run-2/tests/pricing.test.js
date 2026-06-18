const assert = require("assert");
const {
  MEMBERSHIP_DISCOUNT_RATES,
  subtotal,
  getMembershipDiscountRate,
  calculateDiscountAmount,
  applyDiscount,
  calculateTax,
  calculateInvoice,
} = require("../src/pricing");
const { createInvoiceSummary } = require("../src/invoice");
const { renderInvoiceReport } = require("../src/report");

function runPricingTests() {
  const items = [
    { price: 19.99, quantity: 2 },
    { price: 5.0, quantity: 3 },
  ];

  assert.deepStrictEqual(MEMBERSHIP_DISCOUNT_RATES, {
    gold: 0.15,
    silver: 0.08,
  });

  assert.strictEqual(subtotal(items), 54.98);
  assert.strictEqual(subtotal([]), 0);

  assert.strictEqual(getMembershipDiscountRate("gold"), 0.15);
  assert.strictEqual(getMembershipDiscountRate("silver"), 0.08);
  assert.strictEqual(getMembershipDiscountRate("guest"), 0);

  assert.strictEqual(calculateDiscountAmount(100, "gold"), 15);
  assert.strictEqual(calculateDiscountAmount(54.98, "silver"), 4.4);
  assert.strictEqual(applyDiscount(100, "gold"), 85);
  assert.strictEqual(applyDiscount(100, "silver"), 92);
  assert.strictEqual(applyDiscount(100, "guest"), 100);

  assert.strictEqual(calculateTax(50.58, 0.06), 3.03);

  const invoice = calculateInvoice(items, "silver", 0.06);
  assert.deepStrictEqual(invoice, {
    beforeDiscount: 54.98,
    discountRate: 0.08,
    discountAmount: 4.4,
    discountedSubtotal: 50.58,
    tax: 3.03,
    total: 53.61,
  });

  const guestInvoice = calculateInvoice([], "guest", 0.06);
  assert.deepStrictEqual(guestInvoice, {
    beforeDiscount: 0,
    discountRate: 0,
    discountAmount: 0,
    discountedSubtotal: 0,
    tax: 0,
    total: 0,
  });

  const summary = createInvoiceSummary("Mina", items, "gold", 0.06);
  assert.deepStrictEqual(summary, {
    customerName: "Mina",
    membershipLevel: "gold",
    itemCount: 2,
    unitCount: 5,
    beforeDiscount: 54.98,
    discountRate: 0.15,
    discountAmount: 8.25,
    discountedSubtotal: 46.73,
    tax: 2.8,
    total: 49.53,
  });

  const report = renderInvoiceReport("Mina", items, "gold", 0.06);
  assert.ok(report.includes("Customer: Mina"));
  assert.ok(report.includes("Membership: gold"));
  assert.ok(report.includes("Discount amount: 8.25"));
  assert.ok(report.includes("After discount: 46.73"));
  assert.ok(report.includes("Total: 49.53"));
}

module.exports = {
  runPricingTests,
};
