// Copilote : questions sur les composants et les cartes, réponses citées (sources du catalogue).
import { useState } from 'react';
import { Status, message } from '../ui.jsx';

const EXEMPLES = [
  "Broches I2C par défaut de l'ESP32 DevKit V1 ?",
  'Le DS18B20 marche-t-il sur un ESP32-C6 ?',
  'Quelle résistance pour une LED sur 5 V ?',
];

export default function Copilote({ client, workshop }) {
  const [thread, setThread] = useState([]);
  const [question, setQuestion] = useState('');
  const [state, setState] = useState(null);
  async function ask(e) {
    e.preventDefault();
    const q = question.trim();
    if (!q) return;
    setState({ text: 'Recherche dans le catalogue…' });
    setQuestion('');
    try {
      const a = await client.ask(q, workshop.summary);
      setThread((t) => [...t, { q, a }]);
      setState(null);
    } catch (err) {
      setThread((t) => [...t, { q, a: null }]);
      setState({ text: message(err), error: true });
    }
  }
  return (
    <>
      <header className="page-head">
        <p className="eyebrow">Copilote</p>
        <h1>Une question sur un montage ?</h1>
        <p className="notice">Tu échanges avec un assistant d'intelligence artificielle. Il répond à partir du catalogue MicroForge et cite ses sources ; vérifie toujours un montage avant de le mettre sous tension.</p>
      </header>
      <div className="chat" aria-live="polite">
        {thread.length === 0 && (
          <div className="examples">
            <p className="small muted">Exemples :</p>
            {EXEMPLES.map((x) => <button key={x} type="button" className="chip-btn" onClick={() => setQuestion(x)}>{x}</button>)}
          </div>
        )}
        {thread.map(({ q, a }, k) => (
          <div key={k} className="turn">
            <p className="bubble me">{q}</p>
            {a && (
              <article className="bubble bot">
                <p className="answer">{a.answer}</p>
                {a.index === 'mots-clés' && (
                  <p className="small muted">Recherche par mots-clés : aucun modèle d'IA n'est joignable (lance Ollama, ou renseigne une clé Gemini, pour des réponses rédigées et une recherche par le sens).</p>
                )}
                {a.notice && <p className="small muted">{a.notice}</p>}
                <h2 className="sources-title">Sources ({a.sources.length})</h2>
                <ol className="sources">
                  {a.sources.map((s) => (
                    <li key={s.n}><strong>[{s.n}] {s.title}</strong> <span className="muted">({s.kind})</span><br />{s.excerpt}
                      {s.url && <> · <a href={s.url} target="_blank" rel="noopener noreferrer">source officielle</a></>}</li>
                  ))}
                </ol>
              </article>
            )}
          </div>
        ))}
      </div>
      <form className="ask" onSubmit={ask}>
        <label htmlFor="f-question" className="sr">Ta question</label>
        <textarea id="f-question" name="question" rows={2} required maxLength={300} value={question}
          onChange={(e) => setQuestion(e.target.value)} placeholder="Pose ta question…" />
        <button className="btn" type="submit">Demander</button>
      </form>
      <Status state={state} />
    </>
  );
}
