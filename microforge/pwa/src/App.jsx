import { useCallback, useEffect, useMemo, useState } from 'react';
import { ApiError, NetworkError, createClient } from './api.js';

// Adresses des API : config.js (au lancement), sinon variables de construction, sinon le poste local.
const CONFIG = globalThis.MF_CONFIG ?? {};
const DATA_URL = CONFIG.apiDataUrl || import.meta.env.VITE_API_DATA_URL || 'http://localhost:8000';
const IA_URL = CONFIG.apiIaUrl || import.meta.env.VITE_API_IA_URL || 'http://localhost:8001';
const VIEWS = [
  ['stock', 'Mon stock'],
  ['photo', 'Photo'],
  ['idees', 'Idées'],
  ['projet', 'Projet'],
  ['copilote', 'Copilote'],
];

const message = (err) => {
  if (!navigator.onLine) return 'Hors ligne : réessaie une fois connecté.';
  if (err instanceof NetworkError) {
    return `Impossible de joindre l'API ${err.url} depuis ${location.origin}. Vérifie qu'elle tourne (docker compose --profile core ps) et que l'adresse de cette page est autorisée par l'API (MF_CORS_ORIGINS).`;
  }
  if (!(err instanceof ApiError)) return `Erreur : ${err.message}`;
  if (Array.isArray(err.detail)) return err.detail.map((d) => d.msg).join(' ; ');
  return typeof err.detail === 'string' ? err.detail : `Erreur ${err.status}`;
};
const dots = (n) => '●'.repeat(n) + '○'.repeat(Math.max(0, 3 - n));
const euros = (v) => (v == null ? '—' : `${v.toFixed(2).replace('.', ',')} €`);

function useRoute() {
  const read = () => {
    const v = location.hash.slice(1);
    return VIEWS.some(([id]) => id === v) ? v : 'stock';
  };
  const [route, setRoute] = useState(read);
  useEffect(() => {
    const on = () => setRoute(read());
    addEventListener('hashchange', on);
    return () => removeEventListener('hashchange', on);
  }, []);
  return route;
}

function useOnline() {
  const [online, setOnline] = useState(navigator.onLine);
  useEffect(() => {
    const on = () => setOnline(navigator.onLine);
    addEventListener('online', on);
    addEventListener('offline', on);
    return () => { removeEventListener('online', on); removeEventListener('offline', on); };
  }, []);
  return online;
}

function Status({ state }) {
  return (
    <p className={`status${state?.error ? ' err' : ''}`} role="status" aria-live="polite">
      {state?.text ?? ''}
    </p>
  );
}

/* ------------------------------------------------------------------ connexion */
function Connexion({ client, onLogged }) {
  const [mode, setMode] = useState('login');
  const [busy, setBusy] = useState(false);
  const [state, setState] = useState(null);
  async function submit(e) {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    setBusy(true);
    setState({ text: mode === 'login' ? 'Connexion…' : 'Création du compte…' });
    try {
      if (mode === 'register') {
        await client.register({
          username: f.get('username'), email: f.get('email'), password: f.get('password'),
          city: f.get('city'), consent: f.get('consent') === 'on',
        });
      }
      await client.login(f.get('username'), f.get('password'));
      onLogged();
    } catch (err) {
      setState({ text: message(err), error: true });
    } finally {
      setBusy(false);
    }
  }
  return (
    <section className="card" aria-labelledby="t-connexion">
      <h1 id="t-connexion">{mode === 'login' ? 'Connexion' : 'Créer un compte'}</h1>
      <p className="lede">Ton stock de composants, des idées de projets, le câblage et le code.</p>
      <form className="stack" onSubmit={submit}>
        <label>Pseudo{mode === 'register' ? ' (3 à 40 caractères)' : ' ou e-mail'}
          <input id="f-username" name="username" autoComplete="username" required minLength={3} />
        </label>
        {mode === 'register' && (
          <label>E-mail<input id="f-email" name="email" type="email" autoComplete="email" required /></label>
        )}
        <label>Mot de passe{mode === 'register' ? ' (10 caractères min., lettres et chiffres)' : ''}
          <input id="f-password" name="password" type="password" required minLength={mode === 'register' ? 10 : 1}
            autoComplete={mode === 'register' ? 'new-password' : 'current-password'} />
        </label>
        {mode === 'register' && (
          <>
            <label>Ville (facultatif)<input id="f-city" name="city" autoComplete="address-level2" /></label>
            <label className="check"><input id="f-consent" name="consent" type="checkbox" />
              J'accepte que mes photos corrigées servent à améliorer le modèle (facultatif)</label>
          </>
        )}
        <div className="row">
          <button className="btn" type="submit" disabled={busy}>{mode === 'login' ? 'Se connecter' : 'Créer mon compte'}</button>
          <button className="btn ghost" type="button" onClick={() => { setMode(mode === 'login' ? 'register' : 'login'); setState(null); }}>
            {mode === 'login' ? 'Créer un compte' : "J'ai déjà un compte"}
          </button>
        </div>
      </form>
      <Status state={state} />
    </section>
  );
}

/* ------------------------------------------------------------------ stock */
function Stock({ client }) {
  const [items, setItems] = useState(null);
  const [catalog, setCatalog] = useState({ boards: [], components: [] });
  const [state, setState] = useState(null);
  const names = useMemo(
    () => Object.fromEntries([...catalog.boards, ...catalog.components].map((c) => [c.id, c.name])),
    [catalog],
  );
  const load = useCallback(async () => {
    try {
      const [inv, boards, components] = await Promise.all([client.inventory(), client.boards(), client.components()]);
      setItems(inv);
      setCatalog({ boards, components });
    } catch (err) {
      setState({ text: message(err), error: true });
    }
  }, [client]);
  useEffect(() => { load(); }, [load]);

  async function add(e) {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    try {
      await client.addItem({ component_id: f.get('component'), quantity: Number(f.get('quantity')), location: f.get('location') || '' });
      setState({ text: `Ajouté : ${names[f.get('component')] ?? f.get('component')}.` });
      load();
    } catch (err) {
      setState({ text: message(err), error: true });
    }
  }
  async function remove(id) {
    try {
      await client.deleteItem(id);
      setState({ text: 'Ligne supprimée.' });
      load();
    } catch (err) {
      setState({ text: message(err), error: true });
    }
  }
  const total = (items ?? []).reduce((s, i) => s + i.quantity, 0);
  return (
    <>
      <div>
        <h1>Mon stock</h1>
        <p className="lede">{items == null ? 'Chargement…' : `${total} pièces, ${items.length} lignes.`}</p>
      </div>
      {items?.length > 0 && (
        <div className="card scroll" tabIndex={0} role="region" aria-label="Mon stock (tableau)">
          <table>
            <caption className="muted" style={{ textAlign: 'left' }}>Composants que tu possèdes</caption>
            <thead><tr><th scope="col">Composant</th><th scope="col" className="num">Quantité</th><th scope="col">Emplacement</th><th scope="col"><span className="sr">Action</span></th></tr></thead>
            <tbody>
              {items.map((i) => (
                <tr key={i.id}>
                  <td>{names[i.component_id] ?? i.component_id}</td>
                  <td className="num">{i.quantity}</td>
                  <td>{i.location || '—'}</td>
                  <td><button className="btn ghost" type="button" onClick={() => remove(i.id)} aria-label={`Supprimer ${names[i.component_id] ?? i.component_id}`}>Supprimer</button></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <form className="card stack" onSubmit={add} aria-labelledby="t-ajout">
        <h2 id="t-ajout">Ajouter un composant</h2>
        <label>Composant
          <select id="f-component" name="component" required defaultValue="">
            <option value="" disabled>Choisir…</option>
            <optgroup label="Cartes">
              {catalog.boards.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
            </optgroup>
            <optgroup label="Composants">
              {catalog.components.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
            </optgroup>
          </select>
        </label>
        <label>Quantité<input id="f-quantity" name="quantity" type="number" min="1" max="999" defaultValue="1" required /></label>
        <label>Emplacement (facultatif)<input id="f-location" name="location" placeholder="tiroir 2, boîte rouge…" /></label>
        <div><button className="btn" type="submit">Ajouter au stock</button></div>
      </form>
      <Status state={state} />
    </>
  );
}

/* ------------------------------------------------------------------ photo */
function Photo({ client }) {
  const [file, setFile] = useState(null);
  const [preview, setPreview] = useState(null);
  const [result, setResult] = useState(null);
  const [state, setState] = useState(null);
  useEffect(() => () => preview && URL.revokeObjectURL(preview), [preview]);
  function pick(e) {
    const f = e.target.files?.[0] ?? null;
    setFile(f);
    setResult(null);
    setPreview(f ? URL.createObjectURL(f) : null);
  }
  async function analyse() {
    setState({ text: 'Analyse de la photo…' });
    try {
      const r = await client.scan(file);
      setResult(r);
      setState({ text: `${r.items.length} composant(s) reconnu(s), ${r.unknown.length} à identifier.` });
    } catch (err) {
      setState({ text: message(err), error: true });
    }
  }
  async function keep() {
    try {
      await client.addBulk(result.items.map((i) => ({ component_id: i.component_id, quantity: i.quantity })), 'photo');
      setState({ text: 'Composants reconnus ajoutés au stock.' });
    } catch (err) {
      setState({ text: message(err), error: true });
    }
  }
  return (
    <>
      <div>
        <h1>Photographier mon stock</h1>
        <p className="lede">Sur téléphone, l'appareil photo s'ouvre directement. La photo est analysée puis oubliée : ses métadonnées (position GPS) sont retirées avant l'analyse.</p>
      </div>
      <div className="card">
        <label>Photo de tes composants
          <input id="f-photo" type="file" accept="image/*" capture="environment" onChange={pick} />
        </label>
        {preview && <img className="preview" src={preview} alt="Aperçu de la photo choisie" />}
        <div><button className="btn" type="button" onClick={analyse} disabled={!file}>Analyser la photo</button></div>
      </div>
      {result && (
        <div className="card">
          <h2>Résultat</h2>
          {result.items.length === 0 && <p>Aucun composant reconnu avec certitude.</p>}
          <ul>
            {result.items.map((i, k) => <li key={k}>{i.label || i.component_id} × {i.quantity} <span className="muted">(confiance {Math.round(i.confidence * 100)} %)</span></li>)}
            {result.unknown.map((u, k) => <li key={`u${k}`} className="muted">À identifier : {u.label} × {u.quantity}</li>)}
          </ul>
          {result.items.length > 0 && <div><button className="btn" type="button" onClick={keep}>Ajouter les composants reconnus</button></div>}
          <p className="muted">Modèle : {result.model_version} · {result.latency_ms} ms</p>
        </div>
      )}
      <Status state={state} />
    </>
  );
}

/* ------------------------------------------------------------------ idées */
function Idees({ client, onBuild }) {
  const [ideas, setIdeas] = useState(null);
  const [state, setState] = useState(null);
  useEffect(() => {
    (async () => {
      try {
        setIdeas(await client.suggest(await client.summary()));
      } catch (err) {
        setState({ text: message(err), error: true });
      }
    })();
  }, [client]);
  async function build(idea) {
    setState({ text: `Génération de « ${idea.title} »…` });
    try {
      onBuild(await client.generate(idea.template_id, idea.board));
      location.hash = 'projet';
    } catch (err) {
      setState({ text: message(err), error: true });
    }
  }
  return (
    <>
      <div>
        <h1>Que puis-je construire ?</h1>
        <p className="lede">Projets classés selon ce que tu as déjà dans ton stock.</p>
      </div>
      <Status state={state} />
      <div className="grid">
        {(ideas ?? []).map((s) => (
          <article className="card" key={`${s.template_id}@${s.board}`}>
            <div className="row" style={{ justifyContent: 'space-between' }}>
              <h2 style={{ fontSize: 20 }}>{s.title}</h2>
              <span className="dots" aria-label={`difficulté ${s.difficulty} sur 3`}>{dots(s.difficulty)}</span>
            </div>
            <p>{s.description}</p>
            <p className="muted">Carte : {s.board_name}</p>
            <p>{s.feasible_now
              ? <span className="pill ok">réalisable avec ton stock</span>
              : <span className="pill warn">il manque : {Object.entries(s.missing).map(([id, n]) => `${id} ×${n}`).join(', ') || 'la carte'}</span>}</p>
            <div><button className="btn" type="button" onClick={() => build(s)}>Générer ce projet</button></div>
          </article>
        ))}
      </div>
    </>
  );
}

/* ------------------------------------------------------------------ projet */
const TABS = [['cablage', 'Câblage'], ['schema', 'Schéma'], ['code', 'Code'], ['bom', 'Nomenclature'], ['controle', 'Contrôle électrique']];

function Projet({ build }) {
  const [tab, setTab] = useState('cablage');
  const [copied, setCopied] = useState('');
  if (!build) {
    return (
      <div className="card">
        <h1>Aucun projet ouvert</h1>
        <p>Choisis un projet dans <a href="#idees">Idées</a>.</p>
      </div>
    );
  }
  const files = build.files;
  const ino = Object.keys(files).find((p) => p.endsWith('.ino') && !p.startsWith('wokwi/'));
  const header = Object.keys(files).find((p) => p.endsWith('mf_components.h') && !p.startsWith('wokwi/'));
  const svg = files['cablage.svg'];
  const total = build.bom.reduce((s, b) => s + b.quantity * (b.unit_price_eur ?? 0), 0);
  async function copy(path) {
    try { await navigator.clipboard.writeText(files[path]); setCopied(path); } catch { setCopied(''); }
  }
  const onKey = (e) => {
    const i = TABS.findIndex(([id]) => id === tab);
    if (e.key === 'ArrowRight') setTab(TABS[(i + 1) % TABS.length][0]);
    if (e.key === 'ArrowLeft') setTab(TABS[(i + TABS.length - 1) % TABS.length][0]);
  };
  return (
    <>
      <div>
        <h1>{build.spec.title}</h1>
        <p className="lede">{build.spec.description}</p>
        <p>{build.ok ? <span className="pill ok">contrôle électrique OK</span> : <span className="pill err">à corriger avant de brancher</span>}</p>
      </div>
      <div role="tablist" aria-label="Livrables du projet" onKeyDown={onKey}>
        {TABS.map(([id, label]) => (
          <button key={id} id={`tab-${id}`} role="tab" type="button" aria-selected={tab === id} aria-controls="panel"
            tabIndex={tab === id ? 0 : -1} onClick={() => setTab(id)}>{label}</button>
        ))}
      </div>
      <section id="panel" role="tabpanel" aria-labelledby={`tab-${tab}`} className="card">
        {tab === 'cablage' && (
          <div className="scroll" tabIndex={0} role="region" aria-label="Tableau (défile horizontalement)">
            <table>
              <thead><tr><th scope="col">Composant</th><th scope="col">Broche</th><th scope="col">Broche carte</th><th scope="col">Rôle</th><th scope="col">Signal</th></tr></thead>
              <tbody>{build.assignments.map((a, k) => (
                <tr key={k}><td>{a.part}</td><td>{a.pin}</td><td><strong>{a.board_label}</strong></td><td>{a.role}</td><td>{a.net}</td></tr>
              ))}</tbody>
            </table>
          </div>
        )}
        {tab === 'schema' && svg && (
          <div className="schema"><img src={`data:image/svg+xml;charset=utf-8,${encodeURIComponent(svg)}`} alt={`Schéma de câblage : ${build.spec.title}`} /></div>
        )}
        {tab === 'code' && [ino, header].filter(Boolean).map((path) => (
          <div key={path}>
            <div className="row" style={{ justifyContent: 'space-between' }}>
              <h2 style={{ fontSize: 18 }}><code>{path.split('/').pop()}</code></h2>
              <button className="btn ghost" type="button" onClick={() => copy(path)}>{copied === path ? 'Copié' : 'Copier'}</button>
            </div>
            <pre className="code" tabIndex={0} aria-label={`Code ${path.split('/').pop()}`}><code>{files[path]}</code></pre>
          </div>
        ))}
        {tab === 'bom' && (
          <div className="scroll" tabIndex={0} role="region" aria-label="Tableau (défile horizontalement)">
            <table>
              <thead><tr><th scope="col">Désignation</th><th scope="col" className="num">Qté</th><th scope="col" className="num">Prix indicatif</th></tr></thead>
              <tbody>{build.bom.map((b, k) => (
                <tr key={k}><td>{b.name}</td><td className="num">{b.quantity}</td><td className="num">{euros(b.unit_price_eur)}</td></tr>
              ))}</tbody>
              <tfoot><tr><th scope="row" colSpan={2}>Total indicatif</th><td className="num">{euros(total)}</td></tr></tfoot>
            </table>
          </div>
        )}
        {tab === 'controle' && (build.issues.length === 0
          ? <p><span className="pill ok">aucun problème</span> Broches, tensions et bus vérifiés par le moteur.</p>
          : <ul>{build.issues.map((i, k) => <li key={k}><strong>{i.severity}</strong> : {i.message}{i.fix ? ` (correctif : ${i.fix})` : ''}</li>)}</ul>)}
      </section>
    </>
  );
}

/* ------------------------------------------------------------------ copilote */
function Copilote({ client }) {
  const [answer, setAnswer] = useState(null);
  const [state, setState] = useState(null);
  async function ask(e) {
    e.preventDefault();
    const q = new FormData(e.currentTarget).get('question');
    setState({ text: 'Recherche dans le catalogue…' });
    try {
      setAnswer(await client.ask(q));
      setState(null);
    } catch (err) {
      setState({ text: message(err), error: true });
    }
  }
  return (
    <>
      <div>
        <h1>Copilote</h1>
        <p className="notice">Tu échanges avec un assistant d'intelligence artificielle. Il répond à partir du catalogue MicroForge et cite ses sources ; vérifie toujours un montage avant de le mettre sous tension.</p>
      </div>
      <form className="card" onSubmit={ask}>
        <label>Ta question<textarea id="f-question" name="question" rows={2} required maxLength={300} placeholder="Broches I2C de l'ESP32-C3 ? Le DS18B20 marche-t-il sur un C6 ?" /></label>
        <div><button className="btn" type="submit">Demander</button></div>
      </form>
      <Status state={state} />
      {answer && (
        <article className="card" aria-live="polite">
          <p>{answer.answer}</p>
          {answer.notice && <p className="muted">{answer.notice}</p>}
          <h2 style={{ fontSize: 18 }}>Sources ({answer.sources.length})</h2>
          <ol className="sources">
            {answer.sources.map((s) => (
              <li key={s.n}><strong>[{s.n}] {s.title}</strong> <span className="muted">({s.kind})</span><br />{s.excerpt}
                {s.url && <> · <a href={s.url} target="_blank" rel="noopener noreferrer">source officielle</a></>}</li>
            ))}
          </ol>
        </article>
      )}
    </>
  );
}

/* ------------------------------------------------------------------ application */
export default function App() {
  const client = useMemo(() => createClient({ dataUrl: DATA_URL, iaUrl: IA_URL }), []);
  const [logged, setLogged] = useState(client.loggedIn);
  const [build, setBuild] = useState(null);
  const route = useRoute();
  const online = useOnline();
  async function logout() {
    await client.logout();
    setLogged(false);
  }
  return (
    <>
      <a className="skip" href="#contenu">Aller au contenu</a>
      {!online && <p className="offline" role="status">Hors ligne : l'interface reste disponible, les données reviendront avec le réseau.</p>}
      <header className="bar">
        <div className="wrap">
          <p className="brand">MicroForge</p>
          {logged && <button className="btn ghost" type="button" onClick={logout}>Se déconnecter</button>}
          {logged && (
            <nav className="views" aria-label="Sections">
              {VIEWS.map(([id, label]) => (
                <a key={id} href={`#${id}`} aria-current={route === id ? 'page' : undefined}>{label}</a>
              ))}
            </nav>
          )}
        </div>
      </header>
      <main id="contenu" className="wrap" tabIndex={-1}>
        {!logged && <Connexion client={client} onLogged={() => setLogged(true)} />}
        {logged && route === 'stock' && <Stock client={client} />}
        {logged && route === 'photo' && <Photo client={client} />}
        {logged && route === 'idees' && <Idees client={client} onBuild={setBuild} />}
        {logged && route === 'projet' && <Projet build={build} />}
        {logged && route === 'copilote' && <Copilote client={client} />}
      </main>
    </>
  );
}
