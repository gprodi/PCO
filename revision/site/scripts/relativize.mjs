// Transforme le build Astro (base absolue « /PCO/ ») en site autonome à liens RELATIFS,
// publiable n'importe où (Artifact, clé USB, sous-dossier d'un serveur).
//
//   ARTIFACT=1 npm run build && node scripts/relativize.mjs dist dist-relatif
//
// Le script échoue (code 1) s'il reste un lien interne absolu ou un lien qui ne pointe sur aucun fichier.
import { cpSync, existsSync, readdirSync, readFileSync, rmSync, statSync, writeFileSync } from 'node:fs';
import { dirname, join, posix, relative, sep } from 'node:path';

const [src = 'dist', out = 'dist-relatif', base = '/PCO/'] = process.argv.slice(2);
const baseNoSlash = base.replace(/\/$/, '');

rmSync(out, { recursive: true, force: true });
cpSync(src, out, { recursive: true });
for (const f of ['pagefind', 'sitemap-index.xml', 'sitemap-0.xml']) rmSync(join(out, f), { recursive: true, force: true });

const files = [];
(function walk(d) {
  for (const n of readdirSync(d)) {
    const p = join(d, n);
    if (statSync(p).isDirectory()) walk(p);
    else files.push(p);
  }
})(out);
const rel = (p) => relative(out, p).split(sep).join('/');

/** Chemin interne (sans la base) -> fichier réel du site, ou null. */
function resolveTarget(path) {
  const clean = decodeURIComponent(path);
  const candidates = clean === '' ? ['index.html']
    : clean.endsWith('/') ? [`${clean}index.html`]
    : [clean, `${clean}/index.html`, `${clean}.html`];
  return candidates.find((c) => existsSync(join(out, c)) && statSync(join(out, c)).isFile()) ?? null;
}

const broken = [];
let rewritten = 0;
const ATTR = /(\s(?:href|src|component-url|renderer-url|poster|action)=)(["'])([^"']*)\2/g;

for (const file of files.filter((f) => f.endsWith('.html'))) {
  const here = rel(file);
  const prefix = posix.relative(posix.dirname(here), '.') || '.';
  const toRel = (target) => (prefix === '.' ? target : `${prefix}/${target}`);
  let html = readFileSync(file, 'utf-8');
  html = html.replace(/<link rel="sitemap"[^>]*>/g, ''); // plan du site retiré de cette version
  html = html.replace(ATTR, (m, attr, q, value) => {
    if (!(value === baseNoSlash || value.startsWith(base))) return m;
    const [pathAndQuery, hash = ''] = value.slice(base.length).split('#');
    const path = pathAndQuery.split('?')[0];
    const target = resolveTarget(path);
    if (!target) {
      broken.push(`${here} -> ${value}`);
      return m;
    }
    rewritten += 1;
    return `${attr}${q}${toRel(target)}${hash ? `#${hash}` : ''}${q}`;
  });
  // Props JSON des îlots React (échappées en HTML) : {"base":[0,"/PCO/"]} -> préfixe relatif de la page.
  html = html.replaceAll(`&quot;${base}&quot;`, `&quot;${prefix === '.' ? './' : `${prefix}/`}&quot;`);
  writeFileSync(file, html);
}

// Imports dynamiques de Vite : "/PCO/"+chemin -> URL calculée depuis le module (_astro/ est à la racine).
for (const file of files.filter((f) => f.endsWith('.js'))) {
  let js = readFileSync(file, 'utf-8');
  const before = js;
  js = js.replaceAll(`"${base}"+`, ' new URL("../",import.meta.url).href+'); // espace : « return"…" » minifié
  // Caractère U+FFFD littéral (décodeur UTF-8 de markmap) : échappé, strictement équivalent dans une chaîne.
  js = js.replaceAll('\uFFFD', '\\uFFFD');
  if (js !== before) writeFileSync(file, js);
}

// Contrôle final : plus aucune référence interne absolue (le texte « localhost:4321/PCO/ » est permis).
const leftovers = [];
for (const file of files.filter((f) => /\.(html|js|css)$/.test(f) && existsSync(f))) {
  const text = readFileSync(file, 'utf-8');
  const re = new RegExp(`(href|src|component-url|renderer-url)=["']${base}|"${base}"\\+|url\\(${base}`, 'g');
  if (re.test(text)) leftovers.push(rel(file));
}

console.log(`${rewritten} liens réécrits, ${files.length} fichiers.`);
if (broken.length || leftovers.length) {
  if (broken.length) console.error(`Liens internes cassés (${broken.length}) :\n  ${broken.slice(0, 30).join('\n  ')}`);
  if (leftovers.length) console.error(`Références absolues restantes : ${leftovers.join(', ')}`);
  process.exit(1);
}
console.log(`Site relatif prêt : ${out}`);
