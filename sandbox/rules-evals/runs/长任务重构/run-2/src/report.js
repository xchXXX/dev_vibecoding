const { calculateInvoice } = require("./pricing");
const {
  buildInvoiceReportLines,
  renderInvoiceLines,
} = require("./reportFormatter");

function renderInvoiceReport(customerName, items, membershipLevel, taxRate) {
  const invoice = calculateInvoice(items, membershipLevel, taxRate);
  const lines = buildInvoiceReportLines(customerName, items.length, invoice);
  return renderInvoiceLines(lines);
}

module.exports = {
  renderInvoiceReport,
};
