function roundMoney(value) {
  return Math.round(value * 100) / 100;
}

function formatMoney(value) {
  return roundMoney(value).toFixed(2);
}

module.exports = {
  roundMoney,
  formatMoney,
};
