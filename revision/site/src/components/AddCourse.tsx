import { useState } from 'react';
import LocalOnly from './LocalOnly';
import { API_URL } from './storage';

const THEMES: Record<string, string> = { bases: 'Python & outils', data: 'Données & SQL', ml: 'ML / DL', api: 'API & sécurité', mlops: 'MLOps', monitoring: 'Monitoring', agentic: 'IA générative & agents', projets: 'Projets' };

function Inner() {
  const [file, setFile] = useState<File | null>(null);
  const [url, setUrl] = useState('');
  const [title, setTitle] = useState('');
  const [theme, setTheme] = useState('bases');
  const [status, setStatus] = useState('');

  async function poll(jobId: string) {
    for (let i = 0; i < 600; i++) {
      const r = await fetch(`${API_URL}/jobs/${jobId}`);
      const job = await r.json();
      setStatus(`État : ${job.status}${job.titre ? ` — ${job.titre}` : ''}${job.error ? ` — ${job.error}` : ''}`);
      if (job.status === 'done' || job.status === 'failed') return;
      await new Promise((res) => setTimeout(res, 2000));
    }
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setStatus('Envoi…');
    let r: Response;
    if (file) {
      const fd = new FormData();
      fd.append('file', file);
      if (title) fd.append('title', title);
      fd.append('theme', theme);
      r = await fetch(`${API_URL}/sources`, { method: 'POST', body: fd });
    } else {
      r = await fetch(`${API_URL}/sources/url`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ url, title: title || null, theme }) });
    }
    if (!r.ok) {
      setStatus(`Refusé : ${(await r.json()).detail}`);
      return;
    }
    const { job_id } = await r.json();
    setStatus('Traitement par l’IA locale (quelques minutes)…');
    await poll(job_id);
  }

  return (
    <form onSubmit={submit} className="mf-card">
      <p><label htmlFor="mf-file">Fichier (md, pdf, pptx, html, docx, ipynb, txt)</label><br />
        <input id="mf-file" type="file" accept=".md,.pdf,.pptx,.html,.htm,.docx,.ipynb,.txt" onChange={(e) => setFile(e.target.files?.[0] ?? null)} /></p>
      <p><label htmlFor="mf-url">… ou adresse d’une page web</label><br />
        <input id="mf-url" type="url" style={{ width: '100%' }} value={url} onChange={(e) => setUrl(e.target.value)} placeholder="https://…" /></p>
      <p><label htmlFor="mf-title">Titre (facultatif)</label><br />
        <input id="mf-title" style={{ width: '100%' }} value={title} onChange={(e) => setTitle(e.target.value)} /></p>
      <p><label htmlFor="mf-theme">Thème</label><br />
        <select id="mf-theme" value={theme} onChange={(e) => setTheme(e.target.value)}>
          {Object.entries(THEMES).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
        </select></p>
      <button className="mf-btn" type="submit" disabled={!file && !url}>Ajouter et générer</button>
      <p role="status" aria-live="polite">{status}</p>
    </form>
  );
}

export default function AddCourse() {
  return <LocalOnly feature="L’ajout de cours"><Inner /></LocalOnly>;
}
