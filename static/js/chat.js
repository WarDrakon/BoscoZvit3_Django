// Приватний чат: Fetch API + періодичне опитування сервера (без WebSocket і Redis)
(() => {
  const root = document.getElementById("chat");
  if (!root) return;
  const log = document.getElementById("chat-log");
  const form = document.getElementById("chat-form");
  const input = document.getElementById("chat-input");
  const sendBtn = document.getElementById("chat-send");
  const status = document.getElementById("chat-status");
  const POLL_MS = 3000;
  const csrf = document.querySelector("[name=csrfmiddlewaretoken]").value;
  let lastId = 0;
  let lastDate = "";
  let polling = false;
  const bubbles = new Map();

  function addMessage(m) {
    if (bubbles.has(m.id)) return;
    if (m.date !== lastDate) {
      const day = document.createElement("div");
      day.className = "day";
      day.textContent = m.date;
      log.appendChild(day);
      lastDate = m.date;
    }
    const el = document.createElement("div");
    el.className = "bubble" + (m.mine ? " mine" : "");
    el.appendChild(document.createTextNode(m.text)); // текстовий вузол: без XSS
    const meta = document.createElement("small");
    meta.textContent = m.time + (m.mine ? (m.read ? " · прочитано" : " · надіслано") : "");
    el.appendChild(meta);
    log.appendChild(el);
    bubbles.set(m.id, { meta, mine: m.mine, time: m.time });
    lastId = Math.max(lastId, m.id);
  }

  function markRead(ids) {
    ids.forEach((id) => {
      const b = bubbles.get(id);
      if (b && b.mine) b.meta.textContent = b.time + " · прочитано";
    });
  }

  function setBlocked(blocked) {
    input.disabled = blocked;
    sendBtn.disabled = blocked;
    if (blocked) status.textContent = "Надсилання недоступне: один із користувачів заблокований.";
  }

  function scrollDown() { log.scrollTop = log.scrollHeight; }

  async function poll(initial) {
    if (polling) return;
    polling = true;
    try {
      const r = await fetch(`${root.dataset.messagesUrl}?after=${lastId}`, { headers: { Accept: "application/json" } });
      if (!r.ok) throw new Error("fetch");
      const data = await r.json();
      const nearBottom = log.scrollHeight - log.scrollTop - log.clientHeight < 80;
      data.messages.forEach(addMessage);
      markRead(data.read_ids);
      setBlocked(data.blocked);
      if (initial || (data.messages.length && nearBottom)) scrollDown();
      if (status.dataset.err) { status.textContent = ""; delete status.dataset.err; }
    } catch (e) {
      status.textContent = "Не вдалося оновити розмову. Спробуємо ще раз…";
      status.dataset.err = "1";
    } finally {
      polling = false;
    }
  }

  async function send() {
    const text = input.value.trim();
    if (!text) return;
    sendBtn.disabled = true;
    sendBtn.innerHTML = '<span class="spinner" aria-hidden="true"></span> Надсилання';
    status.textContent = "";
    try {
      const r = await fetch(root.dataset.sendUrl, {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-CSRFToken": csrf },
        body: JSON.stringify({ text }),
      });
      const data = await r.json();
      if (!r.ok) throw new Error(data.error || "Помилка надсилання");
      input.value = "";
      addMessage(data.message);
      scrollDown();
    } catch (e) {
      status.textContent = e.message;
    } finally {
      sendBtn.disabled = input.disabled;
      sendBtn.textContent = "Надіслати";
      input.focus();
    }
  }

  form.addEventListener("submit", (e) => { e.preventDefault(); send(); });
  input.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); }
  });
  poll(true);
  setInterval(() => { if (!document.hidden) poll(false); }, POLL_MS);
})();
