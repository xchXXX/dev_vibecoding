const { runSlugifyTests } = require("./slugify.test");

try {
  runSlugifyTests();
  console.log("ALL TESTS PASSED");
  process.exit(0);
} catch (error) {
  console.error(error && error.stack ? error.stack : String(error));
  process.exit(1);
}
