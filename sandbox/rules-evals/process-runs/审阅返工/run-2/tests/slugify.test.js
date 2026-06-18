const assert = require("assert");
const { slugify } = require("../src/slugify");

function runSlugifyTests() {
  assert.strictEqual(slugify("Hello World"), "hello-world");
  assert.strictEqual(slugify("  Keep   Calm  "), "keep-calm");
  assert.strictEqual(slugify("Alpha - Beta"), "alpha-beta");
  assert.strictEqual(slugify("__Hello__"), "hello");
  assert.strictEqual(slugify("a__b---c"), "a-b-c");
  assert.strictEqual(slugify("---A---"), "a");
}

module.exports = {
  runSlugifyTests,
};
