const { roundMoney } = require("./money");

const MEMBERSHIP_DISCOUNT_RATES = Object.freeze({
  gold: 0.15,
  silver: 0.08,
});

function subtotal(items) {
  return roundMoney(
    items.reduce((total, item) => total + item.price * item.quantity, 0)
  );
}

function getMembershipDiscountRate(membershipLevel) {
  return MEMBERSHIP_DISCOUNT_RATES[membershipLevel] || 0;
}

function calculateDiscountAmount(total, membershipLevel) {
  return roundMoney(total * getMembershipDiscountRate(membershipLevel));
}

function applyDiscount(total, membershipLevel) {
  return roundMoney(total - calculateDiscountAmount(total, membershipLevel));
}

function calculateTax(total, taxRate) {
  return roundMoney(total * taxRate);
}

function calculateInvoice(items, membershipLevel, taxRate) {
  const beforeDiscount = subtotal(items);
  const discountRate = getMembershipDiscountRate(membershipLevel);
  const discountAmount = calculateDiscountAmount(beforeDiscount, membershipLevel);
  const discountedSubtotal = applyDiscount(beforeDiscount, membershipLevel);
  const tax = calculateTax(discountedSubtotal, taxRate);
  const total = roundMoney(discountedSubtotal + tax);

  return {
    beforeDiscount,
    discountRate,
    discountAmount,
    discountedSubtotal,
    tax,
    total,
  };
}

module.exports = {
  MEMBERSHIP_DISCOUNT_RATES,
  subtotal,
  getMembershipDiscountRate,
  calculateDiscountAmount,
  applyDiscount,
  calculateTax,
  calculateInvoice,
};
