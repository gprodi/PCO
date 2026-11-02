import type { ReactNode } from 'react';
import { LOCAL_MODE } from './storage';

export default function LocalOnly({ children, feature }: { children: ReactNode; feature: string }) {
  if (LOCAL_MODE) return <>{children}</>;
  return (
    <div className="mf-notice">
      <p><strong>{feature}</strong> fonctionne avec l’application locale (IA sur ta machine, rien n’est envoyé en ligne).</p>
      <ol>
        <li><code>uv run revise serve</code> (à la racine du dépôt)</li>
        <li><code>cd revision/site && npm run dev</code> puis ouvre <code>http://localhost:4321/PCO/</code></li>
      </ol>
    </div>
  );
}
