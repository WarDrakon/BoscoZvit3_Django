document.addEventListener("DOMContentLoaded", () => {
  const toggle = document.querySelector(".nav-toggle");
  const links = document.querySelector(".nav-links");
  if (toggle && links) {
    toggle.addEventListener("click", () => {
      const open = links.classList.toggle("open");
      toggle.setAttribute("aria-expanded", String(open));
    });
  }
  // Тінь шапки при прокрутці
  const nav = document.querySelector(".nav");
  if (nav) {
    const onScroll = () => nav.classList.toggle("scrolled", window.scrollY > 8);
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
  }
  // Плавна поява блоків; при prefers-reduced-motion CSS показує все одразу
  const targets = document.querySelectorAll(
    "main .cand, main .listing, main .feature, main .process li, main .scenario, main .stat, main .cta, main .section-head, main .card.demo, main .row-item"
  );
  const show = (el) => el.classList.add("in");
  if ("IntersectionObserver" in window && !window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
    const io = new IntersectionObserver((entries) => {
      entries.forEach((e) => { if (e.isIntersecting) { show(e.target); io.unobserve(e.target); } });
    }, { threshold: 0.12, rootMargin: "0px 0px -6% 0px" });
    targets.forEach((el, i) => {
      el.classList.add("reveal");
      el.style.setProperty("--d", `${(i % 6) * 70}ms`);
      io.observe(el);
    });
    setTimeout(() => targets.forEach(show), 2500); // страховка: нічого не лишається прихованим
  } else {
    targets.forEach(show);
  }
  // Стан завантаження: блокуємо кнопку після відправлення форми, щоб уникнути дублів
  document.querySelectorAll("form[data-loading]").forEach((form) => {
    form.addEventListener("submit", (e) => {
      if (e.defaultPrevented) return; // форму зупинила клієнтська перевірка — кнопку не блокуємо
      const btn = form.querySelector("button[type=submit]");
      if (btn) {
        btn.insertAdjacentHTML("afterbegin", '<span class="spinner" aria-hidden="true"></span> ');
        setTimeout(() => { btn.disabled = true; }, 0);
      }
    });
  });
  document.querySelectorAll("form[data-confirm]").forEach((form) => {
    form.addEventListener("submit", (e) => {
      if (!window.confirm(form.dataset.confirm)) e.preventDefault();
    });
  });
  initDemoCard();
});

// Hero: кілька прикладів результату змінюються по колу. Перший приклад уже відрендерено на сервері (SSR),
// тож без JS сторінка повна; при prefers-reduced-motion автоматичної зміни немає, лишаються кнопки-крапки.
function initDemoCard() {
  const card = document.getElementById("demo-card");
  const raw = document.getElementById("demo-variants");
  if (!card || !raw || card.dataset.ready) return;
  card.dataset.ready = "1"; // повторна ініціалізація не дублює крапки й таймер
  let variants;
  try { variants = JSON.parse(raw.textContent); } catch (e) { return; }
  if (!Array.isArray(variants) || variants.length < 2) return;
  const $ = (id) => document.getElementById(id);
  const rows = card.querySelectorAll(".demo-row");
  const dots = $("demo-dots");
  const reduce = !!(window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches);
  let index = 0, timer = null, userPicked = false;

  const level = (n) => (n >= 75 ? "" : n >= 50 ? "mid" : "bad");
  function render(v) {
    $("demo-avatar").textContent = v.initial;
    $("demo-avatar").style.background = `linear-gradient(135deg, ${v.grad[0]}, ${v.grad[1]})`;
    $("demo-name").textContent = v.name;
    $("demo-meta").textContent = v.meta;
    $("demo-score").textContent = `${v.score}%`;
    const ring = $("demo-ring");
    ring.style.setProperty("--p", v.score);
    ring.classList.toggle("mid", v.score < 75 && v.score >= 50);
    ring.classList.toggle("low", v.score < 50);
    v.rows.forEach(([label, value], i) => {
      const row = rows[i]; if (!row) return;
      row.querySelector("[data-label]").textContent = label;
      row.querySelector("[data-value]").textContent = `${value}%`;
      const bar = row.querySelector(".bar"), fill = row.querySelector("[data-bar]");
      bar.className = `bar ${level(value)}`.trim();
      fill.style.animation = "none"; fill.style.width = `${value}%`; void fill.offsetWidth; fill.style.animation = "";
    });
    $("demo-note").lastElementChild.textContent = v.note;
    dots.querySelectorAll("button").forEach((b, i) => b.setAttribute("aria-pressed", String(i === index)));
  }
  function show(i, instant) {
    index = (i + variants.length) % variants.length;
    if (instant || reduce) { render(variants[index]); return; }
    card.classList.add("fading");
    setTimeout(() => { render(variants[index]); card.classList.remove("fading"); }, 240);
  }
  variants.forEach((v, i) => {
    const b = document.createElement("button");
    b.type = "button"; b.setAttribute("aria-label", `Показати приклад: ${v.name}`);
    b.setAttribute("aria-pressed", String(i === 0));
    b.addEventListener("click", () => { userPicked = true; stop(); show(i); });
    dots.appendChild(b);
  });
  function start() { if (!reduce && !userPicked && !timer) timer = setInterval(() => show(index + 1), 5500); }
  function stop() { clearInterval(timer); timer = null; }
  card.addEventListener("mouseenter", stop); card.addEventListener("mouseleave", start);
  card.addEventListener("focusin", stop); card.addEventListener("focusout", start);
  document.addEventListener("visibilitychange", () => (document.hidden ? stop() : start()));
  start();
}
