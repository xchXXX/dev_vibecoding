const { formatMoney } = require("./money");

function buildInvoiceReportLines(customerName, itemCount, invoice) {
  return [
    `Customer: ${customerName}`,
    `Items: ${itemCount}`,
    `Before discount: ${formatMoney(invoice.beforeDiscount)}`,
    `After discount: ${formatMoney(invoice.discounted)}`,
    `Tax: ${formatMoney(invoice.tax)}`,
    `Total: ${formatMoney(invoice.total)}`,
  ];
}

function renderInvoiceLines(lines) {
  return lines.join("\n");
}

module.exports = {
  buildInvoiceReportLines,
  renderInvoiceLines,
};
