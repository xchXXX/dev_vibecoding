const { subtotal, applyDiscount, createInvoice } = require("./invoice");

function calculateInvoice(items, membershipLevel, taxRate) {
  return createInvoice(items, membershipLevel, taxRate);
}

module.exports = {
  subtotal,
  applyDiscount,
  calculateInvoice,
};
