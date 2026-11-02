import type { ReactNode } from 'react';
import { LOCAL_MODE } from './storage';

export default function LocalOnly({ children, feature }: { children: ReactNode; feature: string }) {
  if (LOCAL_MODE) return <>{children}</>;
  return (
    <div className="mf-notice">
      <p><strong>{feature}</strong> fonctionne avec l’application locale (IA sur ta machine, rien n’est envoyé en ligne).</p>
      <ol>
        <li>À la racine du dépôt : <code>uv run revise start</code> (lance l’API et le site, ouvre <code>http://localhost:4321/PCO/</code>)</li>
        <li>Pour l’IA locale : installe <a href="https://ollama.com">Ollama</a> puis <code>ollama pull qwen3:4b</code></li>
      </ol>
    </div>
  );
}
