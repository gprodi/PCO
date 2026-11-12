/* MicroForge — moteur de l'atelier virtuel (navigateur et Node).
 *
 * Exécute la logique d'un projet transpilée du C++ (microforge.sim.transpile) avec un temps virtuel,
 * et des modèles de comportement pour chaque composant : les capteurs se règlent avec des curseurs ou
 * des boutons, les sorties (LED, servo, écran, anneau, moteurs…) exposent un état à dessiner.
 * C'est une simulation du COMPORTEMENT (logique du projet + composants modélisés) : l'émulation
 * complète du microcontrôleur se fait dans Wokwi (onglet dédié).
 */
(function (root, factory) {
  if (typeof module === "object" && module.exports) module.exports = factory();
  else root.MFSim = factory();
})(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  const STOP = { stop: true };
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
  const clamp = (v, lo, hi) => Math.min(hi, Math.max(lo, v));
  const pad2 = (n) => String(n).padStart(2, "0");

  // ---------------------------------------------------------------- fonctions Arduino
  function ffmt(v, digits) {
    if (Number.isNaN(v)) return "nan";
    if (!Number.isFinite(v)) return v > 0 ? "inf" : "-inf";
    return Number(v).toFixed(Math.max(0, digits | 0));
  }
  function ifmt(v, base) {
    const b = base | 0 || 10;
    if (b === 10) return String(v);
    return (v >>> 0).toString(b).toUpperCase();
  }
  function idiv(a, b, unsigned) {
    if (b === 0) return unsigned ? 0xffffffff : -1; // résultat indéfini en C : valeur stable
    const q = Math.trunc(a / b);
    return unsigned ? q >>> 0 : q | 0;
  }
  function imod(a, b, unsigned) {
    if (b === 0) return 0;
    return unsigned ? (a % b) >>> 0 : (a % b) | 0;
  }
  function amap(x, inMin, inMax, outMin, outMax) {
    if (inMax === inMin) return outMin;
    return (Math.trunc(((x - inMin) * (outMax - outMin)) / (inMax - inMin)) + outMin) | 0;
  }

  // Générateur pseudo-aléatoire reproductible (mulberry32) : random() d'Arduino est aussi déterministe.
  function rng(seed) {
    let a = seed >>> 0;
    return function () {
      a = (a + 0x6d2b79f5) >>> 0;
      let t = a;
      t = Math.imul(t ^ (t >>> 15), t | 1);
      t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  }

  // Adafruit_NeoPixel::ColorHSV (saturation et luminosité maximales)
  function colorHSV(hue) {
    let h = ((hue & 65535) * 1530 + 32768) >> 16;
    let r, g, b;
    if (h < 510) {
      b = 0;
      if (h < 255) { r = 255; g = h; } else { r = 510 - h; g = 255; }
    } else if (h < 1020) {
      r = 0;
      if (h < 765) { g = 255; b = h - 510; } else { g = 1020 - h; b = 255; }
    } else if (h < 1530) {
      g = 0;
      if (h < 1275) { r = h - 1020; b = 255; } else { r = 255; b = 1530 - h; }
    } else { r = 255; g = 0; b = 0; }
    return [r, g, b];
  }

  // ---------------------------------------------------------------- contrôles des capteurs
  const slider = (key, label, min, max, step, value, unit) => ({ type: "slider", key, label, min, max, step, value, unit: unit || "" });
  const button = (key, label) => ({ type: "button", key, label });
  const toggle = (key, label, value) => ({ type: "toggle", key, label, value: !!value });
  const choice = (key, label, options) => ({ type: "choice", key, label, options });

  class Part {
    constructor(sim, def) {
      this.sim = sim;
      this.name = def.name;
      this.component = def.component;
      this.label = def.label || def.name;
      this.attrs = def.attrs || {};
      this.view = "generic";
      this.inputs = [];
      this.v = {}; // valeurs des contrôles
      this.s = {}; // état à dessiner
      this.modeled = true;
      this.plugged = true; // débranché : sorties inertes, capteurs « absents »
      this._edges = {};
      this._absent = {};
    }
    _init(spec) {
      this.view = spec.view;
      this.inputs = spec.inputs || [];
      for (const inp of this.inputs) {
        if (inp.type === "slider" || inp.type === "toggle") this.v[inp.key] = inp.value;
        if (inp.type === "button") this.v[inp.key] = false;
      }
      Object.assign(this.s, spec.state || {});
      this._absent = spec.absent || {};
      for (const [k, fn] of Object.entries(spec.api || {})) {
        this[k] = (...args) => (this.plugged ? fn(...args) : k in this._absent ? this._absent[k] : 0);
      }
      if (spec.onEvent) this._onEvent = spec.onEvent;
    }
    /** Curseur, interrupteur. */
    set(key, value) {
      this.v[key] = value;
      this.sim._touched();
      this.sim._notify(true);
    }
    /** Bouton momentané : appui (front montant mémorisé pour clicked()/tapped()). */
    press(key) {
      if (!this.v[key]) this._edges[key] = true;
      this.v[key] = true;
      this.presses = (this.presses || 0) + 1; // compté pour les missions de l'atelier
      this.sim._touched();
      this.sim._notify(true); // avant que le programme ne réagisse
    }
    release(key) {
      this.v[key] = false;
      this.sim._touched();
    }
    /** Événement ponctuel : touche de clavier, code IR, badge RFID. */
    fire(key, value) {
      if (this._onEvent) this._onEvent(key, value);
      this.fired = (this.fired || 0) + 1;
      this.sim._touched();
      this.sim._notify(true);
    }
    edge(key) {
      const e = !!this._edges[key];
      this._edges[key] = false;
      return e;
    }
    reading() {
      return "";
    }
  }

  const MODELS = {};
  function model(ids, make) {
    for (const id of ids.split(/\s+/)) if (id) MODELS[id] = make;
  }
  const now = (p) => p.sim.now;

  // -- capteurs d'ambiance
  model("dht22 dht11", (p) => ({
    view: "sensor",
    inputs: [slider("temperature", "Température", -10, 50, 0.5, 22, "°C"), slider("humidity", "Humidité", 0, 100, 1, 50, "%")],
    absent: { temperature: NaN, humidity: NaN },
    api: { temperature: () => p.v.temperature, humidity: () => p.v.humidity },
  }));
  model("bme280", (p) => ({
    view: "sensor",
    inputs: [
      slider("temperature", "Température", -10, 50, 0.5, 21, "°C"),
      slider("humidity", "Humidité", 0, 100, 1, 45, "%"),
      slider("pressure", "Pression", 950, 1050, 0.5, 1013.25, "hPa"),
    ],
    api: {
      temperature: () => p.v.temperature,
      humidity: () => p.v.humidity,
      pressure_hpa: () => p.v.pressure,
      altitude_m: () => 44330 * (1 - Math.pow(p.v.pressure / 1013.25, 0.1903)),
    },
    absent: { temperature: NaN, humidity: NaN, pressure_hpa: NaN, altitude_m: NaN },
  }));
  model("bmp280", (p) => ({
    view: "sensor",
    inputs: [slider("temperature", "Température", -10, 50, 0.5, 21, "°C"), slider("pressure", "Pression", 950, 1050, 0.5, 1013.25, "hPa")],
    api: {
      temperature: () => p.v.temperature,
      pressure_hpa: () => p.v.pressure,
      altitude_m: (mer) => 44330 * (1 - Math.pow(p.v.pressure / (mer || 1013.25), 0.1903)),
    },
  }));
  model("ds18b20", (p) => ({
    view: "sensor",
    inputs: [slider("temperature", "Température", -20, 100, 0.5, 21, "°C")],
    absent: { temperature: -127 }, // DEVICE_DISCONNECTED_C de DallasTemperature
    api: { temperature: () => p.v.temperature },
  }));
  model("bh1750", (p) => ({
    view: "sensor",
    inputs: [slider("lux", "Éclairement", 0, 2000, 10, 350, "lx")],
    api: { lux: () => p.v.lux },
  }));
  model("ldr-module", (p) => ({
    view: "sensor",
    inputs: [slider("light", "Lumière", 0, 100, 1, 60, "%")],
    api: { light_percent: () => p.v.light },
  }));
  model("mq2-gas", (p) => ({
    view: "sensor",
    inputs: [slider("level", "Gaz / fumée", 0, 100, 1, 10, "%")],
    api: { level_percent: () => p.v.level },
  }));
  model("mq135-air", (p) => ({
    view: "sensor",
    inputs: [slider("level", "Pollution de l'air", 0, 100, 1, 15, "%")],
    api: {
      raw: () => Math.round((p.v.level / 100) * p.sim.adcMax),
      level_percent: () => p.v.level,
    },
  }));
  model("ina219", (p) => ({
    view: "sensor",
    inputs: [slider("voltage", "Tension", 0, 26, 0.1, 5, "V"), slider("current", "Courant", 0, 3200, 10, 250, "mA")],
    api: {
      voltage_v: () => p.v.voltage,
      current_ma: () => p.v.current,
      power_mw: () => p.v.voltage * p.v.current,
    },
  }));
  model("soil-moisture-capacitive", (p) => ({
    view: "sensor",
    inputs: [slider("moisture", "Humidité du sol", 0, 100, 1, 50, "%")],
    api: {
      percent: () => p.v.moisture,
      raw: () => Math.round((1 - p.v.moisture / 100) * p.sim.adcMax),
    },
  }));
  model("water-level-sensor", (p) => ({
    view: "sensor",
    inputs: [slider("level", "Niveau d'eau", 0, 100, 1, 0, "%")],
    api: { percent: () => p.v.level, wet: () => p.v.level > 10 },
  }));
  model("flame-sensor", (p) => ({
    view: "sensor",
    inputs: [slider("intensity", "Flamme", 0, 100, 1, 0, "%")],
    api: { intensity: () => p.v.intensity, detected: () => p.v.intensity > 50 },
  }));

  // -- distance
  model("hc-sr04", (p) => ({
    view: "sensor",
    inputs: [slider("distance", "Distance (450 = aucun écho)", 2, 450, 1, 50, "cm")],
    absent: { distance_cm: -1 },
    api: { distance_cm: () => (p.v.distance > 400 ? -1 : p.v.distance) },
  }));
  model("vl53l0x", (p) => ({
    view: "sensor",
    inputs: [slider("distance", "Distance (1500 = hors portée)", 30, 1500, 5, 300, "mm")],
    absent: { distance_mm: -1 },
    api: { distance_mm: () => (p.v.distance > 1200 ? -1 : Math.round(p.v.distance)) },
  }));

  // -- présence, contacts
  const motion = (holdMs) => (p) => ({
    view: "sensor",
    inputs: [button("pass", "Passer devant"), toggle("stay", "Présence continue", false)],
    state: { until: 0 },
    api: {
      motion: () => {
        if (p.edge("pass")) p.s.until = now(p) + holdMs;
        return p.v.pass || p.v.stay || now(p) < p.s.until;
      },
    },
  });
  model("pir-hc-sr501", motion(3000));
  model("rcwl-0516", motion(2000));
  model("reed-switch", (p) => ({
    view: "sensor",
    inputs: [toggle("open", "Porte ouverte", false)],
    api: { open: () => !!p.v.open },
  }));
  model("tcrt5000-line", (p) => ({
    view: "sensor",
    inputs: [toggle("line", "Au-dessus de la ligne noire", false)],
    api: { on_line: () => !!p.v.line },
  }));
  model("pushbutton", (p) => ({
    view: "button",
    inputs: [button("pressed", "Appuyer")],
    api: { pressed: () => !!p.v.pressed, clicked: () => p.edge("pressed") },
  }));
  model("ttp223-touch", (p) => ({
    view: "button",
    inputs: [button("touch", "Toucher")],
    api: { touched: () => !!p.v.touch, tapped: () => p.edge("touch") },
  }));
  model("ky038-sound", (p) => ({
    view: "sensor",
    inputs: [slider("level", "Bruit ambiant", 0, 100, 1, 5, "%"), button("clap", "Clap !")],
    state: { until: 0 },
    api: {
      loud: () => {
        if (p.edge("clap")) p.s.until = now(p) + 150;
        return now(p) < p.s.until || p.v.level > 70;
      },
      level: () => (now(p) < p.s.until || p.v.clap ? 100 : p.v.level),
    },
  }));

  // -- commandes manuelles
  model("potentiometer-10k", (p) => ({
    view: "sensor",
    inputs: [slider("position", "Bouton rotatif", 0, 100, 1, 50, "%")],
    api: { percent: () => Math.round(p.v.position), raw: () => Math.round((p.v.position / 100) * p.sim.adcMax) },
  }));
  model("joystick-analog", (p) => ({
    view: "sensor",
    inputs: [slider("x", "Axe X", -100, 100, 1, 0, ""), slider("y", "Axe Y", -100, 100, 1, 0, ""), button("sw", "Appui")],
    api: { x: () => Math.round(p.v.x), y: () => Math.round(p.v.y), pressed: () => !!p.v.sw },
  }));
  model("rotary-encoder-ky040", (p) => ({
    view: "sensor",
    inputs: [choice("turn", "Tourner", [["-1", "↺ un cran"], ["1", "↻ un cran"]]), button("sw", "Appui")],
    state: { pending: 0 },
    onEvent: (key, value) => { p.s.pending += Number(value); },
    api: {
      delta: () => {
        if (!p.s.pending) return 0;
        const d = Math.sign(p.s.pending);
        p.s.pending -= d;
        return d;
      },
      pressed: () => !!p.v.sw,
    },
  }));
  model("keypad-4x4", (p) => ({
    view: "sensor",
    inputs: [choice("key", "Clavier", "123A456B789C*0#D".split("").map((k) => [k, k]))],
    state: { queue: [] },
    onEvent: (key, value) => { p.s.queue.push(String(value).charCodeAt(0)); },
    api: { key: () => (p.s.queue.length ? p.s.queue.shift() : 0) },
  }));
  model("ir-receiver", (p) => ({
    view: "sensor",
    inputs: [choice("code", "Télécommande", [["69", "1"], ["70", "2"], ["71", "3"], ["28", "OK"], ["64", "▶"]])],
    state: { queue: [] },
    onEvent: (key, value) => { p.s.queue.push(Number(value)); },
    api: { command: () => (p.s.queue.length ? p.s.queue.shift() : 0) },
  }));
  model("rc522-rfid", (p) => ({
    view: "sensor",
    inputs: [choice("badge", "Présenter un badge", [["DE AD BE EF", "Badge autorisé"], ["12 34 56 78", "Autre badge"]])],
    state: { queue: [] },
    onEvent: (key, value) => { p.s.queue.push(String(value)); },
    absent: { read_uid: "" },
    api: { read_uid: () => (p.s.queue.length ? p.s.queue.shift() : "") },
  }));
  model("hx711-load-cell", (p) => ({
    view: "sensor",
    inputs: [slider("mass", "Masse posée", 0, 5000, 5, 0, "g")],
    state: { offset: 0 },
    absent: { grams: NaN },
    api: { grams: () => p.v.mass - p.s.offset, tare: () => { p.s.offset = p.v.mass; } },
  }));
  model("mpu6050", (p) => ({
    view: "sensor",
    inputs: [slider("tx", "Inclinaison X", -90, 90, 1, 0, "°"), slider("ty", "Inclinaison Y", -90, 90, 1, 0, "°")],
    api: { tilt_x: () => p.v.tx, tilt_y: () => p.v.ty },
  }));
  model("ds3231-rtc", (p) => ({
    view: "sensor",
    absent: { time: "--:--:--", date: "--/--/----", hour: 0, minute: 0, second: 0, day: 1, month: 1 },
    api: {
      time: () => { const d = p.sim.clock(); return `${pad2(d.getHours())}:${pad2(d.getMinutes())}:${pad2(d.getSeconds())}`; },
      date: () => { const d = p.sim.clock(); return `${pad2(d.getDate())}/${pad2(d.getMonth() + 1)}/${d.getFullYear()}`; },
      hour: () => p.sim.clock().getHours(),
      minute: () => p.sim.clock().getMinutes(),
      second: () => p.sim.clock().getSeconds(),
      day: () => p.sim.clock().getDate(),
      month: () => p.sim.clock().getMonth() + 1,
    },
  }));
  model("shift-register-74hc165", (p) => ({
    view: "sensor",
    inputs: [0, 1, 2, 3, 4, 5, 6, 7].map((i) => toggle(`d${i}`, `D${i}`, false)),
    api: { read: () => [0, 1, 2, 3, 4, 5, 6, 7].reduce((acc, i) => acc | (p.v[`d${i}`] ? 1 << i : 0), 0) },
  }));

  // -- sorties lumineuses et sonores
  model("led", (p) => ({
    view: "led",
    state: { on: false, color: p.attrs.color || "red" },
    api: {
      on: () => { p.s.on = true; },
      off: () => { p.s.on = false; },
      set: (v) => { p.s.on = !!v; },
      toggle: () => { p.s.on = !p.s.on; },
    },
  }));
  model("rgb-led", (p) => ({
    view: "rgb",
    state: { rgb: [0, 0, 0] },
    api: { color: (r, g, b) => { p.s.rgb = [r & 255, g & 255, b & 255]; } },
  }));
  model("buzzer", (p) => ({
    view: "buzzer",
    state: { freq: 0, until: 0 },
    api: {
      beep: (freq, ms) => {
        p.s.freq = freq;
        p.s.until = now(p) + ms;
        p.sim.sounds.push({ part: p.name, freq, ms, at: now(p) });
      },
      stop: () => { p.s.until = 0; },
    },
  }));
  model("vibration-motor", (p) => ({
    view: "vibe",
    state: { until: 0 },
    // buzz() est bloquant sur la carte (delay(ms) dans le composant) : le temps virtuel avance aussi.
    api: { buzz: (ms) => { p.s.until = now(p) + ms; p.s.count = (p.s.count || 0) + 1; p.sim.advance(ms); } },
  }));
  model("ws2812-ring-12", (p) => {
    const n = Number(p.attrs.pixels || 12);
    const set = (fn) => { p.s.pixels = Array.from({ length: n }, (_, i) => fn(i)); };
    return {
      view: "ring",
      state: { pixels: Array.from({ length: n }, () => [0, 0, 0]) },
      api: {
        fill: (r, g, b) => set(() => [r & 255, g & 255, b & 255]),
        gauge: (percent) => {
          const k = amap(clamp(percent, 0, 100), 0, 100, 0, n);
          set((i) => { const r = amap(i, 0, n - 1, 0, 255) & 255; return i < k ? [r, 255 - r, 0] : [0, 0, 0]; });
        },
        wheel: (pos) => set((i) => colorHSV(((pos & 255) * 256 + Math.trunc((i * 65536) / n)) & 65535)),
        pixel: (i, r, g, b) => {
          const k = (((i | 0) % n) + n) % n;
          p.s.pixels = p.s.pixels.map((px, j) => (j === k ? [r & 255, g & 255, b & 255] : px));
        },
      },
    };
  });
  model("max7219-matrix", (p) => ({
    view: "matrix",
    state: { rows: [0, 0, 0, 0, 0, 0, 0, 0] },
    api: {
      write: (reg, data) => { if (reg >= 1 && reg <= 8) p.s.rows[reg - 1] = data & 255; },
      show: (img) => { p.s.rows = Array.from({ length: 8 }, (_, r) => (img[r] || 0) & 255); },
      clear: () => { p.s.rows = [0, 0, 0, 0, 0, 0, 0, 0]; },
      bars: (k) => { let v = 0; for (let c = 0; c < 8 && c < k; c++) v |= 0x80 >> c; p.s.rows = new Array(8).fill(v); },
    },
  }));
  model("shift-register-74hc595", (p) => ({
    view: "leds8",
    state: { bits: 0 },
    api: { write: (bits) => { p.s.bits = bits & 255; } },
  }));

  // -- écrans
  model("ssd1306-i2c", (p) => ({
    view: "oled",
    state: { lines: ["", "", ""], big: false },
    api: { print: (l1, l2, l3, big) => { p.s.lines = [String(l1 ?? ""), String(l2 ?? ""), String(l3 ?? "")]; p.s.big = !!big; } },
  }));
  model("lcd1602-i2c", (p) => ({
    view: "lcd",
    state: { lines: ["", ""] },
    api: { print: (l1, l2) => { p.s.lines = [String(l1 ?? "").slice(0, 16), String(l2 ?? "").slice(0, 16)]; } },
  }));
  model("tm1637-display", (p) => ({
    view: "seg7",
    state: { text: "", colon: false },
    api: {
      number: (k) => { p.s.text = String(k | 0).slice(-4).padStart(4, " "); p.s.colon = false; },
      time: (hh, mm) => { p.s.text = pad2(clamp(hh | 0, 0, 99)) + pad2(clamp(mm | 0, 0, 99)); p.s.colon = true; },
    },
  }));

  // -- puissance et mouvement
  model("sg90-servo", (p) => ({
    view: "servo",
    state: { angle: 0 },
    api: { angle: (deg) => { p.s.angle = clamp(deg | 0, 0, 180); } },
  }));
  model("relay-module-1ch", (p) => ({
    view: "relay",
    state: { on: false },
    api: { on: () => { p.s.on = true; }, off: () => { p.s.on = false; } },
  }));
  model("l298n-driver tb6612fng-driver", (p) => ({
    view: "driver",
    state: { left: 0, right: 0, standby: false },
    api: {
      motors: (g, d) => { p.s.left = clamp(g | 0, -255, 255); p.s.right = clamp(d | 0, -255, 255); },
      stop: () => { p.s.left = 0; p.s.right = 0; },
      standby: (v) => { p.s.standby = !!v; },
    },
  }));
  model("darlington-tip120 mosfet-irlz44n mosfet-irf520 npn-2n2222 npn-bc547 mosfet-2n7000", (p) => ({
    view: "switch",
    state: { level: 0 },
    api: {
      on: () => { p.s.level = 255; },
      off: () => { p.s.level = 0; },
      set: (lvl) => { p.s.level = lvl & 255; },
    },
  }));
  model("mosfet-module", (p) => ({
    view: "switch",
    state: { level: 0 },
    api: { power: (pct) => { p.s.level = amap(clamp(pct, 0, 100), 0, 100, 0, 255); }, off: () => { p.s.level = 0; } },
  }));
  model("stepper-28byj48", (p) => ({
    view: "stepper",
    state: { position: 0 },
    api: {
      // step() est bloquant : ~2,9 ms par pas (2048 pas = un tour en 6 s environ)
      steps: (k) => { p.s.position += k | 0; p.sim.advance(Math.abs(k | 0) * 2.93); },
      degrees: (deg) => { const k = Math.trunc((deg * 2048) / 360); p.s.position += k; p.sim.advance(Math.abs(k) * 2.93); },
    },
  }));
  model("microsd-module", (p) => ({
    view: "sd",
    state: { files: {} },
    absent: { append: false },
    api: {
      append: (path, line) => {
        p.s.files[path] = (p.s.files[path] || "") + String(line) + "\n";
        return true;
      },
    },
  }));
  // Pièces passives : leur état vient du pilote (moteurs, ventilateur, pompe) ou n'a pas à être montré.
  model("battery-holder-4aa diode-1n4007 diode-1n4148 diode-1n5819 dc-motor-tt fan-12v water-pump-5v", (p) => ({
    view: ["dc-motor-tt", "fan-12v", "water-pump-5v"].includes(p.component) ? "load" : "passive",
    state: { speed: 0 },
  }));

  function genericModel(p) {
    // Composant sans modèle : les appels sont acceptés et affichés, les lectures valent 0.
    p.modeled = false;
    return {
      view: "generic",
      state: { last: "" },
    };
  }

  const DRIVER_VIEWS = new Set(["driver", "switch", "relay"]);

  // ---------------------------------------------------------------- simulation
  class Simulation {
    constructor(opts) {
      this.title = opts.title || "";
      this.adcMax = opts.adcMax || 1023;
      this.startDate = opts.startDate ? new Date(opts.startDate) : new Date();
      this.now = 0;
      this.serial = "";
      this.serialTotal = 0; // caractères écrits depuis le début (le tampon, lui, est tronqué)
      this.sounds = [];
      this._observers = [];
      this.events = [];
      this.speed = 1;
      this.realtime = false;
      this.paused = false;
      this.stopped = false;
      this.error = null;
      this.running = false;
      this._spins = 0;
      this._debt = 0;
      this._random = rng(1);
      this.web = { handlers: {}, page: null, requests: 0, queue: [], total: 0 };
      this.parts = {};
      for (const def of opts.parts) {
        const p = new Part(this, def);
        p.plugged = opts.plugged !== false;
        const make = MODELS[def.component] || genericModel;
        p._init(make(p));
        this.parts[def.name] = p.modeled ? p : this._proxy(p);
      }
      const rt = this._runtime();
      // eslint-disable-next-line no-new-func
      this.program = new Function("__rt", opts.code)(rt);
    }

    _proxy(p) {
      return new Proxy(p, {
        get(target, prop) {
          if (prop in target || typeof prop !== "string") return target[prop];
          return (...args) => { target.s.last = `${prop}(${args.join(", ")})`; return 0; };
        },
      });
    }

    _runtime() {
      const sim = this;
      class WebServer {
        constructor(port) { this.port = port; }
        on(path, handler) { sim.web.handlers[path] = handler; }
        begin() {}
        send(code, type, body) { sim.web.page = { code, type, body: String(body) }; }
        async handleClient() {
          if (sim.web.requests > 0) {
            sim.web.requests -= 1;
            const path = sim.web.queue.shift() || "/";
            const h = sim.web.handlers[path] || sim.web.handlers["/"];
            if (h) await h();
          }
        }
      }
      return {
        parts: this.parts,
        __delay: (ms) => this._delay(ms),
        __spin: () => this._spin(),
        __ffmt: ffmt,
        __ifmt: ifmt,
        __idiv: idiv,
        __imod: imod,
        __map: amap,
        __constrain: (v, lo, hi) => (v < lo ? lo : v > hi ? hi : v),
        __random: (a, b) => {
          const [lo, hi] = b === undefined ? [0, a] : [a, b];
          if (hi <= lo) return lo;
          return lo + Math.floor(this._random() * (hi - lo));
        },
        __randomSeed: (seed) => { this._random = rng(seed || 1); },
        __isinf: (v) => v === Infinity || v === -Infinity,
        __toInt: (s) => parseInt(s, 10) || 0,
        __timeHHMM: () => { const d = this.clock(); return `${pad2(d.getHours())}:${pad2(d.getMinutes())}`; },
        millis: () => Math.floor(this.now) >>> 0,
        micros: () => Math.floor(this.now * 1000) >>> 0,
        Serial: {
          print: (s) => this._serial(String(s)),
          println: (s) => this._serial(String(s) + "\n"),
        },
        WiFi: { status: () => 3, localIP: () => "192.168.1.42" },
        WebServer,
      };
    }

    clock() {
      return new Date(this.startDate.getTime() + this.now);
    }

    _serial(text) {
      this.serial += text;
      this.serialTotal += text.length;
      if (this.serial.length > 20000) this.serial = this.serial.slice(-15000);
    }

    _touched() {
      this.version = (this.version || 0) + 1;
    }

    /** Planifie une action au temps virtuel ``ms`` (scénarios de test, démonstrations). */
    at(ms, fn) {
      this.events.push({ ms, fn });
      this.events.sort((a, b) => a.ms - b.ms);
    }

    /** Appelle ``fn(sim)`` au plus toutes les ``everyMs`` ms virtuelles (missions de l'atelier). */
    observe(fn, everyMs = 10) {
      const o = { fn, everyMs, last: -Infinity };
      this._observers.push(o);
      return () => { this._observers = this._observers.filter((x) => x !== o); };
    }

    /** ``force`` : action de l'utilisateur, à signaler avant que le programme n'y réagisse. */
    _notify(force) {
      for (const o of this._observers) {
        if (force || this.now - o.last >= o.everyMs) {
          o.last = this.now;
          o.fn(this);
        }
      }
    }

    /** Temps consommé par une opération bloquante (moteur pas à pas…). */
    advance(ms) {
      this.now += ms;
    }

    async _delay(ms) {
      await this._wait(Math.max(0, Number(ms) || 0));
    }

    async _spin() {
      await this._wait(0.02, (++this._spins & 255) === 0);
    }

    async _wait(ms, forceYield) {
      if (this.stopped || this.now >= this.stopAt) throw STOP;
      if (this.now + ms > this.stopAt) ms = this.stopAt - this.now;
      // Fin de l'attente fixée au départ : les évènements qui tombent pendant l'attente sont
      // appliqués à leur heure, sans la prolonger (avant : chaque évènement repoussait la fin).
      const end = this.now + ms;
      while (this.events.length && this.events[0].ms <= end) {
        const ev = this.events.shift();
        this.now = Math.max(this.now, ev.ms);
        ev.fn(this);
        if (this._observers.length) this._notify();
      }
      this.now = end;
      if (this._observers.length) this._notify();
      if (this.realtime) {
        this._debt += ms / this.speed;
        while (this.paused && !this.stopped) await sleep(50);
        if (this._debt >= 8) {
          const d = this._debt;
          this._debt = 0;
          await sleep(d);
        } else if (forceYield || ms > 0) {
          await sleep(0);
        }
      } else if (forceYield) {
        await null;
      }
      if (this.stopped) throw STOP;
    }

    /** Exécute setup() puis loop() en boucle jusqu'au temps virtuel ``until`` (ms). */
    async run({ until = Infinity, realtime = false, speed = 1 } = {}) {
      this.stopAt = until;
      this.realtime = realtime;
      this.speed = speed;
      this.running = true;
      try {
        await this.program.setup();
        for (;;) {
          await this.program.loop();
          await this._spin();
        }
      } catch (e) {
        if (e !== STOP) {
          this.error = e;
          throw e;
        }
      } finally {
        this.running = false;
      }
      return this.snapshot();
    }

    stop() {
      this.stopped = true;
      this.paused = false;
    }

    /** Ouvre la page web du projet (station météo Wi-Fi…) : le prochain handleClient() y répond. */
    request(path = "/") {
      this.web.queue.push(path);
      this.web.requests += 1;
      this.web.total += 1;
      this._notify(true);
    }

    /** Charges (moteurs, ventilateur, pompe) alimentées par un pilote, un transistor ou un relais. */
    loads() {
      const parts = Object.values(this.parts);
      const driver = parts.find((p) => DRIVER_VIEWS.has(p.view));
      const out = {};
      let motorIndex = 0;
      for (const p of parts) {
        if (p.view !== "load") continue;
        let speed = 0;
        if (!driver || !driver.plugged || !p.plugged) {
          out[p.name] = 0;
          if (driver && driver.view === "driver") motorIndex++;
          continue;
        }
        if (driver && driver.view === "driver") {
          speed = driver.s.standby ? 0 : motorIndex++ === 0 ? driver.s.left : driver.s.right;
        } else if (driver && driver.view === "switch") {
          speed = driver.s.level;
        } else if (driver && driver.view === "relay") {
          speed = driver.s.on ? 255 : 0;
        }
        out[p.name] = speed;
      }
      return out;
    }

    snapshot() {
      const parts = {};
      for (const [name, p] of Object.entries(this.parts)) {
        parts[name] = { view: p.view, component: p.component, modeled: p.modeled, plugged: p.plugged, state: JSON.parse(JSON.stringify(p.s)), inputs: { ...p.v } };
      }
      return { now: this.now, serial: this.serial, parts, loads: this.loads(), web: this.web.page, error: this.error ? String(this.error) : null };
    }
  }

  return { Simulation, MODELS, colorHSV, map: amap, ffmt, version: "1.0" };
});
