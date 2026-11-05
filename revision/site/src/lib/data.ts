import { marked } from 'marked';
import coursesData from '../data/courses.json';
import referentiel from '../data/referentiel.json';
import boilerplates from '../data/boilerplates.json';

export type Course = { slug: string; titre: string; theme: string; disponible: boolean; audio: boolean };
export type Content = {
  slug: string; titre: string; theme: string; origine: string;
  fiche: { titre: string; resume: string; objectifs: string[]; notions: { terme: string; definition: string }[]; points_cles: string[];
    code: { titre: string; lang: string; code: string; explication: string }[]; pieges: string[]; competences: string[]; sources: string[];
    aller_plus_loin?: { titre: string; contenu: string; lien?: string }[]; jury?: string };
  quiz: { questions: { question: string; choix: string[]; bonne: number; explication: string; difficulte: number }[] };
  flashcards: { cartes: { recto: string; verso: string; tags: string[] }[] };
  exercices: { exercices: { titre: string; niveau: number; enonce: string; indices: string[]; corrige: string }[] };
  mindmap: { markdown: string };
  podcast: { titre: string; repliques: { voix: string; texte: string }[] };
};

const files = import.meta.glob<Content>('../data/content/*.json', { eager: true, import: 'default' });
export const contents: Record<string, Content> = Object.fromEntries(Object.values(files).map((c) => [c.slug, c]));
export const themes: Record<string, string> = coursesData.themes;
export const courses: Course[] = coursesData.courses;
export const ref = referentiel as any;
export const bps = boilerplates as any[];
export const base = import.meta.env.BASE_URL.replace(/\/?$/, '/');
// Blocs de code : ils défilent horizontalement sur téléphone, donc ils doivent être atteignables au
// clavier (WCAG 2.1.1, règle axe scrollable-region-focusable) : tabindex et nom accessible.
export const md = (s: string) =>
  (marked.parse(s ?? '', { async: false }) as string).replaceAll(
    '<pre>',
    '<pre tabindex="0" role="region" aria-label="Exemple de code">',
  );
export const competence = (id: string) => ref.competences.find((c: any) => c.id === id);
import idees from '../data/idees.json';
export type Idea = { titre: string; description: string; difficulte: number; composants: string[]; composants_noms: string[]; template?: string; wifi?: boolean };
export type Theme = { id: string; titre: string; icone: string; description: string; idees: Idea[] };
export const themesIdees: Theme[] = idees as Theme[];
