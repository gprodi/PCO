// Explorer par thème : 145 idées en 17 thèmes, annotées avec le stock (pièces manquantes,
// réalisable tout de suite), et en tête les projets les plus proches de ce que l'on possède.
import { useEffect, useMemo, useState } from 'react';
import { Dots, Icon, Status, message, plural } from '../ui.jsx';

function Meter({ value, label }) {
  return (
    <span className="meter" role="img" aria-label={label}>
      <i style={{ width: `${Math.round(value * 100)}%` }} />
    </span>
  );
}

function IdeaCard({ idea, names, onGenerate }) {
  const missing = new Set(idea.manquants);
  const state = idea.realisable
    ? <span className="pill ok">réalisable avec ton stock</span>
    : <span className="pill warn">{missing.size ? `il manque ${plural(missing.size, 'pièce', 'pièces')}` : 'il manque la carte'}</span>;
  return (
    <article className="card idea">
      <div className="idea-head">
        <h3>{idea.titre}</h3>
        <Dots n={idea.difficulte} />
      </div>
      <p>{idea.description}</p>
      <ul className="chips" aria-label="Composants">
        {idea.composants.map((id, k) => (
          <li key={id} className={missing.has(id) ? 'chip missing' : 'chip owned'}>
            <span className="sr">{missing.has(id) ? 'manquant : ' : 'en stock : '}</span>
            {idea.composants_noms?.[k] ?? names[id] ?? id}
          </li>
        ))}
      </ul>
      <div className="meta">
        {state}
        {idea.wifi && <span className="pill info">Wi-Fi</span>}
      </div>
      {idea.template
        ? <button className="btn" type="button" onClick={() => onGenerate(idea.template, idea.wifi, idea.titre)}>
            Générer ce projet <Icon name="fleche" size={16} />
          </button>
        : <p className="muted small">Idée à monter soi-même : pas encore de modèle générable.</p>}
    </article>
  );
}

export default function Explorer({ client, workshop, onGenerate }) {
  const [themes, setThemes] = useState(null);
  const [ideas, setIdeas] = useState(null);
  const [theme, setTheme] = useState(null);
  const [state, setState] = useState(null);
  const inv = workshop.summary;

  useEffect(() => {
    if (!inv) return;
    (async () => {
      try {
        const [t, s] = await Promise.all([client.explore(inv), client.suggest(inv, 6)]);
        setThemes(t);
        setIdeas(s);
        setTheme((cur) => cur ?? t.find((x) => x.idees.some((i) => i.realisable))?.id ?? t[0]?.id);
      } catch (err) {
        setState({ text: message(err), error: true });
      }
    })();
  }, [client, inv]);

  const current = useMemo(() => themes?.find((t) => t.id === theme), [themes, theme]);
  const total = themes?.reduce((s, t) => s + t.idees.length, 0) ?? 0;

  return (
    <>
      <header className="page-head">
        <p className="eyebrow">Explorer</p>
        <h1>Que construire avec ce que tu as ?</h1>
        <p className="lede">
          {themes ? `${total} idées en ${themes.length} thèmes, classées selon ton stock.` : 'Chargement des idées…'}
        </p>
      </header>
      <Status state={state} />

      {ideas?.length > 0 && (
        <section aria-labelledby="t-proches">
          <h2 id="t-proches">Les plus proches de ton stock</h2>
          <div className="grid">
            {ideas.map((s) => (
              <article className="card idea" key={`${s.template_id}@${s.board}`}>
                <div className="idea-head"><h3>{s.title}</h3><Dots n={s.difficulty} /></div>
                <p>{s.description}</p>
                <div className="meta">
                  <span className="pill">{s.board_name}</span>
                  {s.feasible_now
                    ? <span className="pill ok">réalisable avec ton stock</span>
                    : <span className="pill warn">il manque : {Object.entries(s.missing).map(([id, n]) => `${workshop.names[id] ?? id} ×${n}`).join(', ') || 'la carte'}</span>}
                </div>
                <button className="btn" type="button" onClick={() => onGenerate(s.template_id, false, s.title, s.board)}>
                  Générer ce projet <Icon name="fleche" size={16} />
                </button>
              </article>
            ))}
          </div>
        </section>
      )}

      {themes && (
        <section aria-labelledby="t-themes">
          <h2 id="t-themes">Par thème</h2>
          <div className="themes">
            {themes.map((t) => {
              const ready = t.idees.filter((i) => i.realisable).length;
              return (
                <button key={t.id} type="button" className="theme" aria-pressed={t.id === theme} onClick={() => setTheme(t.id)}>
                  <span className="theme-icon" aria-hidden="true">{t.icone}</span>
                  <b>{t.titre}</b>
                  <span className="theme-count">{plural(t.idees.length, 'idée', 'idées')} · {ready} réalisable{ready > 1 ? 's' : ''}</span>
                  <Meter value={ready / Math.max(1, t.idees.length)} label={`${ready} sur ${t.idees.length} réalisables`} />
                </button>
              );
            })}
          </div>
        </section>
      )}

      {current && (
        <section aria-labelledby="t-theme" className="theme-panel">
          <div className="theme-panel-head">
            <span className="theme-icon big" aria-hidden="true">{current.icone}</span>
            <div>
              <h2 id="t-theme">{current.titre}</h2>
              <p className="lede">{current.description}</p>
            </div>
          </div>
          <div className="grid">
            {[...current.idees]
              .sort((a, b) => Number(b.realisable) - Number(a.realisable) || a.manquants.length - b.manquants.length)
              .map((i) => <IdeaCard key={i.titre} idea={i} names={workshop.names} onGenerate={onGenerate} />)}
          </div>
        </section>
      )}
    </>
  );
}
