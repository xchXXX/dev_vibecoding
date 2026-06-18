const { calculateInvoice } = require("./pricing");

function formatMoney(value) {
  return value.toFixed(2);
}

function buildReportLines(customerName, itemCount, invoice) {
  const lines = [];
  lines.push(`Customer: ${customerName}`);
  lines.push(`Items: ${itemCount}`);
  lines.push(`Before discount: ${formatMoney(invoice.beforeDiscount)}`);
  lines.push(`After discount: ${formatMoney(invoice.discounted)}`);
  lines.push(`Tax: ${formatMoney(invoice.tax)}`);
  lines.push(`Total: ${formatMoney(invoice.total)}`);

  return lines;
}

function renderInvoiceReport(customerName, items, membershipLevel, taxRate) {
  const invoice = calculateInvoice(items, membershipLevel, taxRate);
  const itemCount = Array.isArray(items) ? items.length : 0;

  return buildReportLines(customerName, itemCount, invoice).join("\n");
}

module.exports = {
  renderInvoiceReport,
};
