// Créer un projet, comme la page « Je veux construire… » de Streamlit : décrire son idée (l'IA
// choisit les composants, le moteur câble et vérifie ; sans IA, modèle le plus proche, signalé) ou
// choisir un modèle du catalogue ; carte imposée ou choisie par MicroForge. Plus les projets
// enregistrés (rouvrir, supprimer).
import { useEffect, useMemo, useState } from 'react';
import { Icon, Status, message } from '../ui.jsx';

export default function Creer({ client, workshop, build, onGenerate, onGoal, onOpen }) {
  const [mode, setMode] = useState('idee');
  const [templates, setTemplates] = useState(null);
  const [projects, setProjects] = useState(null);
  const [state, setState] = useState(null);
  const boards = useMemo(
    () => [...workshop.boards].sort((a, b) => a.name.localeCompare(b.name, 'fr')),
    [workshop.boards],
  );

  async function loadProjects() {
    try {
      setProjects(await client.projects());
    } catch (err) {
      setState({ text: message(err), error: true });
    }
  }

  useEffect(() => {
    (async () => {
      try {
        const list = await client.templates();
        setTemplates(list.sort((a, b) => a.title.localeCompare(b.title, 'fr')));
      } catch (err) {
        setState({ text: message(err), error: true });
      }
    })();
    loadProjects();
  }, [client]); // eslint-disable-line react-hooks/exhaustive-deps

  function submit(event) {
    event.preventDefault();
    const f = new FormData(event.currentTarget);
    const board = f.get('board') || null;
    if (mode === 'idee') {
      const goal = String(f.get('goal') ?? '').trim();
      if (goal.length < 5) {
        setState({ text: 'Décris ton idée en quelques mots (5 caractères au moins).', error: true });
        return;
      }
      setState(null);
      onGoal(goal, { board, useStock: f.get('stock') === 'on' });
    } else {
      const tpl = templates?.find((t) => t.id === f.get('template'));
      if (!tpl) return;
      setState(null);
      onGenerate(tpl.id, tpl.requires_wifi, tpl.title, board);
    }
  }

  async function remove(p) {
    try {
      await client.deleteProject(p.id);
      setState({ text: `Projet supprimé : ${p.title}.` });
      await loadProjects();
    } catch (err) {
      setState({ text: message(err), error: true });
    }
  }

  return (
    <>
      <header className="page-head">
        <p className="eyebrow">Créer</p>
        <h1>Je veux construire…</h1>
        <p className="lede">Décris ton idée ou pars d'un modèle : MicroForge câble, écrit le code et vérifie le montage.</p>
      </header>

      <div className="stock-layout">
        <form className="card form" onSubmit={submit} aria-labelledby="t-creer">
          <h2 id="t-creer">Nouveau projet</h2>
          <fieldset className="seg">
            <legend>Point de départ</legend>
            <label><input type="radio" name="mode" value="idee" checked={mode === 'idee'} onChange={() => setMode('idee')} /> Décrire mon idée</label>
            <label><input type="radio" name="mode" value="modele" checked={mode === 'modele'} onChange={() => setMode('modele')} /> Choisir un modèle</label>
          </fieldset>

          {mode === 'idee' ? (
            <>
              <label htmlFor="f-goal">Décris ce que tu veux construire</label>
              <textarea id="f-goal" name="goal" rows={4} maxLength={500}
                placeholder="Ex. : une station qui mesure la température de ma serre et m'avertit si elle dépasse 35 °C" />
              <label className="check" htmlFor="f-stock"><input id="f-stock" name="stock" type="checkbox" defaultChecked /> Privilégier mon stock</label>
              <p className="small muted">L'IA (Ollama, ou Gemini en offre gratuite) choisit les composants ; MicroForge les câble et contrôle le montage. Sans IA disponible, tu obtiens le modèle du catalogue le plus proche, et c'est indiqué.</p>
            </>
          ) : (
            <>
              <label htmlFor="f-template">Modèle {templates && <span className="muted">({templates.length}, vérifiés et compilés en CI)</span>}</label>
              <select id="f-template" name="template" required defaultValue={build?.spec.template_id ?? ''}>
                <option value="" disabled>Choisir…</option>
                {templates?.map((t) => <option key={t.id} value={t.id}>{t.title}{t.requires_wifi ? ' (Wi-Fi)' : ''}</option>)}
              </select>
            </>
          )}

          <label htmlFor="f-board">Carte</label>
          <select id="f-board" name="board" defaultValue="">
            <option value="">Choisie par MicroForge</option>
            {boards.map((b) => <option key={b.id} value={b.id}>{b.name}{workshop.summary?.[b.id] ? ' (en stock)' : ''}</option>)}
          </select>

          <button className="btn" type="submit">
            {mode === 'idee' ? 'Concevoir le projet' : 'Générer'} <Icon name="fleche" size={16} />
          </button>
          <Status state={state} />
        </form>

        <div className="stock-list">
          {build && (
            <section className="card" aria-labelledby="t-dernier">
              <h2 id="t-dernier">Dernier projet</h2>
              <p><strong>{build.spec.title}</strong></p>
              <a className="btn ghost" href="#projet">Ouvrir le projet <Icon name="fleche" size={16} /></a>
            </section>
          )}
          <section className="card group" aria-labelledby="t-mes-projets">
            <h2 id="t-mes-projets">Mes projets enregistrés {projects && <span className="count">{projects.length}</span>}</h2>
            {projects?.length === 0 && <p className="small muted">Aucun pour l'instant : « Enregistrer dans mes projets » depuis la page d'un projet.</p>}
            {projects?.length > 0 && (
              <ul className="projects">
                {projects.map((p) => (
                  <li key={p.id}>
                    <span>{p.title}<br /><span className="small muted">{workshop.names[p.board_id] ?? p.board_id} · {new Date(p.created_at).toLocaleDateString('fr-FR')}</span></span>
                    <span className="actions">
                      <button className="btn small" type="button" onClick={() => onOpen(p.id)}>Ouvrir</button>
                      <button className="btn small ghost" type="button" onClick={() => remove(p)} aria-label={`Supprimer ${p.title}`}>Supprimer</button>
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </section>
        </div>
      </div>
    </>
  );
}
