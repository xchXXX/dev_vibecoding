const { formatMoney } = require("./money");
const { calculateInvoice } = require("./pricing");

function createInvoiceReportModel(customerName, items, membershipLevel, taxRate) {
  const invoice = calculateInvoice(items, membershipLevel, taxRate);

  return {
    customerName,
    itemCount: items.length,
    beforeDiscount: formatMoney(invoice.beforeDiscount),
    discounted: formatMoney(invoice.discounted),
    tax: formatMoney(invoice.tax),
    total: formatMoney(invoice.total),
  };
}

function renderInvoiceReport(customerName, items, membershipLevel, taxRate) {
  const reportModel = createInvoiceReportModel(
    customerName,
    items,
    membershipLevel,
    taxRate
  );
  const lines = [];

  lines.push(`Customer: ${reportModel.customerName}`);
  lines.push(`Items: ${reportModel.itemCount}`);
  lines.push(`Before discount: ${reportModel.beforeDiscount}`);
  lines.push(`After discount: ${reportModel.discounted}`);
  lines.push(`Tax: ${reportModel.tax}`);
  lines.push(`Total: ${reportModel.total}`);

  return lines.join("\n");
}

module.exports = {
  createInvoiceReportModel,
  renderInvoiceReport,
};
