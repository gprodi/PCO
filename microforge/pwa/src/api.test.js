import { describe, expect, it } from 'vitest';
import { ApiError, NetworkError, createClient, safeStorage } from './api.js';

const DATA = 'http://data';
const IA = 'http://ia';

function memoryStorage() {
  const m = new Map();
  return { get: (k) => m.get(k) ?? null, set: (k, v) => m.set(k, v), remove: (k) => m.delete(k), m };
}

/** Faux serveur : une liste de réponses servies dans l'ordre, et le journal des requêtes. */
function fakeFetch(responses) {
  const calls = [];
  const fn = async (url, init = {}) => {
    calls.push({ url, ...init });
    const r = responses.shift();
    if (!r) throw new Error(`requête inattendue : ${url}`);
    return new Response(r.body === undefined ? null : JSON.stringify(r.body), { status: r.status ?? 200 });
  };
  fn.calls = calls;
  return fn;
}

const tokens = (n) => ({ access_token: `a${n}`, refresh_token: `r${n}`, token_type: 'bearer', expires_in: 900 });

describe('client MicroForge', () => {
  it('connexion : jetons gardés, accès envoyé en Bearer', async () => {
    const fetchImpl = fakeFetch([{ body: tokens(1) }, { body: { esp32: 1 } }]);
    const storage = memoryStorage();
    const c = createClient({ dataUrl: DATA, iaUrl: IA, fetchImpl, storage });
    await c.login('lea', 'motdepasse123');
    expect(c.loggedIn).toBe(true);
    expect(storage.m.get('mf-refresh')).toBe('r1');
    expect(fetchImpl.calls[0].body).toBe('username=lea&password=motdepasse123');
    expect(await c.summary()).toEqual({ esp32: 1 });
    expect(fetchImpl.calls[1].headers.Authorization).toBe('Bearer a1');
  });

  it('jeton expiré : renouvelé puis requête rejouée', async () => {
    const fetchImpl = fakeFetch([{ body: tokens(1) }, { status: 401, body: { detail: 'expiré' } }, { body: tokens(2) }, { body: [] }]);
    const c = createClient({ dataUrl: DATA, iaUrl: IA, fetchImpl, storage: memoryStorage() });
    await c.login('lea', 'x');
    expect(await c.inventory()).toEqual([]);
    expect(fetchImpl.calls[2].url).toBe(`${DATA}/v1/auth/refresh`);
    expect(JSON.parse(fetchImpl.calls[2].body)).toEqual({ refresh_token: 'r1' });
    expect(fetchImpl.calls[3].headers.Authorization).toBe('Bearer a2');
  });

  it('rafraîchissement refusé : session oubliée et erreur 401 remontée', async () => {
    const storage = memoryStorage();
    storage.set('mf-refresh', 'vieux');
    const fetchImpl = fakeFetch([{ status: 401, body: { detail: 'expiré' } }, { status: 401, body: { detail: 'révoqué' } }]);
    const c = createClient({ dataUrl: DATA, iaUrl: IA, fetchImpl, storage });
    expect(c.loggedIn).toBe(true); // reprise de session après rechargement de la page
    await expect(c.inventory()).rejects.toMatchObject({ status: 401, detail: 'expiré' });
    expect(c.loggedIn).toBe(false);
    expect(storage.m.has('mf-refresh')).toBe(false);
  });

  it('erreurs : détail de FastAPI conservé, corps non JSON toléré', async () => {
    const fetchImpl = fakeFetch([{ status: 422, body: { detail: [{ msg: 'champ requis' }] } }]);
    const c = createClient({ dataUrl: DATA, iaUrl: IA, fetchImpl, storage: memoryStorage() });
    const err = await c.register({ username: 'a', email: 'b', password: 'c' }).catch((e) => e);
    expect(err).toBeInstanceOf(ApiError);
    expect(err.status).toBe(422);
    expect(err.detail[0].msg).toBe('champ requis');
  });

  it('photo envoyée en multipart à api_ia, génération et copilote en JSON', async () => {
    const fetchImpl = fakeFetch([{ body: { items: [], unknown: [] } }, { body: { ok: true } }, { body: { answer: 'D21/D22' } }]);
    const c = createClient({ dataUrl: DATA, iaUrl: IA, fetchImpl, storage: memoryStorage() });
    await c.scan(new File([new Uint8Array([1, 2])], 'p.jpg', { type: 'image/jpeg' }));
    expect(fetchImpl.calls[0].url).toBe(`${IA}/v1/vision/scan`);
    expect(fetchImpl.calls[0].body).toBeInstanceOf(FormData);
    await c.generate('station-meteo-oled', 'esp32-devkit-v1');
    expect(JSON.parse(fetchImpl.calls[1].body)).toEqual({ template_id: 'station-meteo-oled', board: 'esp32-devkit-v1' });
    expect((await c.ask('I2C ?')).answer).toBe('D21/D22');
  });

  it('catalogue : toutes les pages de composants sont lues', async () => {
    const page = (n, from) => Array.from({ length: n }, (_, i) => ({ id: `c${from + i}` }));
    const fetchImpl = fakeFetch([{ body: page(200, 0) }, { body: page(37, 200) }]);
    const c = createClient({ dataUrl: DATA, iaUrl: IA, fetchImpl, storage: memoryStorage() });
    const all = await c.components();
    expect(all).toHaveLength(237);
    expect(fetchImpl.calls.map((x) => x.url)).toEqual([
      `${DATA}/v1/components?limit=200&offset=0`,
      `${DATA}/v1/components?limit=200&offset=200`,
    ]);
  });

  it('API injoignable (« Failed to fetch ») : erreur qui nomme l\'adresse visée', async () => {
    const fetchImpl = async () => { throw new TypeError('Failed to fetch'); };
    const c = createClient({ dataUrl: DATA, iaUrl: IA, fetchImpl, storage: memoryStorage() });
    const err = await c.register({ username: 'a', email: 'b', password: 'c' }).catch((e) => e);
    expect(err).toBeInstanceOf(NetworkError);
    expect(err.url).toBe(DATA);
    const err2 = await c.login('a', 'b').catch((e) => e);
    expect(err2.url).toBe(DATA);
    const err3 = await c.ask('?').catch((e) => e);
    expect(err3.url).toBe(IA);
  });

  it('stockage indisponible : aucune exception', () => {
    const broken = { getItem() { throw new Error('bloqué'); }, setItem() { throw new Error('bloqué'); }, removeItem() { throw new Error('bloqué'); } };
    const s = safeStorage(broken);
    expect(s.get('x')).toBeNull();
    expect(() => s.set('x', '1')).not.toThrow();
    expect(() => s.remove('x')).not.toThrow();
  });
});
