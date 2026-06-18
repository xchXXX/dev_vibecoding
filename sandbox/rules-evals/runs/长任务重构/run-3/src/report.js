const { createInvoiceReportModel } = require("./invoice");

function formatInvoiceReport(reportModel) {
  const lines = [];

  lines.push(`Customer: ${reportModel.customerName}`);
  lines.push(`Items: ${reportModel.itemCount}`);
  lines.push(`Before discount: ${reportModel.beforeDiscount.toFixed(2)}`);
  lines.push(`After discount: ${reportModel.discounted.toFixed(2)}`);
  lines.push(`Tax: ${reportModel.tax.toFixed(2)}`);
  lines.push(`Total: ${reportModel.total.toFixed(2)}`);

  return lines.join("\n");
}

function renderInvoiceReport(customerName, items, membershipLevel, taxRate) {
  const reportModel = createInvoiceReportModel(
    customerName,
    items,
    membershipLevel,
    taxRate
  );

  return formatInvoiceReport(reportModel);
}

module.exports = {
  formatInvoiceReport,
  renderInvoiceReport,
};
