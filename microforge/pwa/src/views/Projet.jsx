// Projet généré, comme la démo : câblage aux couleurs des fils Dupont, atelier virtuel (cadre isolé),
// schéma, code, guide de soudure, simulation Wokwi, nomenclature, KiCad, fiabilité et sources.
// Au-dessus des onglets : notions, difficulté, contrôle électrique, choix de la carte, archive .zip.
import { useEffect, useState } from 'react';
import AtelierFrame from '../atelier-frame.jsx';
import Apprendre from './Apprendre.jsx';
import { renderMarkdown } from '../markdown.js';
import { Dots, Icon, euros, message, plural, wireColor } from '../ui.jsx';

const TABS = [
  ['cablage', 'Câblage'], ['apprendre', 'Apprendre'], ['atelier', 'Atelier virtuel'], ['schema', 'Schéma'], ['code', 'Code'],
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

export function CodeBlock({ name, text, caption }) {
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

/** Liste d'achat d'un projet enregistré : ce qui manque au stock, chiffré avec les offres collectées. */
function Achats({ list }) {
  if (!list.to_buy.length) return <p>Rien à acheter : tout est dans ton stock.</p>;
  return (
    <>
      <div className="scroll" tabIndex={0} role="region" aria-label="Liste d'achat (défile horizontalement)">
        <table>
          <thead><tr><th scope="col">Composant</th><th scope="col" className="num">Il faut</th><th scope="col" className="num">En stock</th><th scope="col" className="num">À acheter</th><th scope="col">Fournisseur</th><th scope="col" className="num">Sous-total</th></tr></thead>
          <tbody>{list.to_buy.map((l) => (
            <tr key={l.component}>
              <td>{l.name}</td><td className="num">{l.needed}</td><td className="num">{l.owned}</td><td className="num"><strong>{l.to_buy}</strong></td>
              <td>{l.url ? <a href={l.url} target="_blank" rel="noopener noreferrer">{l.supplier}</a> : l.supplier}</td>
              <td className="num">{l.unit_price_eur == null ? '—' : euros(l.subtotal)}</td>
            </tr>
          ))}</tbody>
        </table>
      </div>
      <p><strong>Total : {euros(list.total_eur)}</strong> <span className="small muted">(prix des offres collectées, sinon prix indicatif du catalogue)</span></p>
    </>
  );
}

/** Bandeau de progression au-dessus de l'atelier : niveau, points, dernière mission réussie. */
function Progression({ prog, last, libre }) {
  if (libre) return <p className="small muted">Projet libre : les missions se jouent, mais ne comptent pas dans ta progression.</p>;
  if (!prog) return null;
  const n = prog.niveau;
  const part = n.xp_prochain ? Math.round((100 * (prog.xp - n.xp_niveau)) / (n.xp_prochain - n.xp_niveau)) : 100;
  return (
    <div className="xp" role="group" aria-label="Ta progression">
      <span><b>{n.nom}</b> · {prog.xp} XP</span>
      <span className="xp-bar" role="progressbar" aria-valuemin={0} aria-valuemax={100} aria-valuenow={part}
        aria-label={n.prochain ? `Vers le niveau ${n.prochain}` : 'Niveau maximal'}><span style={{ width: `${part}%` }} /></span>
      {n.prochain && <span className="small muted">{n.xp_prochain - prog.xp} XP avant « {n.prochain} »</span>}
      <p className="small xp-last" role="status" aria-live="polite">{last}</p>
    </div>
  );
}

export default function Projet({ build, client, onBoard, initialTab }) {
  const [tab, setTab] = useState(initialTab || 'cablage');
  const [zip, setZip] = useState(null);
  const [saved, setSaved] = useState(null);
  const [prog, setProg] = useState(null);
  const [progReady, setProgReady] = useState(false);
  const [last, setLast] = useState('');
  const templateId = build?.spec.template_id ?? null;
  useEffect(() => {
    if (!templateId) return;
    // Progression indisponible (API, hors ligne) : l'atelier s'ouvre quand même, sans enregistrement.
    client.progression().then(setProg).catch(() => setProg(null)).finally(() => setProgReady(true));
  }, [client, templateId]);
  async function mission(id) {
    if (!templateId) return;
    const titre = build.atelier?.missions?.find((m) => m.id === id)?.titre ?? id;
    try {
      const avant = prog?.badges?.filter((b) => b.obtenu).map((b) => b.id) ?? [];
      const apres = await client.saveMission(templateId, id);
      const nouveaux = apres.badges.filter((b) => b.obtenu && !avant.includes(b.id)).map((b) => b.titre);
      setProg(apres);
      setLast(`Mission « ${titre} » enregistrée${nouveaux.length ? ` — badge obtenu : ${nouveaux.join(', ')} !` : '.'}`);
    } catch (err) {
      setLast(`Mission « ${titre} » réussie, mais non enregistrée : ${message(err)}`);
    }
  }
  const faites = (prog?.missions ?? []).filter((m) => m.template_id === templateId).map((m) => m.mission_id);
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
      // Projet libre (conçu par l'IA) : la spécification complète part avec la demande.
      const blob = await client.bundle(spec.template_id, spec.board, spec.template_id ? null : spec);
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${spec.template_id ?? 'projet-libre'}-${spec.board}.zip`;
      document.body.append(a);
      a.click();
      a.remove();
      setTimeout(() => URL.revokeObjectURL(url), 10000);
      setZip({ board, text: `Archive téléchargée : ${a.download}.` });
    } catch (err) {
      setZip({ board, text: message(err), error: true });
    }
  }

  async function save() {
    setSaved({ text: 'Enregistrement…' });
    let id;
    try {
      id = (await client.saveProject(spec)).id;
    } catch (err) {
      setSaved({ text: message(err), error: true });
      return;
    }
    const done = 'Enregistré dans tes projets (page Créer).';
    setSaved({ text: done, id });
    try {
      setSaved({ text: done, id, list: await client.shoppingList(id) });
    } catch (err) {
      setSaved({ text: `${done} Liste d'achat indisponible : ${message(err)}`, id, error: true });
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
          <button className="btn" type="button" onClick={download}><Icon name="telecharger" size={18} /> Télécharger le projet (.zip)</button>
          <button className="btn ghost" type="button" onClick={save} disabled={saved?.id != null}>
            <Icon name="plus" size={18} /> {saved?.id != null ? 'Enregistré' : 'Enregistrer dans mes projets'}
          </button>
        </div>
        {saved && <p className={`status${saved.error ? ' err' : ''}`} role="status">{saved.text}</p>}
        {zip?.board === spec.board && <p className={`status${zip.error ? ' err' : ''}`} role="status">{zip.text}</p>}
        {build.notice && (
          <p className={`notice${build.origin === 'repli' ? ' warn' : ''}`} role="note">
            <strong>{build.origin === 'repli' ? 'Pas de conception sur mesure.' : "Conçu par l'IA."}</strong> {build.notice}
          </p>
        )}
      </header>

      {saved?.list && (
        <section className="card achats" aria-labelledby="t-achats">
          <h2 id="t-achats">Liste d'achat</h2>
          <Achats list={saved.list} />
        </section>
      )}

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

        {tab === 'apprendre' && <Apprendre build={build} client={client} />}

        {tab === 'atelier' && (build.atelier ? (
          <>
            <p className="lede">Branche chaque composant sur la bonne broche de la carte (une erreur est expliquée), puis règle les capteurs : le montage réagit comme le vrai. Les missions te lancent des défis, validés par la simulation.</p>
            <Progression prog={prog} last={last} libre={!templateId} />
            {(!templateId || progReady) && <AtelierFrame payload={build.atelier} title={spec.title} faites={faites} onMission={mission} />}
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
