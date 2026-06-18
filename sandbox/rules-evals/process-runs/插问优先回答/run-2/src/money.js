function roundMoney(value) {
  return Math.round((value + Number.EPSILON) * 100) / 100;
}

function formatMoney(value) {
  return roundMoney(value).toFixed(2);
}

module.exports = {
  roundMoney,
  formatMoney,
};
