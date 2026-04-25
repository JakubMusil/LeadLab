/**
 * LeadLab API Client
 * Handles all communication with the Django Ninja backend.
 */

const API_BASE = '/api/v1';

function getCsrfToken() {
  const match = document.cookie.match(/csrftoken=([^;]+)/);
  return match ? match[1] : '';
}

async function apiFetch(path, options = {}) {
  const headers = {
    'Content-Type': 'application/json',
    'X-CSRFToken': getCsrfToken(),
    ...options.headers,
  };

  const firmId = localStorage.getItem('firmId');
  if (firmId) headers['X-Firm-ID'] = firmId;

  const res = await fetch(`${API_BASE}${path}`, {
    credentials: 'include',
    ...options,
    headers,
  });

  if (res.status === 401) {
    window.location.href = '/login/';
    return null;
  }

  const text = await res.text();
  try {
    const data = JSON.parse(text);
    return { status: res.status, ok: res.ok, data };
  } catch {
    return { status: res.status, ok: res.ok, data: text };
  }
}

// ------------------------------------------------------------------
// Auth
// ------------------------------------------------------------------
const Auth = {
  async register(email, password, firstName, lastName) {
    return apiFetch('/users/register', {
      method: 'POST',
      body: JSON.stringify({ email, password, first_name: firstName, last_name: lastName }),
    });
  },

  async login(email, password) {
    return apiFetch('/users/login', {
      method: 'POST',
      body: JSON.stringify({ email, password }),
    });
  },

  async logout() {
    await apiFetch('/users/logout', { method: 'POST' });
    localStorage.removeItem('firmId');
    localStorage.removeItem('user');
    window.location.href = '/login/';
  },

  async me() {
    return apiFetch('/users/me');
  },
};

// ------------------------------------------------------------------
// Firms
// ------------------------------------------------------------------
const Firms = {
  async list() {
    return apiFetch('/firms/');
  },

  async create(name) {
    return apiFetch('/firms/', { method: 'POST', body: JSON.stringify({ name }) });
  },

  async get(firmId) {
    return apiFetch(`/firms/${firmId}`);
  },

  async listMembers(firmId) {
    return apiFetch(`/firms/${firmId}/members`);
  },

  async invite(firmId, email, role = 'worker') {
    return apiFetch(`/firms/${firmId}/members`, {
      method: 'POST',
      body: JSON.stringify({ email, role }),
    });
  },

  async removeMember(firmId, membershipId) {
    return apiFetch(`/firms/${firmId}/members/${membershipId}`, { method: 'DELETE' });
  },
};

// ------------------------------------------------------------------
// CRM – Leads
// ------------------------------------------------------------------
const Leads = {
  async list(params = {}) {
    const qs = new URLSearchParams(params).toString();
    return apiFetch(`/crm/leads${qs ? '?' + qs : ''}`);
  },

  async get(id) {
    return apiFetch(`/crm/leads/${id}`);
  },

  async create(data) {
    return apiFetch('/crm/leads', { method: 'POST', body: JSON.stringify(data) });
  },

  async update(id, data) {
    return apiFetch(`/crm/leads/${id}`, { method: 'PATCH', body: JSON.stringify(data) });
  },

  async remove(id) {
    return apiFetch(`/crm/leads/${id}`, { method: 'DELETE' });
  },

  async activities(leadId, page = 1) {
    return apiFetch(`/crm/leads/${leadId}/activities?page=${page}&page_size=20`);
  },
};

// ------------------------------------------------------------------
// CRM – Customers
// ------------------------------------------------------------------
const Customers = {
  async list(search = '') {
    return apiFetch(`/crm/customers${search ? '?search=' + encodeURIComponent(search) : ''}`);
  },

  async get(id) {
    return apiFetch(`/crm/customers/${id}`);
  },

  async create(data) {
    return apiFetch('/crm/customers', { method: 'POST', body: JSON.stringify(data) });
  },

  async update(id, data) {
    return apiFetch(`/crm/customers/${id}`, { method: 'PUT', body: JSON.stringify(data) });
  },

  async remove(id) {
    return apiFetch(`/crm/customers/${id}`, { method: 'DELETE' });
  },
};

// ------------------------------------------------------------------
// CRM – Tasks
// ------------------------------------------------------------------
const Tasks = {
  async list(completed = null) {
    const qs = completed !== null ? `?completed=${completed}` : '';
    return apiFetch(`/crm/tasks${qs}`);
  },

  async create(data) {
    return apiFetch('/crm/tasks', { method: 'POST', body: JSON.stringify(data) });
  },

  async complete(id) {
    return apiFetch(`/crm/tasks/${id}/complete`, { method: 'POST' });
  },
};

// ------------------------------------------------------------------
// CRM – Activities
// ------------------------------------------------------------------
const Activities = {
  async create(data) {
    return apiFetch('/crm/activities', { method: 'POST', body: JSON.stringify(data) });
  },
};

// ------------------------------------------------------------------
// CRM – Stats
// ------------------------------------------------------------------
const Stats = {
  async get() {
    return apiFetch('/crm/stats');
  },
};

// ------------------------------------------------------------------
// Utility helpers
// ------------------------------------------------------------------
function fmtCurrency(value, currency = 'CZK') {
  if (value == null) return '—';
  return new Intl.NumberFormat('cs-CZ', { style: 'currency', currency }).format(value);
}

function fmtDate(iso) {
  if (!iso) return '—';
  return new Date(iso).toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' });
}

function fmtDateTime(iso) {
  if (!iso) return '—';
  return new Date(iso).toLocaleString('en-GB', {
    day: '2-digit', month: 'short', year: 'numeric',
    hour: '2-digit', minute: '2-digit',
  });
}

function timeAgo(iso) {
  const diff = (Date.now() - new Date(iso)) / 1000;
  if (diff < 60) return 'just now';
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
  return `${Math.floor(diff / 86400)}d ago`;
}

function statusBadge(status) {
  const map = {
    new: 'bg-blue-100 text-blue-700',
    contacted: 'bg-yellow-100 text-yellow-700',
    proposal: 'bg-purple-100 text-purple-700',
    negotiation: 'bg-orange-100 text-orange-700',
    won: 'bg-green-100 text-green-700',
    lost: 'bg-red-100 text-red-700',
    canceled: 'bg-gray-100 text-gray-500',
  };
  return map[status] || 'bg-gray-100 text-gray-500';
}

function showToast(message, type = 'success') {
  const colors = {
    success: 'bg-green-600',
    error: 'bg-red-600',
    info: 'bg-blue-600',
  };
  const toast = document.createElement('div');
  toast.className = `fixed bottom-6 right-6 z-50 px-5 py-3 rounded-lg text-white text-sm font-medium shadow-lg transition-all ${colors[type] || colors.success}`;
  toast.textContent = message;
  document.body.appendChild(toast);
  setTimeout(() => toast.remove(), 3500);
}

// ------------------------------------------------------------------
// Boot: ensure user + firm are loaded
// ------------------------------------------------------------------
async function bootDashboard() {
  const res = await Auth.me();
  if (!res || !res.ok) {
    window.location.href = '/login/';
    return null;
  }

  const user = res.data;
  localStorage.setItem('user', JSON.stringify(user));

  // If no firm selected, pick or prompt
  if (!localStorage.getItem('firmId')) {
    const firmRes = await Firms.list();
    if (firmRes.ok && firmRes.data.length > 0) {
      localStorage.setItem('firmId', firmRes.data[0].id);
    } else {
      // Redirect to a firm creation prompt (handled in dashboard page itself)
      return { user, firm: null };
    }
  }

  return { user };
}
