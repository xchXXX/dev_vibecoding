const { calculateInvoice } = require("./pricing");

function renderInvoiceReport(customerName, items, membershipLevel, taxRate) {
  const invoice = calculateInvoice(items, membershipLevel, taxRate);
  const lines = [];

  lines.push(`Customer: ${customerName}`);
  lines.push(`Items: ${items.length}`);
  lines.push(`Before discount: ${invoice.beforeDiscount.toFixed(2)}`);
  lines.push(`After discount: ${invoice.discounted.toFixed(2)}`);
  lines.push(`Tax: ${invoice.tax.toFixed(2)}`);
  lines.push(`Total: ${invoice.total.toFixed(2)}`);

  return lines.join("\n");
}

module.exports = {
  renderInvoiceReport,
};
