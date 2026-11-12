/* Run with: node js/tests/test-product-color-detection.cjs */
"use strict";
const assert = require("node:assert/strict");
const { analyzePixels, nameColor } = require("../product-color-detection.js");
let checks = 0;
function check(condition, description) { assert.ok(condition, description); checks++; }
function rgb(hex) { return hex.match(/[a-f\d]{2}/gi).map((part) => parseInt(part, 16)); }
function photograph(color, background = "#fafafa", transparent = false) {
  const width = 120, height = 192, data = new Uint8ClampedArray(width * height * 4);
  function box(left, top, right, bottom, hex, alpha = 255) {
    const values = rgb(hex);
    for (let y = Math.floor(top * height); y < bottom * height; y++) for (let x = Math.floor(left * width); x < right * width; x++) data.set([...values, alpha], (y * width + x) * 4);
  }
  box(0, 0, 1, 1, background, transparent ? 0 : 255);
  box(.42, .06, .60, .22, "#cc967c"); // A face must not become a garment swatch.
  box(.27, .28, .73, .84, color);
  box(.22, .40, .28, .59, "#cc967c");
  box(.72, .40, .78, .59, "#cc967c");
  box(.09, .65, .25, .80, "#443025"); // A dark handbag outside the garment region.
  return { data, width, height, box };
}
function estimate(fixture, options) { return analyzePixels(fixture.data, fixture.width, fixture.height, options); }

for (const [hex, label] of [["#7b233b", "Burgundy"], ["#172b4d", "Navy"], ["#f0e7d7", "Ivory"], ["#222222", "Black"], ["#493027", "Brown"], ["#1a6753", "Green"]]) {
  const fixture = photograph(hex), result = estimate(fixture);
  check(result?.name === label && result.confidence >= .55, `${label} garment is distinguished from skin, accessories and white background`);
  check(result.hex === hex, `${label} swatch comes from the image's actual pixels`);
}
for (const background of ["#171b23", "#dfd8c8", "#627c81"]) {
  const result = estimate(photograph("#7b233b", background));
  check(result?.name === "Burgundy", "The same garment keeps its color on a different backdrop");
}
const blank = photograph("#fafafa"); blank.box(0, 0, 1, 1, "#fafafa");
check(estimate(blank) === null, "A blank background does not invent a product color");
const transparent = photograph("#172b4d", "#ffffff", true);
check(estimate(transparent)?.name === "Navy", "Transparent-background product images are supported");
const patterned = photograph("#7b233b"); patterned.box(.5, .28, .73, .84, "#2255bb");
check(estimate(patterned) === null, "Equally strong competing colors need manual review");
const jacket = photograph("#eee6dd");
jacket.box(.27, .25, .43, .43, "#493027"); jacket.box(.58, .25, .73, .43, "#493027");
check(estimate(jacket, { productName: "The Tailored Jacket" })?.name === "Brown", "Jacket context targets the upper panels rather than the styled trousers");
check(estimate(jacket, { productName: "The Burgundy Tailored Jacket" })?.name === "Brown", "Color words in a product name never determine the answer");
check(analyzePixels([], 120, 192) === null && analyzePixels([], 0, 0) === null, "Malformed and empty pixel buffers fail safely");
check(nameColor(119, 119, 119) === "Grey" && nameColor(199, 173, 145) === "Beige", "Neutral colors have readable fashion labels");
check(nameColor(70, 43, 38) === "Brown" && nameColor(124, 84, 76) === "Brown", "Warm espresso and mocha shades remain brown rather than burgundy");
check(nameColor(90, 28, 44) === "Burgundy" && nameColor(105, 29, 32) === "Burgundy", "Merlot and deep red remain burgundy rather than brown");
console.log(JSON.stringify({ passed: checks }));
