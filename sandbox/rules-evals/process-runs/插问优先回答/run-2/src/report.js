const { createInvoiceSummary } = require("./invoice");
const { formatMoney } = require("./money");

function renderInvoiceReport(customerName, items, membershipLevel, taxRate) {
  const invoice = createInvoiceSummary(
    customerName,
    items,
    membershipLevel,
    taxRate
  );

  return [
    `Customer: ${invoice.customerName}`,
    `Membership: ${invoice.membershipLevel || "guest"}`,
    `Items: ${invoice.itemCount}`,
    `Units: ${invoice.unitCount}`,
    `Before discount: ${formatMoney(invoice.beforeDiscount)}`,
    `Discount amount: ${formatMoney(invoice.discountAmount)}`,
    `After discount: ${formatMoney(invoice.discountedSubtotal)}`,
    `Tax: ${formatMoney(invoice.tax)}`,
    `Total: ${formatMoney(invoice.total)}`,
  ].join("\n");
}

module.exports = {
  renderInvoiceReport,
};
