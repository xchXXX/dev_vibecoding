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

function applyDiscount(total, membershipLevel) {
  if (membershipLevel === "gold") {
    return roundMoney(total * 0.85);
  }
  if (membershipLevel === "silver") {
    return roundMoney(total * 0.92);
  }
  return roundMoney(total);
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
  subtotal,
  applyDiscount,
  calculateInvoice,
};
