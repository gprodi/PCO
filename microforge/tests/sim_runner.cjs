// Exécute une simulation MicroForge dans Node : node sim_runner.cjs <mfsim.js> <payload.json> <scénario.json>
// scénario : { until, events: [[ms, part, action, key, value], ...] } ; affiche l'instantané final en JSON.
const fs = require("fs");
const { Simulation } = require(process.argv[2]);
const payload = JSON.parse(fs.readFileSync(process.argv[3], "utf8"));
const scenario = JSON.parse(fs.readFileSync(process.argv[4], "utf8"));
const sim = new Simulation({ ...payload, startDate: "2026-11-03T08:00:00" });
const marks = {};
for (const [ms, part, action, key, value] of scenario.events || []) {
  sim.at(ms, (s) => {
    if (action === "mark") { marks[key] = s.snapshot(); return; }
    const p = s.parts[part];
    if (action === "set") p.set(key, value);
    else if (action === "press") p.press(key);
    else if (action === "release") p.release(key);
    else if (action === "fire") p.fire(key, value);
    else if (action === "request") s.request();
  });
}
sim.run({ until: scenario.until || 60000 }).then(
  (snap) => { process.stdout.write(JSON.stringify({ ...snap, marks, sounds: sim.sounds.length })); },
  (err) => { process.stderr.write(String(err && err.stack || err)); process.exit(1); },
);
