const assert = require("assert");
const { slugify } = require("../src/slugify");

function runSlugifyTests() {
  assert.strictEqual(slugify("Hello World"), "hello-world");
  assert.strictEqual(slugify("  Keep   Calm  "), "keep-calm");
  assert.strictEqual(slugify("Alpha - Beta"), "alpha-beta");
  assert.strictEqual(slugify("Hello___World"), "hello-world");
  assert.strictEqual(slugify("---Hello---"), "hello");
  assert.strictEqual(slugify(" _ Hello - World _ "), "hello-world");
  assert.strictEqual(slugify("__Hello__World__"), "hello-world");
}

module.exports = {
  runSlugifyTests,
};
