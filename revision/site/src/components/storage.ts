// Stockage local tolérant (navigation privée, stockage bloqué) : jamais d'exception.
export function load<T>(key: string, fallback: T): T {
  try {
    const raw = window.localStorage.getItem(key);
    return raw ? (JSON.parse(raw) as T) : fallback;
  } catch {
    return fallback;
  }
}
export function save(key: string, value: unknown): void {
  try {
    window.localStorage.setItem(key, JSON.stringify(value));
  } catch {
    /* stockage indisponible : on continue sans persistance */
  }
}
export const API_URL: string = import.meta.env.PUBLIC_API_URL ?? 'http://localhost:8765';
export const LOCAL_MODE: boolean = import.meta.env.PUBLIC_MODE === 'local';
