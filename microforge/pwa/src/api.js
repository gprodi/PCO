// Client des deux API MicroForge (même logique que app_streamlit/client.py) :
// jeton d'accès en mémoire, jeton de rafraîchissement conservé le temps de l'onglet (sessionStorage),
// renouvellement automatique sur une réponse 401 puis nouvel essai de la requête.

export class ApiError extends Error {
  constructor(status, detail) {
    super(typeof detail === 'string' ? detail : JSON.stringify(detail));
    this.status = status;
    this.detail = detail;
  }
}

/** L'API n'a pas répondu du tout : service arrêté, mauvaise adresse ou origine refusée (CORS). */
export class NetworkError extends Error {
  constructor(url) {
    super(`API injoignable : ${url}`);
    this.url = url;
  }
}

const REFRESH_KEY = 'mf-refresh';

/** Accès au stockage de session qui ne lève jamais (navigation privée, stockage bloqué). */
export function safeStorage(store) {
  return {
    get: (k) => { try { return store?.getItem(k) ?? null; } catch { return null; } },
    set: (k, v) => { try { store?.setItem(k, v); } catch { /* stockage indisponible */ } },
    remove: (k) => { try { store?.removeItem(k); } catch { /* stockage indisponible */ } },
  };
}

async function readError(res) {
  let detail = res.statusText || `HTTP ${res.status}`;
  try {
    const body = await res.json();
    detail = body.detail ?? body;
  } catch { /* corps non JSON */ }
  return new ApiError(res.status, detail);
}

export function createClient({ dataUrl, iaUrl, fetchImpl = globalThis.fetch.bind(globalThis), storage }) {
  const store = storage ?? safeStorage(globalThis.sessionStorage);
  let access = null;
  let refresh = store.get(REFRESH_KEY);

  const keep = (tokens) => {
    access = tokens.access_token;
    refresh = tokens.refresh_token;
    store.set(REFRESH_KEY, refresh);
  };
  const forget = () => {
    access = null;
    refresh = null;
    store.remove(REFRESH_KEY);
  };

  async function send(base, path, { method = 'GET', json, form, body } = {}) {
    const headers = {};
    if (access) headers.Authorization = `Bearer ${access}`;
    let payload = body;
    if (json !== undefined) {
      headers['Content-Type'] = 'application/json';
      payload = JSON.stringify(json);
    } else if (form !== undefined) {
      headers['Content-Type'] = 'application/x-www-form-urlencoded';
      payload = new URLSearchParams(form).toString();
    }
    return reach(base, `${base}${path}`, { method, headers, body: payload });
  }

  // Le navigateur ne dit rien de plus que « Failed to fetch » : on garde au moins l'adresse visée.
  async function reach(base, url, init) {
    try {
      return await fetchImpl(url, init);
    } catch {
      throw new NetworkError(base);
    }
  }

  async function renew() {
    if (!refresh) return false;
    const res = await reach(dataUrl, `${dataUrl}/v1/auth/refresh`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ refresh_token: refresh }),
    });
    if (!res.ok) {
      forget();
      return false;
    }
    keep(await res.json());
    return true;
  }

  async function call(base, path, options = {}) {
    let res = await send(base, path, options);
    if (res.status === 401 && (await renew())) res = await send(base, path, options);
    if (!res.ok) throw await readError(res);
    return res.status === 204 ? null : res.json();
  }

  return {
    get loggedIn() { return Boolean(access || refresh); },
    async register({ username, email, password, city = null, consent = false }) {
      return call(dataUrl, '/v1/auth/register', {
        method: 'POST',
        json: { username, email, password, city: city || null, consent_training: consent },
      });
    },
    async login(username, password) {
      const res = await send(dataUrl, '/v1/auth/token', { method: 'POST', form: { username, password } });
      if (!res.ok) throw await readError(res);
      keep(await res.json());
    },
    async logout() {
      if (refresh) {
        await send(dataUrl, '/v1/auth/logout', { method: 'POST', json: { refresh_token: refresh } }).catch(() => {});
      }
      forget();
    },
    me: () => call(dataUrl, '/v1/users/me'),
    /** Tout le catalogue de composants (l'API pagine par 200 au plus). */
    async components() {
      const all = [];
      for (let offset = 0; ; offset += 200) {
        const page = await call(dataUrl, `/v1/components?limit=200&offset=${offset}`);
        all.push(...page);
        if (page.length < 200) return all;
      }
    },
    boards: () => call(dataUrl, '/v1/boards'),
    inventory: () => call(dataUrl, '/v1/inventory'),
    summary: () => call(dataUrl, '/v1/inventory/summary'),
    addItem: (item) => call(dataUrl, '/v1/inventory', { method: 'POST', json: item }),
    addBulk: (items, location) => call(dataUrl, '/v1/inventory/bulk', { method: 'POST', json: { items, location } }),
    deleteItem: (id) => call(dataUrl, `/v1/inventory/${id}`, { method: 'DELETE' }),
    scan(file) {
      const body = new FormData();
      body.append('image', file, file.name || 'photo.jpg');
      return call(iaUrl, '/v1/vision/scan', { method: 'POST', body });
    },
    suggest: (inventory, limit = 12) => call(iaUrl, '/v1/builds/suggest', { method: 'POST', json: { inventory, limit } }),
    generate: (templateId, board) =>
      call(iaUrl, '/v1/builds/generate', { method: 'POST', json: { template_id: templateId, board } }),
    ask: (question, inventory = null) => call(iaUrl, '/v1/copilot/ask', { method: 'POST', json: { question, inventory } }),
    /** Thèmes et idées (145), annotés avec le stock : pièces manquantes, réalisable ou non. */
    explore: (inventory) => call(iaUrl, '/v1/ideas/explore', { method: 'POST', json: { inventory } }),
    /** Parcours de progression, vitrine de vrais projets, chiffres du catalogue. */
    inspiration: () => call(iaUrl, '/v1/ideas/inspiration'),
  };
}
