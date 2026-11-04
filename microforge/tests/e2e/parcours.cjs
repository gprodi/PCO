// Parcours de bout en bout de l'application Streamlit (C10, C12) : inscription → stock → idées →
// génération → chaque onglet du projet → exploration par thème → copilote.
// Lancé par tests/test_e2e_parcours.py, qui démarre api_data, api_ia et Streamlit en local.
// Usage : node parcours.cjs <url Streamlit> <dossier des captures>
// Sortie : une ligne JSON {steps, exceptions, errors} ; code de sortie 1 si une étape échoue.
const { chromium } = require('playwright');

const [base, shots] = process.argv.slice(2);
const user = `maker${Date.now().toString().slice(-6)}`;
const TABS = ['Câblage', 'Schéma', 'Code', 'Guide de soudure', 'Simulation Wokwi', 'KiCad', 'Nomenclature', 'Fiabilité & sources'];

(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1280, height: 900 } });
  const steps = [];
  const errors = [];
  page.on('pageerror', (e) => errors.push(String(e)));
  const exceptions = async (where) => {
    const n = await page.locator('[data-testid="stException"]').count();
    if (n) {
      await page.screenshot({ path: `${shots}/erreur-${where}.png`, fullPage: true });
      throw new Error(`exception Streamlit affichée : ${where}`);
    }
  };
  const step = async (name, fn) => {
    const t0 = Date.now();
    await fn();
    await exceptions(name);
    steps.push({ name, ms: Date.now() - t0 });
  };
  const nav = (label) => page.locator('[data-testid="stSidebarNav"]').getByText(label).click();
  try {
    await page.goto(base, { waitUntil: 'networkidle' });

    await step('inscription', async () => {
      await page.getByText('Créer un compte').click();
      await page.getByLabel('Pseudo (3 à 40 caractères)').fill(user);
      await page.getByLabel('E-mail', { exact: true }).fill(`${user}@example.org`);
      await page.getByLabel(/Mot de passe \(10/).fill('motdepasse123');
      await page.getByRole('button', { name: 'Créer mon compte' }).click();
      await page.getByText('Connecté·e en tant que').waitFor({ timeout: 30000 });
    });

    await step('stock', async () => {
      await nav(/Mon stock/);
      await page.getByRole('button', { name: /Diodes et transistors de base/ }).click();
      // « Lot ajouté » disparaît au rechargement de la page : on attend le récapitulatif du stock, qui reste
      await page.getByText(/\d+ pièces, \d+ lignes\./).waitFor({ timeout: 30000 });
    });

    await step('idees', async () => {
      await nav(/Idees de projets|Idées de projets/);
      await page.getByText('Que puis-je construire').first().waitFor({ timeout: 30000 });
      await page.locator('[data-testid="stExpander"] summary').first().click();
      await page.getByRole('button', { name: 'Générer ce projet' }).first().click();
      await page.getByRole('tab', { name: 'Fiabilité & sources' }).waitFor({ timeout: 60000 });
    });

    for (const tab of TABS) {
      await step(`onglet ${tab}`, async () => {
        await page.getByRole('tab', { name: tab }).click();
        await page.waitForTimeout(600);
      });
    }

    await step('explorer', async () => {
      await nav(/Explorer par th/);
      await page.getByText('Parcours : de la première LED au robot autonome').waitFor({ timeout: 30000 });
    });

    await step('copilote', async () => {
      await nav(/Copilote/);
      const input = page.locator('[data-testid="stChatInputTextArea"]');
      await input.fill('Quelles sont les broches I2C par défaut de l’ESP32 DevKit V1 ?');
      await input.press('Enter');
      await page.locator('[data-testid="stChatMessage"]').nth(1).waitFor({ timeout: 60000 });
      await page.getByText(/Sources \(\d+\)/).waitFor({ timeout: 30000 }); // réponse appuyée sur le catalogue
    });

    await page.screenshot({ path: `${shots}/fin.png`, fullPage: true });
    console.log(JSON.stringify({ ok: true, steps, errors }));
  } catch (err) {
    await page.screenshot({ path: `${shots}/echec.png`, fullPage: true }).catch(() => {});
    console.log(JSON.stringify({ ok: false, failed: String(err), steps, errors }));
    process.exitCode = 1;
  } finally {
    await browser.close();
  }
})();
