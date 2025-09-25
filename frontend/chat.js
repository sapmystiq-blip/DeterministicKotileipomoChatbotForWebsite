const qs = (s, el=document) => el.querySelector(s);
const chatWidget = qs('#chatWidget');
// Support either a full-width demo button or a floating bubble
const launcher = qs('#chat-bubble') || qs('#toggleChat');
const closeBtn = qs('#closeChat');
const chatLog = qs('#chatLog');
const chatForm = qs('#chatForm');
const chatInput = qs('#chatInput');
const sendBtn = qs('#sendBtn');

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
    chatInput.focus();
    const hasMsgs = !!chatLog.querySelector('.msg');
    if (!hasMsgs && !chatLog.dataset.welcomed) {
      // Show a welcome message and keep input enabled. Users can still change language later.
      addBot(welcomeForLang(currentLang));
      chatLog.dataset.welcomed = "1";
    } else if (!chatLog.dataset.welcomed && currentLang) {
      addBot(welcomeForLang(currentLang));
      chatLog.dataset.welcomed = "1";
    }
  }
}

if (launcher) launcher.addEventListener('click', () => toggleChat());
if (closeBtn) closeBtn.addEventListener('click', () => toggleChat(false));

// Order flow v2: categories → products → cart → guided checkout
chatLog.addEventListener('click', async (e) => {
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
    const text = sugg.getAttribute('data-suggest');
    if (text){
      chatInput.value = text;
      try {
        if (typeof chatForm.requestSubmit === 'function') { chatForm.requestSubmit(); }
        else { chatForm.dispatchEvent(new Event('submit', { cancelable: true, bubbles: true })); }
      } catch (err) {
        // fallback to clicking the send button
        try { sendBtn.click(); } catch(_){}
      }
    }
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
  chatInput.disabled = !enabled;
  sendBtn.disabled = !enabled;
}

function welcomeForLang(lang){
  switch(lang){
    case 'fi': return "Hei! Olen Piirakkabotti. Kysy tuotteista, aukioloajoista, ruokalistasta, tilauksista tai allergioista.";
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
