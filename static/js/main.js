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
    form.addEventListener("submit", () => {
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
});
