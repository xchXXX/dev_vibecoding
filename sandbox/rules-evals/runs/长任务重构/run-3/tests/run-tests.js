const { runPricingTests } = require("./pricing.test");
const { runInvoiceTests } = require("./invoice.test");
const { runReportTests } = require("./report.test");

try {
  runPricingTests();
  runInvoiceTests();
  runReportTests();
  console.log("ALL TESTS PASSED");
  process.exit(0);
} catch (error) {
  console.error(error && error.stack ? error.stack : String(error));
  process.exit(1);
}
