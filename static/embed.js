(() => {
  const script = document.currentScript || document.querySelector('script[data-ags-embed]');
  if (!script || !script.src) {
    console.error('AI Growth System embed: script source could not be determined.');
    return;
  }

  if (window.__AGS_CHUNK5_EMBED_LOADED__) return;
  window.__AGS_CHUNK5_EMBED_LOADED__ = true;

  const scriptUrl = new URL(script.src, document.baseURI);
  const apiBase = (script.dataset.apiBase || scriptUrl.origin).replace(/\/$/, '');
  const deploymentKey = script.dataset.agsDeployment || 'northstar-website-default';
  const chatEndpoint = `${apiBase}/embed-api/chat`;
  const storageKey = `ags.chunk5.embed.${deploymentKey}`;

  let state = loadState();

  function loadState() {
    try {
      const parsed = JSON.parse(localStorage.getItem(storageKey) || '{}');
      const messages = Array.isArray(parsed.messages)
        ? parsed.messages.filter((item) =>
            item &&
            (item.role === 'user' || item.role === 'assistant') &&
            typeof item.content === 'string' &&
            item.content.trim()
          )
        : [];
      const conversationId = typeof parsed.conversationId === 'string' ? parsed.conversationId : null;
      return { conversationId, messages };
    } catch {
      return { conversationId: null, messages: [] };
    }
  }

  function persistState() {
    try {
      localStorage.setItem(storageKey, JSON.stringify(state));
    } catch {
      // Server persistence remains authoritative even if browser storage is blocked.
    }
  }

  const host = document.createElement('div');
  host.id = 'ags-chat-embed';
  document.body.appendChild(host);
  const root = host.attachShadow({ mode: 'open' });

  root.innerHTML = `
    <style>
      :host { all: initial; }
      * { box-sizing: border-box; }
      .launcher {
        position: fixed; right: 22px; bottom: 22px; z-index: 2147483000;
        border: 0; border-radius: 999px; padding: 14px 18px;
        background: #17221c; color: white; font: 600 14px/1.2 system-ui, sans-serif;
        cursor: pointer; box-shadow: 0 14px 34px rgba(0,0,0,.22);
      }
      .panel {
        position: fixed; right: 22px; bottom: 82px; z-index: 2147483000;
        width: min(360px, calc(100vw - 28px)); height: min(520px, calc(100vh - 120px));
        background: #fff; color: #18201b; border: 1px solid rgba(23,34,28,.14);
        border-radius: 20px; overflow: hidden; box-shadow: 0 20px 55px rgba(0,0,0,.24);
        display: flex; flex-direction: column; font-family: system-ui, sans-serif;
      }
      .panel[hidden] { display: none; }
      .header { display:flex; align-items:center; justify-content:space-between; padding:16px; background:#f5f2e9; border-bottom:1px solid #e7e2d5; }
      .title { font-size:15px; font-weight:750; }
      .subtitle { margin-top:3px; font-size:12px; color:#647066; }
      .header-actions { display:flex; gap:6px; }
      .icon-button { border:0; background:transparent; cursor:pointer; font-size:12px; color:#4f5d53; padding:7px; border-radius:8px; }
      .icon-button:hover { background:rgba(23,34,28,.07); }
      .messages { flex:1; overflow:auto; padding:16px; background:#fbfaf6; }
      .empty { color:#657168; font-size:13px; line-height:1.5; padding:10px 4px; }
      .row { display:flex; margin:0 0 10px; }
      .row.user { justify-content:flex-end; }
      .bubble { max-width:82%; border-radius:16px; padding:10px 12px; font-size:13px; line-height:1.45; white-space:pre-wrap; overflow-wrap:anywhere; }
      .assistant .bubble { background:#fff; border:1px solid #e5e1d7; }
      .user .bubble { background:#17221c; color:#fff; }
      .error { min-height:18px; padding:0 14px; color:#a1342b; font-size:12px; background:#fff; }
      form { display:flex; gap:8px; padding:12px; border-top:1px solid #ebe7dd; background:#fff; }
      input { flex:1; min-width:0; border:1px solid #d9d4c9; border-radius:12px; padding:11px 12px; font:13px system-ui,sans-serif; outline:none; }
      input:focus { border-color:#6b7e70; box-shadow:0 0 0 3px rgba(107,126,112,.12); }
      .send { border:0; border-radius:12px; padding:0 14px; background:#17221c; color:#fff; font-weight:700; cursor:pointer; }
      .send:disabled { opacity:.55; cursor:default; }
      @media (max-width: 520px) {
        .launcher { right:14px; bottom:14px; }
        .panel { right:14px; bottom:72px; width:calc(100vw - 28px); height:min(520px, calc(100vh - 96px)); }
      }
    </style>
    <button class="launcher" type="button" aria-expanded="false">Ask us</button>
    <section class="panel" hidden aria-label="Website chat">
      <div class="header">
        <div>
          <div class="title">Northstar Botanics</div>
          <div class="subtitle">Ask about products, shipping, or returns</div>
        </div>
        <div class="header-actions">
          <button class="icon-button clear" type="button" title="Start a new conversation">New chat</button>
          <button class="icon-button close" type="button" title="Close chat">Close</button>
        </div>
      </div>
      <div class="messages"><div class="empty">Hi! What can I help you find?</div></div>
      <div class="error" role="status"></div>
      <form>
        <input maxlength="2000" autocomplete="off" placeholder="Type your question…" aria-label="Message" />
        <button class="send" type="submit">Send</button>
      </form>
    </section>
  `;

  const launcher = root.querySelector('.launcher');
  const panel = root.querySelector('.panel');
  const closeButton = root.querySelector('.close');
  const clearButton = root.querySelector('.clear');
  const form = root.querySelector('form');
  const input = root.querySelector('input');
  const sendButton = root.querySelector('.send');
  const messagesEl = root.querySelector('.messages');
  const emptyEl = root.querySelector('.empty');
  const errorEl = root.querySelector('.error');

  function renderMessage(role, content) {
    if (emptyEl) emptyEl.hidden = true;
    const row = document.createElement('div');
    row.className = `row ${role}`;
    const bubble = document.createElement('div');
    bubble.className = 'bubble';
    bubble.textContent = content;
    row.appendChild(bubble);
    messagesEl.appendChild(row);
    messagesEl.scrollTop = messagesEl.scrollHeight;
  }

  state.messages.forEach((item) => renderMessage(item.role, item.content));

  function addVisibleMessage(role, content) {
    state.messages.push({ role, content });
    persistState();
    renderMessage(role, content);
  }

  function open() {
    panel.hidden = false;
    launcher.setAttribute('aria-expanded', 'true');
    input.focus();
  }

  function close() {
    panel.hidden = true;
    launcher.setAttribute('aria-expanded', 'false');
    launcher.focus();
  }

  launcher.addEventListener('click', () => panel.hidden ? open() : close());
  closeButton.addEventListener('click', close);
  clearButton.addEventListener('click', () => {
    state = { conversationId: null, messages: [] };
    persistState();
    messagesEl.querySelectorAll('.row').forEach((row) => row.remove());
    if (emptyEl) emptyEl.hidden = false;
    errorEl.textContent = '';
    input.focus();
  });

  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    errorEl.textContent = '';
    const message = input.value.trim();
    if (!message) return;

    addVisibleMessage('user', message);
    input.value = '';
    sendButton.disabled = true;

    try {
      const response = await fetch(chatEndpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          deployment_key: deploymentKey,
          conversation_id: state.conversationId,
          message,
        }),
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(data.detail || `Request failed (${response.status}).`);
      state.conversationId = data.conversation_id;
      addVisibleMessage('assistant', data.answer);
    } catch (error) {
      errorEl.textContent = error && error.message ? error.message : 'Something went wrong.';
    } finally {
      sendButton.disabled = false;
      input.focus();
    }
  });
})();
