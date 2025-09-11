// Controller entrypoint for the ordering flow (WIP module split)
// For now, this file is a placeholder that will orchestrate UI modules.

import { getCategories, getProducts, getConstraints, postOrder } from './api.js';
import { orderSession, load, save, reset } from './state.js';

export async function startOrderFlow(lang) {
  // Placeholder: call existing legacy function to avoid breaking current UI
  load();
  if (typeof window !== 'undefined' && typeof window.startOrderInChat === 'function') {
    window.startOrderInChat();
    return;
  }
  console.warn('startOrderFlow: legacy startOrderInChat is not available yet.');
}

