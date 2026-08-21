const launcher = document.getElementById('chatLauncher');
const widget = document.getElementById('chatWidget');
const closeButton = document.getElementById('chatClose');
const clearButton = document.getElementById('clearStoreConversation');
const form = document.getElementById('storeChatForm');
const messageInput = document.getElementById('storeMessage');
const sendButton = document.getElementById('storeSendButton');
const conversation = document.getElementById('storeConversation');
const emptyState = document.getElementById('storeEmptyState');
const errorEl = document.getElementById('storeError');

const STORE_MESSAGES_KEY = 'ags.chunk3.storeConversationMessages';
const MAX_MODEL_HISTORY = 8;

// Controlled demo knowledge only. Chunk 3 intentionally keeps knowledge static/manual
// and sends it through the already-validated /api/chat request contract.
const STORE_BUSINESS_KNOWLEDGE = `Brand: Northstar Botanics

Products:
- Cloud Cream — $28 — rich daily moisturizer for dry skin.
- Clear Gel — $24 — lightweight daily moisturizer for oily skin.

Shipping: Orders usually arrive in 2–4 business days.
Returns: Unopened products can be returned within 30 days of delivery.
Support: hello@northstar.example

Do not claim either product treats acne, eczema, rosacea, or any medical condition. No information about discounts, international shipping, ingredients, stock availability, or guarantees has been provided.`;

let messages = loadMessages();

function loadMessages() {
  try {
    const saved = JSON.parse(localStorage.getItem(STORE_MESSAGES_KEY) || '[]');
    if (!Array.isArray(saved)) return [];
    return saved.filter((item) =>
      item &&
      (item.role === 'user' || item.role === 'assistant') &&
      typeof item.content === 'string' &&
      item.content.trim()
    );
  } catch {
    return [];
  }
}

function persistMessages() {
  localStorage.setItem(STORE_MESSAGES_KEY, JSON.stringify(messages));
}

function renderMessage(role, text) {
  if (emptyState) emptyState.style.display = 'none';
  const row = document.createElement('div');
  row.className = `store-message-row ${role === 'assistant' ? 'assistant' : 'user'}`;

  const bubble = document.createElement('div');
  bubble.className = 'store-message';
  bubble.textContent = text;
  row.appendChild(bubble);

  conversation.appendChild(row);
  conversation.scrollTop = conversation.scrollHeight;
}

function addAndPersistMessage(role, content) {
  messages.push({ role, content });
  persistMessages();
  renderMessage(role, content);
}

function renderSavedConversation() {
  if (!messages.length) return;
  messages.forEach((item) => renderMessage(item.role, item.content));
}

function recentHistory() {
  return messages.slice(-MAX_MODEL_HISTORY);
}

function openWidget() {
  widget.hidden = false;
  launcher.setAttribute('aria-expanded', 'true');
  launcher.classList.add('is-open');
  messageInput.focus();
}

function closeWidget() {
  widget.hidden = true;
  launcher.setAttribute('aria-expanded', 'false');
  launcher.classList.remove('is-open');
  launcher.focus();
}

launcher.addEventListener('click', () => {
  if (widget.hidden) openWidget();
  else closeWidget();
});

closeButton.addEventListener('click', closeWidget);

clearButton.addEventListener('click', () => {
  messages = [];
  localStorage.removeItem(STORE_MESSAGES_KEY);
  conversation.querySelectorAll('.store-message-row').forEach((row) => row.remove());
  if (emptyState) emptyState.style.display = '';
  errorEl.textContent = '';
  messageInput.focus();
});

form.addEventListener('submit', async (event) => {
  event.preventDefault();
  errorEl.textContent = '';

  const message = messageInput.value.trim();
  if (!message) return;

  // Capture history before storing this turn so the current user message is not duplicated.
  const historyForModel = recentHistory();
  addAndPersistMessage('user', message);
  messageInput.value = '';
  sendButton.disabled = true;

  try {
    const response = await fetch('/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        business_knowledge: STORE_BUSINESS_KNOWLEDGE,
        history: historyForModel,
        message,
      }),
    });

    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || 'Request failed.');
    addAndPersistMessage('assistant', data.answer);
  } catch (error) {
    errorEl.textContent = error.message || 'Something went wrong.';
  } finally {
    sendButton.disabled = false;
    messageInput.focus();
  }
});

renderSavedConversation();
