import { useState } from 'react';
import LocalOnly from './LocalOnly';
import { API_URL } from './storage';

type Citation = { id: string; course: string; heading: string; score: number; extrait: string };
type Msg = { role: 'user' | 'assistant'; text: string; citations?: Citation[] };

function ChatInner({ base }: { base: string }) {
  const [msgs, setMsgs] = useState<Msg[]>([]);
  const [q, setQ] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  async function send(e: React.FormEvent) {
    e.preventDefault();
    if (!q.trim()) return;
    const question = q.trim();
    setMsgs((m) => [...m, { role: 'user', text: question }]);
    setQ('');
    setBusy(true);
    setError('');
    try {
      const r = await fetch(`${API_URL}/chat`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ question }) });
      if (!r.ok) throw new Error((await r.json()).detail ?? r.statusText);
      const data = await r.json();
      setMsgs((m) => [...m, { role: 'assistant', text: data.answer, citations: data.citations }]);
    } catch (err) {
      setError(`Erreur : ${(err as Error).message}`);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div>
      <div aria-live="polite">
        {msgs.map((m, i) => (
          <div key={i} className="mf-card">
            <p><strong>{m.role === 'user' ? 'Toi' : 'Assistant'}</strong></p>
            <p style={{ whiteSpace: 'pre-wrap' }}>{m.text}</p>
            {m.citations && m.citations.length > 0 && (
              <details>
                <summary>Sources ({m.citations.length})</summary>
                <ul>
                  {m.citations.map((c) => (
                    <li key={c.id}><a href={`${base}cours/${c.course}/index.html`}>{c.id}</a> — {c.heading} <small>(score {c.score})</small></li>
                  ))}
                </ul>
              </details>
            )}
          </div>
        ))}
      </div>
      {error && <p role="alert">{error}</p>}
      <form onSubmit={send}>
        <label htmlFor="mf-q">Ta question sur les cours</label>
        <textarea id="mf-q" rows={3} style={{ width: '100%' }} value={q} onChange={(e) => setQ(e.target.value)} placeholder="Ex. : comment fonctionne la rotation des refresh tokens ?" />
        <button className="mf-btn" type="submit" disabled={busy}>{busy ? 'Réflexion…' : 'Envoyer'}</button>
      </form>
    </div>
  );
}

export default function Chat({ base }: { base: string }) {
  return <LocalOnly feature="Le chat avec tes cours"><ChatInner base={base} /></LocalOnly>;
}
