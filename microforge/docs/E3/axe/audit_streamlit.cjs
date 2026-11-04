// Audit axe-core (WCAG 2.2 A/AA) de la page d'accueil Streamlit, thèmes clair et sombre.
// Usage : streamlit run Accueil.py --server.port=8598, puis
//   node audit_streamlit.cjs <chemin de axe.min.js (npm axe-core@4.10.3)> resultats.json
const { chromium } = require('playwright');
const fs = require('fs');
const AXE = fs.readFileSync(process.argv[2], 'utf8');
(async () => {
  const b = await chromium.launch();
  const all = [];
  for (const scheme of ['light', 'dark']) {
    const p = await b.newPage({ viewport: { width: 1280, height: 900 }, colorScheme: scheme });
    await p.goto('http://127.0.0.1:8598/', { waitUntil: 'networkidle' });
    await p.waitForSelector('h1'); await p.waitForTimeout(1500);
    await p.addScriptTag({ content: AXE });
    const res = await p.evaluate(async () => (await axe.run(document, { runOnly: { type: 'tag', values: ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa'] }, resultTypes: ['violations'] }))
      .violations.map((v) => ({ id: v.id, impact: v.impact, n: v.nodes.length, targets: v.nodes.slice(0, 3).map((n) => n.target.join(' ')), summary: (v.nodes[0] && v.nodes[0].failureSummary || '').slice(0, 220) })));
    all.push({ scheme, res });
    console.log(scheme, JSON.stringify(res));
    await p.close();
  }
  fs.writeFileSync(process.argv[3], JSON.stringify(all, null, 1));
  await b.close();
})();
