// Révisions DevIA — Astro + Starlight (recherche Pagefind intégrée) + îlots React.
import { readFileSync } from 'node:fs';
import react from '@astrojs/react';
import starlight from '@astrojs/starlight';
import { defineConfig } from 'astro/config';

const data = JSON.parse(readFileSync(new URL('./src/data/courses.json', import.meta.url), 'utf-8'));
const ref = JSON.parse(readFileSync(new URL('./src/data/referentiel.json', import.meta.url), 'utf-8'));

const coursGroups = Object.entries(data.themes).map(([theme, label]) => ({
  label,
  collapsed: true,
  items: data.courses
    .filter((c) => c.theme === theme)
    .map((c) => ({ label: c.titre, link: `/cours/${c.slug}/` })),
}));

export default defineConfig({
  site: process.env.SITE_URL ?? 'https://gprodi.github.io',
  base: process.env.BASE_PATH ?? '/PCO',
  integrations: [
    react(),
    starlight({
      title: 'Révisions DevIA',
      description: 'Fiches, QCM, flashcards, exercices, cartes mentales et podcasts des cours Développeur en IA (Simplon).',
      defaultLocale: 'root',
      locales: { root: { label: 'Français', lang: 'fr' } },
      customCss: ['./src/styles/custom.css'],
      sidebar: [
        { label: 'Accueil', link: '/' },
        { label: 'Réviser aujourd’hui', link: '/reviser/' },
        { label: 'Tous les cours', link: '/cours/' },
        { label: 'Cours par thème', items: coursGroups },
        {
          label: 'Référentiel E1–E5',
          items: [{ label: 'Vue d’ensemble', link: '/referentiel/' }, ...ref.epreuves.map((e) => ({ label: `${e.id} — ${e.type}`, link: `/referentiel/${e.id.toLowerCase()}/` }))],
        },
        { label: 'Idées de projets par thème', link: '/idees/' },
        { label: 'Boilerplates', link: '/boilerplates/' },
        { label: 'Chat avec mes cours', link: '/chat/' },
        { label: 'Ajouter un cours', link: '/ajouter/' },
        { label: 'Aller plus loin', link: '/aller-plus-loin/' },
        { label: 'Mode d’emploi', link: '/guide/' },
      ],
    }),
  ],
});
