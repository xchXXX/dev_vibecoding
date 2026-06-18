const { roundMoney } = require("./money");

function calculateLineSubtotal(item) {
  return Number(item.price) * Number(item.quantity);
}

function subtotal(items) {
  const total = items.reduce((sum, item) => sum + calculateLineSubtotal(item), 0);
  return roundMoney(total);
}

function getDiscountRate(membershipLevel) {
  if (membershipLevel === "gold") {
    return 0.15;
  }

  if (membershipLevel === "silver") {
    return 0.08;
  }

  return 0;
}

function applyDiscount(total, membershipLevel) {
  const discountRate = getDiscountRate(membershipLevel);
  return roundMoney(total * (1 - discountRate));
}

function calculateTax(amount, taxRate) {
  return roundMoney(amount * taxRate);
}

function calculateInvoice(items, membershipLevel, taxRate) {
  const beforeDiscount = subtotal(items);
  const discounted = applyDiscount(beforeDiscount, membershipLevel);
  const tax = calculateTax(discounted, taxRate);
  const total = roundMoney(discounted + tax);

  return {
    beforeDiscount,
    discounted,
    tax,
    total,
  };
}

module.exports = {
  subtotal,
  applyDiscount,
  calculateInvoice,
  calculateLineSubtotal,
  getDiscountRate,
  calculateTax,
};
