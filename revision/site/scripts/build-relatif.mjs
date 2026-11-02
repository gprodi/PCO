// Build « autonome » (liens relatifs, sans Pagefind) puis réécriture des liens — multiplateforme
// (remplace « ARTIFACT=1 PUBLIC_MODE=static astro build », syntaxe refusée par PowerShell/cmd).
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';

const root = fileURLToPath(new URL('..', import.meta.url));
const run = (args, env = {}) => {
  const r = spawnSync(process.execPath, args, { cwd: root, stdio: 'inherit', env: { ...process.env, ...env } });
  if (r.status !== 0) process.exit(r.status ?? 1);
};
run(['node_modules/astro/astro.js', 'build'], { ARTIFACT: '1', PUBLIC_MODE: 'static' });
run(['scripts/relativize.mjs', 'dist', 'dist-relatif']);
