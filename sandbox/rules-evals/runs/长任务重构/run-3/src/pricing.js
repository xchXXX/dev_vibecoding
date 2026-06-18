function roundMoney(value) {
  return Math.round(value * 100) / 100;
}

function subtotal(items) {
  let total = 0;
  for (const item of items) {
    total += item.price * item.quantity;
  }
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

function calculateInvoice(items, membershipLevel, taxRate) {
  const beforeDiscount = subtotal(items);
  const discounted = applyDiscount(beforeDiscount, membershipLevel);
  const tax = roundMoney(discounted * taxRate);
  const total = roundMoney(discounted + tax);

  return {
    beforeDiscount,
    discounted,
    tax,
    total,
  };
}

module.exports = {
  roundMoney,
  subtotal,
  getDiscountRate,
  applyDiscount,
  calculateInvoice,
};
