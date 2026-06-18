const {
  roundMoney,
  assertFiniteNumber,
  assertNonNegativeFiniteNumber,
} = require("./money");

function normalizeItems(items) {
  if (!Array.isArray(items)) {
    throw new TypeError("Items must be an array.");
  }

  return items.map((item) => {
    if (!item || typeof item !== "object") {
      throw new TypeError("Each item must be an object.");
    }

    assertFiniteNumber(item.price, "Item price must be a finite number.");
    assertNonNegativeFiniteNumber(
      item.quantity,
      "Item quantity must be a non-negative finite number."
    );

    return {
      price: item.price,
      quantity: item.quantity,
    };
  });
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
  assertFiniteNumber(total, "Total must be a finite number.");

  if (membershipLevel === "gold") {
    return roundMoney(total * 0.85);
  }
  if (membershipLevel === "silver") {
    return roundMoney(total * 0.92);
  }

  return roundMoney(total);
}

function createInvoice(items, membershipLevel, taxRate, customerName = "") {
  assertNonNegativeFiniteNumber(
    taxRate,
    "Tax rate must be a non-negative finite number."
  );

  const normalizedItems = normalizeItems(items);
  const beforeDiscount = subtotal(normalizedItems);
  const discounted = applyDiscount(beforeDiscount, membershipLevel);
  const tax = roundMoney(discounted * taxRate);
  const total = roundMoney(discounted + tax);

  return {
    customerName,
    itemCount: normalizedItems.length,
    beforeDiscount,
    discounted,
    tax,
    total,
    membershipLevel,
    taxRate,
  };
}

module.exports = {
  normalizeItems,
  subtotal,
  applyDiscount,
  createInvoice,
};
