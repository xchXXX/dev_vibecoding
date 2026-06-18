const { roundMoney } = require("./money");

const DISCOUNT_RATES = {
  gold: 0.15,
  silver: 0.08,
};

function subtotal(items) {
  let total = 0;

  for (const item of items) {
    total += item.price * item.quantity;
  }

  return roundMoney(total);
}

function getDiscountRate(membershipLevel) {
  return DISCOUNT_RATES[membershipLevel] || 0;
}

function applyDiscount(total, membershipLevel) {
  const discountRate = getDiscountRate(membershipLevel);
  return roundMoney(total * (1 - discountRate));
}

function calculateInvoice(items, membershipLevel, taxRate) {
  const beforeDiscount = subtotal(items);
  const discounted = applyDiscount(beforeDiscount, membershipLevel);
  const tax = roundMoney(discounted * taxRate);
  const total = roundMoney(discounted + tax);

  return {
    itemCount: items.length,
    membershipLevel,
    taxRate,
    beforeDiscount,
    discounted,
    tax,
    total,
  };
}

module.exports = {
  subtotal,
  getDiscountRate,
  applyDiscount,
  calculateInvoice,
};
