const qs = (s, el=document) => el.querySelector(s);
const chatWidget = qs('#chatWidget');
// Support either a full-width demo button or a floating bubble
const launcher = qs('#chat-bubble') || qs('#toggleChat');
const closeBtn = qs('#closeChat');
const chatLog = qs('#chatLog');
const chatForm = qs('#chatForm');
const chatInput = qs('#chatInput');
const sendBtn = qs('#sendBtn');

let currentLang = localStorage.getItem('chat_lang'); // 'fi' | 'sv' | 'en'

function toggleChat(open) {
  const isOpen = open ?? chatWidget.getAttribute('aria-hidden') === 'true';
  if (!chatWidget) return;
  chatWidget.setAttribute('aria-hidden', isOpen ? 'false' : 'true');
  // Ensure visibility even if stylesheet fails to load
  if (isOpen) chatWidget.style.display = 'block';
  else chatWidget.style.display = '';
  if (launcher) {
    // If using the large demo button, toggle its text; if using floating bubble, hide when open
    if (launcher.id === 'toggleChat') {
      launcher.textContent = isOpen ? 'Close demo' : 'Launch demo';
    } else if (launcher.id === 'chat-bubble') {
      launcher.style.display = isOpen ? 'none' : 'flex';
    }
    launcher.setAttribute('aria-expanded', isOpen ? 'true' : 'false');
  }
  if (isOpen) {
    chatInput.focus();
    const hasMsgs = !!chatLog.querySelector('.msg');
    if (!hasMsgs) {
      // Always show language chooser at the start of a brand-new chat
      showLanguagePicker();
      setInputEnabled(false);
    } else if (!chatLog.dataset.welcomed && currentLang) {
      addBot(welcomeForLang(currentLang));
      chatLog.dataset.welcomed = "1";
    }
  }
}

if (launcher) launcher.addEventListener('click', () => toggleChat());
if (closeBtn) closeBtn.addEventListener('click', () => toggleChat(false));

function addMsg(text, who='bot', typing=false) {
  const wrap = document.createElement('div');
  wrap.className = `msg ${who}`;
  const bubble = document.createElement('div');
  bubble.className = 'bubble';
  bubble.textContent = text;
  if (typing) bubble.classList.add('typing');
  wrap.appendChild(bubble);
  chatLog.appendChild(wrap);
  chatLog.scrollTop = chatLog.scrollHeight;
  return bubble;
}

function addUser(text) { addMsg(text, 'user'); }
function addBot(text) { addMsg(text, 'bot'); }
function addBotHtml(html) {
  const wrap = document.createElement('div');
  wrap.className = 'msg bot';
  const bubble = document.createElement('div');
  bubble.className = 'bubble html';
  // Trim leading whitespace/newlines so we don't render extra space in pre-wrap bubbles
  bubble.innerHTML = html.trimStart();
  wrap.appendChild(bubble);
  chatLog.appendChild(wrap);
  chatLog.scrollTop = chatLog.scrollHeight;
}

function setTyping(on) {
  if (on) chatLog._typing = addMsg('Typing…', 'bot', true);
  else if (chatLog._typing) { chatLog._typing.parentElement.remove(); chatLog._typing = null; }
}

function setInputEnabled(enabled){
  chatInput.disabled = !enabled;
  sendBtn.disabled = !enabled;
}

function welcomeForLang(lang){
  switch(lang){
    case 'fi': return "Hei! Olen Piirakkabotti. Kysy tuotteista, aukioloajoista, menusta, tilauksista tai allergioista.";
    case 'sv': return "Hej! Jag är Piirakkabotti. Fråga om produkter, öppettider, meny, beställningar eller allergier.";
    default: return "Hi! I’m Piirakkabotti. Ask about products, opening hours, menu, orders, or allergies.";
  }
}

function showLanguagePicker(){
  const isMobile = window.matchMedia('(max-width: 520px)').matches;
  let html;
  if (isMobile) {
    // Mobile: flags only, horizontal layout
    html = `<div class="lang-picker mobile">
      <div class="lang-buttons">
        <button type="button" data-lang="fi" aria-label="Suomi"><span class="flag" aria-hidden="true">🇫🇮</span></button>
        <button type="button" data-lang="sv" aria-label="Svenska"><span class="flag" aria-hidden="true">🇸🇪</span></button>
        <button type="button" data-lang="en" aria-label="English"><span class="flag" aria-hidden="true">🇬🇧</span></button>
      </div>
    </div>`;
  } else {
    // Desktop: flags + labels, stacked
    html = `<div class="lang-picker">
      <div class="lang-title">Valitse kieli:</div>
      <div class="lang-buttons">
        <button type="button" data-lang="fi"><span class="flag" aria-hidden="true">🇫🇮</span><span>Suomi</span></button>
        <button type="button" data-lang="sv"><span class="flag" aria-hidden="true">🇸🇪</span><span>Svenska</span></button>
        <button type="button" data-lang="en"><span class="flag" aria-hidden="true">🇬🇧</span><span>English</span></button>
      </div>
    </div>`;
  }
  addBotHtml(html);
  const last = chatLog.querySelector('.lang-picker');
  if (last){
    last.addEventListener('click', (e)=>{
      const btn = e.target.closest('button[data-lang]');
      if (!btn) return;
      currentLang = btn.getAttribute('data-lang');
      localStorage.setItem('chat_lang', currentLang);
      // Show welcome in chosen language
      addBot(welcomeForLang(currentLang));
      chatLog.dataset.welcomed = "1";
      setInputEnabled(true);
      // Remove the language picker bubble after selection
      const container = last.closest('.msg');
      if (container) container.remove();
    });
  }
}

chatInput.addEventListener('keydown', (e) => {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    sendBtn.click();
  }
});

chatForm.addEventListener('submit', async (e) => {
  e.preventDefault();
  const text = chatInput.value.trim();
  if (!text) return;
  addUser(text);
  chatInput.value = '';
  setTyping(true);
  try {
    const res = await fetch('/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message: text, lang: currentLang || undefined })
    });
    if (!res.ok) throw new Error('Network error');
    const data = await res.json();
    setTyping(false);
    const reply = data.reply || '...';
    if (/^\s*</.test(reply) || reply.includes('order-ui')) {
      addBotHtml(reply);
    } else {
      addBot(reply);
    }
  } catch (err) {
    setTyping(false);
    addBot('Sorry, something went wrong. Please try again.');
    console.error(err);
  }
});
