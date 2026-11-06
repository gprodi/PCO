// Projet généré, comme la démo : câblage aux couleurs des fils Dupont, atelier virtuel (cadre isolé),
// schéma, code, guide de soudure, simulation Wokwi, nomenclature, KiCad, fiabilité et sources.
// Au-dessus des onglets : notions, difficulté, contrôle électrique, choix de la carte, archive .zip.
import { useState } from 'react';
import AtelierFrame from '../atelier-frame.jsx';
import { renderMarkdown } from '../markdown.js';
import { Dots, Icon, euros, message, plural, wireColor } from '../ui.jsx';

const TABS = [
  ['cablage', 'Câblage'], ['atelier', 'Atelier virtuel'], ['schema', 'Schéma'], ['code', 'Code'],
  ['guide', 'Guide de soudure'], ['wokwi', 'Simulation Wokwi'], ['bom', 'Nomenclature'],
  ['kicad', 'KiCad'], ['sources', 'Fiabilité & sources'],
];
const SEVERITY = { error: ['err', 'bloquant'], warning: ['warn', 'attention'], info: ['info', 'info'] };

function CopyButton({ text, label = 'Copier' }) {
  const [done, setDone] = useState('');
  async function copy() {
    try { await navigator.clipboard.writeText(text); setDone('Copié'); } catch { setDone('Copie impossible'); }
    setTimeout(() => setDone(''), 2000);
  }
  return (
    <button className="btn ghost small" type="button" onClick={copy}>
      <Icon name="copier" size={16} /> {done || label}
    </button>
  );
}

function CodeBlock({ name, text, caption }) {
  return (
    <div className="codeblock">
      <div className="codebar">
        <span><code>{name}</code>{caption && <span className="muted small"> · {caption}</span>}</span>
        <CopyButton text={text} />
      </div>
      <pre className="code" tabIndex={0} aria-label={`Fichier ${name}`}><code>{text}</code></pre>
    </div>
  );
}

function Check({ ok, label, children }) {
  return (
    <li><span className={`pill ${ok ? 'ok' : 'warn'}`}>{label ?? (ok ? 'vérifié' : 'à faire')}</span><span>{children}</span></li>
  );
}

export default function Projet({ build, client, onBoard }) {
  const [tab, setTab] = useState('cablage');
  const [zip, setZip] = useState(null);
  if (!build) {
    return (
      <div className="card empty">
        <h1>Aucun projet ouvert</h1>
        <p>Choisis une idée dans <a href="#explorer">Explorer</a> ou une étape du parcours sur l'<a href="#accueil">accueil</a>.</p>
      </div>
    );
  }
  const { spec, files, template } = build;
  const paths = Object.keys(files);
  const ino = paths.find((p) => p.endsWith('.ino') && !p.startsWith('wokwi/'));
  const header = paths.find((p) => p.endsWith('mf_components.h') && !p.startsWith('wokwi/'));
  const total = build.bom.reduce((s, b) => s + b.quantity * (b.unit_price_eur ?? 0), 0);
  const errors = build.issues.filter((i) => i.severity === 'error').length;
  const boards = template?.boards ?? [];
  const wokwiBoard = build.atelier?.wiring?.board?.wokwi;

  function select(id, focus) {
    setTab(id);
    if (focus) requestAnimationFrame(() => document.getElementById(`tab-${id}`)?.focus());
  }
  const onKey = (e) => {
    const i = TABS.findIndex(([id]) => id === tab);
    const to = { ArrowRight: i + 1, ArrowLeft: i - 1 + TABS.length, Home: 0, End: TABS.length - 1 }[e.key];
    if (to === undefined) return;
    e.preventDefault();
    select(TABS[to % TABS.length][0], true);
  };

  async function download() {
    const board = spec.board;
    setZip({ board, text: 'Préparation de l\'archive…' });
    try {
      const blob = await client.bundle(spec.template_id, spec.board);
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${spec.template_id}-${spec.board}.zip`;
      document.body.append(a);
      a.click();
      a.remove();
      setTimeout(() => URL.revokeObjectURL(url), 10000);
      setZip({ board, text: `Archive téléchargée : ${a.download}.` });
    } catch (err) {
      setZip({ board, text: message(err), error: true });
    }
  }

  return (
    <>
      <header className="page-head project-head">
        <p className="eyebrow">{template?.theme ? `${template.theme.icone} ${template.theme.titre}` : 'Projet libre'}</p>
        <h1>{spec.title}</h1>
        <p className="lede">{spec.description}</p>
        <div className="meta">
          {template && <Dots n={template.difficulty} />}
          {template?.learning.map((l) => <span key={l} className="pill">{l}</span>)}
          {build.ok
            ? <span className="pill ok">contrôle électrique OK</span>
            : <span className="pill err">{plural(errors, 'point à corriger', 'points à corriger')} avant de brancher</span>}
          <span className="pill">{plural(build.assignments.length, 'connexion', 'connexions')}</span>
          <span className="pill">{euros(total)} de pièces</span>
        </div>
        <div className="project-tools">
          {boards.length > 1 ? (
            <label className="board-pick">
              <span>Carte</span>
              <select value={spec.board} onChange={(e) => onBoard(e.target.value)}>
                {boards.map((b) => <option key={b.id} value={b.id}>{b.name}</option>)}
              </select>
            </label>
          ) : (
            <span className="pill">{boards[0]?.name ?? spec.board}</span>
          )}
          {spec.template_id && (
            <button className="btn" type="button" onClick={download}><Icon name="telecharger" size={18} /> Télécharger le projet (.zip)</button>
          )}
        </div>
        {zip?.board === spec.board && <p className={`status${zip.error ? ' err' : ''}`} role="status">{zip.text}</p>}
      </header>

      {build.issues.length > 0 && (
        <ul className="issues" aria-label="Contrôle électrique">
          {build.issues.map((i, k) => (
            <li key={k} className={`issue ${i.severity}`}>
              <span><span className={`pill ${SEVERITY[i.severity]?.[0] ?? 'info'}`}>{SEVERITY[i.severity]?.[1] ?? i.severity}</span> {i.message}</span>
              {i.fix ? <small>Correctif : {i.fix}</small> : null}
            </li>
          ))}
        </ul>
      )}

      <div role="tablist" aria-label="Livrables du projet" onKeyDown={onKey}>
        {TABS.map(([id, label]) => (
          <button key={id} id={`tab-${id}`} role="tab" type="button" aria-selected={tab === id} aria-controls="panel"
            tabIndex={tab === id ? 0 : -1} onClick={() => select(id)}>{label}</button>
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

        {tab === 'atelier' && (build.atelier ? (
          <>
            <p className="lede">Branche chaque composant sur la bonne broche de la carte (une erreur est expliquée), puis règle les capteurs : le montage réagit comme le vrai.</p>
            <AtelierFrame payload={build.atelier} title={spec.title} />
          </>
        ) : <p>La logique de ce projet ne se simule pas dans l'atelier : utilise l'onglet Simulation Wokwi.</p>)}

        {tab === 'schema' && files['cablage.svg'] && (
          <div className="schema"><img src={`data:image/svg+xml;charset=utf-8,${encodeURIComponent(files['cablage.svg'])}`} alt={`Schéma de câblage : ${spec.title}`} /></div>
        )}

        {tab === 'code' && (
          <>
            {ino && <CodeBlock name={ino.split('/').pop()} text={files[ino]} caption="logique du projet" />}
            {header && <CodeBlock name="mf_components.h" text={files[header]} caption="broches, objets, fonctions" />}
            <p className="small">Bibliothèques : {build.libraries.length ? build.libraries.map((l, k) => <span key={l}>{k > 0 && ', '}<code>{l}</code></span>) : 'aucune'}.</p>
            {files['platformio.ini'] && <CodeBlock name="platformio.ini" text={files['platformio.ini']} caption="pour PlatformIO" />}
          </>
        )}

        {tab === 'guide' && (
          // Document produit par le moteur ; rendu par markdown.js (HTML brut échappé).
          <div className="md" dangerouslySetInnerHTML={{ __html: renderMarkdown(files['guide-montage.md']) }} />
        )}

        {tab === 'wokwi' && (
          <>
            {!wokwiBoard && <p className="issue warning">Cette carte n'existe pas dans Wokwi : le schéma utilise la carte simulable la plus proche.</p>}
            <ol className="steps-list">
              <li>Ouvre <a href="https://wokwi.com" target="_blank" rel="noopener noreferrer">wokwi.com <Icon name="lien" size={14} /></a> et crée un projet pour ta carte.</li>
              <li>Remplace <code>diagram.json</code> par le contenu ci-dessous.</li>
              <li>Colle <code>sketch.ino</code>, ajoute le fichier <code>mf_components.h</code> et la liste <code>libraries.txt</code>.</li>
              <li>Lance la simulation.</li>
            </ol>
            <div className="copy-row">
              {files['wokwi/sketch.ino'] && <CopyButton text={files['wokwi/sketch.ino']} label="Copier sketch.ino" />}
              {files['wokwi/mf_components.h'] && <CopyButton text={files['wokwi/mf_components.h']} label="Copier mf_components.h" />}
            </div>
            {files['wokwi/diagram.json'] && <CodeBlock name="diagram.json" text={files['wokwi/diagram.json']} />}
            {files['wokwi/libraries.txt'] && <CodeBlock name="libraries.txt" text={files['wokwi/libraries.txt']} />}
          </>
        )}

        {tab === 'bom' && (
          <>
            <div className="scroll" tabIndex={0} role="region" aria-label="Nomenclature (défile horizontalement)">
              <table>
                <thead><tr><th scope="col">Désignation</th><th scope="col" className="num">Qté</th><th scope="col" className="num">Prix indicatif</th></tr></thead>
                <tbody>{build.bom.map((b, k) => (
                  <tr key={k}><td>{b.name}</td><td className="num">{b.quantity}</td><td className="num">{euros(b.unit_price_eur)}</td></tr>
                ))}</tbody>
                <tfoot><tr><th scope="row" colSpan={2}>Total indicatif</th><td className="num">{euros(total)}</td></tr></tfoot>
              </table>
            </div>
            {files['nomenclature.csv'] && <div className="copy-row"><CopyButton text={files['nomenclature.csv']} label="Copier nomenclature.csv" /></div>}
          </>
        )}

        {tab === 'kicad' && files['kicad/projet.net'] && (
          <>
            <p className="lede">Netlist à importer dans l'éditeur de PCB de KiCad (Fichier → Importer → Netlist).</p>
            <CodeBlock name="projet.net" text={files['kicad/projet.net']} />
          </>
        )}

        {tab === 'sources' && (
          <>
            <h2 className="panel-title">Niveau de vérification</h2>
            <ul className="checks">
              <Check ok={build.ok} label={build.ok ? 'vérifié' : 'à corriger'}>Allocation des broches et contrôle électrique, recalculés à chaque génération (résultat en haut de page).</Check>
              <Check ok>Syntaxe C++ vérifiée par les tests du dépôt (g++ avec en-têtes Arduino simulés).</Check>
              <Check ok>Compilation réelle avec arduino-cli dans la CI du dépôt, sur la carte de référence de chaque famille de cartes compatible.</Check>
              {template?.hardware_tested?.length
                ? <Check ok>Monté et testé sur {template.hardware_tested.join(', ')}.</Check>
                : <Check ok={false}>Pas encore monté sur du vrai matériel : teste d'abord sur breadboard ou dans Wokwi, et vérifie le câblage avant la mise sous tension.</Check>}
            </ul>
            {template?.references?.length > 0 && (
              <>
                <h2 className="panel-title">Tutoriels publics du même montage</h2>
                <p className="lede">Pour recouper le câblage et le code. MicroForge ne copie pas leur code : il génère le sien à partir de son catalogue de composants.</p>
                <ul className="refs">
                  {template.references.map((r) => (
                    <li key={r.url}>
                      <a href={r.url} target="_blank" rel="noopener noreferrer">{r.title}</a> · {r.site}
                      {r.proche && <span className="pill">variante proche</span>}
                    </li>
                  ))}
                </ul>
              </>
            )}
            {template && <p className="small muted">{plural(boards.length, 'carte compatible', 'cartes compatibles')} avec ce modèle.</p>}
          </>
        )}
      </section>
    </>
  );
}
