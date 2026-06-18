const { calculateInvoice } = require("./pricing");

function createInvoiceReportModel(customerName, items, membershipLevel, taxRate) {
  const invoice = calculateInvoice(items, membershipLevel, taxRate);

  return {
    customerName,
    itemCount: items.length,
    beforeDiscount: invoice.beforeDiscount,
    discounted: invoice.discounted,
    tax: invoice.tax,
    total: invoice.total,
  };
}

module.exports = {
  createInvoiceReportModel,
};
