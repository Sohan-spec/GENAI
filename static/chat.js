(function(){
  const panel = document.getElementById('chatPanel');
  const toggle = document.getElementById('chatToggle');
  const closeBtn = document.getElementById('chatClose');
  const contactsEl = document.getElementById('chatContacts');
  const headerEl = document.getElementById('chatHeader');
  const messagesEl = document.getElementById('chatMessages');
  const form = document.getElementById('chatForm');
  const input = document.getElementById('chatInput');

  if (!panel || !toggle || !contactsEl) return;

  let open = false;
  let activeContact = null;
  let pollTimer = null;

  function openPanel(){
    panel.style.transform = 'translateX(0)';
    panel.setAttribute('aria-hidden','false');
    open = true;
    // fetch contacts if empty
    if (!contactsEl.dataset.loaded) loadContacts();
  }
  function closePanel(){
    panel.style.transform = 'translateX(100%)';
    panel.setAttribute('aria-hidden','true');
    open = false;
    // stop polling on close
    if (pollTimer) { clearInterval(pollTimer); pollTimer = null; }
  }

  toggle.addEventListener('click', () => {
    if (open) closePanel(); else openPanel();
  });
  if (closeBtn) closeBtn.addEventListener('click', closePanel);
  // Auto-close on scroll
  window.addEventListener('scroll', () => { if (open) closePanel(); }, { passive: true });

  async function loadContacts(){
    try {
      const res = await fetch('/api/chat/contacts');
      if (!res.ok) {
        contactsEl.innerHTML = '<div style="padding:10px;" class="muted">No contacts. You can chat only with artists you both follow.</div>';
        return;
      }
      const contacts = await res.json();
      if (!Array.isArray(contacts) || !contacts.length) {
        contactsEl.innerHTML = '<div style="padding:10px;" class="muted">No contacts yet.</div>';
        return;
      }
      contactsEl.dataset.loaded = '1';
      contactsEl.innerHTML = contacts.map(name => `
        <button class="contact" data-name="${name}" style="
          display:block; width:100%; text-align:left; padding:12px 14px;
          border:none; border-bottom:1px solid var(--border);
          background: transparent !important; color: var(--text) !important;
          box-shadow: none !important; cursor:pointer; font-weight:600;
        ">${name}</button>
      `).join('');
      contactsEl.querySelectorAll('.contact').forEach(btn => {
        btn.addEventListener('click', () => {
          const name = btn.getAttribute('data-name');
          selectContact(name);
        });
      });
    } catch(e){
      contactsEl.innerHTML = '<div style="padding:10px; color:#e74c3c;">Error loading contacts</div>';
    }
  }

  async function selectContact(name){
    activeContact = name;
    headerEl.textContent = name;
    messagesEl.innerHTML = '';
    // mark selected in list
    contactsEl.querySelectorAll('.contact').forEach(b => {
      const selected = b.getAttribute('data-name') === name;
      b.style.background = selected ? 'rgba(0,0,0,0.06)' : 'transparent';
      b.style.color = selected ? 'var(--text-strong)' : 'var(--text)';
      b.style.fontWeight = selected ? '800' : '600';
    });
    await loadMessages();
    // start polling
    if (pollTimer) clearInterval(pollTimer);
    pollTimer = setInterval(loadMessages, 2500);
  }

  async function loadMessages(){
    if (!activeContact) return;
    try {
      const res = await fetch(`/api/chat/messages?with_user=${encodeURIComponent(activeContact)}&limit=200`);
      if (!res.ok) {
        messagesEl.innerHTML = '<div style="padding:10px;" class="muted">Not allowed or error.</div>';
        return;
      }
      const msgs = await res.json();
      messagesEl.innerHTML = msgs.map(m => renderMsg(m)).join('');
      messagesEl.scrollTop = messagesEl.scrollHeight;
    } catch(e){
      // ignore
    }
  }

  function renderMsg(m){
    const mine = (headerEl.dataset.me || '').toLowerCase() === (m.sender||'').toLowerCase();
    return `<div style="margin:6px 0; display:flex; ${mine?'justify-content:flex-end':'justify-content:flex-start'};">
      <div style="max-width:70%; padding:8px 10px; border-radius:12px; ${mine?'background: #e8f5ff;':'background:#f3f4f6;'} border:1px solid var(--border);">
        <div style="font-size:12px;color:#6b7280;margin-bottom:4px;">${m.sender}</div>
        <div style="white-space:pre-wrap;">${escapeHtml(m.content)}</div>
      </div>
    </div>`;
  }

  function escapeHtml(str){
    return String(str).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;').replace(/'/g,'&#039;');
  }

  if (form) {
    form.addEventListener('submit', async (e) => {
      e.preventDefault();
      const text = input.value.trim();
      if (!text || !activeContact) return;
      try {
        const res = await fetch('/api/chat/send', {
          method: 'POST',
          headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
          body: `to=${encodeURIComponent(activeContact)}&content=${encodeURIComponent(text)}`
        });
        if (res.ok) {
          input.value = '';
          await loadMessages();
        }
      } catch(e){}
    });
  }
})();
