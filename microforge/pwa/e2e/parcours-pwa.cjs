// Parcours de bout en bout de la PWA (version construite, servie par « vite preview ») :
// inscription → stock → idées → projet (5 onglets) → copilote, audit axe (WCAG 2.2 A/AA) de chaque
// vue, puis hors ligne : la page se recharge depuis le service worker.
// Usage : node e2e/parcours-pwa.cjs <url de la PWA> <dossier des captures>
const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

const [base, shots] = process.argv.slice(2);
const AXE = fs.readFileSync(require.resolve('axe-core/axe.min.js'), 'utf8');
const user = `pwa${Date.now().toString().slice(-6)}`;

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
  const audit = async (view) => {
    await page.evaluate(AXE); // hors CSP (un script en ligne serait bloqué, à raison)
    const v = await page.evaluate(async () => (await axe.run(document, {
      runOnly: { type: 'tag', values: ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa'] },
      resultTypes: ['violations'],
    })).violations.map((x) => `${x.id}:${x.impact}:${x.nodes.length}`));
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
      await page.getByRole('heading', { name: 'Mon stock' }).waitFor({ timeout: 30000 });
    });
    await step('stock', async () => {
      await page.locator('#f-component').selectOption('esp32-devkit-v1');
      await page.locator('#f-quantity').fill('1');
      await page.getByRole('button', { name: 'Ajouter au stock' }).click();
      await page.getByText('1 pièces, 1 lignes.').waitFor({ timeout: 30000 });
      for (const id of ['dht22', 'ssd1306-i2c']) {
        await page.locator('#f-component').selectOption(id);
        await page.getByRole('button', { name: 'Ajouter au stock' }).click();
      }
      await page.getByText('3 pièces, 3 lignes.').waitFor({ timeout: 30000 });
      await page.screenshot({ path: path.join(shots, 'pwa-stock.png') });
    });
    await step('idees', async () => {
      await page.getByRole('link', { name: 'Idées' }).click();
      await page.getByRole('button', { name: 'Générer ce projet' }).first().waitFor({ timeout: 30000 });
    });
    await step('projet', async () => {
      await page.getByRole('button', { name: 'Générer ce projet' }).first().click();
      await page.getByRole('tab', { name: 'Câblage' }).waitFor({ timeout: 60000 });
      for (const tab of ['Schéma', 'Code', 'Nomenclature', 'Contrôle électrique', 'Câblage']) {
        await page.getByRole('tab', { name: tab }).click();
        await page.getByRole('tabpanel').waitFor();
      }
      await page.screenshot({ path: path.join(shots, 'pwa-projet.png') });
    });
    await step('copilote', async () => {
      await page.getByRole('link', { name: 'Copilote' }).click();
      await page.getByLabel('Ta question').fill('Broches I2C par défaut de l’ESP32 DevKit V1 ?');
      await page.getByRole('button', { name: 'Demander' }).click();
      await page.getByRole('heading', { name: /Sources \(\d+\)/ }).waitFor({ timeout: 60000 });
      await page.screenshot({ path: path.join(shots, 'pwa-copilote.png') });
    });
    await step('photo', async () => {
      await page.getByRole('link', { name: 'Photo' }).click();
      await page.getByRole('heading', { name: 'Photographier mon stock' }).waitFor();
    });
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
