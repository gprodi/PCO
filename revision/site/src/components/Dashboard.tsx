import { useEffect, useState } from 'react';
import type { Card } from 'ts-fsrs';
import { revive } from './Flashcards';
import { load } from './storage';

type Course = { slug: string; titre: string; nbCartes: number };

/** Tableau de bord : cartes à revoir aujourd'hui et derniers scores de QCM, par cours. */
export default function Dashboard({ courses, base }: { courses: Course[]; base: string }) {
  const [rows, setRows] = useState<{ slug: string; titre: string; dues: number; quiz?: { score: number; total: number } }[]>([]);
  useEffect(() => {
    const now = new Date();
    setRows(
      courses.map((c) => {
        const st = load<Record<string, Card>>(`fsrs:${c.slug}`, {});
        const seen = Object.values(st);
        const dues = c.nbCartes - seen.length + seen.filter((k) => revive(k).due <= now).length;
        return { slug: c.slug, titre: c.titre, dues, quiz: load(`quiz:${c.slug}:last`, undefined) };
      }).sort((a, b) => b.dues - a.dues),
    );
  }, [courses]);
  const total = rows.reduce((s, r) => s + r.dues, 0);
  return (
    <div>
      <p aria-live="polite"><strong>{total}</strong> cartes à revoir aujourd’hui.</p>
      <table>
        <thead><tr><th scope="col">Cours</th><th scope="col">Cartes à revoir</th><th scope="col">Dernier QCM</th></tr></thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.slug}>
              <td><a href={`${base}cours/${r.slug}/index.html#flashcards`}>{r.titre}</a></td>
              <td>{r.dues}</td>
              <td>{r.quiz ? `${r.quiz.score} / ${r.quiz.total}` : '—'}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
