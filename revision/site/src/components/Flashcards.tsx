import { useEffect, useMemo, useState } from 'react';
import { type Card, createEmptyCard, fsrs, Rating, type Grade } from 'ts-fsrs';
import { load, save } from './storage';

type Flash = { recto: string; verso: string; tags?: string[] };
type Stored = Record<string, Card>;
const scheduler = fsrs();

export function revive(c: Card): Card {
  return { ...c, due: new Date(c.due), last_review: c.last_review ? new Date(c.last_review) : undefined };
}

/** Flashcards avec répétition espacée FSRS (état conservé dans le navigateur). */
export default function Flashcards({ slug, cards }: { slug: string; cards: Flash[] }) {
  const key = `fsrs:${slug}`;
  const [state, setState] = useState<Stored>({});
  const [flipped, setFlipped] = useState(false);
  const [mode, setMode] = useState<'due' | 'all'>('due');
  const [pos, setPos] = useState(0);

  useEffect(() => setState(load<Stored>(key, {})), [key]);

  const now = new Date();
  const queue = useMemo(() => {
    const idx = cards.map((_, i) => i);
    return mode === 'all' ? idx : idx.filter((i) => !state[i] || revive(state[i]).due <= now);
  }, [cards, state, mode]);

  const current = queue[pos % Math.max(queue.length, 1)];

  function grade(g: Grade) {
    const card = state[current] ? revive(state[current]) : createEmptyCard(new Date());
    const next = scheduler.next(card, new Date(), g).card;
    const updated = { ...state, [current]: next };
    setState(updated);
    save(key, updated);
    setFlipped(false);
    setPos((p) => p + (mode === 'all' ? 1 : 0));
  }

  if (!cards.length) return <p>Aucune carte.</p>;
  if (queue.length === 0)
    return (
      <div className="mf-card">
        <p>✅ Aucune carte à revoir pour aujourd’hui sur ce cours.</p>
        <button type="button" className="mf-btn secondary" onClick={() => setMode('all')}>Revoir toutes les cartes</button>
      </div>
    );

  const c = cards[current];
  return (
    <div>
      <p aria-live="polite">
        {mode === 'due' ? `${queue.length} carte(s) à revoir aujourd’hui` : `Carte ${(pos % cards.length) + 1} / ${cards.length}`}
      </p>
      <div className="mf-card mf-flash" aria-live="polite">
        <div>
          <p><strong>{flipped ? 'Réponse' : 'Question'}</strong></p>
          <p>{flipped ? c.verso : c.recto}</p>
        </div>
      </div>
      {!flipped ? (
        <button type="button" className="mf-btn" onClick={() => setFlipped(true)}>Afficher la réponse</button>
      ) : (
        <div role="group" aria-label="Évalue ta réponse">
          <button type="button" className="mf-btn secondary" onClick={() => grade(Rating.Again)}>À revoir</button>
          <button type="button" className="mf-btn secondary" onClick={() => grade(Rating.Hard)}>Difficile</button>
          <button type="button" className="mf-btn" onClick={() => grade(Rating.Good)}>Bien</button>
          <button type="button" className="mf-btn" onClick={() => grade(Rating.Easy)}>Facile</button>
        </div>
      )}
    </div>
  );
}
