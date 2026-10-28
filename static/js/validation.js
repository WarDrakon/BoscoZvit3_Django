/* Roommate — миттєва перевірка імені, прізвища та дати народження (реєстрація, акаунт, профіль).
 * Правила дублюють серверні з config/person_validators.py; остаточна перевірка завжди на сервері.
 * Поля підключаються атрибутами data-validate="name" | "birth-date". Без JavaScript форми працюють як раніше. */
(function (root) {
  "use strict";
  var NAME_MIN = 2, NAME_MAX = 50, AGE_MIN = 18, AGE_MAX = 100;

  function normalize(value) { return (value || "").split(/\s+/).filter(Boolean).join(" "); }

  /** Повертає текст помилки або "" для коректного імені. */
  function validateName(value, label) {
    var name = normalize(value);
    label = label || "Ім’я";
    if (!name) return label + " не може бути порожнім або складатися лише з пробілів.";
    if (/^[\p{Nd} ]+$/u.test(name)) return label + " не може складатися лише з цифр.";
    if (name.length < NAME_MIN) return label + " має містити щонайменше " + NAME_MIN + " символи.";
    if (name.length > NAME_MAX) return label + " не може бути довшим за " + NAME_MAX + " символів.";
    if (!/^[\p{L}\p{M} '’ʼ-]+$/u.test(name)) return label + " може містити лише літери, пробіли, дефіс і апостроф (без цифр і спецсимволів).";
    if ((name.match(/\p{L}/gu) || []).length < 2) return label + " має містити щонайменше дві літери.";
    if (!/^\p{L}/u.test(name) || !/[\p{L}\p{M}]$/u.test(name)) return label + " має починатися й закінчуватися літерою.";
    return "";
  }

  function ageOn(y, m, d, today) {
    var age = today.getFullYear() - y;
    if (today.getMonth() + 1 < m || (today.getMonth() + 1 === m && today.getDate() < d)) age--;
    return age;
  }

  /** value — рядок YYYY-MM-DD (як дає <input type="date">). Порожнє значення коректне (поле необов’язкове). */
  function validateBirthDate(value, today) {
    if (!value) return "";
    var m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value);
    if (!m) return "Вкажіть дату у форматі рік-місяць-день.";
    var y = +m[1], mo = +m[2], d = +m[3], check = new Date(y, mo - 1, d);
    if (check.getFullYear() !== y || check.getMonth() !== mo - 1 || check.getDate() !== d) return "Такої дати не існує.";
    today = today || new Date();
    var todayKey = today.getFullYear() * 10000 + (today.getMonth() + 1) * 100 + today.getDate();
    if (y * 10000 + mo * 100 + d > todayKey) return "Дата народження не може бути в майбутньому.";
    var age = ageOn(y, mo, d, today);
    if (age < AGE_MIN) return "Сервіс доступний лише повнолітнім: вік має бути від " + AGE_MIN + " років.";
    if (age > AGE_MAX) return "Вік не може перевищувати " + AGE_MAX + " років. Перевірте дату народження.";
    return "";
  }

  var api = { validateName: validateName, validateBirthDate: validateBirthDate, normalize: normalize };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  root.RoommateValidation = api;
  if (typeof document === "undefined") return;

  function messageFor(input) {
    var kind = input.dataset.validate;
    if (kind === "name") return validateName(input.value, input.dataset.label);
    if (kind === "birth-date") return validateBirthDate(input.value);
    return "";
  }

  function show(input, text) {
    var box = input.closest(".field").querySelector(".live-error");
    if (!box) {
      box = document.createElement("div");
      box.className = "live-error";
      box.id = input.id + "-live";
      box.setAttribute("role", "alert");
      input.closest(".field").appendChild(box);
    }
    box.textContent = text;
    box.hidden = !text;
    input.classList.toggle("is-invalid", !!text);
    if (text) { input.setAttribute("aria-invalid", "true"); input.setAttribute("aria-describedby", box.id); }
    else { input.removeAttribute("aria-invalid"); input.removeAttribute("aria-describedby"); }
  }

  document.addEventListener("DOMContentLoaded", function () {
    document.querySelectorAll("input[data-validate]").forEach(function (input) {
      var touched = false;
      var run = function () { show(input, messageFor(input)); };
      input.addEventListener("input", function () { touched = true; run(); });
      input.addEventListener("blur", function () { if (touched || input.value) run(); });
      input.addEventListener("change", run);
    });
    // Невалідні дані не відправляємо: показуємо причини; main.js не вмикає спінер, бо подію скасовано.
    document.querySelectorAll("form").forEach(function (form) {
      var fields = form.querySelectorAll("input[data-validate]");
      if (!fields.length) return;
      form.addEventListener("submit", function (e) {
        var first = null;
        fields.forEach(function (input) {
          var text = messageFor(input);
          show(input, text);
          if (text && !first) first = input;
        });
        if (first) { e.preventDefault(); first.focus(); }
      }, true);
    });
    window.addEventListener("pageshow", function () {
      document.querySelectorAll("form[data-loading] button[type=submit]").forEach(function (btn) {
        btn.disabled = false; var sp = btn.querySelector(".spinner"); if (sp) sp.remove();
      });
    });
  });
})(typeof window !== "undefined" ? window : globalThis);
