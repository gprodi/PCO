// Atelier virtuel dans un cadre isolé (public/atelier/) : le simulateur exécute la logique du projet
// (new Function), ce que la CSP de l'application interdit. Le cadre a une origine opaque
// (sandbox sans allow-same-origin) : ni jetons, ni stockage, ni API de l'application.
// Échanges par postMessage, filtrés sur la fenêtre d'origine des deux côtés.
import { useEffect, useRef, useState } from 'react';

const MIN_H = 240;
const MAX_H = 6000;

export default function AtelierFrame({ payload, title }) {
  const frame = useRef(null);
  const [ready, setReady] = useState(0); // incrémenté à chaque (re)chargement du cadre
  const [height, setHeight] = useState(520);

  useEffect(() => {
    const onMessage = (event) => {
      if (!frame.current || event.source !== frame.current.contentWindow) return;
      const msg = event.data;
      if (msg?.type === 'mf-atelier-ready') setReady((n) => n + 1);
      if (msg?.type === 'mf-atelier-height' && Number.isFinite(msg.height)) {
        setHeight(Math.min(MAX_H, Math.max(MIN_H, Math.ceil(msg.height))));
      }
    };
    addEventListener('message', onMessage);
    return () => removeEventListener('message', onMessage);
  }, []);

  useEffect(() => {
    // Origine opaque : aucune origine cible nommable, d'où '*'. Rien de secret dans la charge.
    if (ready && payload) frame.current?.contentWindow?.postMessage({ type: 'mf-atelier', payload }, '*');
  }, [ready, payload]);

  return (
    <iframe
      ref={frame}
      className="atelier-frame"
      src="atelier/index.html"
      sandbox="allow-scripts"
      title={`Atelier virtuel : ${title}`}
      height={height}
      loading="lazy"
    />
  );
}
