const FIRM_ID_KEY = 'firmId';
function getCsrf() {
    const match = document.cookie.match(/csrftoken=([^;]+)/);
    return match?.[1] ?? '';
}
function getFirmId() {
    return localStorage.getItem(FIRM_ID_KEY) ?? '';
}
async function request(method, url, body) {
    const headers = {
        'Content-Type': 'application/json',
        'X-CSRFToken': getCsrf(),
    };
    const firmId = getFirmId();
    if (firmId) {
        headers['X-Firm-ID'] = firmId;
    }
    const res = await fetch(url, {
        method,
        credentials: 'include',
        headers,
        body: body !== undefined ? JSON.stringify(body) : undefined,
    });
    let data;
    try {
        data = await res.json();
    }
    catch {
        data = null;
    }
    return { ok: res.ok, status: res.status, data };
}
async function requestFormData(method, url, formData) {
    const headers = {
        'X-CSRFToken': getCsrf(),
    };
    const firmId = getFirmId();
    if (firmId) {
        headers['X-Firm-ID'] = firmId;
    }
    const res = await fetch(url, {
        method,
        credentials: 'include',
        headers,
        body: formData,
    });
    let data;
    try {
        data = await res.json();
    }
    catch {
        data = null;
    }
    return { ok: res.ok, status: res.status, data };
}
export const api = {
    get: (url) => request('GET', url),
    post: (url, body) => request('POST', url, body),
    put: (url, body) => request('PUT', url, body),
    patch: (url, body) => request('PATCH', url, body),
    delete: (url) => request('DELETE', url),
    postForm: (url, formData) => requestFormData('POST', url, formData),
};
