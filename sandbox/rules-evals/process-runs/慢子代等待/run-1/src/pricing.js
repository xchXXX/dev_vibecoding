const { roundMoney } = require("./money");

const MEMBERSHIP_DISCOUNTS = {
  gold: 0.15,
  silver: 0.08,
};

function normalizeItems(items) {
  if (!Array.isArray(items)) {
    throw new TypeError("items must be an array");
  }

  return items.map((item, index) => {
    if (!item || typeof item !== "object") {
      throw new TypeError(`items[${index}] must be an object`);
    }

    const { price, quantity } = item;
    if (!Number.isFinite(price) || price < 0) {
      throw new TypeError(`items[${index}].price must be a non-negative number`);
    }
    if (!Number.isFinite(quantity) || quantity < 0) {
      throw new TypeError(`items[${index}].quantity must be a non-negative number`);
    }

    return { price, quantity };
  });
}

function normalizeMembershipLevel(membershipLevel) {
  return typeof membershipLevel === "string"
    ? membershipLevel.trim().toLowerCase()
    : "";
}

function subtotal(items) {
  const normalizedItems = normalizeItems(items);
  let total = 0;
  for (const item of normalizedItems) {
    total += item.price * item.quantity;
  }
  return roundMoney(total);
}

function applyDiscount(total, membershipLevel) {
  const normalizedMembershipLevel = normalizeMembershipLevel(membershipLevel);
  const discountRate = MEMBERSHIP_DISCOUNTS[normalizedMembershipLevel] || 0;
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
  subtotal,
  applyDiscount,
  calculateInvoice,
  normalizeMembershipLevel,
};
