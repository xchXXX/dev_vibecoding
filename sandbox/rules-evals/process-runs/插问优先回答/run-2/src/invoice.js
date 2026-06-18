const { calculateInvoice } = require("./pricing");

function countItems(items) {
  return items.length;
}

function countUnits(items) {
  return items.reduce((total, item) => total + item.quantity, 0);
}

function createInvoiceSummary(customerName, items, membershipLevel, taxRate) {
  const pricing = calculateInvoice(items, membershipLevel, taxRate);

  return {
    customerName,
    membershipLevel,
    itemCount: countItems(items),
    unitCount: countUnits(items),
    ...pricing,
  };
}

module.exports = {
  createInvoiceSummary,
};
