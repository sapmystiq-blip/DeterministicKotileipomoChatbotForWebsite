const qs = (s, el=document) => el.querySelector(s);
const chatWidget = qs('#chatWidget');
// Support either a full-width demo button or a floating bubble
const launcher = qs('#chat-bubble') || qs('#toggleChat');
const closeBtn = qs('#closeChat');
const chatLog = qs('#chatLog');
const chatForm = qs('#chatForm');
const chatInput = qs('#chatInput');
const sendBtn = qs('#sendBtn');
const chatCard = qs('.chat-card');
if (chatCard) chatCard.classList.add('readonly');
if (chatForm) {
  chatForm.setAttribute('aria-hidden', 'true');
}
if (chatInput) {
  chatInput.disabled = true;
  chatInput.setAttribute('aria-hidden', 'true');
  chatInput.setAttribute('tabindex', '-1');
}
if (sendBtn) {
  sendBtn.disabled = true;
  sendBtn.setAttribute('aria-hidden', 'true');
  sendBtn.setAttribute('tabindex', '-1');
}

let currentLang = localStorage.getItem('chat_lang') || 'fi'; // default to Finnish
// Answer display flags (deterministic vs RAG). If both true → show both.
let showLegacy = false;
let showRag = true;
try {
  const params = new URLSearchParams(window.location.search);
  const lsRag = localStorage.getItem('show_rag');
  if (lsRag != null) showRag = (lsRag === '1' || lsRag === 'true');
  if (params.has('legacy')) showLegacy = !['0','false','no','off'].includes((params.get('legacy')||'').toLowerCase());
  if (params.has('rag')) showRag = !['0','false','no','off'].includes((params.get('rag')||'').toLowerCase());
  if (!showLegacy && !showRag) showRag = true; // ensure at least one answer
} catch(e) {}
// Persist default language immediately so backend receives a cookie hint as well
if (!localStorage.getItem('chat_lang')) {
  try {
    localStorage.setItem('chat_lang', currentLang);
    document.cookie = `chat_lang=${currentLang}; path=/; max-age=${60*60*24*30}`;
  } catch(e) {}
}
let pickupHoursCache = null;
let orderConstraintsCache = null; // { min_lead_minutes, max_days }
const ORDER_ONLINE_URL = 'https://rakaskotileipomo.fi/verkkokauppa';

function updateChatViewportUnit(){
  try {
    const vh = window.innerHeight * 0.01;
    document.documentElement.style.setProperty('--chat-vh', `${vh}px`);
  } catch (err) {
    // no-op
  }
}
updateChatViewportUnit();
window.addEventListener('resize', updateChatViewportUnit);
window.addEventListener('orientationchange', updateChatViewportUnit);

// Simple i18n helper for order flow
const I18N = {
  fi: {
    start_choose_category: 'Aloitetaan tilaus. Valitse ensin kategoria.',
    choose_category: 'Valitse kategoria',
    categories_unavailable: 'Tuotekategoriat eivät ole saatavilla juuri nyt.',
    products_unavailable: 'Tuotteita ei voitu ladata.',
    no_products_in_category: 'Ei tuotteita kategoriassa:',
    add: 'Lisää',
    cart_title: 'Ostoskori',
    cart_empty: 'Ei tuotteita',
    continue_shopping: 'Jatka ostoksia',
    go_checkout: 'Siirry kassalle',
    ask_name: 'Nimi',
    ask_email: 'Sähköposti',
    ask_email_optional: '(valinnainen)',
    ask_phone: 'Puhelin',
    ask_date: 'Valitse noutopäivä',
    ask_time: 'Valitse noutoaika',
    ask_note: 'Lisätieto',
    next: 'Seuraava',
    back: 'Takaisin',
    submit_order: 'Lähetä tilaus',
    order_ok: 'Kiitos! Tilaus vastaanotettu. Vahvistusnumero:',
    order_fail: 'Valitettavasti tilauksen luonti epäonnistui.',
    order_fail_reason: 'Syy:',
    invalid_pickup_time: 'Valittu noutoaika ei ole mahdollinen:',
    invalid_pickup_format: 'tarkista muoto YYYY-MM-DDTHH:MM',
    in_stock: 'Varastossa',
    out_of_stock: 'Loppu varastosta',
    add_items_first: 'Lisää tuotteita ensin.',
    view_cart: 'Näytä ostoskori',
    remove: 'Poista',
    clear_cart: 'Tyhjennä ostoskori',
    confirm_clear_cart: 'Tyhjennetäänkö koko ostoskori?',
    confirm_remove_item: 'Poistetaanko tuote ostoskorista?',
    order_notice_fi_only: 'Huomio: Tuotenimet ja kuvaukset näkyvät suomeksi. Tilauksen voit tehdä valitsemallasi kielellä.',
    taught_ok: 'Tallennettu. Käytän tätä jatkossa.'
    ,
    feedback_header: 'Jaa palautetta',
    feedback_prompt: 'Kerro meille, miten voimme parantaa. Viestisi menee suoraan leipomotiimille.',
    feedback_message: 'Palaute',
    feedback_submit: 'Lähetä palaute',
    feedback_placeholder: 'Kirjoita palautteesi tähän…',
    thanks_feedback: 'Kiitos palautteestasi!'
  },
  sv: {
    start_choose_category: 'Vi börjar beställningen. Välj kategori.',
    choose_category: 'Välj kategori',
    categories_unavailable: 'Produktkategorier är inte tillgängliga just nu.',
    products_unavailable: 'Produkter kunde inte laddas.',
    no_products_in_category: 'Inga produkter i kategori:',
    add: 'Lägg till',
    cart_title: 'Varukorg',
    cart_empty: 'Inga produkter',
    continue_shopping: 'Fortsätt handla',
    go_checkout: 'Till kassan',
    ask_name: 'Namn',
    ask_email: 'E‑post',
    ask_email_optional: '(valfritt)',
    ask_phone: 'Telefon',
    ask_date: 'Välj avhämtningsdag',
    ask_time: 'Välj avhämtnings tid',
    ask_note: 'Tilläggsinformation',
    next: 'Nästa',
    back: 'Tillbaka',
    submit_order: 'Skicka beställning',
    order_ok: 'Tack! Beställning mottagen. Ordernummer:',
    order_fail: 'Tyvärr misslyckades beställningen.',
    order_fail_reason: 'Orsak:',
    invalid_pickup_time: 'Vald avhämtnings tid är inte möjlig:',
    invalid_pickup_format: 'kontrollera formatet ÅÅÅÅ-MM-DDTT:MM',
    in_stock: 'I lager',
    out_of_stock: 'Slut i lager',
    add_items_first: 'Lägg till produkter först.',
    view_cart: 'Visa varukorg',
    remove: 'Ta bort',
    clear_cart: 'Töm varukorgen',
    confirm_clear_cart: 'Vill du tömma hela varukorgen?',
    confirm_remove_item: 'Ta bort produkten från varukorgen?',
    order_notice_fi_only: 'Observera: Produktnamn och beskrivningar visas på finska. Du kan slutföra beställningen på ditt valda språk.',
    taught_ok: 'Sparat. Jag kommer att använda detta framöver.'
    ,
    feedback_header: 'Dela feedback',
    feedback_prompt: 'Berätta hur vi kan bli bättre. Ditt meddelande går direkt till bageriteamet.',
    feedback_message: 'Feedback',
    feedback_submit: 'Skicka feedback',
    feedback_placeholder: 'Skriv ditt meddelande här…',
    thanks_feedback: 'Tack för din feedback!'
  },
  en: {
    start_choose_category: 'Let’s start your order. Choose a category.',
    choose_category: 'Choose a category',
    categories_unavailable: 'Categories are not available right now.',
    products_unavailable: 'Could not load products.',
    no_products_in_category: 'No products in category:',
    add: 'Add',
    cart_title: 'Cart',
    cart_empty: 'No items',
    continue_shopping: 'Continue shopping',
    go_checkout: 'Checkout',
    ask_name: 'Name',
    ask_email: 'Email',
    ask_email_optional: '(optional)',
    ask_phone: 'Phone',
    ask_date: 'Choose pickup date',
    ask_time: 'Choose pickup time',
    ask_note: 'Additional note',
    next: 'Next',
    back: 'Back',
    submit_order: 'Place order',
    order_ok: 'Thanks! Order received. Confirmation number:',
    order_fail: 'Sorry, order could not be created.',
    order_fail_reason: 'Reason:',
    invalid_pickup_time: 'Selected pickup time is not available:',
    invalid_pickup_format: 'check format YYYY-MM-DDTHH:MM',
    in_stock: 'In stock',
    out_of_stock: 'Out of stock',
    add_items_first: 'Add some items first.',
    view_cart: 'View cart',
    remove: 'Remove',
    clear_cart: 'Clear cart',
    confirm_clear_cart: 'Clear all items from the cart?',
    confirm_remove_item: 'Remove this item from the cart?',
    order_notice_fi_only: 'Note: Product names and descriptions are shown in Finnish. You can complete your order in your selected language.',
    taught_ok: 'Learned. I will use this going forward.'
    ,
    feedback_header: 'Share your feedback',
    feedback_prompt: 'Tell us how we can improve. Your message goes straight to the bakery team.',
    feedback_message: 'Feedback',
    feedback_submit: 'Send feedback',
    feedback_placeholder: 'Write your message here…',
    thanks_feedback: 'Thank you for your feedback!'
  }
};
function tr(key){ const lang = (currentLang||'fi'); return (I18N[lang]&&I18N[lang][key]) || I18N.en[key] || key; }

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
    if (!chatLog.dataset.welcomed) {
      addBot(welcomeForLang(currentLang));
      chatLog.dataset.welcomed = "1";
    }
    renderFaqRoot();
  }
}

if (launcher) launcher.addEventListener('click', () => toggleChat());
if (closeBtn) closeBtn.addEventListener('click', () => toggleChat(false));
document.addEventListener('keydown', (e) => {
  if (e.key === 'Escape' && chatWidget && chatWidget.getAttribute('aria-hidden') === 'false') {
    toggleChat(false);
  }
});

// Order flow v2: categories → products → cart → guided checkout
chatLog.addEventListener('click', async (e) => {
  const backToRootBtn = e.target.closest('[data-action="back-to-root"]');
  if (backToRootBtn) {
    e.preventDefault();
    renderFaqMainMenu();
    return;
  }
  const openFaqRootBtn = e.target.closest('[data-action="open-faq-root"]');
  if (openFaqRootBtn) {
    e.preventDefault();
    await renderFaqTopicMenu();
    return;
  }
  const rootMenuBtn = e.target.closest('[data-action="root-open-menu"]');
  if (rootMenuBtn) {
    e.preventDefault();
    await openFaqPath(['menu']);
    return;
  }
  const rootFaqBtn = e.target.closest('[data-action="root-open-faq"]');
  if (rootFaqBtn) {
    e.preventDefault();
    await renderFaqTopicMenu();
    return;
  }
  const rootOrderingBtn = e.target.closest('[data-action="root-open-ordering"]');
  if (rootOrderingBtn) {
    e.preventDefault();
    await renderOrderingHub();
    return;
  }
  const rootFeedbackBtn = e.target.closest('[data-action="root-open-feedback"]');
  if (rootFeedbackBtn) {
    e.preventDefault();
    renderFeedbackPanel();
    return;
  }
  const faqPathBtn = e.target.closest('[data-faq-path]');
  if (faqPathBtn) {
    e.preventDefault();
    const targetPath = parsePath(faqPathBtn.getAttribute('data-faq-path') || '');
    try {
      await openFaqPath(targetPath);
    } catch (err) {
      console.error(err);
      renderFaqError(trFaq('loadError'), faqState.currentPath || []);
    }
    return;
  }
  const menuFreshBtn = e.target.closest('[data-action="menu-show-fresh"]');
  if (menuFreshBtn) {
    e.preventDefault();
    try {
      await renderMenuTuoreetDetail();
    } catch (err) {
      console.error(err);
      renderFaqError(trFaq('loadError'), ['menu','menu-tuoreet']);
    }
    return;
  }
  const menuFrozenBtn = e.target.closest('[data-action="menu-show-frozen"]');
  if (menuFrozenBtn) {
    e.preventDefault();
    try {
      await renderMenuPakasteDetail();
    } catch (err) {
      console.error(err);
      renderFaqError(trFaq('loadError'), ['menu','menu-pakasteet']);
    }
    return;
  }
  const orderOnlineBtn = e.target.closest('[data-action="menu-order-online"]');
  if (orderOnlineBtn) {
    e.preventDefault();
    try {
      window.open(ORDER_ONLINE_URL, '_blank', 'noopener');
    } catch (err) {
      console.error(err);
    }
    return;
  }
  const orderChatBtn = e.target.closest('[data-action="menu-order-chat"]');
  if (orderChatBtn) {
    e.preventDefault();
    startOrderFlow();
    return;
  }
  const dietItemBtn = e.target.closest('[data-diet-item]');
  if (dietItemBtn) {
    e.preventDefault();
    if (dietItemBtn.disabled) {
      return;
    }
    const groupId = dietItemBtn.getAttribute('data-diet-group') || '';
    const itemId = dietItemBtn.getAttribute('data-diet-item') || '';
    showDietItem(groupId, itemId);
    return;
  }
  const dietToggle = e.target.closest('[data-action="diet-toggle"]');
  if (dietToggle) {
    e.preventDefault();
    const targetId = dietToggle.getAttribute('data-target');
    if (!targetId) return;
    const panel = chatLog.querySelector('.faq-panel[data-faq-current="menu.ruokavaliot"]');
    if (!panel) return;
    const content = panel.querySelector(`.diet-nutrition-content[data-diet-content="${targetId}"]`);
    if (!content) return;
    const expanded = !content.hasAttribute('hidden');
    if (expanded) {
      content.setAttribute('hidden', '');
      dietToggle.setAttribute('aria-expanded', 'false');
      dietToggle.textContent = trFaq('dietReadMore');
    } else {
      content.removeAttribute('hidden');
      dietToggle.setAttribute('aria-expanded', 'true');
      dietToggle.textContent = trFaq('dietReadLess');
    }
    return;
  }
  const dietVariantBtn = e.target.closest('[data-action="diet-variant"]');
  if (dietVariantBtn) {
    e.preventDefault();
    const targetId = dietVariantBtn.getAttribute('data-target');
    if (!targetId) return;
    const panel = chatLog.querySelector('.faq-panel[data-faq-current="menu.ruokavaliot"]');
    if (!panel) return;
    const content = panel.querySelector(`.diet-variant-content[data-variant-content="${targetId}"]`);
    if (!content) return;
    const expanded = !content.hasAttribute('hidden');
    if (expanded) {
      content.setAttribute('hidden', '');
      dietVariantBtn.setAttribute('aria-expanded', 'false');
    } else {
      content.removeAttribute('hidden');
      dietVariantBtn.setAttribute('aria-expanded', 'true');
    }
    return;
  }
  const backBtn = e.target.closest('[data-action="menu-back"]');
  if (backBtn) {
    e.preventDefault();
    const targetPath = parsePath(backBtn.getAttribute('data-target-path') || 'menu');
    try {
      await openFaqPath(targetPath);
    } catch (err) {
      console.error(err);
      renderFaqError(trFaq('loadError'), faqState.currentPath || []);
    }
    return;
  }
  const faqQuestionBtn = e.target.closest('[data-faq-question]');
  if (faqQuestionBtn) {
    e.preventDefault();
    const scope = faqQuestionBtn.getAttribute('data-faq-scope') || '';
    const entryId = faqQuestionBtn.getAttribute('data-faq-question');
    const entries = faqState.entries.get(scope) || [];
    const entry = entries.find(item => String(item.id) === String(entryId));
    if (entry) {
      renderFaqAnswer(entry, parsePath(scope));
    }
    return;
  }
  const faqAnswerBack = e.target.closest('[data-faq-answer-back]');
  if (faqAnswerBack) {
    e.preventDefault();
    const container = faqAnswerBack.closest('.faq-answer');
    const scope = container?.getAttribute('data-faq-scope') || '';
    const wrap = faqAnswerBack.closest('.msg');
    if (wrap) wrap.remove();
    try {
      await openFaqPath(parsePath(scope));
    } catch (err) {
      console.error(err);
      renderFaqError(trFaq('loadError'), faqState.currentPath || []);
    }
    return;
  }
  // Start order from any bubble that offers it (order-ui or suggest)
  const startBtn = e.target.closest('.order-ui .btn[data-action="start-order"], .suggest .btn[data-action="start-order"]');
  if (startBtn) { e.preventDefault(); startOrderFlow(); return; }
  const catBtn = e.target.closest('.cat-list .btn[data-cat-id]');
  if (catBtn) { e.preventDefault(); const id = parseInt(catBtn.dataset.catId,10); showCategoryItems(id, catBtn.textContent.trim()); return; }
  const viewBtn = e.target.closest('.btn-view-cart');
  if (viewBtn) { e.preventDefault(); viewCart(); return; }
  const addBtn = e.target.closest('.prod-list .btn-add');
  if (addBtn) {
    e.preventDefault();
    const id = addBtn.dataset.id,
          sku = addBtn.dataset.sku,
          name = addBtn.dataset.name,
          price = addBtn.dataset.price ? parseFloat(addBtn.dataset.price) : null;
    addToCart({id, sku, name, price}, 1);
    return;
  }
  const incBtn = e.target.closest('.prod-list .btn-inc');
  if (incBtn) { e.preventDefault(); const id = incBtn.dataset.id; changeQty(id, +1); return; }
  const decBtn = e.target.closest('.prod-list .btn-dec');
  if (decBtn) { e.preventDefault(); const id = decBtn.dataset.id; changeQty(id, -1); return; }
  const contBtn = e.target.closest('.cart-actions .btn-continue');
  if (contBtn) { e.preventDefault(); showCategories(); return; }
  const checkoutBtn = e.target.closest('.cart-actions .btn-checkout');
  if (checkoutBtn) { e.preventDefault(); startCheckout(); return; }
  const clearBtn = e.target.closest('.cart-actions .btn-clear');
  if (clearBtn) { e.preventDefault(); handleClearCart(); return; }
  // Suggestion buttons: prefill and send
  const sugg = e.target.closest('.suggest .suggest-btn[data-suggest]');
  if (sugg) {
    e.preventDefault();
    renderFaqRoot();
    return;
  }
  // Inline cart controls (inc/dec/remove)
  const cart = e.target.closest('.bot-block[data-key="cart-summary"]');
  if (cart){
    const line = e.target.closest('.cart-lines .line');
    if (line){
      const key = line.dataset.key;
      if (e.target.closest('.btn-rm')){ 
        e.preventDefault(); 
        const it = orderSession.cart.find(x=>x.key===key);
        if (confirm(tr('confirm_remove_item'))){ removeByKey(key); }
        return; 
      }
      if (e.target.closest('.btn-inc')){ e.preventDefault(); changeQtyKey(key, +1); return; }
      if (e.target.closest('.btn-dec')){ e.preventDefault(); changeQtyKey(key, -1); return; }
    }
  }
});

// Feedback form submission (embedded in chat bubbles)
chatLog.addEventListener('submit', async (e) => {
  const form = e.target.closest('form.feedback-form');
  if (!form) return;
  e.preventDefault();
  const fd = new FormData(form);
  const payload = Object.fromEntries(fd.entries());
  const msg = (payload.message||'').trim();
  if (!msg) return;
  try{
    const r = await fetch('/api/feedback', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(payload) });
    if (!r.ok) throw new Error('feedback');
    addBot(tr('thanks_feedback')||'Kiitos palautteesta!');
    // disable form after success
    [...form.elements].forEach(el=> el.disabled = true);
  }catch(err){ addBot('Failed to send feedback. Please try again.'); }
});

// Teach form submission (admin-only, embedded in chat)
chatLog.addEventListener('submit', async (e) => {
  const form = e.target.closest('form.teach-form');
  if (!form) return;
  e.preventDefault();
  const fd = new FormData(form);
  const payload = Object.fromEntries(fd.entries());
  const q = (payload.question||'').trim();
  const a = (payload.answer||'').trim();
  const key = (payload.admin_key||'').trim();
  if (!q || !a || !key) return;
  try{
    const r = await fetch('/api/kb/add', {
      method:'POST',
      headers:{'Content-Type':'application/json', 'x-admin-key': key},
      body: JSON.stringify({ lang: payload.lang||currentLang||'fi', question: q, answer: a })
    });
    if (!r.ok) throw new Error('teach');
    addBot(tr('taught_ok')||'Learned. I will use this going forward.');
    [...form.elements].forEach(el=> el.disabled = true);
  }catch(err){ addBot('Failed to save. Check your admin key.'); }
});

const orderSession = {
  cart: [], // {key, id, sku, name, quantity}
  pickupDate: null,
  pickupTime: null,
  name: '', email: '', phone: '', note: '',
  step: null,
};

// Persist order session
const ORDER_KEY = 'order_session_v1';
function saveSession(){ try{ localStorage.setItem(ORDER_KEY, JSON.stringify(orderSession)); }catch{} }
function loadSession(){ try{ const s = JSON.parse(localStorage.getItem(ORDER_KEY)||'null'); if (s && typeof s==='object'){ Object.assign(orderSession, s); } }catch{} }
loadSession();
if (orderSession.cart && orderSession.cart.length) { updateCartSummary(); }

function keyFor(it){ return String(it.id || it.sku || ''); }
function addToCart(it, qty){
  const key = keyFor(it); if (!key) return;
  const found = orderSession.cart.find(x => x.key === key);
  if (found) found.quantity += qty; else orderSession.cart.push({ key, id: it.id?parseInt(it.id,10):null, sku: it.sku||null, name: it.name, price: (typeof it.price==='number'?it.price:null), quantity: qty });
  if (orderSession.cart.find(x=>x.key===key).quantity <= 0){
    orderSession.cart = orderSession.cart.filter(x=>x.key!==key);
  }
  updateCartSummary();
  saveSession();
}
function changeQty(id, delta){
  const item = orderSession.cart.find(x=>String(x.id)===String(id));
  if (item){ item.quantity += delta; if (item.quantity<=0){ orderSession.cart = orderSession.cart.filter(x=>x!==item); } }
  updateCartSummary();
  saveSession();
}

function changeQtyKey(key, delta){
  const item = orderSession.cart.find(x=>x.key===String(key));
  if (item){ item.quantity += delta; if (item.quantity<=0){ orderSession.cart = orderSession.cart.filter(x=>x!==item); } }
  updateCartSummary();
  saveSession();
}

function removeByKey(key){
  orderSession.cart = orderSession.cart.filter(x=>x.key!==String(key));
  updateCartSummary();
  saveSession();
}

async function startOrderFlow(){
  orderSession.cart = [];
  saveSession();
  if ((currentLang || 'fi') !== 'fi') { addBot(tr('order_notice_fi_only')); }
  addBot(tr('start_choose_category'));
  await showCategories();
}

async function showCategories(){
  try{
    const r = await fetch('/api/v2/categories');
    if (!r.ok) throw new Error('categories');
    const data = await r.json();
    const items = (data.items||[]);
    const preferred = items.filter(c=>/uunituoreet/i.test(c.name) || /pakaste/i.test(c.name));
    const list = (preferred.length?preferred:items).map(c=>{
      const img = c.imageUrl ? `<img class=\"cat-img\" src=\"${c.imageUrl}\" alt=\"\">` : '';
      return `<button class=\"btn cat-btn\" data-cat-id=\"${c.id}\">${img}<span class=\"cat-name\">${escapeHtml(c.name)}</span></button>`;
    }).join(' ');
    addBotHtml(`<div class="cat-list">
      <div class="title-row"><div class="of-title">${tr('choose_category')}</div><button class="btn btn-view-cart">${tr('view_cart')}</button></div>
      <div class="order-buttons">${list}</div>
    </div>`);
  }catch(e){
    addBot(tr('categories_unavailable'));
    // Fallback: try to fetch a flat product list so ordering can proceed
    try{
      const rp = await fetch('/api/v2/products');
      if (!rp.ok) throw new Error('products');
      const pdata = await rp.json();
      const items = (pdata.items||[]);
      if (!items.length) return;
      const rows = items.map(it=>{
        const inCart = orderSession.cart.find(x=>String(x.id)===String(it.id));
        const qty = inCart ? inCart.quantity : 0;
        const n = escapeHtml(it.name);
        const price = (it.price != null) ? `<span class=\"price\">${Number(it.price).toFixed(2)}€</span>` : '';
        const img = it.imageUrl ? `<img class=\"prod-img\" src=\"${it.imageUrl}\" alt=\"\">` : '';
        const out = (it.inStock === false) || (it.quantity === 0);
        const stock = out ? `<span class=\"stock-badge out\">${tr('out_of_stock')}</span>` : '';
        const ctrls = (qty>0)
          ? `<div class=\"qty-ctrls\"><button class=\"btn-dec\" data-id=\"${it.id}\">−</button><span class=\"qty\">${qty}</span><button class=\"btn-inc\" data-id=\"${it.id}\">+</button></div>`
          : `<button class=\"btn-add\" ${out?'disabled':''} data-id=\"${it.id||''}\" data-sku=\"${it.sku||''}\" data-name=\"${n}\" data-price=\"${it.price!=null?String(Number(it.price).toFixed(2)):''}\">${tr('add')}</button>`;
        return `<div class=\"prod-row\">\n        <div class=\"prod-main\">${img}\n          <div class=\"prod-info\">\n            <div class=\"prod-name\">${n}</div>\n            <div class=\"prod-meta\">${price} ${stock}<span class=\"prod-ctrls-inline\">${ctrls}</span></div>\n          </div>\n        </div>\n      </div>`;
      }).join('');
      addBotHtml(`<div class=\"prod-list\">\n        <div class=\"title-row\"><div class=\"of-title\">Tuotteet</div><button class=\"btn btn-view-cart\">${tr('view_cart')}</button></div>\n        ${rows}\n      </div>`);
      updateCartSummary();
    }catch(e2){ /* no-op */ }
  }
}

async function showCategoryItems(catId, catName){
  try{
    const r = await fetch(`/api/v2/products?category=${encodeURIComponent(catId)}`);
    if (!r.ok) throw new Error('products');
    const data = await r.json();
    const items = (data.items||[]);
    if (!items.length){ addBot(`${tr('no_products_in_category')} ${escapeHtml(catName)}.`); return; }
    const rows = items.map(it=>{
      const inCart = orderSession.cart.find(x=>String(x.id)===String(it.id));
      const qty = inCart ? inCart.quantity : 0;
      const n = escapeHtml(it.name);
      const price = (it.price != null) ? `<span class=\"price\">${Number(it.price).toFixed(2)}€</span>` : '';
      const img = it.imageUrl ? `<img class=\"prod-img\" src=\"${it.imageUrl}\" alt=\"\">` : '';
      const out = (it.inStock === false) || (it.quantity === 0);
      const stock = out ? `<span class=\"stock-badge out\">${tr('out_of_stock')}</span>` : '';
      const ctrls = (qty>0)
        ? `<div class=\"qty-ctrls\"><button class=\"btn-dec\" data-id=\"${it.id}\">−</button><span class=\"qty\">${qty}</span><button class=\"btn-inc\" data-id=\"${it.id}\">+</button></div>`
        : `<button class=\"btn-add\" ${out?'disabled':''} data-id=\"${it.id||''}\" data-sku=\"${it.sku||''}\" data-name=\"${n}\" data-price=\"${it.price!=null?String(Number(it.price).toFixed(2)):''}\">${tr('add')}</button>`;
      return `<div class="prod-row">
        <div class="prod-main">${img}
          <div class="prod-info">
            <div class="prod-name">${n}</div>
            <div class="prod-meta">${price} ${stock}<span class="prod-ctrls-inline">${ctrls}</span></div>
          </div>
        </div>
      </div>`;
    }).join('');
    addBotHtml(`<div class="prod-list">
      <div class="title-row"><div class="of-title">${escapeHtml(catName)}</div><button class="btn btn-view-cart">${tr('view_cart')}</button></div>
      ${rows}
    </div>`);
    updateCartSummary();
  }catch(e){ addBot(tr('products_unavailable')); }
}

function updateCartSummary(){
  const totalItems = orderSession.cart.reduce((s,it)=>s+it.quantity,0);
  const lines = orderSession.cart.map(it=>`<div class=\"line\" data-key=\"${it.key}\"><span class=\"nm\">${escapeHtml(it.name)}</span><span class=\"qty-ctrls\"><button class=\"btn-dec\">−</button><span class=\"qty\">${it.quantity}</span><button class=\"btn-inc\">+</button><button class=\"btn-rm\">${tr('remove')}</button></span></div>`).join('');
  const html = `<div class="cart-summary">
    <div class="of-title">${tr('cart_title')} (${totalItems})</div>
    <div class="cart-lines">${lines || tr('cart_empty')}</div>
    <div class="cart-actions">
      <button class="btn-continue">${tr('continue_shopping')}</button>
      <button class="btn-checkout" ${totalItems? '':'disabled'}>${tr('go_checkout')}</button>
      <button class="btn-clear" ${totalItems? '':'disabled'}>${tr('clear_cart')}</button>
    </div>
  </div>`;
  addOrReplaceBotBlock('cart-summary', html);
}

function handleClearCart(){
  if (!orderSession.cart.length) return;
  if (confirm(tr('confirm_clear_cart'))){
    orderSession.cart = [];
    saveSession();
    updateCartSummary();
  }
}

function addOrReplaceBotBlock(key, html){
  const selector = `.bot-block[data-key="${key}"]`;
  let el = chatLog.querySelector(selector);
  if (!el){
    const wrap = document.createElement('div');
    wrap.className = 'msg bot';
    const bubble = document.createElement('div');
    bubble.className = 'bubble html';
    const block = document.createElement('div');
    block.className = 'bot-block';
    block.setAttribute('data-key', key);
    block.innerHTML = html;
    bubble.appendChild(block);
    wrap.appendChild(bubble);
    chatLog.appendChild(wrap);
  } else {
    el.innerHTML = html;
    const msg = el.closest('.msg');
    if (msg && msg.parentElement === chatLog){ chatLog.appendChild(msg); }
  }
  chatLog.scrollTop = chatLog.scrollHeight;
  const node = chatLog.querySelector(selector);
  if (node){ node.classList.remove('flash'); void node.offsetWidth; node.classList.add('flash'); setTimeout(()=> node.classList.remove('flash'), 600); }
}

// Guided checkout: ask details one by one
async function startCheckout(){
  if (!orderSession.cart.length){ addBot(tr('add_items_first')); return; }
  orderSession.name = orderSession.name || '';
  orderSession.step = 'name'; saveSession();
  askName();
}

function askName(){
  addBotHtml(`<form class="step-form" data-step="name"><div class="of-field"><label>${tr('ask_name')}</label><input name="name" type="text" required /></div><div class="of-actions"><button class="btn-back" type="button">${tr('back')}</button><button class="btn-send" type="submit">${tr('next')}</button></div></form>`);
  bindStepForm('name', (v)=>{ orderSession.name = v.name.trim(); orderSession.step='email'; saveSession(); askEmail(); });
  bindBack('name', ()=>{ /* back to cart */ showCategories(); });
}
function askEmail(){
  addBotHtml(`<form class="step-form" data-step="email"><div class="of-field"><label>${tr('ask_email')}</label><input name="email" type="email" placeholder="email@example.com" required /></div><div class="of-actions"><button class="btn-back" type="button">${tr('back')}</button><button class="btn-send" type="submit">${tr('next')}</button></div></form>`);
  bindStepForm('email', (v)=>{ orderSession.email = (v.email||'').trim(); if(!orderSession.email){ return; } orderSession.step='phone'; saveSession(); askPhone(); });
  bindBack('email', ()=>{ askName(); });
}
function askPhone(){
  addBotHtml(`<form class="step-form" data-step="phone"><div class="of-field"><label>${tr('ask_phone')}</label><input name="phone" type="tel" placeholder="+358 12 345 6789" required /></div><div class="of-actions"><button class="btn-back" type="button">${tr('back')}</button><button class="btn-send" type="submit">${tr('next')}</button></div></form>`);
  bindStepForm('phone', (v)=>{ orderSession.phone = v.phone.trim(); orderSession.step='date'; saveSession(); askDate(); });
  bindBack('phone', ()=>{ askEmail(); });
}

async function askDate(){
  const {hours} = await fetchPickupHours();
  pickupHoursCache = hours;
  const cons = await fetchOrderConstraints();
  // Initialize shown month to current month if not set
  if (!orderSession._calMonth){
    const now = new Date();
    const m = String(now.getMonth()+1).padStart(2,'0');
    orderSession._calMonth = `${now.getFullYear()}-${m}-01`;
  }
  const calHtml = renderCalendarHTML(orderSession._calMonth, hours, cons);
  addBotHtml(`<div class="dt-picker" data-step="date">
    <div class="of-title">${tr('ask_date')}</div>
    ${calHtml}
    <div class="of-actions"><button class="btn-back" type="button">${tr('back')}</button></div>
  </div>`);
  bindCalendarHandlers(hours, cons);
  bindBack('date', ()=>{ askPhone(); });
}

async function askTime(hours){
  hours = hours || pickupHoursCache || {};
  const cons = await fetchOrderConstraints();
  const slots = buildTimeSlots(orderSession.pickupDate, hours, cons);
  const btns = slots.map(s=>`<button class="dt-btn ${s.enabled?'':'disabled'}" data-time="${s.value}" ${s.enabled?'':'disabled'}>${s.label}</button>`).join('');
  addBotHtml(`<div class="dt-picker" data-step="time"><div class="of-title">${tr('ask_time')}</div><div class="dt-grid">${btns}</div><div class="of-actions"><button class="btn-back" type="button">${tr('back')}</button></div></div>`);
  chatLog.querySelectorAll('.dt-picker[data-step="time"] .dt-btn').forEach(btn=>{
    btn.addEventListener('click',(e)=>{ e.preventDefault(); if (btn.disabled) return; orderSession.pickupTime = btn.dataset.time; orderSession.step='note'; saveSession(); askNote(); });
  });
  bindBack('time', ()=>{ askDate(); });
}

function askNote(){
  addBotHtml(`<form class="step-form" data-step="note"><div class="of-field"><label>${tr('ask_note')}</label><input name="note" type="text" placeholder="${tr('ask_email_optional')}" /></div><div class="of-actions"><button class="btn-back" type="button">${tr('back')}</button><button class="btn-send" type="submit">${tr('submit_order')}</button></div></form>`);
  bindStepForm('note', async (v)=>{ orderSession.note = (v.note||'').trim(); saveSession(); await submitOrder(); });
  bindBack('note', ()=>{ askTime(); });
}

function bindStepForm(step, onOk){
  const form = [...chatLog.querySelectorAll(`form.step-form[data-step="${step}"]`)].slice(-1)[0];
  if (!form) return;
  form.addEventListener('submit', (e)=>{
    e.preventDefault();
    const fd = new FormData(form); const v = Object.fromEntries(fd.entries());
    onOk(v);
  });
}
function bindBack(step, onBack){
  const node = [...chatLog.querySelectorAll(`[data-step="${step}"]`)].slice(-1)[0];
  if (!node) return;
  const btn = node.querySelector('.btn-back');
  if (!btn) return;
  btn.addEventListener('click', (e)=>{ e.preventDefault(); onBack&&onBack(); });
}

async function submitOrder(){
  const items = orderSession.cart.map(it=>({
    quantity: it.quantity,
    name: it.name,
    ...(typeof it.price==='number' ? { price: Number(it.price) } : {}),
    ...(it.id?{productId: parseInt(it.id,10)}:{}),
    ...(it.sku?{sku: it.sku}:{})
  }));
  const iso = `${orderSession.pickupDate}T${orderSession.pickupTime}`;
  const payload = { items, name: orderSession.name, email: orderSession.email||null, phone: orderSession.phone, pickup_time: iso, note: orderSession.note||null };
  try{
    const r = await fetch('/api/v2/order', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(payload)});
    const data = await r.json();
    if (!r.ok){ addBot(`${tr('order_fail')} ${tr('order_fail_reason')} ${escapeHtml(data.detail||JSON.stringify(data))}`); return; }
    addBot(`${tr('order_ok')} ${data.orderNumber || data.id || '—'}`);
    orderSession.cart = []; orderSession.step = null; saveSession(); updateCartSummary();
  }catch(err){ console.error(err); addBot(tr('order_fail')); }
}

async function fetchPickupHours(){
  try{ const r = await fetch('/api/v2/pickup_hours'); if (!r.ok) throw 0; return await r.json(); }catch{ return {hours:{}}; }
}
async function fetchOrderConstraints(){
  if (orderConstraintsCache) return orderConstraintsCache;
  try{ const r = await fetch('/api/v2/order_constraints'); if (!r.ok) throw 0; orderConstraintsCache = await r.json(); return orderConstraintsCache; }catch{ return { min_lead_minutes: 720, max_days: 60 }; }
}
function buildNextDays(hours, n){
  const out=[]; const now=new Date(); for(let i=0;i<n;i++){ const d=new Date(now); d.setDate(now.getDate()+i); const dow=(d.getDay()+6)%7; // Mon=0
    const has=Array.isArray(hours[dow]); const yyyy=d.getFullYear(); const mm=String(d.getMonth()+1).padStart(2,'0'); const dd=String(d.getDate()).padStart(2,'0');
    const iso=`${yyyy}-${mm}-${dd}`; const label=d.toLocaleDateString(undefined,{weekday:'short', day:'numeric', month:'short'});
    out.push({iso,label,enabled: !!has}); }
  return out; }
function buildTimeSlots(dateIso, hours, cons){
  const [y,m,d] = dateIso.split('-').map(x=>parseInt(x,10)); const dt=new Date(y, m-1, d);
  const dow=(dt.getDay()+6)%7; const wins=hours[dow]||[]; const slots=[]; const now=new Date();
  const minLeadMs = ((cons && cons.min_lead_minutes) ? cons.min_lead_minutes : 720) * 60 * 1000;
  const minTime = new Date(Date.now() + minLeadMs);
  for(const [start,end] of wins){ const [sh,sm]=start.split(':').map(n=>parseInt(n,10)); const [eh,em]=end.split(':').map(n=>parseInt(n,10));
    for(let h=sh; h<=eh; h++){
      const m = 0; const tM = h*60+m; if (tM<sh*60+sm || tM>eh*60+em) continue;
      const label=`${String(h).padStart(2,'0')}:00`; const value=label;
      const cand=new Date(dt); cand.setHours(h,m,0,0);
      const enabled = cand.getTime() > minTime.getTime();
      if (enabled) slots.push({label,value,enabled});
    }
  }
  const seen=new Set(); const uniq=[]; for(const s of slots){ if (seen.has(s.value)) continue; seen.add(s.value); uniq.push(s); }
  return uniq;
}
// ---- Calendar helpers ----
function _localeTag(){
  const map = { fi: 'fi-FI', sv: 'sv-SE', en: 'en-US' };
  return map[currentLang] || 'en-US';
}
function _startOfMonth(iso){ const [y,m] = iso.split('-').map(x=>parseInt(x,10)); return new Date(y, m-1, 1); }
function _fmtMonthTitle(d){ return d.toLocaleDateString(_localeTag(), { month: 'long', year: 'numeric' }); }
function _fmtISO(d){ const y=d.getFullYear(); const m=String(d.getMonth()+1).padStart(2,'0'); const dd=String(d.getDate()).padStart(2,'0'); return `${y}-${m}-${dd}`; }
function _weekdayMon0(d){ return (d.getDay()+6)%7; } // Mon=0 .. Sun=6
function _weekdayHeaders(){
  // Start from a known Monday
  const start = new Date(2023, 0, 2); // Mon Jan 2, 2023
  const loc = _localeTag();
  const out = [];
  for (let i=0;i<7;i++){
    const d = new Date(start); d.setDate(start.getDate()+i);
    out.push(d.toLocaleDateString(loc, { weekday: 'short' }));
  }
  return out;
}

function renderCalendarHTML(monthISO, hours, cons){
  const month = _startOfMonth(monthISO);
  const firstDow = _weekdayMon0(month);
  const start = new Date(month); start.setDate(1 - firstDow); // Monday on or before the 1st
  const today = new Date(); today.setHours(0,0,0,0);
  const minLeadMs = ((cons && cons.min_lead_minutes) ? cons.min_lead_minutes : 720) * 60 * 1000;
  const minDate = new Date(Date.now() + minLeadMs); minDate.setHours(0,0,0,0);
  const maxDays = (cons && cons.max_days) ? cons.max_days : 60;
  const maxDate = new Date(); maxDate.setDate(maxDate.getDate() + maxDays); maxDate.setHours(0,0,0,0);
  // Build blackout date predicate
  const blackouts = Array.isArray(cons && cons.blackout_dates) ? cons.blackout_dates : [];
  const isBlackout = (d)=>{
    if (!blackouts.length) return false;
    const y = d.getFullYear();
    const md = (s)=>{ const [yy,mm,dd] = s.split('-').map(x=>parseInt(x,10)); return {yy,mm,dd}; };
    for (const b of blackouts){
      if (!(b && b.from && b.to)) continue;
      const f = md(b.from); const t = md(b.to);
      // Build actual date range for this year if repeatedAnnually
      const fy = b.repeatedAnnually ? y : f.yy;
      const ty = b.repeatedAnnually ? y : t.yy;
      const from = new Date(fy, (f.mm||1)-1, f.dd||1);
      const to = new Date(ty, (t.mm||1)-1, t.dd||1);
      from.setHours(0,0,0,0); to.setHours(0,0,0,0);
      if (d >= from && d <= to) return true;
    }
    return false;
  };
  // Build 6 weeks grid (42 days)
  let cells = '';
  let earliestIso = null;
  for (let i=0; i<42; i++){
    const d = new Date(start); d.setDate(start.getDate()+i);
    const inMonth = d.getMonth() === month.getMonth();
    const dow = _weekdayMon0(d);
    const avail = Array.isArray(hours[dow]) && hours[dow].length > 0;
    const isPast = d < today;
    const beforeMin = d < minDate;
    const afterMax = d > maxDate;
    const isBlk = isBlackout(d);
    const iso = _fmtISO(d);
    const classes = ['cal-day'];
    if (!inMonth) classes.push('other');
    if (isBlk) classes.push('blackout');
    if (!avail || isPast || beforeMin || afterMax || isBlk) classes.push('disabled');
    if (d.getTime() === today.getTime()) classes.push('today');
    const label = d.getDate();
    // Track earliest available in this month
    if (!classes.includes('disabled') && inMonth && !earliestIso){ earliestIso = iso; }
    // Mark selected day if it matches
    const selectedIso = orderSession.pickupDate;
    if (selectedIso && selectedIso === iso){ classes.push('selected'); }
    if (classes.includes('disabled')){
      cells += `<div class="${classes.join(' ')}" aria-disabled="true"><span>${label}</span></div>`;
    } else {
      cells += `<button class="${classes.join(' ')}" data-date="${iso}" aria-label="${iso}"><span>${label}</span></button>`;
    }
  }
  const title = _fmtMonthTitle(month);
  // If no availability this month within constraints, auto-advance to next available month in range
  if (!earliestIso){
    const m0 = new Date(month);
    for (let step=1; step<=11; step++){
      const cand = new Date(m0); cand.setMonth(m0.getMonth()+step);
      if (cand > maxDate) break;
      const ciso = _fmtISO(new Date(cand.getFullYear(), cand.getMonth(), 1));
      return renderCalendarHTML(ciso, hours, cons);
    }
  }
  // Auto-preselect earliest available if none selected yet
  if (!orderSession.pickupDate && earliestIso){ orderSession.pickupDate = earliestIso; saveSession?.(); }
  const wds = _weekdayHeaders();
  const whtml = wds.map(w=>`<div>${w}</div>`).join('');
  return `<div class="calendar" data-month="${_fmtISO(month)}">
    <div class="cal-header">
      <button class="cal-nav cal-prev" aria-label="Prev">‹</button>
      <div class="cal-title">${title}</div>
      <button class="cal-nav cal-next" aria-label="Next">›</button>
    </div>
    <div class="cal-weekdays">${whtml}</div>
    <div class="cal-grid">${cells}</div>
  </div>`;
}

function bindCalendarHandlers(hours, cons){
  const wrap = [...chatLog.querySelectorAll('.dt-picker[data-step="date"] .calendar')].slice(-1)[0];
  if (!wrap) return;
  const update = (iso)=>{
    orderSession._calMonth = iso; saveSession();
    wrap.outerHTML = renderCalendarHTML(orderSession._calMonth, hours, cons);
    bindCalendarHandlers(hours, cons);
  };
  const monthISO = wrap.getAttribute('data-month');
  const monthDate = _startOfMonth(monthISO);
  const prev = chatLog.querySelector('.dt-picker[data-step="date"] .cal-prev');
  const next = chatLog.querySelector('.dt-picker[data-step="date"] .cal-next');
  if (prev){ prev.addEventListener('click',(e)=>{ e.preventDefault(); const d=new Date(monthDate); d.setMonth(d.getMonth()-1); update(_fmtISO(new Date(d.getFullYear(), d.getMonth(), 1))); }); }
  if (next){ next.addEventListener('click',(e)=>{ e.preventDefault(); const d=new Date(monthDate); d.setMonth(d.getMonth()+1); update(_fmtISO(new Date(d.getFullYear(), d.getMonth(), 1))); }); }
  chatLog.querySelectorAll('.dt-picker[data-step="date"] .cal-day[data-date]').forEach(btn=>{
    btn.addEventListener('click',(e)=>{ e.preventDefault(); const iso = btn.getAttribute('data-date');
      orderSession.pickupDate = iso; saveSession();
      // Highlight selected day before moving to time
      chatLog.querySelectorAll('.dt-picker[data-step="date"] .cal-day').forEach(n=>n.classList.remove('selected'));
      btn.classList.add('selected');
      setTimeout(()=>{ orderSession.step='time'; askTime(hours); }, 180);
    });
  });
}

function viewCart(){
  updateCartSummary();
  const el = chatLog.querySelector('.bot-block[data-key="cart-summary"]');
  if (el){ el.scrollIntoView({behavior:'smooth', block:'end'}); el.classList.add('flash'); setTimeout(()=> el.classList.remove('flash'), 800); }
}

function resumeOrder(){
  if (!orderSession.step) return;
  updateCartSummary();
  switch(orderSession.step){
    case 'name': askName(); break;
    case 'email': askEmail(); break;
    case 'phone': askPhone(); break;
    case 'date': askDate(); break;
    case 'time': askTime(); break;
    case 'note': askNote(); break;
  }
}

// Auto-resume on load
resumeOrder();

function escapeHtml(s){
  return s.replace(/[&<>"]+/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
}

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
  if (chatCard && chatCard.classList.contains('readonly')) {
    enabled = false;
  }
  if (chatInput) chatInput.disabled = !enabled;
  if (sendBtn) sendBtn.disabled = !enabled;
}

function welcomeForLang(lang){
  switch(lang){
    case 'fi': return "Hei! Valitse aihe valikosta, niin näytän valmiit vastaukset.";
    case 'sv': return "Hej! Välj ett ämne i menyn så visar jag färdiga svar.";
    default: return "Hi! Choose a topic from the menu to see the curated answers.";
  }
}

const FAQ_TEXT = {
  fi: {
    home: 'Päävalikko',
    chooseRoot: 'Valitse aihealue alla olevista napeista.',
    chooseOrdering: 'Valitse tilaukseen liittyvä osio.',
    chooseSub: 'Valitse tarkempi alavalinta.',
    chooseQuestion: 'Valitse kysymys, johon haluat vastauksen.',
    noEntries: 'Tähän kategoriaan ei ole vielä vastauksia.',
    loading: 'Ladataan valikoimaa…',
    loadError: 'Tiedostoja ei saatu ladattua. Yritä hetken kuluttua uudelleen.',
    backToList: 'Takaisin kysymyslistaan',
    chooseFresh: 'Valitse, haluatko tutustua uunituoreisiin vai pakasteisiin tuotteisiin.',
    btnUunituoreet: 'Uunituoreet',
    btnPakasteet: 'Pakasteet',
    orderOnline: 'Tilaa verkkokaupasta',
    orderInChat: 'Tilaa chatissa',
    goBack: '← Takaisin',
    rootFaq: 'UKK',
    rootMenu: 'Menu',
    rootOrdering: 'Tilaaminen',
    rootFeedback: 'Palaute',
    faqOrders: 'Tilaukset',
    orderingIntro: 'Valitse tilauksiin liittyvä aihe.',
    feedbackIntro: 'Jätä palautteesi alla olevalla lomakkeella.',
    otherLabel: 'Muut',
    feedbackTitle: 'Palaute',
    dietIntro: 'Valitse tuote nähdäksesi ainesosat ja allergeenit.',
    dietIngredients: 'Ainesosat',
    dietAllergens: 'Allergeenit',
    dietNutrition: 'Ravintosisältö',
    dietReadMore: 'Näytä ravintosisältö',
    dietReadLess: 'Piilota ravintosisältö',
    dietUnavailable: 'Tiedot eivät ole saatavilla juuri nyt.',
    dietSelectPrompt: 'Valitse tuote alta.',
  },
  sv: {
    home: 'Huvudmeny',
    chooseRoot: 'Välj ett ämnesområde nedan.',
    chooseOrdering: 'Välj ett beställningsrelaterat område.',
    chooseSub: 'Välj en underkategori.',
    chooseQuestion: 'Välj den fråga du vill se svaret på.',
    noEntries: 'Inga svar finns ännu i denna kategori.',
    loading: 'Laddar innehåll…',
    loadError: 'Kunde inte hämta information. Försök igen senare.',
    backToList: 'Tillbaka till frågelistan',
    chooseFresh: 'Välj om du vill se ugnsfärska produkter eller frysta.',
    btnUunituoreet: 'Ugnsfärska',
    btnPakasteet: 'Frysta produkter',
    orderOnline: 'Beställ i webbutiken',
    orderInChat: 'Beställ i chatten',
    goBack: '← Tillbaka',
    rootFaq: 'FAQ',
    rootMenu: 'Meny',
    rootOrdering: 'Beställning',
    rootFeedback: 'Feedback',
    faqOrders: 'Beställningar',
    orderingIntro: 'Välj vilket beställningsområde du behöver hjälp med.',
    feedbackIntro: 'Lämna din feedback via formuläret nedan.',
    otherLabel: 'Övrigt',
    feedbackTitle: 'Feedback',
    dietIntro: 'Välj en produkt för att se ingredienser och allergener.',
    dietIngredients: 'Ingredienser',
    dietAllergens: 'Allergener',
    dietNutrition: 'Näringsvärde',
    dietReadMore: 'Visa näringsvärden',
    dietReadLess: 'Dölj näringsvärden',
    dietUnavailable: 'Uppgifterna är inte tillgängliga just nu.',
    dietSelectPrompt: 'Välj en produkt nedan.',
  },
  en: {
    home: 'Main menu',
    chooseRoot: 'Pick a topic to get started.',
    chooseOrdering: 'Choose an ordering topic.',
    chooseSub: 'Choose a subcategory.',
    chooseQuestion: 'Select the question you want answered.',
    noEntries: 'No answers yet for this category.',
    loading: 'Loading answers…',
    loadError: 'Could not load the knowledge base. Please try again soon.',
    backToList: 'Back to question list',
    chooseFresh: 'Choose whether you want to browse fresh or frozen products.',
    btnUunituoreet: 'Oven-fresh',
    btnPakasteet: 'Frozen',
    orderOnline: 'Order online',
    orderInChat: 'Order in chat',
    goBack: '← Back',
    rootFaq: 'FAQ',
    rootMenu: 'Menu',
    rootOrdering: 'Ordering',
    rootFeedback: 'Feedback',
    faqOrders: 'Orders',
    orderingIntro: 'Pick the ordering topic you need.',
    feedbackIntro: 'Share your feedback with the form below.',
    otherLabel: 'Other',
    feedbackTitle: 'Feedback',
    dietIntro: 'Pick a product to see its ingredients and allergens.',
    dietIngredients: 'Ingredients',
    dietAllergens: 'Allergens',
    dietNutrition: 'Nutrition',
    dietReadMore: 'Show nutrition',
    dietReadLess: 'Hide nutrition',
    dietUnavailable: 'Details are not available right now.',
    dietSelectPrompt: 'Choose a product below.',
  },
};

const faqState = {
  tree: null,
  nodes: new Map(),
  entries: new Map(),
  version: null,
  lang: null,
  currentPath: [],
  dietData: null,
  dietLang: null,
  dietVersion: null,
  context: null, // 'main' | 'faq' | 'ordering' | 'feedback' | null
};

function trFaq(key){
  const fallback = FAQ_TEXT.fi[key] || key;
  const perLang = FAQ_TEXT[currentLang] || FAQ_TEXT.fi;
  return perLang[key] || fallback;
}

function parsePath(str){
  if (!str) return [];
  return str.split('.').map(s => s.trim()).filter(Boolean);
}

function pathKey(path){
  return path.join('.');
}

function focusFirstFaqControl(container){
  if (!container) return;
  const focusable = container.querySelector('button, [href], [tabindex]:not([tabindex="-1"])');
  if (focusable) {
    focusable.focus({ preventScroll: false });
  } else {
    container.focus({ preventScroll: false });
  }
}

function renderFaqPanel(innerHtml, path){
  const currentKey = pathKey(path || []);
  chatLog.querySelectorAll('.faq-panel').forEach(panel => {
    const wrap = panel.closest('.msg');
    if (wrap) wrap.remove();
  });
  chatLog.querySelectorAll('.faq-answer').forEach(panel => {
    const wrap = panel.closest('.msg');
    if (wrap) wrap.remove();
  });
  addBotHtml(`<div class="faq-panel" data-faq-current="${currentKey}" tabindex="-1">${innerHtml}</div>`);
  requestAnimationFrame(() => {
    const panel = chatLog.querySelector(`.faq-panel[data-faq-current="${currentKey}"]`);
    focusFirstFaqControl(panel);
  });
}

function renderFaqError(message, path = []){
  renderFaqPanel(`<div class="faq-empty">${escapeHtml(message)}</div>`, path);
}

function appendMenuActions(type, path){
  const panel = chatLog.querySelector(`.faq-panel[data-faq-current="${pathKey(path)}"]`);
  if (!panel) return;
  const buttons = [];
  if (type === 'fresh') {
    buttons.push(`<button type="button" data-action="menu-show-frozen">${escapeHtml(trFaq('btnPakasteet'))}</button>`);
    buttons.push(`<button type="button" data-action="menu-order-online">${escapeHtml(trFaq('orderOnline'))}</button>`);
    buttons.push(`<button type="button" data-action="menu-order-chat">${escapeHtml(trFaq('orderInChat'))}</button>`);
  } else if (type === 'frozen') {
    buttons.push(`<button type="button" data-action="menu-show-fresh">${escapeHtml(trFaq('btnUunituoreet'))}</button>`);
    buttons.push(`<button type="button" data-action="menu-order-online">${escapeHtml(trFaq('orderOnline'))}</button>`);
    buttons.push(`<button type="button" data-action="menu-order-chat">${escapeHtml(trFaq('orderInChat'))}</button>`);
  }
  if (buttons.length) {
    panel.insertAdjacentHTML('beforeend', `<div class="faq-actions">${buttons.join('')}</div>`);
  }
  panel.insertAdjacentHTML('beforeend', `<div class="faq-back"><button type="button" data-action="menu-back" data-target-path="menu">${escapeHtml(trFaq('goBack'))}</button></div>`);
}

async function renderMenuTuoreetDetail(){
  await ensureFaqTree();
  const path = ['menu', 'menu-tuoreet'];
  faqState.currentPath = path.slice();
  let html = '';
  try {
    html = await loadMenuHtml('fresh');
  } catch (err) {
    console.error(err);
    renderFaqError(trFaq('loadError'), path);
    return;
  }
  const crumb = buildBreadcrumb(path);
  renderFaqPanel(`${crumb}<div class="faq-menu-html">${html}</div>`, path);
  appendMenuActions('fresh', path);
}

async function renderMenuPakasteDetail(){
  await ensureFaqTree();
  const path = ['menu', 'menu-pakasteet'];
  faqState.currentPath = path.slice();
  let html = '';
  try {
    html = await loadMenuHtml('frozen');
  } catch (err) {
    console.error(err);
    renderFaqError(trFaq('loadError'), path);
    return;
  }
  const crumb = buildBreadcrumb(path);
  renderFaqPanel(`${crumb}<div class="faq-menu-html">${html}</div>`, path);
  appendMenuActions('frozen', path);
}

async function loadDietMenuData(force = false){
  const lang = currentLang || 'fi';
  const cached = faqState.dietData;
  if (!force && cached && faqState.dietLang === lang) {
    if (!faqState.dietVersion || faqState.dietVersion === faqState.version) {
      return cached;
    }
  }
  const versionParam = faqState.version ? `&v=${encodeURIComponent(faqState.version)}` : '';
  const res = await fetch(`/faq/menu/diet?lang=${encodeURIComponent(lang)}${versionParam}`);
  if (!res.ok) {
    throw new Error(`Failed to load diet menu: ${res.status}`);
  }
  const data = await res.json();
  faqState.dietData = data;
  faqState.dietLang = lang;
  faqState.dietVersion = data.version || null;
  return data;
}

function formatPlainText(text){
  if (!text) return '';
  return escapeHtml(text).replace(/(?:\r\n|\r|\n)/g, '<br>');
}

async function renderMenuDietary(force = false){
  await ensureFaqTree();
  const path = ['menu', 'ruokavaliot'];
  faqState.currentPath = path.slice();
  let data;
  try {
    data = await loadDietMenuData(force);
  } catch (err) {
    console.error(err);
    renderFaqError(trFaq('loadError'), path);
    return;
  }
  const crumb = buildBreadcrumb(path);
  const intro = `<div class="faq-intro">${escapeHtml(trFaq('dietIntro'))}</div>`;
  const groups = Array.isArray(data.groups) ? data.groups : [];
  const groupsHtml = groups.map((group) => buildDietGroupHtml(group)).join('') || `<div class="faq-empty">${escapeHtml(trFaq('dietUnavailable'))}</div>`;
  const disclaimer = data.disclaimer ? `<div class="diet-disclaimer">${escapeHtml(data.disclaimer)}</div>` : '';
  const content = `${crumb}${intro}<div class="dietary-panel">${groupsHtml}</div>${disclaimer}<div class="faq-back"><button type="button" data-action="back-to-root">${escapeHtml(trFaq('goBack'))}</button></div>`;
  renderFaqPanel(content, path);
}

function buildDietGroupHtml(group){
  const groupId = group.id || '';
  const title = group.title || '';
  const items = Array.isArray(group.items) ? group.items : [];
  const buttons = items.map((item) => {
    const disabled = item.missing ? ' disabled' : '';
    const aria = item.missing ? ' aria-disabled="true"' : '';
    const itemLabel = escapeHtml(item.title || item.displayName || item.id || '');
    const safeGroup = escapeHtml(groupId);
    const safeId = escapeHtml(item.id || '');
    return `<button type="button" class="diet-button" data-diet-group="${safeGroup}" data-diet-item="${safeId}"${disabled}${aria}>${itemLabel}</button>`;
  }).join('') || `<div class="diet-empty">${escapeHtml(trFaq('dietUnavailable'))}</div>`;
  const safeGroup = escapeHtml(groupId);
  return `<section class="diet-group" data-diet-group="${safeGroup}"><div class="diet-group-header">${escapeHtml(title)}</div><div class="diet-group-buttons">${buttons}</div><div class="diet-group-detail" data-diet-detail></div></section>`;
}

function buildDietDetailHtml(groupId, item){
  const heading = item.displayName || item.title || '';
  const intro = item.intro ? `<p class="diet-detail-intro">${formatPlainText(item.intro)}</p>` : '';
  // ingredients may contain safe inline markup (e.g., <strong>allergen</strong>), so do not escape
  const ingredients = item.ingredients ? `<div class="diet-detail-section"><div class="diet-detail-label">${escapeHtml(trFaq('dietIngredients'))}</div><div class="diet-detail-text">${item.ingredients}</div></div>` : '';
  const allergens = item.allergens ? `<div class="diet-detail-section"><div class="diet-detail-label">${escapeHtml(trFaq('dietAllergens'))}</div><div class="diet-detail-text">${formatPlainText(item.allergens)}</div></div>` : '';
  let nutrition = '';
  if (item.nutrition) {
    const target = `${groupId}-${item.id}`;
    nutrition = `<div class="diet-detail-section diet-detail-nutrition"><button type="button" class="diet-toggle" data-action="diet-toggle" data-target="${escapeHtml(target)}" aria-expanded="false">${escapeHtml(trFaq('dietReadMore'))}</button><div class="diet-nutrition-content" data-diet-content="${escapeHtml(target)}" hidden>${formatPlainText(item.nutrition)}</div></div>`;
  }
  const variants = buildDietVariantSection(groupId, item);
  return `<div class="diet-card"><div class="diet-card-title">${escapeHtml(heading)}</div>${intro}${ingredients}${allergens}${nutrition}${variants}</div>`;
}

function buildDietVariantSection(groupId, item){
  const variants = Array.isArray(item.variants) ? item.variants : [];
  if (!variants.length) return '';
  const itemsHtml = variants.map((variant, idx) => {
    const target = `${groupId}-${item.id}-${variant.id || idx}`;
    const label = escapeHtml(variant.label || variant.title || variant.id || 'Variant');
    const content = buildDietVariantContent(variant);
    return `<div class="diet-variant-item"><button type="button" class="diet-variant-button" data-action="diet-variant" data-target="${escapeHtml(target)}" aria-expanded="false">${label}</button><div class="diet-variant-content" data-variant-content="${escapeHtml(target)}" hidden>${content}</div></div>`;
  }).join('');
  return `<div class="diet-variant-section">${itemsHtml}</div>`;
}

function buildDietVariantContent(variant){
  const detail = variant.detail || {};
  const heading = detail.name || variant.label || '';
  const intro = detail.intro ? `<p class="diet-detail-intro">${formatPlainText(detail.intro)}</p>` : '';
  // allow safe inline markup from backend in variant ingredients
  const ingredients = detail.ingredients ? `<div class="diet-detail-section"><div class="diet-detail-label">${escapeHtml(trFaq('dietIngredients'))}</div><div class="diet-detail-text">${detail.ingredients}</div></div>` : '';
  const allergens = detail.allergens ? `<div class="diet-detail-section"><div class="diet-detail-label">${escapeHtml(trFaq('dietAllergens'))}</div><div class="diet-detail-text">${formatPlainText(detail.allergens)}</div></div>` : '';
  const nutrition = detail.nutrition ? `<div class="diet-detail-section"><div class="diet-detail-label">${escapeHtml(trFaq('dietNutrition'))}</div><div class="diet-detail-text">${formatPlainText(detail.nutrition)}</div></div>` : '';
  return `<div class="diet-card diet-card-variant"><div class="diet-card-title">${escapeHtml(heading)}</div>${intro}${ingredients}${allergens}${nutrition}</div>`;
}

function showDietItem(groupId, itemId, options = {}){
  const data = faqState.dietData;
  if (!data) return;
  const groups = Array.isArray(data.groups) ? data.groups : [];
  const group = groups.find((g) => g.id === groupId);
  const panel = chatLog.querySelector('.faq-panel[data-faq-current="menu.ruokavaliot"]');
  if (!group || !panel) return;
  panel.querySelectorAll('.diet-group').forEach((el) => {
    const isCurrent = el.getAttribute('data-diet-group') === groupId;
    el.querySelectorAll('.diet-button').forEach((btn) => {
      const match = isCurrent && btn.getAttribute('data-diet-item') === itemId && !btn.disabled;
      btn.classList.toggle('active', match);
    });
    const detail = el.querySelector('[data-diet-detail]');
    if (!detail) return;
    if (!isCurrent) {
      detail.innerHTML = '';
      return;
    }
    const item = (group.items || []).find((it) => it.id === itemId);
    if (!item || item.missing) {
      detail.innerHTML = `<div class="diet-card diet-card-empty">${escapeHtml(trFaq('dietUnavailable'))}</div>`;
    } else {
      detail.innerHTML = buildDietDetailHtml(groupId, item);
    }
    if ((!options || options.scroll !== false) && detail.innerHTML) {
      detail.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
  });
}

function buildBreadcrumb(path){
  const parts = [];
  const homeLabel = escapeHtml(trFaq('home'));
  if (path.length === 0) {
    parts.push(`<span class="faq-crumb current">${homeLabel}</span>`);
  } else {
    parts.push(`<button type="button" class="faq-crumb" data-faq-path="">${homeLabel}</button>`);
  }
  // If we are navigating within the UKK (FAQ) context, include an extra crumb level
  // so the nav shows: Päävalikko › UKK › <Category>
  if (faqState.context === 'faq' && path.length > 0) {
    parts.push('<span class="faq-sep">›</span>');
    parts.push(`<button type="button" class="faq-crumb" data-action="open-faq-root">${escapeHtml(trFaq('rootFaq'))}</button>`);
  }
  path.forEach((_, idx) => {
    const prefix = path.slice(0, idx + 1);
    const key = pathKey(prefix);
    const node = faqState.nodes.get(key);
    const label = escapeHtml((node && node.label) || prefix[prefix.length - 1] || '');
    const sep = '<span class="faq-sep">›</span>';
    if (idx === 0 && path.length === 0) return;
    parts.push(sep);
    if (idx === path.length - 1) {
      parts.push(`<span class="faq-crumb current">${label}</span>`);
    } else {
      parts.push(`<button type="button" class="faq-crumb" data-faq-path="${key}">${label}</button>`);
    }
  });
  return `<nav class="faq-crumbs">${parts.join('')}</nav>`;
}

async function ensureFaqTree(forceReload = false){
  const lang = currentLang || 'fi';
  if (!forceReload && faqState.tree && faqState.lang === lang) {
    return faqState.tree;
  }
  const res = await fetch(`/faq/tree?lang=${encodeURIComponent(lang)}`);
  if (!res.ok) {
    throw new Error(`Failed to load FAQ tree: ${res.status}`);
  }
  const data = await res.json();
  const tree = Array.isArray(data.tree) ? data.tree : [];
  const nodes = new Map();
  const index = (items) => {
    items.forEach((node) => {
      const key = pathKey(node.path || []);
      nodes.set(key, node);
      if (Array.isArray(node.children) && node.children.length) {
        index(node.children);
      }
    });
  };
  index(tree);
  faqState.tree = tree;
  faqState.nodes = nodes;
  faqState.entries = new Map();
  faqState.version = data.version || null;
  faqState.lang = lang;
  return tree;
}

async function loadFaqEntries(path){
  const key = pathKey(path);
  if (faqState.entries.has(key)) {
    return faqState.entries.get(key);
  }
  const lang = currentLang || 'fi';
  const versionParam = faqState.version ? `&v=${encodeURIComponent(faqState.version)}` : '';
  const res = await fetch(`/faq/entries?path=${encodeURIComponent(key)}&lang=${encodeURIComponent(lang)}${versionParam}`);
  if (res.status === 404) {
    faqState.entries.set(key, []);
    return [];
  }
  if (!res.ok) {
    throw new Error(`Failed to load FAQ entries: ${res.status}`);
  }
  const data = await res.json();
  const items = Array.isArray(data.items) ? data.items : [];
  faqState.entries.set(key, items);
  return items;
}

async function loadMenuHtml(kind){
  const lang = currentLang || 'fi';
  const versionParam = faqState.version ? `&v=${encodeURIComponent(faqState.version)}` : '';
  const res = await fetch(`/faq/menu?menu_type=${encodeURIComponent(kind)}&lang=${encodeURIComponent(lang)}${versionParam}`);
  if (!res.ok) {
    throw new Error(`Failed to load menu: ${res.status}`);
  }
  const data = await res.json();
  return data.html || '';
}

function renderFaqCategories(children, path){
  faqState.currentPath = path.slice();
  const info = escapeHtml(path.length ? trFaq('chooseSub') : trFaq('chooseRoot'));
  const crumb = buildBreadcrumb(path);
  const list = (children || []).map((child) => {
    const label = escapeHtml(child.label || child.id || '');
    const childKey = pathKey(child.path || []);
    return `<button type="button" class="faq-item" data-faq-path="${childKey}"><span class="faq-item-label">${label}</span></button>`;
  }).join('');
  const content = list || `<div class="faq-empty">${escapeHtml(trFaq('noEntries'))}</div>`;
  renderFaqPanel(`${crumb}<div class="faq-intro">${info}</div><div class="faq-list faq-categories">${content}</div>`, path);
}

async function renderFaqEntries(path){
  faqState.currentPath = path.slice();
  chatLog.querySelectorAll('.faq-answer').forEach(panel => {
    const wrap = panel.closest('.msg');
    if (wrap) wrap.remove();
  });
  renderFaqPanel(`<div class="faq-intro">${escapeHtml(trFaq('loading'))}</div>`, path);
  let entries = [];
  try {
    entries = await loadFaqEntries(path);
  } catch (err) {
    console.error(err);
    renderFaqError(trFaq('loadError'), path);
    return;
  }
  const crumb = buildBreadcrumb(path);
  const intro = escapeHtml(trFaq('chooseQuestion'));
  const key = pathKey(path);
  const list = entries.map((entry) => {
    const q = entry.question?.[currentLang] || entry.question?.fi || entry.default_question || '';
    return `<button type="button" class="faq-question" data-faq-question="${entry.id}" data-faq-scope="${key}">${escapeHtml(q)}</button>`;
  }).join('');
  const content = list || `<div class="faq-empty">${escapeHtml(trFaq('noEntries'))}</div>`;
  renderFaqPanel(`${crumb}<div class="faq-intro">${intro}</div><div class="faq-list faq-questions">${content}</div>`, path);
}

function renderFaqAnswer(entry, path){
  const scopeKey = pathKey(path);
  const question = entry.question?.[currentLang] || entry.question?.fi || entry.default_question || '';
  let answer = entry.answer?.[currentLang] || entry.answer?.fi || entry.default_answer || '';
  const trimmed = (answer || '').trim();
  const hasHtml = /<[a-z]+[^>]*>/i.test(trimmed);
  if (!hasHtml) {
    answer = `<p>${escapeHtml(answer)}</p>`;
  } else if (!trimmed.startsWith('<')) {
    const firstTagIndex = trimmed.search(/<[a-z]+[^>]*>/i);
    if (firstTagIndex > 0) {
      const textPart = trimmed.slice(0, firstTagIndex);
      const htmlPart = trimmed.slice(firstTagIndex);
      answer = `<p>${escapeHtml(textPart)}</p>${htmlPart}`;
    }
  }
  chatLog.querySelectorAll('.faq-answer').forEach(panel => {
    const wrap = panel.closest('.msg');
    if (wrap) wrap.remove();
  });
  const html = `<div class="faq-answer" data-faq-scope="${scopeKey}" tabindex="-1">
    <div class="faq-answer-question">${escapeHtml(question)}</div>
    <div class="faq-answer-body">${answer}</div>
    <div class="faq-answer-actions"><button type="button" data-faq-answer-back>${escapeHtml(trFaq('backToList'))}</button></div>
  </div>`;
  addBotHtml(html);
  requestAnimationFrame(() => {
    const answerNode = chatLog.querySelector(`.faq-answer[data-faq-scope="${scopeKey}"]`);
    focusFirstFaqControl(answerNode);
  });
}

async function renderFaqRoot(force = false){
  try {
    await ensureFaqTree(force);
    renderFaqMainMenu();
  } catch (err) {
    console.error(err);
    renderFaqError(trFaq('loadError'), []);
  }
}

async function openFaqPath(path){
  await ensureFaqTree();
  const key = pathKey(path);
  if (key === 'menu.menu-tuoreet') {
    await renderMenuTuoreetDetail();
    return;
  }
  if (key === 'menu.menu-pakasteet') {
    await renderMenuPakasteDetail();
    return;
  }
  if (key === 'menu.ruokavaliot') {
    await renderMenuDietary();
    return;
  }
  if (path.length === 0) {
    renderFaqMainMenu();
    return;
  }
  const node = faqState.nodes.get(key);
  if (node && Array.isArray(node.children) && node.children.length) {
    renderFaqCategories(node.children, path);
    return;
  }
  if (!node && path.length > 0) {
    console.warn('Unknown FAQ path', key);
    renderFaqError(trFaq('loadError'), path.slice(0, -1));
    return;
  }
  await renderFaqEntries(path);
}

function labelForPath(path){
  const node = faqState.nodes.get(pathKey(path));
  if (!node) {
    return path[path.length - 1] || '';
  }
  const labels = node.labels || {};
  return labels[currentLang] || node.label || labels.fi || labels.en || path[path.length - 1] || '';
}

function buildCustomCrumb(label){
  const home = escapeHtml(trFaq('home'));
  const current = escapeHtml(label || '');
  return `<nav class="faq-crumbs"><button type="button" class="faq-crumb" data-action="back-to-root">${home}</button><span class="faq-sep">›</span><span class="faq-crumb current">${current}</span></nav>`;
}

function renderFaqMainMenu(){
  faqState.currentPath = [];
  faqState.context = 'main';
  const crumb = buildBreadcrumb([]);
  const intro = `<div class="faq-intro">${escapeHtml(trFaq('chooseRoot'))}</div>`;
  // Show FAQ (UKK) first in the main actions
  const actions = `<div class="faq-actions faq-root-actions">
    <button type="button" data-action="root-open-faq">${escapeHtml(trFaq('rootFaq'))}</button>
    <button type="button" data-action="root-open-menu">${escapeHtml(trFaq('rootMenu'))}</button>
    <button type="button" data-action="root-open-ordering">${escapeHtml(trFaq('rootOrdering'))}</button>
    <button type="button" data-action="root-open-feedback">${escapeHtml(trFaq('rootFeedback'))}</button>
  </div>`;
  renderFaqPanel(`${crumb}${intro}${actions}`, []);
}

async function renderFaqTopicMenu(){
  await ensureFaqTree();
  faqState.currentPath = [];
  faqState.context = 'faq';
  const crumb = buildCustomCrumb(trFaq('rootFaq'));
  const intro = `<div class="faq-intro">${escapeHtml(trFaq('chooseRoot'))}</div>`;
  const topics = [
    { path: ['tutustu'], label: labelForPath(['tutustu']) },
    { path: ['tuotteet'], label: labelForPath(['tuotteet']) },
    // Expose ordering subsections under UKK as "Tilaukset"
    { path: ['tilaus'], label: trFaq('faqOrders') },
    { path: ['maksaminen'], label: labelForPath(['maksaminen']) },
    { path: ['kestavyys'], label: trFaq('otherLabel') },
  ];
  const buttons = topics.map((topic) => {
    const label = escapeHtml(topic.label || '');
    const key = pathKey(topic.path);
    return `<button type="button" class="faq-item" data-faq-path="${key}"><span class="faq-item-label">${label}</span></button>`;
  }).join('');
  const content = `<div class="faq-list faq-categories">${buttons}</div>`;
  const back = `<div class="faq-back"><button type="button" data-action="back-to-root">${escapeHtml(trFaq('goBack'))}</button></div>`;
  renderFaqPanel(`${crumb}${intro}${content}${back}`, []);
}

async function renderOrderingHub(){
  await ensureFaqTree();
  faqState.currentPath = [];
  const crumb = buildCustomCrumb(trFaq('rootOrdering'));
  const introText = trFaq('orderingIntro') || trFaq('chooseOrdering') || trFaq('chooseSub');
  const intro = `<div class="faq-intro">${escapeHtml(introText)}</div>`;
  const quickActions = `<div class="faq-actions"><button type="button" data-action="menu-order-chat">${escapeHtml(trFaq('orderInChat'))}</button><button type="button" data-action="menu-order-online">${escapeHtml(trFaq('orderOnline'))}</button></div>`;
  const options = [
    { path: ['tilaus', 'tilaamisen-peruspolku'] },
    { path: ['tilaus', 'suuret-ja-rateloidyt'] },
    { path: ['tilaus', 'nouto-ja-toimitus'] },
  ];
  const buttons = options.map((option) => {
    const label = escapeHtml(labelForPath(option.path));
    const key = pathKey(option.path);
    return `<button type="button" class="faq-item" data-faq-path="${key}"><span class="faq-item-label">${label}</span></button>`;
  }).join('');
  const content = `<div class="faq-list faq-categories ordering-grid">${buttons}</div>`;
  const back = `<div class="faq-back"><button type="button" data-action="back-to-root">${escapeHtml(trFaq('goBack'))}</button></div>`;
  renderFaqPanel(`${crumb}${intro}${quickActions}${content}${back}`, []);
}

function buildFeedbackForm(){
  const title = escapeHtml(tr('feedback_header') || trFaq('feedbackTitle'));
  const prompt = tr('feedback_prompt') ? `<p>${escapeHtml(tr('feedback_prompt'))}</p>` : '';
  const nameLabel = escapeHtml(tr('ask_name'));
  const emailLabel = escapeHtml(tr('ask_email'));
  const emailOptional = escapeHtml(tr('ask_email_optional') || '');
  const emailCombined = emailOptional ? `${emailLabel} ${emailOptional}` : emailLabel;
  const messageLabel = escapeHtml(tr('feedback_message') || trFaq('feedbackTitle'));
  const placeholder = escapeHtml(tr('feedback_placeholder') || '');
  const submitLabel = escapeHtml(tr('feedback_submit') || trFaq('rootFeedback'));
  const langValue = escapeHtml(currentLang || '');
  return `<div class="feedback-ui">
    <div class="title">${title}</div>
    ${prompt}
    <form class="feedback-form">
      <div class="row">
        <label>${nameLabel}</label>
        <input type="text" name="name" placeholder="${nameLabel}">
      </div>
      <div class="row">
        <label>${emailCombined}</label>
        <input type="email" name="email" placeholder="${emailCombined}">
      </div>
      <div class="row">
        <label>${messageLabel}</label>
        <textarea name="message" rows="4" placeholder="${placeholder}" required></textarea>
      </div>
      <input type="hidden" name="lang" value="${langValue}">
      <input type="hidden" name="context" value="faq_feedback">
      <div class="actions">
        <button type="submit" class="btn btn-primary">${submitLabel}</button>
      </div>
    </form>
  </div>`;
}

function renderFeedbackPanel(){
  faqState.currentPath = [];
  const crumb = buildCustomCrumb(trFaq('rootFeedback'));
  const intro = `<div class="faq-intro">${escapeHtml(trFaq('feedbackIntro'))}</div>`;
  const form = buildFeedbackForm();
  const back = `<div class="faq-back"><button type="button" data-action="back-to-root">${escapeHtml(trFaq('goBack'))}</button></div>`;
  renderFaqPanel(`${crumb}${intro}${form}${back}`, []);
}

function showLanguagePicker(){
  const isMobile = window.matchMedia('(max-width: 520px)').matches;
  let html;
  if (isMobile) {
    // Mobile: flags only, horizontal layout
    html = `<div class="lang-picker mobile">
      <div class="lang-title">Valitse kieli</div>
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
      try { document.cookie = `chat_lang=${currentLang}; path=/; max-age=${60*60*24*30}`; } catch(e) {}
      // Show welcome in chosen language
      addBot(welcomeForLang(currentLang));
      chatLog.dataset.welcomed = "1";
      renderFaqRoot(true);
      // Remove the language picker bubble after selection
      const container = last.closest('.msg');
      if (container) container.remove();
    });
  }
}

if (chatInput && (!chatCard || !chatCard.classList.contains('readonly'))){
  chatInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendBtn.click();
    }
  });
}

chatForm.addEventListener('submit', async (e) => {
  e.preventDefault();
  if (chatCard && chatCard.classList.contains('readonly')) {
    return;
  }
  const text = chatInput.value.trim();
  if (!text) return;
  addUser(text);
  chatInput.value = '';
  setTyping(true);
  try {
    const res = await fetch('/api/chat_dual', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message: text, lang: currentLang || undefined, legacy: !!showLegacy, rag: !!showRag })
    });
    if (!res.ok) throw new Error('Network error');
    const data = await res.json();
    setTyping(false);
    // If dual payload: show both legacy and RAG answers. Else fallback to single.
    if (data && (data.legacy || data.rag)) {
      const renderAnswer = (reply) => {
        const txt = reply || '';
        const isHtml = /^\s*</.test(txt) || txt.includes('order-ui');
        if (isHtml) {
          addBotHtml(txt);
        } else {
          addBotHtml(`<div>${escapeHtml(txt)}</div>`);
        }
      };
      let rendered = false;
      if (showRag && data.rag && data.rag.reply) {
        renderAnswer(data.rag.reply);
        rendered = true;
      }
      if (!rendered && showLegacy && data.legacy && data.legacy.reply) {
        renderAnswer(data.legacy.reply);
        rendered = true;
      }
      if (!rendered) {
        const fallback = (data.rag && data.rag.reply) || (data.legacy && data.legacy.reply) || '';
        if (fallback) renderAnswer(fallback);
      }
    } else {
      const reply = data.reply || '...';
      if (/^\s*</.test(reply) || reply.includes('order-ui')) {
        addBotHtml(reply);
      } else {
        addBot(reply);
      }
    }
  } catch (err) {
    setTyping(false);
    addBot('Sorry, something went wrong. Please try again.');
    console.error(err);
  }
});

// Quick language switcher button in header
const changeLangBtn = qs('#changeLang');
if (changeLangBtn){
  changeLangBtn.addEventListener('click', (e)=>{
    e.preventDefault();
    showLanguagePicker();
  });
}
