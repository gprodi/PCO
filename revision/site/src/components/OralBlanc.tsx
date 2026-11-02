import { useState } from 'react';
import LocalOnly from './LocalOnly';
import { API_URL } from './storage';

type Q = { competence: string; question: string; attendus: string[] };
type Ev = { note: number; points_forts: string[]; a_ameliorer: string[]; criteres_couverts: string[] };

function Inner({ epreuve }: { epreuve: string }) {
  const [qs, setQs] = useState<Q[]>([]);
  const [i, setI] = useState(0);
  const [answer, setAnswer] = useState('');
  const [ev, setEv] = useState<Ev | null>(null);
  const [busy, setBusy] = useState(false);

  async function start() {
    setBusy(true);
    const r = await fetch(`${API_URL}/oral-blanc/${epreuve}?n=5`, { method: 'POST' });
    setQs((await r.json()).questions);
    setI(0); setEv(null); setAnswer(''); setBusy(false);
  }
  async function evaluate() {
    setBusy(true);
    const r = await fetch(`${API_URL}/oral-blanc/evaluer`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ question: qs[i], answer }) });
    setEv(await r.json());
    setBusy(false);
  }

  if (!qs.length) return <button className="mf-btn" type="button" onClick={start} disabled={busy}>{busy ? 'Préparation du jury…' : `Commencer l’oral blanc ${epreuve}`}</button>;
  const q = qs[i];
  return (
    <div className="mf-card">
      <p><span className="mf-badge">{q.competence}</span> Question {i + 1} / {qs.length}</p>
      <p><strong>{q.question}</strong></p>
      <label htmlFor="mf-ans">Ta réponse</label>
      <textarea id="mf-ans" rows={6} style={{ width: '100%' }} value={answer} onChange={(e) => setAnswer(e.target.value)} />
      <button className="mf-btn" type="button" onClick={evaluate} disabled={busy || answer.length < 3}>{busy ? 'Évaluation…' : 'Évaluer ma réponse'}</button>
      {ev && (
        <div aria-live="polite">
          <p><strong>Note : {ev.note} / 20</strong></p>
          <p>Points forts : {ev.points_forts.join(' ; ')}</p>
          <p>À améliorer : {ev.a_ameliorer.join(' ; ')}</p>
          <details><summary>Ce que le jury attendait</summary><ul>{q.attendus.map((a, k) => <li key={k}>{a}</li>)}</ul></details>
          {i + 1 < qs.length ? <button className="mf-btn secondary" type="button" onClick={() => { setI(i + 1); setEv(null); setAnswer(''); }}>Question suivante</button> : <button className="mf-btn secondary" type="button" onClick={start}>Nouvel oral</button>}
        </div>
      )}
    </div>
  );
}

export default function OralBlanc({ epreuve }: { epreuve: string }) {
  return <LocalOnly feature="L’oral blanc avec un jury simulé"><Inner epreuve={epreuve} /></LocalOnly>;
}
