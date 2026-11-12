// Onglet « Apprendre » de la page Projet : monter pas à pas (avec le pourquoi de chaque fil),
// lire le programme expliqué, retrouver les notions, puis vérifier ses acquis avec le quiz de l'étape.
import { useState } from 'react';
import { safeStorage } from '../api.js';
import { wireColor } from '../ui.jsx';

const store = safeStorage(globalThis.localStorage);

function Montage({ etapes, cle }) {
  const [faits, setFaits] = useState(() => {
    try { return new Set(JSON.parse(store.get(cle) ?? '[]')); } catch { return new Set(); }
  });
  const basculer = (i) => {
    const suite = new Set(faits);
    if (suite.has(i)) suite.delete(i); else suite.add(i);
    setFaits(suite);
    store.set(cle, JSON.stringify([...suite]));
  };
  const n = etapes.filter((_, i) => faits.has(i)).length;
  return (
    <section aria-labelledby="t-montage">
      <h2 id="t-montage">Monter pas à pas <span className="small muted">({n}/{etapes.length} fils)</span></h2>
      <p className="small muted">Les masses d'abord, puis les alimentations, puis les signaux. Coche chaque fil posé : ta progression reste sur cet appareil.</p>
      <span className="xp-bar" role="progressbar" aria-valuemin={0} aria-valuemax={etapes.length} aria-valuenow={n}
        aria-label="Fils posés"><span style={{ width: `${(100 * n) / Math.max(1, etapes.length)}%` }} /></span>
      <ol className="montage">
        {etapes.map((e, i) => {
          const [couleur, sens] = wireColor({ role: e.role, net: e.net, board_label: e.vers });
          return (
            <li key={`${e.part}.${e.pin}`} className={faits.has(i) ? 'fait' : ''}>
              <label>
                <input type="checkbox" checked={faits.has(i)} onChange={() => basculer(i)} />
                <span><code>{e.part}.{e.pin}</code> → <code>{e.vers}</code> <span className={`fil fil-${couleur}`}>fil {couleur}</span><span className="sr"> ({sens})</span></span>
              </label>
              <p>{e.pourquoi}</p>
            </li>
          );
        })}
      </ol>
    </section>
  );
}

function Programme({ lignes }) {
  return (
    <section aria-labelledby="t-programme">
      <h2 id="t-programme">Le programme expliqué</h2>
      <p className="small muted">Chaque fonction est expliquée à sa première apparition. setup() s'exécute une fois au démarrage, loop() se répète sans fin.</p>
      <ol className="programme" tabIndex={0} aria-label="Programme ligne par ligne">
        {lignes.map((l, i) => (
          // eslint-disable-next-line react/no-array-index-key
          <li key={i} className={l.notes.length ? 'explique' : ''}>
            <code>{l.ligne || ' '}</code>
            {l.notes.length > 0 && <ul className="notes">{l.notes.map((n) => <li key={n}>{n}</li>)}</ul>}
          </li>
        ))}
      </ol>
    </section>
  );
}

function Quiz({ quiz, onReussi }) {
  const [reponses, setReponses] = useState({});
  const [corrige, setCorrige] = useState(false);
  const [message, setMessage] = useState('');
  const justes = quiz.questions.filter((q, i) => reponses[i] === q.bonne).length;
  async function verifier(e) {
    e.preventDefault();
    setCorrige(true);
    if (justes === quiz.questions.length) setMessage(await onReussi());
    else setMessage(`${justes}/${quiz.questions.length} : relis les explications, puis réessaie.`);
  }
  return (
    <section aria-labelledby="t-quiz">
      <h2 id="t-quiz">Quiz de l'étape {quiz.etape} : {quiz.titre}</h2>
      <form className="quiz" onSubmit={verifier}>
        {quiz.questions.map((q, i) => (
          <fieldset key={q.question}>
            <legend>{i + 1}. {q.question}</legend>
            {q.choix.map((c, j) => (
              <label key={c} className={corrige && j === q.bonne ? 'bonne' : corrige && reponses[i] === j ? 'fausse' : ''}>
                <input type="radio" name={`q${i}`} checked={reponses[i] === j}
                  onChange={() => { setReponses({ ...reponses, [i]: j }); setCorrige(false); }} />
                {c}
              </label>
            ))}
            {corrige && <p className="small">{reponses[i] === q.bonne ? 'Juste. ' : 'Pas tout à fait. '}{q.explication}</p>}
          </fieldset>
        ))}
        <button className="btn" type="submit" disabled={Object.keys(reponses).length < quiz.questions.length}>Vérifier mes réponses</button>
        <p role="status" aria-live="polite" className="quiz-msg">{message}</p>
      </form>
    </section>
  );
}

export default function Apprendre({ build, client }) {
  const a = build.apprendre;
  if (!a) return <p>Pas de contenu d'apprentissage pour ce projet.</p>;
  const { spec } = build;
  const cle = `mf-montage:${spec.template_id ?? spec.title}:${spec.board}`;
  async function quizReussi() {
    try {
      const prog = await client.saveMission('quiz', `etape-${a.quiz.etape}`);
      const badges = prog.badges.filter((b) => b.obtenu && ['curieux', 'savant'].includes(b.id)).map((b) => b.titre);
      return `Sans faute ! Quiz enregistré dans ta progression${badges.length ? ` (badge : ${badges.join(', ')})` : ''}.`;
    } catch {
      return 'Sans faute ! (progression non enregistrée : API injoignable)';
    }
  }
  return (
    <div className="apprendre">
      <Montage etapes={a.montage} cle={cle} />
      {a.notions.length > 0 && (
        <section aria-labelledby="t-notions">
          <h2 id="t-notions">Notions du projet</h2>
          <dl className="notions">
            {a.notions.map((n) => (<div key={n.terme}><dt><dfn>{n.terme}</dfn></dt><dd>{n.definition}</dd></div>))}
          </dl>
        </section>
      )}
      <Programme lignes={a.code} />
      {a.quiz && <Quiz quiz={a.quiz} onReussi={quizReussi} />}
    </div>
  );
}
