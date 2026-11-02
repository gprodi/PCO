import { useEffect, useState } from 'react';
import { load, save } from './storage';

/** Check-list cochable (mémorisée dans le navigateur) — critères et livrables d'une compétence. */
export default function Checklist({ id, items }: { id: string; items: string[] }) {
  const key = `check:${id}`;
  const [done, setDone] = useState<boolean[]>([]);
  useEffect(() => setDone(load<boolean[]>(key, items.map(() => false))), [key, items.length]);
  const count = done.filter(Boolean).length;
  return (
    <div>
      <p aria-live="polite"><strong>{count} / {items.length}</strong> validés</p>
      <ul style={{ listStyle: 'none', paddingLeft: 0 }}>
        {items.map((it, i) => (
          <li key={i}>
            <label style={{ display: 'flex', gap: '0.5rem', alignItems: 'flex-start' }}>
              <input type="checkbox" checked={!!done[i]} onChange={() => { const n = [...done]; n[i] = !n[i]; setDone(n); save(key, n); }} />
              <span>{it}</span>
            </label>
          </li>
        ))}
      </ul>
    </div>
  );
}
