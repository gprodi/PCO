// Projet généré : câblage broche par broche avec la couleur du fil Dupont, schéma, code,
// nomenclature et contrôle électrique.
import { useState } from 'react';
import { Icon, euros, wireColor } from '../ui.jsx';

const TABS = [['cablage', 'Câblage'], ['schema', 'Schéma'], ['code', 'Code'], ['bom', 'Nomenclature'], ['controle', 'Contrôle électrique']];

export default function Projet({ build }) {
  const [tab, setTab] = useState('cablage');
  const [copied, setCopied] = useState('');
  if (!build) {
    return (
      <div className="card empty">
        <h1>Aucun projet ouvert</h1>
        <p>Choisis une idée dans <a href="#explorer">Explorer</a> ou une étape du parcours sur l'<a href="#accueil">accueil</a>.</p>
      </div>
    );
  }
  const files = build.files;
  const ino = Object.keys(files).find((p) => p.endsWith('.ino') && !p.startsWith('wokwi/'));
  const header = Object.keys(files).find((p) => p.endsWith('mf_components.h') && !p.startsWith('wokwi/'));
  const svg = files['cablage.svg'];
  const total = build.bom.reduce((s, b) => s + b.quantity * (b.unit_price_eur ?? 0), 0);
  const errors = build.issues.filter((i) => i.severity === 'error').length;
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
      <header className="page-head project-head">
        <p className="eyebrow">Projet · {build.spec.board}</p>
        <h1>{build.spec.title}</h1>
        <p className="lede">{build.spec.description}</p>
        <div className="meta">
          {build.ok ? <span className="pill ok">contrôle électrique OK</span> : <span className="pill err">{errors} point(s) à corriger avant de brancher</span>}
          <span className="pill">{build.assignments.length} connexions</span>
          <span className="pill">{euros(total)} de pièces</span>
        </div>
      </header>
      <div role="tablist" aria-label="Livrables du projet" onKeyDown={onKey}>
        {TABS.map(([id, label]) => (
          <button key={id} id={`tab-${id}`} role="tab" type="button" aria-selected={tab === id} aria-controls="panel"
            tabIndex={tab === id ? 0 : -1} onClick={() => setTab(id)}>{label}</button>
        ))}
      </div>
      <section id="panel" role="tabpanel" aria-labelledby={`tab-${tab}`} className="card panel">
        {tab === 'cablage' && (
          <>
            <p className="legend small">
              <span><i className="wire w-rouge" />5 V</span><span><i className="wire w-orange" />3,3 V</span>
              <span><i className="wire w-noir" />masse</span><span><i className="wire w-bleu" />SDA</span>
              <span><i className="wire w-jaune" />SCL</span><span><i className="wire w-violet" />SPI</span>
              <span><i className="wire w-vert" />signal</span>
            </p>
            <div className="scroll" tabIndex={0} role="region" aria-label="Tableau de câblage (défile horizontalement)">
              <table className="wiring">
                <thead><tr><th scope="col">Fil</th><th scope="col">Composant</th><th scope="col">Broche</th><th scope="col">Broche carte</th><th scope="col">Signal</th></tr></thead>
                <tbody>{build.assignments.map((a, k) => {
                  const [color, meaning] = wireColor(a);
                  return (
                    <tr key={k}>
                      <td><i className={`wire w-${color}`} aria-hidden="true" />{color}<span className="sr"> ({meaning})</span></td>
                      <td>{a.part}</td><td>{a.pin}</td><td><strong>{a.board_label}</strong></td><td><code>{a.net}</code></td>
                    </tr>
                  );
                })}</tbody>
              </table>
            </div>
            {build.added_parts?.length > 0 && (
              <p className="small muted">Ajouté par le moteur : {build.added_parts.map((p) => `${p.name} ${p.value} (${p.part})`).join(', ')}.</p>
            )}
          </>
        )}
        {tab === 'schema' && svg && (
          <div className="schema"><img src={`data:image/svg+xml;charset=utf-8,${encodeURIComponent(svg)}`} alt={`Schéma de câblage : ${build.spec.title}`} /></div>
        )}
        {tab === 'code' && [ino, header].filter(Boolean).map((path) => (
          <div key={path} className="codeblock">
            <div className="codebar">
              <code>{path.split('/').pop()}</code>
              <button className="btn ghost small" type="button" onClick={() => copy(path)}><Icon name="copier" size={16} /> {copied === path ? 'Copié' : 'Copier'}</button>
            </div>
            <pre className="code" tabIndex={0} aria-label={`Code ${path.split('/').pop()}`}><code>{files[path]}</code></pre>
          </div>
        ))}
        {tab === 'bom' && (
          <div className="scroll" tabIndex={0} role="region" aria-label="Nomenclature (défile horizontalement)">
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
          : <ul className="issues">{build.issues.map((i, k) => (
              <li key={k} className={`issue ${i.severity}`}><strong>{i.severity === 'error' ? 'Erreur' : i.severity === 'warning' ? 'Attention' : 'Info'}</strong> {i.message}{i.fix ? <small>Correctif : {i.fix}</small> : null}</li>
            ))}</ul>)}
      </section>
    </>
  );
}
