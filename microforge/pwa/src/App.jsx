import { useCallback, useEffect, useMemo, useState } from 'react';
import { createClient } from './api.js';
import { Icon, Status, message } from './ui.jsx';
import Accueil from './views/Accueil.jsx';
import Connexion from './views/Connexion.jsx';
import Copilote from './views/Copilote.jsx';
import Explorer from './views/Explorer.jsx';
import Photo from './views/Photo.jsx';
import Projet from './views/Projet.jsx';
import Stock from './views/Stock.jsx';

// Adresses des API : config.js (au lancement), sinon variables de construction, sinon le poste local.
const CONFIG = globalThis.MF_CONFIG ?? {};
const DATA_URL = CONFIG.apiDataUrl || import.meta.env.VITE_API_DATA_URL || 'http://localhost:8000';
const IA_URL = CONFIG.apiIaUrl || import.meta.env.VITE_API_IA_URL || 'http://localhost:8001';

// Barre de navigation (en haut sur ordinateur, en bas sur téléphone) ; Photo s'ouvre depuis le stock.
const NAV = [
  ['accueil', 'Accueil'],
  ['explorer', 'Explorer'],
  ['stock', 'Mon stock'],
  ['projet', 'Projet'],
  ['copilote', 'Copilote'],
];
const ROUTES = new Set([...NAV.map(([id]) => id), 'photo']);

function useRoute() {
  const read = () => {
    const v = location.hash.slice(1);
    return ROUTES.has(v) ? v : 'accueil';
  };
  const [route, setRoute] = useState(read);
  useEffect(() => {
    const on = () => { setRoute(read()); scrollTo(0, 0); };
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

/** Ce que les vues partagent : stock résumé, cartes et composants du catalogue, noms lisibles. */
function useWorkshop(client, logged) {
  const [data, setData] = useState({ summary: null, boards: [], components: [] });
  const refresh = useCallback(async () => {
    const summary = await client.summary();
    setData((d) => ({ ...d, summary }));
  }, [client]);
  useEffect(() => {
    if (!logged) return;
    (async () => {
      try {
        const [summary, boards, components] = await Promise.all([client.summary(), client.boards(), client.components()]);
        setData({ summary, boards, components });
      } catch { /* chaque vue affiche sa propre erreur */ }
    })();
  }, [client, logged]);
  return useMemo(() => {
    const all = [...data.boards, ...data.components];
    return {
      ...data,
      refresh,
      names: Object.fromEntries(all.map((c) => [c.id, c.name])),
      categoryOf: Object.fromEntries(all.map((c) => [c.id, c.category_id])),
      ownedBoards: data.boards.filter((b) => data.summary?.[b.id]).map((b) => b.id),
    };
  }, [data, refresh]);
}

export default function App() {
  const client = useMemo(() => createClient({ dataUrl: DATA_URL, iaUrl: IA_URL }), []);
  const [logged, setLogged] = useState(client.loggedIn);
  const [build, setBuild] = useState(null);
  const [busy, setBusy] = useState(null);
  const route = useRoute();
  const online = useOnline();
  const workshop = useWorkshop(client, logged);

  async function logout() {
    await client.logout();
    setLogged(false);
    location.hash = 'accueil';
  }

  /** Génère un modèle de projet : carte demandée, sinon une carte possédée, sinon la carte de référence. */
  async function generate(templateId, wifi, title, board) {
    const owned = workshop.ownedBoards.filter((b) => !wifi || /esp|pico-w|wifi|nano-33-iot|mkr/i.test(b));
    const candidates = [...new Set([board, ...owned, wifi ? 'esp32-devkit-v1' : 'arduino-uno', 'esp32-devkit-v1'].filter(Boolean))];
    setBusy({ text: `Génération de « ${title ?? templateId} »…` });
    let last;
    for (const b of candidates) {
      try {
        setBuild(await client.generate(templateId, b));
        setBusy(null);
        location.hash = 'projet';
        return;
      } catch (err) {
        last = err;
        if (err.status !== 422) break; // seule une carte incompatible justifie d'essayer la suivante
      }
    }
    setBusy({ text: message(last), error: true });
  }

  return (
    <>
      <a className="skip" href="#contenu">Aller au contenu</a>
      {!online && <p className="offline" role="status">Hors ligne : l'interface reste disponible, les données reviendront avec le réseau.</p>}
      <header className="bar">
        <div className="wrap bar-inner">
          <a className="brand" href="#accueil" aria-label="MicroForge, accueil">
            <svg className="brand-mark" viewBox="0 0 32 32" aria-hidden="true" focusable="false">
              <rect x="5" y="5" width="22" height="22" rx="3" />
              <path d="M10 1v4M16 1v4M22 1v4M10 27v4M16 27v4M22 27v4M1 10h4M1 16h4M1 22h4M27 10h4M27 16h4M27 22h4" />
              <circle cx="16" cy="16" r="4" />
            </svg>
            <span>MicroForge</span>
          </a>
          {logged && (
            <nav className="nav" aria-label="Sections">
              {NAV.map(([id, label]) => (
                <a key={id} href={`#${id}`} aria-current={route === id || (route === 'photo' && id === 'stock') ? 'page' : undefined}>
                  <Icon name={id} size={22} />
                  <span>{label}</span>
                </a>
              ))}
            </nav>
          )}
          {logged && (
            <button className="logout" type="button" onClick={logout}><Icon name="sortie" size={18} /><span>Se déconnecter</span></button>
          )}
        </div>
      </header>
      <main id="contenu" className={`wrap view-${logged ? route : 'connexion'}`} tabIndex={-1}>
        {busy && <Status state={busy} />}
        {!logged && <Connexion client={client} onLogged={() => { setLogged(true); location.hash = 'accueil'; }} />}
        {logged && route === 'accueil' && <Accueil client={client} workshop={workshop} onGenerate={generate} />}
        {logged && route === 'explorer' && <Explorer client={client} workshop={workshop} onGenerate={generate} />}
        {logged && route === 'stock' && <Stock client={client} workshop={workshop} onChange={workshop.refresh} />}
        {logged && route === 'photo' && <Photo client={client} onChange={workshop.refresh} />}
        {logged && route === 'projet' && (
          <Projet key={build?.spec.template_id ?? 'vide'} build={build} client={client}
            onBoard={(board) => generate(build.spec.template_id, build.spec.uses_wifi, build.spec.title, board)} />
        )}
        {logged && route === 'copilote' && <Copilote client={client} workshop={workshop} />}
      </main>
    </>
  );
}
