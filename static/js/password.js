/* Roommate — перевірка пароля на сторінці реєстрації: 5 рівнів надійності, вимоги, збіг із підтвердженням,
 * показ/приховування. Це лише підказка в браузері: остаточну перевірку виконують валідатори Django на сервері
 * (config/password_validators.py). Додатково, з невеликою затримкою, пароль перевіряється тими самими
 * серверними валідаторами через /accounts/password-check/, щоб поширені паролі не вважалися надійними.
 * Без JavaScript форма працює як звичайна. */
(function (root) {
  "use strict";

  var LEVELS = ["Дуже слабкий", "Слабкий", "Середній", "Надійний", "Дуже надійний"];
  var MIN_LENGTH = 8;
  var REQUIREMENTS = [
    ["length", "Щонайменше 8 символів", "Збільште довжину пароля до 8 символів і більше."],
    ["lower", "Мала літера", "Додайте хоча б одну малу літеру."],
    ["upper", "Велика літера", "Додайте хоча б одну велику літеру."],
    ["digit", "Цифра", "Додайте хоча б одну цифру."],
    ["special", "Спеціальний символ (! ? # $ % -)", "Додайте хоча б один спеціальний символ (наприклад, ! ? # $ % -)."]
  ];

  // Найпоширеніші паролі для миттєвої перевірки. Повний перелік Django перевіряє сервер.
  var COMMON = ("password passw0rd passwd password1 password12 password123 qwerty qwerty1 qwerty12 qwerty123 qwertyuiop qwertyui " +
    "qazwsx qazwsxedc 1q2w3e 1q2w3e4r 1q2w3e4r5t 1qaz2wsx asdfgh asdfghjk asdfghjkl zxcvbn zxcvbnm 123456 1234567 12345678 123456789 " +
    "1234567890 12345 123123 123321 111111 000000 654321 666666 696969 112233 987654321 abc123 abcd1234 abcdef abcdefg abcdefgh " +
    "iloveyou iloveu letmein welcome welcome1 admin admin123 administrator root login master hello hello123 monkey dragon football " +
    "baseball soccer hockey batman superman sunshine princess shadow michael jordan jessica ashley charlie trustno1 secret freedom " +
    "whatever starwars pokemon minecraft changeme default guest test test123 temp temp123 user google facebook computer internet " +
    "samsung iphone ukraine ukraina slavaukraini kyiv lviv kharkiv odesa dnipro roommate " +
    "пароль пароль1 пароль123 йцукен йцукен123 привіт привет україна украина слава кохання люблютебе").split(" ");
  var COMMON_SET = {};
  COMMON.forEach(function (w) { COMMON_SET[w] = true; });
  var ROWS = ["qwertyuiop", "asdfghjkl", "zxcvbnm", "1234567890", "йцукенгшщзхї", "фівапролджє", "ячсмитьбю"];
  var LEET = { "0": "o", "1": "i", "3": "e", "4": "a", "5": "s", "7": "t", "@": "a", "$": "s", "!": "i" };

  function leet(s) { return s.split("").map(function (c) { return LEET[c] || c; }).join(""); }
  function reverse(s) { return s.split("").reverse().join(""); }

  function isCommon(password) {
    var low = password.toLowerCase();
    return [low, leet(low)].some(function (f) {
      var core = f.replace(/^[^\p{L}]+|[^\p{L}]+$/gu, "");   // «123Password!» → «password»
      if (COMMON_SET[f] || (core.length >= 5 && COMMON_SET[core])) return true;
      var letters = f.replace(/[^\p{L}]+/gu, "");
      return letters.length >= 5 && ROWS.some(function (r) { return r.indexOf(letters) !== -1 || reverse(r).indexOf(letters) !== -1; });
    });
  }

  function isRepeated(password) {
    for (var size = 1; size <= 4; size++) {
      if (password.length < size * 2 || password.length % size !== 0) continue;
      var chunk = password.slice(0, size), ok = true;
      for (var i = size; i < password.length; i += size) if (password.slice(i, i + size) !== chunk) { ok = false; break; }
      if (ok) return true;
    }
    return false;
  }

  // Скільки символів належить до послідовностей (abc, 4321) — вони майже не додають стійкості
  function sequenceChars(password) {
    var low = password.toLowerCase(), covered = [], i = 0, j, k;
    while (i < low.length - 2) {
      var d = low.charCodeAt(i + 1) - low.charCodeAt(i);
      if (Math.abs(d) === 1) {
        j = i + 1;
        while (j + 1 < low.length && low.charCodeAt(j + 1) - low.charCodeAt(j) === d) j++;
        if (j - i + 1 >= 3) for (k = i; k <= j; k++) covered[k] = true;
        i = j;
      } else i++;
    }
    return covered.filter(Boolean).length;
  }

  function personal(password, ctx) {
    if (!ctx) return false;
    var low = password.toLowerCase(), tokens = [], email = (ctx.email || "").toLowerCase().split("@")[0];
    if (email.length >= 3) tokens.push(email);
    [ctx.firstName, ctx.lastName].forEach(function (v) { v = (v || "").toLowerCase().trim(); if (v.length >= 3) tokens.push(v); });
    return tokens.some(function (t) { return low.indexOf(t) !== -1; });
  }

  /** Оцінка: {level: -1..4, rules, met, blocked, reason}. level -1 — порожнє поле. */
  function assess(password, ctx) {
    var rules = {
      length: password.length >= MIN_LENGTH,
      lower: /\p{Ll}/u.test(password), upper: /\p{Lu}/u.test(password),
      digit: /\p{Nd}/u.test(password), special: /[^\p{L}\p{N}\s]/u.test(password)
    };
    var met = REQUIREMENTS.every(function (r) { return rules[r[0]]; });
    if (!password) return { level: -1, rules: rules, met: false, blocked: false, reason: "" };

    var reason = "";
    if (/^\p{Nd}+$/u.test(password)) reason = "Пароль складається лише з цифр.";
    else if (isRepeated(password)) reason = "Пароль складається з повторень одного й того самого.";
    else if (isCommon(password)) reason = "Пароль надто очевидний або поширений: його легко підібрати.";
    else if (personal(password, ctx)) reason = "Пароль надто схожий на ваше ім’я чи пошту.";

    var pool = (rules.lower ? 26 : 0) + (rules.upper ? 26 : 0) + (rules.digit ? 10 : 0) + (rules.special ? 33 : 0);
    var seen = {}; password.split("").forEach(function (c) { seen[c] = true; });
    var uniq = Object.keys(seen).length;
    var effective = Math.max(0, uniq + 0.5 * (password.length - uniq) - 0.7 * sequenceChars(password));
    var bits = effective * (pool ? Math.log(pool) / Math.LN2 : 0);

    var level;
    if (reason || password.length < 6 || bits < 25) level = 0;
    else if (!met) level = 1;
    else if (bits < 45 || password.length < 10) level = 2;
    else if (bits < 60 || password.length < 12) level = 3;
    else level = 4;
    return { level: level, rules: rules, met: met, blocked: !!reason, reason: reason, bits: bits };
  }

  var api = { assess: assess, LEVELS: LEVELS, REQUIREMENTS: REQUIREMENTS };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  root.RoommatePassword = api;
  if (typeof document === "undefined") return;

  /* ------------------------------------------------------------------ інтерфейс */
  var EYE = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M2 12s3.6-6.5 10-6.5S22 12 22 12s-3.6 6.5-10 6.5S2 12 2 12z"/><circle cx="12" cy="12" r="3"/></svg>';
  var EYE_OFF = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M3 3l18 18"/><path d="M10.6 5.6A10.6 10.6 0 0 1 12 5.5C18.4 5.5 22 12 22 12a17 17 0 0 1-3.2 4M6.5 6.9A17 17 0 0 0 2 12s3.6 6.5 10 6.5c1.6 0 3-.4 4.3-1"/><path d="M9.9 9.9a3 3 0 0 0 4.2 4.2"/></svg>';
  var SERVER_BLOCKING = ["password_obvious", "password_too_common", "password_entirely_numeric", "password_too_similar"];

  function el(tag, cls, html) { var n = document.createElement(tag); if (cls) n.className = cls; if (html != null) n.innerHTML = html; return n; }

  function wrapWithToggle(input) {
    var wrap = el("div", "pw-input");
    input.parentNode.insertBefore(wrap, input);
    wrap.appendChild(input);
    var btn = el("button", "pw-toggle", EYE);
    btn.type = "button";
    btn.setAttribute("aria-label", "Показати пароль");
    btn.setAttribute("aria-pressed", "false");
    btn.addEventListener("click", function () {
      var show = input.type === "password";
      input.type = show ? "text" : "password";
      btn.innerHTML = show ? EYE_OFF : EYE;
      btn.setAttribute("aria-pressed", String(show));
      btn.setAttribute("aria-label", show ? "Сховати пароль" : "Показати пароль");
      input.focus({ preventScroll: true });
    });
    wrap.appendChild(btn);
    return wrap;
  }

  function init() {
    var main = document.querySelector('input[data-pw="main"]'), confirm = document.querySelector('input[data-pw="confirm"]');
    if (!main) return;
    var form = main.form, checkUrl = form && form.dataset.pwCheckUrl;
    var ctx = function () {
      var get = function (n) { var f = form.querySelector('[name="' + n + '"]'); return f ? f.value : ""; };
      return { email: get("email"), firstName: get("first_name"), lastName: get("last_name") };
    };

    var wrap = wrapWithToggle(main), meter = el("div", "pw-meter");
    meter.id = "pw-meter";
    meter.dataset.level = "-1";
    meter.innerHTML =
      '<div class="pw-track" role="progressbar" aria-label="Надійність пароля" aria-valuemin="0" aria-valuemax="100" aria-valuenow="0">' +
      '<div class="pw-fill"></div><span class="pw-tick" style="left:20%"></span><span class="pw-tick" style="left:40%"></span><span class="pw-tick" style="left:60%"></span><span class="pw-tick" style="left:80%"></span></div>' +
      '<div class="pw-status"><span class="pw-label" aria-live="polite">Введіть пароль</span><span class="pw-hint"></span></div>' +
      '<ul class="pw-rules"></ul><div class="pw-error" role="alert" hidden></div>';
    wrap.insertAdjacentElement("afterend", meter);
    main.setAttribute("aria-describedby", ((main.getAttribute("aria-describedby") || "") + " pw-meter").trim());
    var track = meter.querySelector(".pw-track"), label = meter.querySelector(".pw-label"), hint = meter.querySelector(".pw-hint");
    var list = meter.querySelector(".pw-rules"), errorBox = meter.querySelector(".pw-error"), items = {};
    REQUIREMENTS.forEach(function (r) {
      var li = el("li", "pw-rule", '<span class="pw-mark" aria-hidden="true"></span><span>' + r[1] + "</span>");
      li.dataset.state = "idle"; list.appendChild(li); items[r[0]] = li;
    });
    var server = { password: null, blocked: false, messages: [] }, timer = null, controller = null, ticket = 0;

    function state() {
      var a = assess(main.value, ctx()), fromServer = server.password === main.value && server.blocked;
      var level = a.level > 0 && fromServer ? 0 : a.level;
      return { a: a, level: level, reason: a.reason || (fromServer ? server.messages[0] || "Пароль надто очевидний або поширений." : "") };
    }

    function render() {
      var s = state(), has = !!main.value;
      meter.dataset.level = String(s.level);
      track.setAttribute("aria-valuenow", String(s.level < 0 ? 0 : (s.level + 1) * 20));
      track.setAttribute("aria-valuetext", s.level < 0 ? "Пароль не введено" : LEVELS[s.level]);
      label.textContent = s.level < 0 ? "Введіть пароль" : "Надійність: " + LEVELS[s.level];
      hint.textContent = has ? s.reason : "";
      REQUIREMENTS.forEach(function (r) { items[r[0]].dataset.state = !has ? "idle" : s.a.rules[r[0]] ? "ok" : "no"; });
      if (!errorBox.hidden && s.a.met && !s.reason) errorBox.hidden = true;
    }

    function remote() {
      if (!checkUrl) return;
      clearTimeout(timer);
      var password = main.value;
      if (!password) { server.password = null; return; }
      timer = setTimeout(function () {
        if (controller) controller.abort();
        controller = window.AbortController ? new AbortController() : null;
        var mine = ++ticket, c = ctx(), body = new URLSearchParams();
        body.set("password", password); body.set("email", c.email); body.set("first_name", c.firstName); body.set("last_name", c.lastName);
        var token = form.querySelector('[name="csrfmiddlewaretoken"]');
        fetch(checkUrl, { method: "POST", credentials: "same-origin", signal: controller ? controller.signal : undefined,
          headers: { "Content-Type": "application/x-www-form-urlencoded", "X-CSRFToken": token ? token.value : "" }, body: body.toString() })
          .then(function (r) { return r.ok ? r.json() : null; })
          .then(function (data) {
            if (!data || mine !== ticket || main.value !== password) return;
            var codes = data.codes || [];
            server = { password: password, messages: data.messages || [], blocked: SERVER_BLOCKING.some(function (x) { return codes.indexOf(x) !== -1; }) };
            render();
          }).catch(function () { /* офлайн: лишається локальна перевірка, сервер перевірить під час відправлення */ });
      }, 450);
    }

    main.addEventListener("input", function () { render(); remote(); });
    ["email", "first_name", "last_name"].forEach(function (n) {
      var f = form.querySelector('[name="' + n + '"]');
      if (f) f.addEventListener("input", function () { render(); remote(); });
    });

    var note = null;
    if (confirm) {
      wrapWithToggle(confirm);
      note = el("div", "pw-match"); note.setAttribute("aria-live", "polite");
      confirm.parentNode.insertAdjacentElement("afterend", note);
    }
    function renderMatch() {
      if (!note) return;
      var a = main.value, b = confirm.value;
      note.dataset.state = !b ? "idle" : a === b ? "ok" : "no";
      note.textContent = !b ? "" : a === b ? "Паролі збігаються" : "Паролі не збігаються";
    }
    if (confirm) { confirm.addEventListener("input", renderMatch); main.addEventListener("input", renderMatch); }

    // Не відправляємо форму, якщо пароль не проходить перевірку: показуємо причини й залишаємо кнопку активною.
    // main.js не вмикає спінер для скасованої події (defaultPrevented), тож кнопка лишається активною.
    form.addEventListener("submit", function (e) {
      var s = state(), problems = [];
      REQUIREMENTS.forEach(function (r) { if (!s.a.rules[r[0]]) problems.push(r[2]); });
      if (s.reason) problems.push(s.reason);
      if (confirm && main.value !== confirm.value) problems.push("Паролі не збігаються.");
      if (!main.value) problems = ["Введіть пароль."];
      if (!problems.length) return;
      e.preventDefault();
      errorBox.innerHTML = "<strong>Пароль не пройшов перевірку:</strong><ul>" + problems.map(function (p) { return "<li>" + p + "</li>"; }).join("") + "</ul>";
      errorBox.hidden = false;
      (confirm && main.value && main.value !== confirm.value && s.a.met && !s.reason ? confirm : main).focus();
    }, true);

    // Повернення на сторінку кнопкою «Назад» не повинно лишати кнопку заблокованою
    window.addEventListener("pageshow", function () {
      var btn = form.querySelector("button[type=submit]");
      if (btn) { btn.disabled = false; var sp = btn.querySelector(".spinner"); if (sp) sp.remove(); }
    });
    render(); renderMatch();
    if (main.value) remote();
  }

  document.addEventListener("DOMContentLoaded", init);
})(typeof window !== "undefined" ? window : globalThis);
