// Éléments partagés par les vues : messages d'erreur, statut, icônes, couleurs des fils.
import { ApiError, NetworkError } from './api.js';

export const message = (err) => {
  if (!navigator.onLine) return 'Hors ligne : réessaie une fois connecté.';
  if (err instanceof NetworkError) {
    return `Impossible de joindre l'API ${err.url} depuis ${location.origin}. Vérifie qu'elle tourne (docker compose --profile core ps) et que l'adresse de cette page est autorisée par l'API (MF_CORS_ORIGINS).`;
  }
  if (!(err instanceof ApiError)) return `Erreur : ${err.message}`;
  if (Array.isArray(err.detail)) return err.detail.map((d) => d.msg).join(' ; ');
  return typeof err.detail === 'string' ? err.detail : `Erreur ${err.status}`;
};

export function Status({ state }) {
  return (
    <p className={`status${state?.error ? ' err' : ''}`} role="status" aria-live="polite">
      {state?.text ?? ''}
    </p>
  );
}

/** Difficulté 1 à 3, lue « difficulté 2 sur 3 » par les lecteurs d'écran. */
export function Dots({ n }) {
  return (
    <span className="dots" role="img" aria-label={`difficulté ${n} sur 3`}>
      {[1, 2, 3].map((i) => <i key={i} className={i <= n ? 'on' : ''} />)}
    </span>
  );
}

export const plural = (n, one, many) => `${n} ${n > 1 ? many : one}`;
export const euros = (v) => (v == null ? '—' : `${v.toFixed(2).replace('.', ',')} €`);

export const CATEGORIES = {
  carte: 'Cartes', capteur: 'Capteurs', afficheur: 'Afficheurs', actionneur: 'Actionneurs',
  entree: 'Entrées', communication: 'Communication', stockage: 'Stockage', passif: 'Passifs',
  discret: 'Semi-conducteurs', ci: 'Circuits intégrés', consommable: 'Connectique',
  outillage: 'Outillage', alimentation: 'Alimentation',
};

// Code couleur des fils Dupont, le même que le générateur (core/outputs/colors.py).
const RAIL_3V3 = /^(3V3|3\.3V|3,3V)$/i;
export function wireColor(a) {
  const net = a.net ?? '';
  if (a.role === 'ground' || net === 'GND') return ['noir', 'masse'];
  if (a.role === 'power') return RAIL_3V3.test(a.board_label) ? ['orange', 'alimentation 3,3 V'] : ['rouge', 'alimentation 5 V'];
  if (net.startsWith('I2C_SDA')) return ['bleu', 'données I2C'];
  if (net.startsWith('I2C_SCL')) return ['jaune', 'horloge I2C'];
  if (net.startsWith('SPI_') || net.endsWith('_CS')) return ['violet', 'bus SPI'];
  return ['vert', 'signal'];
}

/* Icônes au trait (24 × 24), décoratives : le libellé est toujours écrit à côté. */
const PATHS = {
  accueil: 'M4 11.5 12 5l8 6.5V20h-5.5v-5h-5v5H4z',
  explorer: 'M4 4h7v7H4zM13 4h7v7h-7zM4 13h7v7H4zM13 13h7v7h-7z',
  stock: 'M3.5 8 12 4l8.5 4v8L12 20l-8.5-4zM3.5 8 12 12l8.5-4M12 12v8',
  projet: 'M7 3h10v18H7zM10 7h4M10 11h4M4 8h3M4 12h3M4 16h3M17 8h3M17 12h3M17 16h3',
  copilote: 'M4 5h16v11H9l-5 4zM8 9.5h8M8 12.5h5',
  photo: 'M4 8h3.5L9 5.5h6L16.5 8H20v11H4zM12 16.5a3 3 0 1 0 0-6 3 3 0 0 0 0 6z',
  fleche: 'M5 12h13M13 7l5 5-5 5',
  plus: 'M12 5v14M5 12h14',
  sortie: 'M10 5H5v14h5M14 8l4 4-4 4M18 12H9',
  copier: 'M8 8h11v12H8zM5 16V4h11',
  lien: 'M10 14 20 4M14 4h6v6M18 14v6H4V6h6',
  telecharger: 'M12 4v11M7 10l5 5 5-5M5 19h14',
};

export function Icon({ name, size = 20 }) {
  return (
    <svg className="icon" width={size} height={size} viewBox="0 0 24 24" aria-hidden="true" focusable="false">
      <path d={PATHS[name]} />
    </svg>
  );
}
