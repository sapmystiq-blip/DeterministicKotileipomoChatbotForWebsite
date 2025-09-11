// Lightweight API wrapper for ordering endpoints
export async function getCategories() {
  const r = await fetch('/api/categories');
  if (!r.ok) throw new Error('categories');
  return r.json();
}

export async function getProducts(category) {
  const url = category ? `/api/products?category=${encodeURIComponent(category)}` : '/api/products';
  const r = await fetch(url);
  if (!r.ok) throw new Error('products');
  return r.json();
}

export async function getConstraints() {
  const r = await fetch('/api/order_constraints');
  if (!r.ok) throw new Error('constraints');
  return r.json();
}

export async function postOrder(payload) {
  const r = await fetch('/api/order', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(payload)});
  const body = await r.json().catch(()=>({}));
  if (!r.ok) {
    const msg = body && (body.detail || body.error || body.message) || 'Order failed';
    throw new Error(msg);
  }
  return body;
}

