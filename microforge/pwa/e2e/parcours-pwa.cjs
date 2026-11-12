// Parcours de bout en bout de la PWA (version construite, servie par « vite preview ») :
// inscription → stock → idées → projet (9 onglets, atelier virtuel dans son cadre isolé, changement
// de carte, archive .zip) → copilote, audit axe (WCAG 2.2 A/AA) de chaque vue et du cadre de
// l'atelier, puis hors ligne : la page se recharge depuis le service worker.
// Usage : node e2e/parcours-pwa.cjs <url de la PWA> <dossier des captures>
const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

const [base, shots] = process.argv.slice(2);
const AXE = fs.readFileSync(require.resolve('axe-core/axe.min.js'), 'utf8');
const user = `pwa${Date.now().toString().slice(-6)}`;
const expect = (cond, what) => { if (!cond) throw new Error(`attendu : ${what}`); };

(async () => {
  const browser = await chromium.launch();
  // Téléphone d'abord ; captures en double densité (rapport E4, artefacts de la CI).
  const context = await browser.newContext({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 2 });
  const page = await context.newPage();
  const steps = [];
  const errors = [];
  const a11y = {};
  page.on('pageerror', (e) => errors.push(String(e)));
  // Ressource bloquée par la politique CSP (servie avec les en-têtes de l'image nginx).
  let online = true;
  page.on('console', (m) => {
    if (online && /Content Security Policy/i.test(m.text())) errors.push(`CSP : ${m.text()}`);
  });
  // preload : axe relit les feuilles de style par le réseau ; le cadre de l'atelier l'interdit
  // (connect-src 'none'), on l'audite donc sans ce préchargement.
  const audit = async (view, target = page, preload = true) => {
    await target.evaluate(AXE); // hors CSP (un script en ligne serait bloqué, à raison)
    const v = await target.evaluate(async (pre) => (await axe.run(document, {
      runOnly: { type: 'tag', values: ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa'] },
      resultTypes: ['violations'],
      preload: pre,
    })).violations.map((x) => `${x.id}:${x.impact}:${x.nodes.length}:${x.nodes[0].target.join(' ')}`), preload);
    a11y[view] = v;
  };
  const step = async (name, fn) => {
    const t0 = Date.now();
    await fn();
    await audit(name);
    steps.push({ name, ms: Date.now() - t0 });
  };
  try {
    await page.goto(base, { waitUntil: 'networkidle' });
    await step('inscription', async () => {
      await page.getByRole('button', { name: 'Créer un compte' }).click();
      await page.getByLabel(/Pseudo/).fill(user);
      await page.getByLabel('E-mail').fill(`${user}@example.org`);
      await page.getByLabel(/Mot de passe/).fill('motdepasse123');
      await page.getByRole('button', { name: 'Créer mon compte' }).click();
      await page.getByRole('heading', { name: /Tes composants deviennent des projets/ }).waitFor({ timeout: 30000 });
    });
    await step('accueil', async () => {
      await page.getByRole('heading', { name: /Le parcours/ }).waitFor({ timeout: 30000 });
      await page.getByRole('heading', { name: /Ils l'ont construit/ }).waitFor({ timeout: 30000 });
      await page.screenshot({ path: path.join(shots, 'pwa-accueil.png') });
    });
    await step('stock', async () => {
      await page.getByRole('link', { name: 'Mon stock', exact: true }).click();
      await page.getByRole('heading', { name: 'Mon stock', level: 1 }).waitFor();
      await page.locator('#f-component').selectOption('esp32-devkit-v1');
      await page.locator('#f-quantity').fill('1');
      await page.getByRole('button', { name: 'Ajouter au stock' }).click();
      await page.getByText('1 pièce, 1 ligne.').waitFor({ timeout: 30000 });
      for (const id of ['dht22', 'ssd1306-i2c']) {
        await page.locator('#f-component').selectOption(id);
        await page.getByRole('button', { name: 'Ajouter au stock' }).click();
      }
      await page.getByText('3 pièces, 3 lignes.').waitFor({ timeout: 30000 });
      await page.screenshot({ path: path.join(shots, 'pwa-stock.png') });
    });
    await step('explorer', async () => {
      await page.getByRole('link', { name: 'Explorer', exact: true }).click();
      await page.getByRole('heading', { name: 'Par thème' }).waitFor({ timeout: 30000 });
      await page.getByRole('button', { name: 'Générer ce projet' }).first().waitFor({ timeout: 30000 });
      await page.screenshot({ path: path.join(shots, 'pwa-explorer.png') });
      // Changer de thème : la liste d'idées suit.
      await page.getByRole('button', { name: /Robots & mouvement/ }).click();
      await page.getByRole('heading', { name: 'Robots & mouvement', level: 2 }).waitFor();
    });
    await step('projet', async () => {
      await page.getByRole('button', { name: 'Générer ce projet' }).first().click();
      await page.getByRole('tab', { name: 'Câblage' }).waitFor({ timeout: 60000 });
      const tabs = ['Atelier virtuel', 'Schéma', 'Code', 'Guide de soudure', 'Simulation Wokwi', 'Nomenclature', 'KiCad', 'Fiabilité & sources', 'Câblage'];
      for (const tab of tabs) {
        await page.getByRole('tab', { name: tab, exact: true }).click();
        await page.getByRole('tabpanel').waitFor();
      }
      expect(await page.getByRole('tab').count() === 9, 'neuf onglets');
      await page.screenshot({ path: path.join(shots, 'pwa-projet.png') });
      // Guide rendu (titres Markdown) et sources (niveaux de vérification).
      await page.getByRole('tab', { name: 'Guide de soudure' }).click();
      await page.getByRole('tabpanel').getByRole('heading', { name: /Outillage/ }).waitFor();
      await page.getByRole('tab', { name: 'Fiabilité & sources' }).click();
      await page.getByRole('heading', { name: 'Niveau de vérification' }).waitFor();
      // Atelier virtuel : cadre isolé, tout brancher, la simulation avance.
      await page.getByRole('tab', { name: 'Atelier virtuel' }).click();
      const frame = page.frameLocator('iframe[title^="Atelier virtuel"]');
      await frame.getByRole('button', { name: 'Tout brancher' }).click({ timeout: 30000 });
      await frame.locator('.mfa-time').filter({ hasNotText: '00:00.0' }).waitFor({ timeout: 15000 });
      await page.screenshot({ path: path.join(shots, 'pwa-atelier.png') });
      const atelier = page.frames().find((f) => f.url().includes('/atelier/'));
      expect(atelier, 'cadre de l\'atelier chargé');
      await audit('atelier (cadre)', atelier, false);
      // Archive .zip du projet.
      const [download] = await Promise.all([
        page.waitForEvent('download', { timeout: 30000 }),
        page.getByRole('button', { name: 'Télécharger le projet (.zip)' }).click(),
      ]);
      expect(download.suggestedFilename().endsWith('.zip'), 'archive .zip');
      // Enregistrement : le projet rejoint « Mes projets », la liste d'achat compare au stock.
      await page.getByRole('button', { name: 'Enregistrer dans mes projets' }).click();
      await page.getByRole('heading', { name: "Liste d'achat" }).waitFor({ timeout: 30000 });
      // Changement de carte : le projet est régénéré pour la carte choisie.
      const pick = page.getByLabel('Carte');
      const options = await pick.locator('option').evaluateAll((os) => os.map((o) => o.value));
      const current = await pick.inputValue();
      const other = options.find((v) => v !== current);
      expect(other, 'au moins deux cartes compatibles');
      await pick.selectOption(other);
      await page.waitForFunction((v) => document.querySelector('.board-pick select')?.value === v, other, { timeout: 60000 });
      // Atelier au format bureau (documentation) : dessins Wokwi de la carte choisie.
      await page.setViewportSize({ width: 1280, height: 900 });
      await page.getByRole('tab', { name: 'Atelier virtuel' }).click();
      await frame.getByRole('button', { name: 'Tout brancher' }).click({ timeout: 30000 });
      await frame.locator('.mfa-time').filter({ hasNotText: '00:00.0' }).waitFor({ timeout: 15000 });
      await page.waitForTimeout(3500); // premier rafraîchissement de l'écran (toutes les 2 s)
      await page.screenshot({ path: path.join(shots, 'pwa-atelier-bureau.png'), fullPage: true });
      await page.setViewportSize({ width: 390, height: 844 });
    });
    await step('idée sans modèle', async () => {
      // Thème sans modèle vérifié : « Concevoir avec l'IA ». Sans vraie IA (modèle simulé en test,
      // pas d'Ollama dans la pile de la CI), le modèle le plus proche est renvoyé, et c'est écrit.
      await page.getByRole('link', { name: 'Explorer', exact: true }).click();
      await page.getByRole('button', { name: /Objets connectés/ }).click({ timeout: 30000 });
      await page.getByRole('heading', { name: /Objets connectés/, level: 2 }).waitFor();
      await page.getByRole('button', { name: "Concevoir avec l'IA" }).first().click();
      const note = page.getByRole('note').filter({ hasText: 'modèle du catalogue le plus proche' });
      await note.waitFor({ timeout: 120000 });
      expect(/Aucune IA n'a répondu|pas proposé de montage valide/.test(await note.innerText()), 'raison du repli');
      await page.getByRole('tab', { name: 'Câblage' }).waitFor();
      await page.screenshot({ path: path.join(shots, 'pwa-idee-ia.png') });
    });
    await step('créer', async () => {
      // Comme la page Streamlit « Je veux construire… » : modèle du catalogue, puis idée libre.
      await page.getByRole('link', { name: 'Créer', exact: true }).click();
      await page.getByRole('heading', { name: 'Je veux construire…', level: 1 }).waitFor();
      const saved = page.getByRole('region', { name: /Mes projets enregistrés/ }).or(page.locator('section[aria-labelledby="t-mes-projets"]'));
      await saved.getByRole('button', { name: 'Ouvrir' }).first().waitFor({ timeout: 30000 });
      await page.getByLabel('Choisir un modèle').check();
      const options = await page.getByLabel(/^Modèle/).locator('option:not([disabled])').evaluateAll((os) => os.map((o) => o.value));
      expect(options.length >= 50, 'modèles du catalogue proposés');
      await page.getByLabel(/^Modèle/).selectOption(options[0]);
      await page.getByRole('button', { name: 'Générer' }).click();
      await page.getByRole('tab', { name: 'Câblage' }).waitFor({ timeout: 60000 });
      await page.getByRole('link', { name: 'Créer', exact: true }).click();
      await page.getByLabel('Décrire mon idée').check();
      await page.getByLabel('Décris ce que tu veux construire').fill('Une veilleuse qui s\'allume quand il fait noir dans le couloir');
      await page.getByRole('button', { name: 'Concevoir le projet' }).click();
      await page.getByRole('note').filter({ hasText: 'modèle du catalogue le plus proche' }).waitFor({ timeout: 120000 });
      await page.getByRole('link', { name: 'Créer', exact: true }).click();
      await page.screenshot({ path: path.join(shots, 'pwa-creer.png') });
      // Projet enregistré rouvert : reconstruit à partir de sa spécification.
      await saved.getByRole('button', { name: 'Ouvrir' }).first().click();
      await page.getByRole('tab', { name: 'Câblage' }).waitFor({ timeout: 60000 });
    });
    await step('atelier', async () => {
      // Comme la page Streamlit « Atelier virtuel » : un projet, une carte, brancher, simuler.
      await page.getByRole('link', { name: 'Atelier', exact: true }).click();
      await page.getByRole('heading', { name: 'Brancher, puis voir fonctionner', level: 1 }).waitFor();
      const frame = page.frameLocator('iframe[title^="Atelier virtuel"]');
      await frame.getByRole('button', { name: 'Tout brancher' }).click({ timeout: 60000 });
      await frame.locator('.mfa-time').filter({ hasNotText: '00:00.0' }).waitFor({ timeout: 15000 });
      await page.screenshot({ path: path.join(shots, 'pwa-atelier-vue.png') });
      // Autre projet : le cadre est rechargé avec le nouveau montage.
      const projets = await page.getByLabel('Projet').locator('option').evaluateAll((os) => os.map((o) => o.value));
      const now = await page.getByLabel('Projet').inputValue();
      await page.getByLabel('Projet').selectOption(projets.find((v) => v !== now));
      await frame.getByRole('button', { name: 'Tout brancher' }).click({ timeout: 60000 });
      await frame.locator('.mfa-time').filter({ hasNotText: '00:00.0' }).waitFor({ timeout: 15000 });
      await page.getByText('Code JavaScript exécuté par la simulation').click();
      await page.getByRole('region', { name: 'Fichier simulation.js' }).or(page.getByLabel('Fichier simulation.js')).waitFor();
    });
    await step('copilote', async () => {
      await page.getByRole('link', { name: 'Copilote', exact: true }).click();
      await page.getByLabel('Ta question').fill('Broches I2C par défaut de l’ESP32 DevKit V1 ?');
      await page.getByRole('button', { name: 'Demander' }).click();
      await page.getByRole('heading', { name: /Sources \(\d+\)/ }).waitFor({ timeout: 60000 });
      await page.screenshot({ path: path.join(shots, 'pwa-copilote.png') });
    });
    await step('photo', async () => {
      await page.getByRole('link', { name: 'Mon stock', exact: true }).click();
      await page.getByRole('link', { name: 'Photographier mon stock' }).click();
      await page.getByRole('heading', { name: 'Photographier mon stock' }).waitFor();
    });
    // Format bureau, thèmes clair et sombre : captures pour la documentation et les artefacts de la CI.
    await page.setViewportSize({ width: 1280, height: 860 });
    await page.goto(`${base}#accueil`, { waitUntil: 'networkidle' });
    await page.getByRole('heading', { name: /Le parcours/ }).waitFor({ timeout: 30000 });
    await page.screenshot({ path: path.join(shots, 'pwa-accueil-bureau.png') });
    await page.emulateMedia({ colorScheme: 'dark' });
    await page.goto(`${base}#explorer`, { waitUntil: 'networkidle' });
    await page.getByRole('heading', { name: 'Par thème' }).waitFor({ timeout: 30000 });
    await page.screenshot({ path: path.join(shots, 'pwa-explorer-sombre.png') });
    await audit('explorer sombre');
    await page.emulateMedia({ colorScheme: 'light' });
    await page.setViewportSize({ width: 390, height: 844 });
    // Hors ligne : l'interface revient du cache du service worker.
    await page.waitForFunction(() => navigator.serviceWorker && navigator.serviceWorker.controller, null, { timeout: 15000 })
      .catch(() => page.reload({ waitUntil: 'networkidle' }));
    online = false;
    await context.setOffline(true);
    await page.reload({ waitUntil: 'domcontentloaded' });
    const offline = await page.getByText(/Hors ligne/).first().isVisible({ timeout: 10000 }).catch(() => false);
    const shell = await page.getByText('MicroForge').first().isVisible().catch(() => false);
    steps.push({ name: 'hors ligne', offline, shell });
    await context.setOffline(false);
    const ok = offline && shell && Object.values(a11y).every((v) => v.length === 0) && errors.length === 0;
    console.log(JSON.stringify({ ok, steps, a11y, errors }));
    if (!ok) process.exitCode = 1;
  } catch (err) {
    await page.screenshot({ path: path.join(shots, 'pwa-echec.png'), fullPage: true }).catch(() => {});
    console.log(JSON.stringify({ ok: false, failed: String(err), steps, a11y, errors }));
    process.exitCode = 1;
  } finally {
    await browser.close();
  }
})();
