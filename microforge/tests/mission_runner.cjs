// Vérifie les missions d'un projet dans Node :
//   node mission_runner.cjs <mfsim.js> <missions.js> <payload.json> <scénario.json>
// scénario : { until, events: [[ms, part, action, key, value]], armer: [[ms, id]], branche, aide }
// Affiche { reussies: [id…], instants: {id: ms}, erreur }.
const fs = require("fs");
const { Simulation } = require(process.argv[2]);
const { Suivi } = require(process.argv[3]);
const payload = JSON.parse(fs.readFileSync(process.argv[4], "utf8"));
const scenario = JSON.parse(fs.readFileSync(process.argv[5], "utf8"));
const sim = new Simulation({ ...payload, startDate: scenario.startDate || "2026-11-03T08:00:00" });
const instants = {};
const suivi = new Suivi(payload.missions || [], {
  faites: scenario.faites || [],
  contexte: () => ({ branche: scenario.branche !== false, aide: !!scenario.aide }),
  onReussite: (m) => { instants[m.id] = Math.round(sim.now); },
});
suivi.attacher(sim);
for (const [ms, part, action, key, value] of scenario.events || []) {
  sim.at(ms, (s) => {
    const p = s.parts[part];
    if (action === "set") p.set(key, value);
    else if (action === "press") p.press(key);
    else if (action === "release") p.release(key);
    else if (action === "fire") p.fire(key, value);
    else if (action === "request") s.request(key || "/");
  });
}
for (const [ms, id] of scenario.armer || []) sim.at(ms, () => suivi.armer(id));
sim.run({ until: scenario.until || 10000 }).then(
  () => process.stdout.write(JSON.stringify({ reussies: suivi.reussies(), instants, erreur: null })),
  (err) => process.stdout.write(JSON.stringify({ reussies: suivi.reussies(), instants, erreur: String(err && err.stack || err) })),
);
