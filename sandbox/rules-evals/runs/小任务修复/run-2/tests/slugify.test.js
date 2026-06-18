const assert = require("assert");
const { slugify } = require("../src/slugify");

function runSlugifyTests() {
  assert.strictEqual(slugify("Hello World"), "hello-world");
  assert.strictEqual(slugify("  Keep   Calm  "), "keep-calm");
  assert.strictEqual(slugify("Alpha - Beta"), "alpha-beta");
}

module.exports = {
  runSlugifyTests,
};
