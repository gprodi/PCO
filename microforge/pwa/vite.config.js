import { createHash } from 'node:crypto';
import fs from 'node:fs';
import path from 'node:path';
import react from '@vitejs/plugin-react';
import { defineConfig } from 'vite';

/** Écrit dans dist/sw.js la liste des fichiers construits (préchargés à l'installation) et un nom de
 *  cache propre à cette version : l'interface fonctionne hors ligne dès la première visite. */
function precache() {
  let outDir = 'dist';
  let files = [];
  return {
    name: 'microforge-precache',
    apply: 'build',
    configResolved(config) { outDir = config.build.outDir; },
    generateBundle(_, bundle) { files = Object.keys(bundle).filter((f) => !f.endsWith('.map')).sort(); },
    closeBundle() {
      const sw = path.resolve(outDir, 'sw.js');
      const version = createHash('sha256').update(files.join('\n')).digest('hex').slice(0, 12);
      const text = fs.readFileSync(sw, 'utf8')
        .replace("const BUILD_ASSETS = [];", `const BUILD_ASSETS = ${JSON.stringify(files.map((f) => `./${f}`))};`)
        .replace("const CACHE = 'microforge-dev';", `const CACHE = 'microforge-${version}';`);
      fs.writeFileSync(sw, text);
    },
  };
}

/** Dessins Wokwi de l'atelier virtuel (public/atelier) : le paquet npm complet (licence MIT) est copié
 *  à la construction et servi tel quel en développement, sans être versionné dans le dépôt. */
const WOKWI_BUNDLE = 'node_modules/@wokwi/elements/dist/wokwi-elements.bundle.min.js';
function wokwiBundle() {
  let outDir = 'dist';
  return {
    name: 'microforge-wokwi-atelier',
    configResolved(config) { outDir = config.build.outDir; },
    configureServer(server) {
      server.middlewares.use('/atelier/wokwi-elements.bundle.min.js', (_req, res) => {
        res.setHeader('Content-Type', 'application/javascript');
        res.end(fs.readFileSync(path.resolve(WOKWI_BUNDLE)));
      });
    },
    closeBundle() {
      fs.copyFileSync(path.resolve(WOKWI_BUNDLE), path.resolve(outDir, 'atelier', 'wokwi-elements.bundle.min.js'));
    },
  };
}

// base relative : la PWA se sert depuis n'importe quel chemin (Traefik, serveur statique, aperçu).
export default defineConfig({
  base: './',
  plugins: [react(), precache(), wokwiBundle()],
  build: { target: 'es2022', sourcemap: true },
  test: { environment: 'node', include: ['src/**/*.test.js'] },
});
