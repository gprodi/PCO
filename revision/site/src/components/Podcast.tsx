import { useEffect, useRef, useState } from 'react';

type Replique = { voix: string; texte: string };

/** Podcast : audio Piper si généré, sinon lecture à deux voix par la synthèse vocale du navigateur. */
export default function Podcast({ titre, repliques, audioUrl }: { titre: string; repliques: Replique[]; audioUrl?: string }) {
  const [playing, setPlaying] = useState(false);
  const [current, setCurrent] = useState(-1);
  const stopRef = useRef(false);
  // Détecté après l'hydratation : le rendu serveur et le premier rendu client doivent être identiques
  // (sinon erreur React #418).
  const [supported, setSupported] = useState(false);
  useEffect(() => setSupported('speechSynthesis' in window), []);

  useEffect(() => () => { if (supported) window.speechSynthesis.cancel(); }, [supported]);

  function speak() {
    if (!supported) return;
    const voices = window.speechSynthesis.getVoices().filter((v) => v.lang.startsWith('fr'));
    stopRef.current = false;
    setPlaying(true);
    const play = (i: number) => {
      if (stopRef.current || i >= repliques.length) {
        setPlaying(false);
        setCurrent(-1);
        return;
      }
      setCurrent(i);
      const u = new SpeechSynthesisUtterance(repliques[i].texte);
      u.lang = 'fr-FR';
      const v = voices[repliques[i].voix === 'B' ? 1 % Math.max(voices.length, 1) : 0];
      if (v) u.voice = v;
      u.pitch = repliques[i].voix === 'B' ? 0.85 : 1.1;
      u.onend = () => play(i + 1);
      window.speechSynthesis.speak(u);
    };
    play(0);
  }

  function stop() {
    stopRef.current = true;
    window.speechSynthesis.cancel();
    setPlaying(false);
    setCurrent(-1);
  }

  return (
    <div className="mf-podcast">
      <h3>{titre}</h3>
      {audioUrl ? (
        <audio controls src={audioUrl} preload="none">Ton navigateur ne lit pas l’audio.</audio>
      ) : supported ? (
        <p>
          {!playing ? <button type="button" className="mf-btn" onClick={speak}>▶️ Écouter (voix du navigateur)</button> : <button type="button" className="mf-btn secondary" onClick={stop}>⏹ Arrêter</button>}
          <span className="mf-badge">audio local : <code>revise podcast</code></span>
        </p>
      ) : (
        <p>Synthèse vocale indisponible : lis le script ci-dessous.</p>
      )}
      <div aria-live="polite">
        {repliques.map((r, i) => (
          <p key={i} style={{ opacity: current === -1 || current === i ? 1 : 0.55 }}>
            <span className="voix">{r.voix === 'A' ? 'Léa' : 'Karim'} :</span>
            {r.texte}
          </p>
        ))}
      </div>
    </div>
  );
}
