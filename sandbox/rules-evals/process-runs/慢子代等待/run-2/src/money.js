function roundMoney(value) {
  return Math.round(value * 100) / 100;
}

function assertFiniteNumber(value, message) {
  if (typeof value !== "number" || !Number.isFinite(value)) {
    throw new TypeError(message);
  }
}

function assertNonNegativeFiniteNumber(value, message) {
  assertFiniteNumber(value, message);
  if (value < 0) {
    throw new TypeError(message);
  }
}

module.exports = {
  roundMoney,
  assertFiniteNumber,
  assertNonNegativeFiniteNumber,
};
