import { useState } from 'react';
import { load, save } from './storage';

type Question = { question: string; choix: string[]; bonne: number; explication: string; difficulte: number };

export default function Quiz({ slug, questions }: { slug: string; questions: Question[] }) {
  const [answers, setAnswers] = useState<Record<number, number>>({});
  const score = Object.entries(answers).filter(([i, a]) => questions[Number(i)].bonne === a).length;
  const done = Object.keys(answers).length === questions.length;

  function choose(qi: number, ci: number) {
    if (answers[qi] !== undefined) return;
    const next = { ...answers, [qi]: ci };
    setAnswers(next);
    if (Object.keys(next).length === questions.length) {
      const best = load<number>(`quiz:${slug}:best`, 0);
      const s = Object.entries(next).filter(([i, a]) => questions[Number(i)].bonne === a).length;
      save(`quiz:${slug}:best`, Math.max(best, s));
      save(`quiz:${slug}:last`, { score: s, total: questions.length, date: new Date().toISOString() });
    }
  }

  return (
    <div>
      {questions.map((q, qi) => (
        <fieldset key={qi} className="mf-card">
          <legend>
            <strong>Question {qi + 1}</strong> <span className="mf-badge">{'★'.repeat(q.difficulte)}</span>
          </legend>
          <p>{q.question}</p>
          {q.choix.map((c, ci) => {
            const answered = answers[qi] !== undefined;
            const state = !answered ? undefined : ci === q.bonne ? 'ok' : ci === answers[qi] ? 'ko' : undefined;
            return (
              <button key={ci} type="button" className="mf-choice" data-state={state} aria-pressed={answers[qi] === ci} disabled={answered} onClick={() => choose(qi, ci)}>
                {String.fromCharCode(65 + ci)}. {c} {state === 'ok' ? ' ✅ bonne réponse' : state === 'ko' ? ' ❌ ta réponse' : ''}
              </button>
            );
          })}
          {answers[qi] !== undefined && (
            <p role="status">
              {answers[qi] === q.bonne ? '✅ Bravo !' : '❌ Pas tout à fait.'} {q.explication}
            </p>
          )}
        </fieldset>
      ))}
      <p role="status" aria-live="polite">
        Score : <strong>{score} / {questions.length}</strong> {done && (score === questions.length ? '🎉 Parfait !' : '— recommence pour progresser.')}
      </p>
      {done && <button type="button" className="mf-btn secondary" onClick={() => setAnswers({})}>Recommencer</button>}
    </div>
  );
}
