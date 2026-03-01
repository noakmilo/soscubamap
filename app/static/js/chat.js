function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll("\"", "&quot;")
    .replaceAll("'", "&#39;");
}

function linkify(text) {
  const escaped = escapeHtml(text);
  const urlRegex = /(https?:\/\/[^\s]+)/g;
  return escaped.replace(urlRegex, (url) => {
    return `<a href="${url}" target="_blank" rel="noopener">${url}</a>`;
  });
}

async function fetchChat() {
  const res = await fetch("/api/chat");
  return await res.json();
}

async function sendChatMessage(nickname, body) {
  const res = await fetch("/api/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ nickname, body }),
  });
  return await res.json();
}

let initialLoad = true;

function renderChat(payload) {
  const container = document.getElementById("chatMessages");
  if (!container) return;
  const items = payload?.items || [];
  const onlineCount = payload?.online_count;
  const onlineEl = document.getElementById("chatOnlineCount");
  if (onlineEl && typeof onlineCount !== "undefined") {
    onlineEl.textContent = onlineCount;
  }

  const nearBottom =
    container.scrollHeight - container.scrollTop - container.clientHeight < 40;

  if (!items.length) {
    container.innerHTML = `<div class="chat-empty">Sin mensajes aún.</div>`;
    return;
  }

  container.innerHTML = items
    .map((msg) => {
      const time = msg.created_at ? new Date(msg.created_at).toLocaleString("es-ES") : "";
      return `
        <div class="chat-item">
          <div class="chat-meta">
            <span class="chat-author">${escapeHtml(msg.author || "Anon")}</span>
            <span class="chat-time">${time}</span>
          </div>
          <div class="chat-body-line">${linkify(msg.body || "")}</div>
        </div>
      `;
    })
    .join("");

  if (initialLoad || nearBottom) {
    container.scrollTop = container.scrollHeight;
  }
  initialLoad = false;
}

document.addEventListener("DOMContentLoaded", () => {
  const form = document.getElementById("chatForm");
  const nickInput = document.getElementById("chatNick");
  const messageInput = document.getElementById("chatMessage");

  const refresh = async () => {
    try {
      const payload = await fetchChat();
      renderChat(payload);
    } catch (e) {
      // no-op
    }
  };

  if (form) {
    form.addEventListener("submit", async (e) => {
      e.preventDefault();
      const nickname = nickInput?.value.trim() || "Anon";
      const body = messageInput?.value.trim();
      if (!body) return;
      await sendChatMessage(nickname, body);
      messageInput.value = "";
      await refresh();
      messageInput.focus();
    });
  }

  refresh();
  setInterval(refresh, 7000);
});
