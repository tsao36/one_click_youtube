const nativeFetch = window.fetch.bind(window);

async function apiRequest(url, options = {}) {
  let response;
  try {
    response = await nativeFetch(url, options);
  } catch (error) {
    throw new Error(error?.message || 'Network request failed');
  }
  if (response.ok) return response;
  const body = await response.json().catch(() => ({}));
  const detail = Array.isArray(body.detail)
    ? body.detail.map(item => item.msg || JSON.stringify(item)).join('; ')
    : (body.detail || body.message);
  throw new Error(detail || `Request failed (${response.status})`);
}

async function apiJson(url, options = {}) {
  const response = await apiRequest(url, options);
  return response.json();
}

function escapeHtml(value) {
  return String(value ?? '').replace(/[&<>"']/g, char => ({
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    '"': '&quot;',
    "'": '&#39;'
  })[char]);
}
