// Запуск: node static/js/tests/password.test.js
const assert = require("assert");
const { assess, LEVELS } = require("../password.js");
const lv = (p, ctx) => assess(p, ctx).level;

assert.deepStrictEqual(LEVELS, ["Дуже слабкий", "Слабкий", "Середній", "Надійний", "Дуже надійний"]);
assert.strictEqual(lv(""), -1);
assert.strictEqual(lv("abc"), 0);
for (const p of ["Password123!", "P@ssw0rd", "Qwerty123!", "Iloveyou1!", "Welcome1!", "Admin12345!", "Пароль123!", "12345678", "Aa1!Aa1!Aa1!"]) {
  assert.strictEqual(lv(p), 0, "очевидний пароль не може бути надійним: " + p);
}
assert.strictEqual(lv("Andriy#Koval9", { email: "a@x.com", firstName: "Andriy", lastName: "Koval" }), 0);
assert.strictEqual(lv("hotelxqmzvbk"), 1, "довгий, але не виконано вимоги");
assert.strictEqual(lv("abcdefghijkl"), 0, "послідовність");
assert.strictEqual(lv("Zx9!kLm2"), 2);
assert.strictEqual(lv("Mn8$vB3!xQ"), 3);
assert.strictEqual(lv("mV7#qRt9$wLp2"), 4);
const r = assess("abcDEF12").rules;
assert.deepStrictEqual([r.length, r.lower, r.upper, r.digit, r.special], [true, true, true, true, false]);
assert.strictEqual(assess("Zx9!kLm2").met, true);
assert.strictEqual(assess("Zx9kLm2p").met, false);
console.log("password.js: усі перевірки пройдено");
