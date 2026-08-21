const apiStatus = document.getElementById('apiStatus');
const navItems = [...document.querySelectorAll('.nav-item')];
const views = [...document.querySelectorAll('.view')];
const conversationList = document.getElementById('conversationList');
const transcript = document.getElementById('transcript');
const transcriptHeader = document.getElementById('transcriptHeader');
const knowledgeList = document.getElementById('knowledgeList');
const actionStatus = document.getElementById('knowledgeActionStatus');

function formatDate(value) {
  if (!value) return '—';
  try { return new Date(value).toLocaleString(); } catch { return value; }
}

async function api(path, options = {}) {
  const response = await fetch(path, options);
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.detail || `Request failed (${response.status}).`);
  return data;
}

navItems.forEach((button) => {
  button.addEventListener('click', () => {
    navItems.forEach((item) => item.classList.toggle('active', item === button));
    views.forEach((view) => view.classList.toggle('active', view.id === button.dataset.target));
  });
});

async function loadHealth() {
  try {
    const data = await api('/api/health');
    apiStatus.textContent = `${data.provider} · ${data.database_backend} · ${data.embedding_provider}`;
    apiStatus.className = data.api_key_configured ? 'status ok' : 'status warn';
  } catch {
    apiStatus.textContent = 'API unavailable';
    apiStatus.className = 'status warn';
  }
}

async function loadOverview() {
  const data = await api('/owner-api/overview');
  document.getElementById('agentName').textContent = data.deployment.name;
  document.getElementById('agentStatus').textContent = `${data.deployment.status.toUpperCase()} · ${data.deployment.channel}`;
  document.getElementById('conversationCount').textContent = data.conversation_count;
  document.getElementById('knowledgeCount').textContent = data.knowledge_source_count;
}

async function loadConversations() {
  const data = await api('/owner-api/conversations');
  conversationList.innerHTML = '';
  if (!data.items.length) {
    conversationList.innerHTML = '<p class="empty-note">No conversations yet. Send a message through the external embed to create one.</p>';
    transcriptHeader.innerHTML = '<p class="empty-note">Select a conversation to view its transcript.</p>';
    transcript.innerHTML = '';
    return;
  }
  data.items.forEach((item) => {
    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'conversation-item';
    button.innerHTML = `
      <span class="item-top">
        <span class="item-origin"></span>
        <span class="item-count"></span>
      </span>
      <span class="item-meta"></span>
    `;
    button.querySelector('.item-origin').textContent = item.origin;
    button.querySelector('.item-count').textContent = `${item.message_count} msg`;
    button.querySelector('.item-meta').textContent = `${item.deployment_name} · ${formatDate(item.updated_at)}`;
    button.addEventListener('click', async () => {
      document.querySelectorAll('.conversation-item').forEach((node) => node.classList.remove('active'));
      button.classList.add('active');
      await loadTranscript(item.id);
    });
    conversationList.appendChild(button);
  });
}

async function loadTranscript(id) {
  const data = await api(`/owner-api/conversations/${encodeURIComponent(id)}`);
  transcriptHeader.innerHTML = '';
  const title = document.createElement('h3');
  title.className = 'transcript-title';
  title.textContent = data.origin;
  const meta = document.createElement('p');
  meta.className = 'transcript-meta';
  meta.textContent = `${data.deployment_name} · started ${formatDate(data.created_at)}`;
  transcriptHeader.append(title, meta);
  transcript.innerHTML = '';
  data.messages.forEach((message) => {
    const row = document.createElement('div');
    row.className = `message-row ${message.role}`;
    const bubble = document.createElement('div');
    bubble.className = 'message-bubble';
    bubble.textContent = message.content;
    row.appendChild(bubble);
    transcript.appendChild(row);
  });
}

async function loadKnowledge() {
  const data = await api('/owner-api/knowledge');
  knowledgeList.innerHTML = '';
  if (!data.items.length) {
    knowledgeList.innerHTML = '<p class="empty-note">No knowledge sources yet.</p>';
    return;
  }
  data.items.forEach((item) => {
    const row = document.createElement('div');
    row.className = 'source-item';
    const info = document.createElement('div');
    const title = document.createElement('div');
    title.className = 'source-title';
    title.textContent = item.title;
    const meta = document.createElement('div');
    meta.className = 'source-meta';
    const parts = [item.source_type, `${item.chunk_count} chunks`, item.status, formatDate(item.updated_at)];
    if (item.source_uri) parts.unshift(item.source_uri);
    parts.forEach((part) => {
      const span = document.createElement('span');
      span.textContent = part;
      meta.appendChild(span);
    });
    info.append(title, meta);
    const remove = document.createElement('button');
    remove.type = 'button';
    remove.className = 'delete-button';
    remove.textContent = 'Remove';
    remove.addEventListener('click', async () => {
      actionStatus.textContent = 'Removing…';
      try {
        await api(`/owner-api/knowledge/${encodeURIComponent(item.id)}`, { method: 'DELETE' });
        actionStatus.textContent = 'Removed';
        await Promise.all([loadKnowledge(), loadOverview()]);
      } catch (error) {
        actionStatus.textContent = error.message;
      }
    });
    row.append(info, remove);
    knowledgeList.appendChild(row);
  });
}

document.getElementById('refreshConversations').addEventListener('click', loadConversations);
document.getElementById('refreshKnowledge').addEventListener('click', loadKnowledge);

document.getElementById('manualKnowledgeForm').addEventListener('submit', async (event) => {
  event.preventDefault();
  actionStatus.textContent = 'Ingesting…';
  try {
    await api('/owner-api/knowledge/manual', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        title: document.getElementById('manualTitle').value.trim(),
        content: document.getElementById('manualContent').value.trim(),
      }),
    });
    document.getElementById('manualContent').value = '';
    actionStatus.textContent = 'Manual source ready';
    await Promise.all([loadKnowledge(), loadOverview()]);
  } catch (error) {
    actionStatus.textContent = error.message;
  }
});

document.getElementById('websiteKnowledgeForm').addEventListener('submit', async (event) => {
  event.preventDefault();
  actionStatus.textContent = 'Fetching and ingesting…';
  try {
    await api('/owner-api/knowledge/website', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        url: document.getElementById('websiteUrl').value.trim(),
        title: document.getElementById('websiteTitle').value.trim() || null,
      }),
    });
    document.getElementById('websiteUrl').value = '';
    document.getElementById('websiteTitle').value = '';
    actionStatus.textContent = 'Website source ready';
    await Promise.all([loadKnowledge(), loadOverview()]);
  } catch (error) {
    actionStatus.textContent = error.message;
  }
});

Promise.all([loadHealth(), loadOverview(), loadConversations(), loadKnowledge()]).catch((error) => {
  apiStatus.textContent = error.message;
  apiStatus.className = 'status warn';
});
