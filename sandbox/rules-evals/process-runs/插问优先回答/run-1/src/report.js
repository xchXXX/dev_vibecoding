const { calculateInvoice } = require("./invoice-calculator");
const { formatMoney } = require("./money");

function buildInvoiceReportModel(customerName, items, membershipLevel, taxRate) {
  const invoice = calculateInvoice(items, membershipLevel, taxRate);

  return {
    customerName,
    itemCount: invoice.itemCount,
    beforeDiscount: formatMoney(invoice.beforeDiscount),
    afterDiscount: formatMoney(invoice.discounted),
    tax: formatMoney(invoice.tax),
    total: formatMoney(invoice.total),
  };
}

function renderInvoiceReportFromModel(model) {
  const lines = [];

  lines.push(`Customer: ${model.customerName}`);
  lines.push(`Items: ${model.itemCount}`);
  lines.push(`Before discount: ${model.beforeDiscount}`);
  lines.push(`After discount: ${model.afterDiscount}`);
  lines.push(`Tax: ${model.tax}`);
  lines.push(`Total: ${model.total}`);

  return lines.join("\n");
}

function renderInvoiceReport(customerName, items, membershipLevel, taxRate) {
  return renderInvoiceReportFromModel(
    buildInvoiceReportModel(customerName, items, membershipLevel, taxRate)
  );
}

module.exports = {
  buildInvoiceReportModel,
  renderInvoiceReportFromModel,
  renderInvoiceReport,
};
