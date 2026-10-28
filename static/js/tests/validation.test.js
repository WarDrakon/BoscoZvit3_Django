// Запуск: node static/js/tests/validation.test.js
const assert = require("assert");
const { validateName, validateBirthDate } = require("../validation.js");
const T = new Date(2026, 9, 26); // 26.10.2026

for (const ok of ["Іван", "Ан", "Анна-Марія", "Д’Артаньян", "Марія  Луїза", "Jean-Luc", "x".repeat(50)]) assert.strictEqual(validateName(ok), "", ok);
const bad = { "": "порожнім", "   ": "порожнім", "А": "щонайменше 2", "12": "цифр", "123 456": "цифр", "А1": "лише літери", "Ан@": "лише літери",
              "-Ан": "починатися", "А-": "дві літери", ["x".repeat(51)]: "довшим за 50" };
for (const [v, part] of Object.entries(bad)) assert.ok(validateName(v, "Ім’я").includes(part), JSON.stringify(v) + " → " + validateName(v));
assert.ok(validateName("А", "Прізвище").startsWith("Прізвище"));

assert.strictEqual(validateBirthDate("", T), "");
assert.strictEqual(validateBirthDate("2008-10-26", T), "", "рівно 18 сьогодні");
assert.strictEqual(validateBirthDate("1926-10-26", T), "", "рівно 100");
assert.ok(validateBirthDate("2026-10-27", T).includes("майбутньому"));
assert.ok(validateBirthDate("2008-10-27", T).includes("повнолітнім"));
assert.ok(validateBirthDate("1925-10-26", T).includes("100"));
assert.ok(validateBirthDate("1000-01-01", T).includes("100"));
assert.ok(validateBirthDate("2000-02-31", T).includes("не існує"));
console.log("validation.js: усі перевірки пройдено");
