const MEMBERSHIP_DISCOUNT_RATES = Object.freeze({
  gold: 0.15,
  silver: 0.08,
});

function roundMoney(value) {
  return Math.round(value * 100) / 100;
}

function normalizeNumber(value) {
  const numericValue = Number(value);
  return Number.isFinite(numericValue) ? numericValue : 0;
}

function normalizeItems(items) {
  if (!Array.isArray(items)) {
    return [];
  }

  return items.map((item) => ({
    price: normalizeNumber(item && item.price),
    quantity: normalizeNumber(item && item.quantity),
  }));
}

function subtotal(items) {
  return roundMoney(
    normalizeItems(items).reduce(
      (total, item) => total + item.price * item.quantity,
      0
    )
  );
}

function resolveDiscountRate(membershipLevel) {
  return MEMBERSHIP_DISCOUNT_RATES[membershipLevel] || 0;
}

function applyDiscount(total, membershipLevel) {
  const discountRate = resolveDiscountRate(membershipLevel);
  return roundMoney(total * (1 - discountRate));
}

function calculateTax(total, taxRate) {
  return roundMoney(total * normalizeNumber(taxRate));
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
};
