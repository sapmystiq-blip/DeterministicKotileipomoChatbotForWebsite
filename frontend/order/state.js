const ORDER_KEY = 'order_session_v1';

export const orderSession = {
  cart: [],
  pickupDate: null,
  pickupTime: null,
  name: '',
  email: '',
  phone: '',
  note: '',
  step: null,
};

export function save() {
  try { localStorage.setItem(ORDER_KEY, JSON.stringify(orderSession)); } catch {}
}

export function load() {
  try {
    const v = JSON.parse(localStorage.getItem(ORDER_KEY) || 'null');
    if (v && typeof v === 'object') Object.assign(orderSession, v);
  } catch {}
}

export function reset() {
  orderSession.cart = [];
  orderSession.pickupDate = null;
  orderSession.pickupTime = null;
  orderSession.name = orderSession.email = orderSession.phone = orderSession.note = '';
  orderSession.step = null;
  save();
}

