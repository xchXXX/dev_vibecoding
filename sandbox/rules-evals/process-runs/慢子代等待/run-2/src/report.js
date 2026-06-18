const { createInvoice } = require("./invoice");

function renderInvoice(invoice) {
  const lines = [];

  lines.push(`Customer: ${invoice.customerName}`);
  lines.push(`Membership: ${invoice.membershipLevel}`);
  lines.push(`Items: ${invoice.itemCount}`);
  lines.push(`Before discount: ${invoice.beforeDiscount.toFixed(2)}`);
  lines.push(`After discount: ${invoice.discounted.toFixed(2)}`);
  lines.push(`Tax: ${invoice.tax.toFixed(2)}`);
  lines.push(`Total: ${invoice.total.toFixed(2)}`);

  return lines.join("\n");
}

function renderInvoiceReport(customerName, items, membershipLevel, taxRate) {
  const invoice = createInvoice(items, membershipLevel, taxRate, customerName);
  return renderInvoice(invoice);
}

module.exports = {
  renderInvoice,
  renderInvoiceReport,
};
