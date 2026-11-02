import { useEffect, useRef } from 'react';

/** Carte mentale interactive (markmap). Le texte Markdown reste disponible en alternative accessible. */
export default function MindMap({ markdown }: { markdown: string }) {
  const ref = useRef<SVGSVGElement>(null);
  useEffect(() => {
    let cancelled = false;
    (async () => {
      const [{ Transformer }, { Markmap }] = await Promise.all([import('markmap-lib'), import('markmap-view')]);
      if (cancelled || !ref.current) return;
      const { root } = new Transformer().transform(markdown);
      ref.current.innerHTML = '';
      Markmap.create(ref.current, { autoFit: true, duration: 300 }, root);
    })();
    return () => {
      cancelled = true;
    };
  }, [markdown]);
  return (
    <div className="mf-mindmap">
      <svg ref={ref} role="img" aria-label="Carte mentale du cours (version texte ci-dessous)" />
      <details>
        <summary>Version texte de la carte mentale</summary>
        <pre style={{ whiteSpace: 'pre-wrap' }}>{markdown}</pre>
      </details>
    </div>
  );
}
