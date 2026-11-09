// Atelier virtuel, comme la page Streamlit : choisir un projet et une carte, brancher chaque
// composant sur la bonne broche (une erreur est expliquée), puis régler les capteurs et regarder le
// montage réagir. Le simulateur tourne dans un cadre isolé (voir atelier-frame.jsx).
import { useEffect, useState } from 'react';
import AtelierFrame from '../atelier-frame.jsx';
import { Icon, Status, message } from '../ui.jsx';
import { CodeBlock } from './Projet.jsx';

const DEFAULT_BOARD = 'esp32-devkit-v1';

export default function Atelier({ client, build, onOpenBuild }) {
  const [templates, setTemplates] = useState(null);
  const [choice, setChoice] = useState({ tid: build?.spec.template_id ?? null, board: build?.spec.template_id ? build.spec.board : null });
  const [result, setResult] = useState(null);
  const [state, setState] = useState(null);

  useEffect(() => {
    (async () => {
      try {
        const list = (await client.templates()).sort((a, b) => a.title.localeCompare(b.title, 'fr'));
        setTemplates(list);
        setChoice((c) => (c.tid ? c : { tid: list[0]?.id ?? null, board: null }));
      } catch (err) {
        setState({ text: message(err), error: true });
      }
    })();
  }, [client]);

  useEffect(() => {
    if (!choice.tid) return;
    let alive = true;
    (async () => {
      setState({ text: 'Préparation du montage…' });
      // Carte demandée, sinon l'ESP32 DevKit V1 (comme Streamlit), sinon l'Uno.
      const candidates = [...new Set([choice.board, DEFAULT_BOARD, 'arduino-uno'].filter(Boolean))];
      let last;
      for (const b of candidates) {
        try {
          const r = await client.generate(choice.tid, b);
          if (!alive) return;
          setResult(r);
          setState(null);
          return;
        } catch (err) {
          last = err;
          if (err.status !== 422) break;
        }
      }
      if (alive) {
        setResult(null);
        setState({ text: message(last), error: true });
      }
    })();
    return () => { alive = false; };
  }, [client, choice]);

  const spec = result?.spec;
  const errors = result?.issues.filter((i) => i.severity === 'error') ?? [];
  const boards = result?.template?.boards ?? [];

  return (
    <>
      <header className="page-head">
        <p className="eyebrow">Atelier virtuel</p>
        <h1>Brancher, puis voir fonctionner</h1>
        <p className="lede">Choisis un projet : branche chaque composant sur la bonne broche (une erreur est expliquée), puis règle les capteurs et regarde le montage réagir. Simulation du comportement, sans matériel.</p>
      </header>

      <div className="card form atelier-pick">
        <div className="two-wide">
          <div>
            <label htmlFor="f-atelier-projet">Projet</label>
            <select id="f-atelier-projet" value={choice.tid ?? ''} onChange={(e) => setChoice({ tid: e.target.value, board: null })}>
              {!templates && <option value="">Chargement…</option>}
              {templates?.map((t) => <option key={t.id} value={t.id}>{t.title}</option>)}
            </select>
          </div>
          <div>
            <label htmlFor="f-atelier-carte">Carte</label>
            <select id="f-atelier-carte" value={spec?.board ?? ''} disabled={!boards.length}
              onChange={(e) => setChoice((c) => ({ ...c, board: e.target.value }))}>
              {!boards.length && <option value="">{spec?.board ?? '…'}</option>}
              {boards.map((b) => <option key={b.id} value={b.id}>{b.name}</option>)}
            </select>
          </div>
        </div>
      </div>

      <Status state={state} />

      {result && errors.length > 0 && (
        <p className="notice warn" role="note">Montage impossible sur cette carte : {errors[0].message}</p>
      )}
      {result && errors.length === 0 && !result.atelier && (
        <p className="notice warn" role="note">Ce projet ne peut pas encore être simulé dans l'atelier : utilise l'onglet Simulation Wokwi de la page du projet.</p>
      )}
      {result && errors.length === 0 && result.atelier && (
        <>
          <AtelierFrame key={`${spec.template_id}@${spec.board}`} payload={result.atelier} title={spec.title} />
          <details className="sim-code">
            <summary>Code JavaScript exécuté par la simulation (traduit du C++ du projet)</summary>
            <CodeBlock name="simulation.js" text={result.atelier.code} caption="généré à partir de la logique du projet" />
          </details>
        </>
      )}
      {result && (
        <p>
          <button className="btn ghost" type="button" onClick={() => onOpenBuild(result)}>
            Ouvrir le projet complet (câblage, code, guide…) <Icon name="fleche" size={16} />
          </button>
        </p>
      )}
    </>
  );
}
