// Atelier virtuel dans un cadre isolé (public/atelier/) : le simulateur exécute la logique du projet
// (new Function), ce que la CSP de l'application interdit. Le cadre a une origine opaque
// (sandbox sans allow-same-origin) : ni jetons, ni stockage, ni API de l'application.
// Échanges par postMessage, filtrés sur la fenêtre d'origine des deux côtés.
import { useEffect, useRef, useState } from 'react';

const MIN_H = 240;
const MAX_H = 6000;

export default function AtelierFrame({ payload, title, faites = [], onMission }) {
  const frame = useRef(null);
  // Missions déjà réussies : lues au montage de l'atelier seulement (les envoyer à chaque
  // réussite remonterait l'atelier et relancerait la simulation).
  const faitesRef = useRef(faites);
  faitesRef.current = faites;
  const onMissionRef = useRef(onMission);
  onMissionRef.current = onMission;
  const [ready, setReady] = useState(0); // incrémenté à chaque (re)chargement du cadre
  const [height, setHeight] = useState(520);

  useEffect(() => {
    const onMessage = (event) => {
      if (!frame.current || event.source !== frame.current.contentWindow) return;
      const msg = event.data;
      if (msg?.type === 'mf-atelier-ready') setReady((n) => n + 1);
      if (msg?.type === 'mf-mission' && typeof msg.id === 'string' && /^[a-z0-9-]{1,60}$/.test(msg.id)) onMissionRef.current?.(msg.id);
      if (msg?.type === 'mf-atelier-height' && Number.isFinite(msg.height)) {
        setHeight(Math.min(MAX_H, Math.max(MIN_H, Math.ceil(msg.height))));
      }
    };
    addEventListener('message', onMessage);
    return () => removeEventListener('message', onMessage);
  }, []);

  useEffect(() => {
    // Origine opaque : aucune origine cible nommable, d'où '*'. Rien de secret dans la charge.
    if (ready && payload) frame.current?.contentWindow?.postMessage({ type: 'mf-atelier', payload, faites: faitesRef.current }, '*');
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
