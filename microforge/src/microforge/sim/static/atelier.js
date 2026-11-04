/* MicroForge — atelier virtuel : brancher les composants, puis voir le projet fonctionner.
 *
 * MFAtelier.mount(element, payload, options) affiche une carte par composant (dessin Wokwi si la
 * bibliothèque @wokwi/elements est chargée, sinon un dessin simple), ses réglages (curseurs, boutons),
 * le mode « Je branche » (chaque broche choisie est vérifiée et expliquée), le moniteur série et les
 * commandes de la simulation (lecture, pause, ×1 / ×10 / ×60, réinitialisation).
 * Dépend de MFSim (mfsim.js). Aucune donnée n'est envoyée nulle part.
 */
(function (root, factory) {
  if (typeof module === "object" && module.exports) module.exports = factory(require("./mfsim.js"));
  else root.MFAtelier = factory(root.MFSim);
})(typeof self !== "undefined" ? self : this, function (MFSim) {
  "use strict";

  const ROLE_LABELS = {
    power: "alimentation", ground: "masse", gpio_in: "entrée", gpio_out: "sortie", gpio_io: "données",
    pwm: "PWM", adc: "analogique", i2c_sda: "I2C SDA", i2c_scl: "I2C SCL", spi_mosi: "SPI MOSI",
    spi_miso: "SPI MISO", spi_sck: "SPI SCK", spi_cs: "SPI CS", uart_tx: "UART TX", uart_rx: "UART RX",
  };
  const OUTPUT_ROLES = new Set(["gpio_out", "gpio_io", "pwm", "i2c_sda", "i2c_scl", "spi_mosi", "spi_sck", "spi_cs", "uart_rx"]);
  const SEGMENTS = { "0": "1111110", "1": "0110000", "2": "1101101", "3": "1111001", "4": "0110011", "5": "1011011", "6": "1011111", "7": "1110000", "8": "1111111", "9": "1111011", "-": "0000001", " ": "0000000" };

  function h(tag, attrs, ...children) {
    const node = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs || {})) {
      if (v === null || v === undefined || v === false) continue;
      if (k === "class") node.className = v;
      else if (k === "text") node.textContent = v;
      else if (k.startsWith("on")) node.addEventListener(k.slice(2), v);
      else if (k in node && typeof v !== "string") node[k] = v;
      else node.setAttribute(k, v === true ? "" : v);
    }
    for (const c of children.flat()) if (c !== null && c !== undefined && c !== false) node.append(c.nodeType ? c : String(c));
    return node;
  }
  const fmtTime = (ms) => {
    const s = Math.floor(ms / 1000);
    return `${String(Math.floor(s / 60)).padStart(2, "0")}:${String(s % 60).padStart(2, "0")}.${Math.floor((ms % 1000) / 100)}`;
  };
  const hasWokwi = () => typeof customElements !== "undefined" && !!customElements.get("wokwi-led");

  // ------------------------------------------------------------------ vérification d'un branchement
  function checkPin(pin, chosen, board, taken, supply) {
    if (!chosen) return { ok: false, msg: "" };
    const info = board.labels.find((l) => l.label === chosen) || {};
    const expected = board.labels.find((l) => l.label === pin.expected) || {};
    if (chosen === pin.expected) {
      return { ok: true, msg: ["Correct", pin.via ? ` — ${pin.via}` : "", pin.note ? ` (${pin.note})` : "", "."].join("") };
    }
    if (pin.role === "power") {
      if (info.kind === "ground") return { ok: false, msg: "Court-circuit : l'alimentation irait directement à la masse." };
      if (info.kind !== "power") return { ok: false, msg: `Une broche GPIO ne fournit que quelques mA : l'alimentation se prend sur ${pin.expected}.` };
      const [lo, hi] = supply || [0, 99];
      if (info.volts > hi + 0.05) return { ok: false, msg: `${chosen} = ${info.volts} V : trop, ce composant accepte ${lo} à ${hi} V. Il serait détruit.` };
      if (info.volts < lo - 0.05) return { ok: false, msg: `${chosen} = ${info.volts} V : pas assez, ce composant demande au moins ${lo} V.` };
      if (info.volts > board.logicV + 0.3) {
        return { ok: false, msg: `Le composant fonctionnerait en ${info.volts} V, mais ses signaux seraient à ${info.volts} V : trop pour les entrées ${board.logicV} V de la carte. Alimente-le sur ${pin.expected} (${expected.volts} V).` };
      }
      return { ok: false, msg: `Possible, mais le montage (niveaux, résistances) a été calculé avec ${pin.expected} : branche-le là.` };
    }
    if (pin.role === "ground") return { ok: false, msg: "La masse du composant se relie à GND." };
    if (info.kind !== "gpio") return { ok: false, msg: `${chosen} est une alimentation : le signal ${pin.pin} va sur une broche GPIO (${pin.expected}).` };
    if (info.reserved) return { ok: false, msg: `${chosen} est réservée${info.note ? ` (${info.note})` : ""} : choisis-en une autre.` };
    if (OUTPUT_ROLES.has(pin.role) && info.inputOnly) return { ok: false, msg: `${chosen} est en entrée seule : elle ne peut pas piloter ${pin.pin}.` };
    const caps = info.caps || [];
    if (pin.role === "adc" && !caps.includes("adc")) return { ok: false, msg: `${chosen} n'a pas d'entrée analogique : il faut une broche ADC.` };
    if (pin.role === "pwm" && !caps.includes("pwm")) return { ok: false, msg: `${chosen} ne sait pas produire de PWM.` };
    if (pin.role.startsWith("i2c_")) return { ok: false, msg: `Le bus I2C par défaut de la carte est sur ${pin.expected} (Wire.begin() sans argument).` };
    if (pin.role.startsWith("spi_") && pin.role !== "spi_cs") return { ok: false, msg: `Le bus SPI matériel de la carte utilise ${pin.expected} pour ${pin.pin}.` };
    const other = taken[chosen];
    if (other) return { ok: false, msg: `${chosen} est déjà utilisée par ${other}.` };
    const strap = info.strapping ? " Attention : broche de démarrage (strapping)." : "";
    return { ok: false, msg: `Possible électriquement, mais le code a été généré pour ${pin.expected} : branche ${pin.pin} sur ${pin.expected}.${strap}` };
  }

  // ------------------------------------------------------------------ dessins
  function fallbackChip(part) {
    return h("div", { class: "mfa-chip", "aria-hidden": "true" }, h("span", { text: part.component.replace(/-/g, " ") }), h("i"));
  }

  function wokwiOr(part, type, fallback) {
    if (hasWokwi() && type && customElements.get(type)) {
      const node = document.createElement(type);
      for (const [k, v] of Object.entries(part.wokwiAttrs || {})) node.setAttribute(k, v);
      return node;
    }
    return fallback();
  }

  function oledImage(lines, big) {
    const c = document.createElement("canvas");
    c.width = 128;
    c.height = 64;
    const ctx = c.getContext("2d");
    ctx.fillStyle = "#000";
    ctx.fillRect(0, 0, 128, 64);
    ctx.fillStyle = "#fff";
    ctx.textBaseline = "top";
    if (big) {
      ctx.font = "bold 22px monospace";
      ctx.fillText(lines[0] || "", 2, 4, 124);
      ctx.font = "10px monospace";
      ctx.fillText(lines[1] || "", 2, 34, 124);
      ctx.fillText(lines[2] || "", 2, 48, 124);
    } else {
      ctx.font = "11px monospace";
      lines.forEach((l, i) => ctx.fillText(l || "", 2, 4 + i * 20, 124));
    }
    const img = ctx.getImageData(0, 0, 128, 64);
    for (let i = 0; i < img.data.length; i += 4) {
      const on = img.data[i] > 100 ? 255 : 0; // pixels nets, comme un vrai OLED
      img.data[i] = img.data[i + 1] = img.data[i + 2] = on;
      img.data[i + 3] = 255;
    }
    return img;
  }

  function wheel(color) {
    return h("div", { class: "mfa-wheel", style: `--c:${color}` }, h("i"), h("i"), h("i"));
  }

  /** Construit le dessin d'un composant ; renvoie {node, update(part, sim)}. */
  function makeVisual(def, view, extra) {
    const wrap = h("div", { class: `mfa-visual mfa-v-${view}` });
    const read = h("p", { class: "mfa-read", "aria-live": "off" });
    let update = () => {};
    const add = (n) => { wrap.append(n); return n; };

    if (view === "led") {
      const color = (def.attrs && def.attrs.color) || "red";
      const node = add(wokwiOr(def, "wokwi-led", () => h("div", { class: "mfa-led", style: `--c:${color}` })));
      node.setAttribute("color", color);
      update = (p) => {
        const on = p.plugged && p.s.on;
        if (node.tagName === "WOKWI-LED") node.value = on; else node.classList.toggle("on", on);
        read.textContent = on ? "allumée" : "éteinte";
      };
    } else if (view === "rgb") {
      const node = add(wokwi(def, "wokwi-rgb-led", () => h("div", { class: "mfa-led" })));
      update = (p) => {
        const [r, g, b] = p.plugged ? p.s.rgb : [0, 0, 0];
        if (node.tagName === "WOKWI-RGB-LED") { node.ledRed = r / 255; node.ledGreen = g / 255; node.ledBlue = b / 255; } else { node.style.setProperty("--c", `rgb(${r},${g},${b})`); node.classList.toggle("on", r + g + b > 0); }
        read.textContent = r + g + b ? `R ${r} · V ${g} · B ${b}` : "éteinte";
      };
    } else if (view === "buzzer") {
      const node = add(wokwiOr(def, "wokwi-buzzer", () => h("div", { class: "mfa-buzz", text: "♪" })));
      update = (p, sim) => {
        const on = p.plugged && sim.now < p.s.until;
        if (node.tagName === "WOKWI-BUZZER") node.hasSignal = on; else node.classList.toggle("on", on);
        read.textContent = on ? `bip ${p.s.freq} Hz` : "silencieux";
      };
    } else if (view === "vibe") {
      const node = add(h("div", { class: "mfa-vibe", text: "≋" }));
      update = (p, sim) => { const on = p.plugged && sim.now < p.s.until; node.classList.toggle("on", on); read.textContent = on ? "vibre" : "au repos"; };
    } else if (view === "servo") {
      const node = add(wokwiOr(def, "wokwi-servo", () => h("div", { class: "mfa-dial" }, h("i"))));
      update = (p) => {
        if (node.tagName === "WOKWI-SERVO") node.angle = p.s.angle; else node.style.setProperty("--a", `${p.s.angle - 90}deg`);
        read.textContent = `${p.s.angle}°`;
      };
    } else if (view === "ring") {
      const node = add(wokwiOr(def, "wokwi-led-ring", () => h("div", { class: "mfa-ring" }, ...Array.from({ length: 12 }, () => h("i")))));
      let last = "";
      update = (p) => {
        const px = p.plugged ? p.s.pixels : p.s.pixels.map(() => [0, 0, 0]);
        const key = JSON.stringify(px);
        if (key !== last) {
          last = key;
          if (node.tagName === "WOKWI-LED-RING") px.forEach(([r, g, b], i) => node.setPixel(i, { r: r / 255, g: g / 255, b: b / 255 }));
          else [...node.children].forEach((d, i) => { const [r, g, b] = px[i] || [0, 0, 0]; d.style.background = r + g + b ? `rgb(${r},${g},${b})` : ""; });
        }
        read.textContent = `${px.filter((c) => c[0] + c[1] + c[2] > 0).length} LED allumées sur ${px.length}`;
      };
    } else if (view === "matrix") {
      const node = add(h("div", { class: "mfa-matrix" }, ...Array.from({ length: 64 }, () => h("i"))));
      update = (p) => {
        const rows = p.plugged ? p.s.rows : new Array(8).fill(0);
        [...node.children].forEach((d, i) => d.classList.toggle("on", !!(rows[i >> 3] & (0x80 >> (i & 7)))));
        read.textContent = "matrice 8 × 8";
      };
    } else if (view === "leds8") {
      const leds = Array.from({ length: 8 }, (_, i) => h("span", { class: "mfa-q" }, h("i", { class: "mfa-led small", style: "--c:red" }), `Q${i}`));
      add(h("div", { class: "mfa-row8" }, ...leds));
      const ledNote = extra.find((e) => e.component === "led");
      update = (p) => {
        const bits = p.plugged ? p.s.bits : 0;
        leds.forEach((l, i) => l.firstChild.classList.toggle("on", !!(bits & (1 << i))));
        read.textContent = `sorties ${bits.toString(2).padStart(8, "0")}${ledNote ? ` · ${ledNote.quantity} LED sur Q0–Q7` : ""}`;
      };
    } else if (view === "oled") {
      const node = add(wokwiOr(def, "wokwi-ssd1306", () => h("pre", { class: "mfa-oled" })));
      let last = "";
      update = (p) => {
        const lines = p.plugged ? p.s.lines : ["", "", ""];
        const key = JSON.stringify([lines, p.s.big]);
        if (key === last) return;
        last = key;
        if (node.tagName === "WOKWI-SSD1306") { node.imageData = oledImage(lines, p.s.big); node.redraw(); } else { node.textContent = lines.join("\n"); node.classList.toggle("big", p.s.big); }
        read.textContent = lines.filter(Boolean).join(" · ") || "écran noir";
      };
    } else if (view === "lcd") {
      const node = add(wokwiOr(def, "wokwi-lcd1602", () => h("pre", { class: "mfa-lcd" })));
      if (node.tagName === "WOKWI-LCD1602") node.setAttribute("pins", "i2c");
      update = (p) => {
        const lines = p.plugged ? p.s.lines : ["", ""];
        const text = lines.map((l) => (l || "").padEnd(16).slice(0, 16)).join("");
        if (node.tagName === "WOKWI-LCD1602") node.characters = Uint8Array.from(text, (ch) => (ch.charCodeAt(0) < 128 ? ch.charCodeAt(0) : 63));
        else node.textContent = lines.join("\n");
        read.textContent = lines.filter((l) => l.trim()).join(" · ") || "écran vide";
      };
    } else if (view === "seg7") {
      const node = add(wokwiOr(def, "wokwi-7segment", () => h("div", { class: "mfa-seg" })));
      if (node.tagName === "WOKWI-7SEGMENT") { node.digits = 4; node.colon = true; }
      update = (p) => {
        const text = p.plugged ? p.s.text.padStart(4, " ").slice(-4) : "    ";
        if (node.tagName === "WOKWI-7SEGMENT") {
          node.values = [...text].flatMap((ch) => [...(SEGMENTS[ch] || "0000000")].map(Number).concat([0]));
          node.colonValue = p.plugged && p.s.colon;
        } else node.textContent = p.s.colon ? `${text.slice(0, 2)}:${text.slice(2)}` : text;
        read.textContent = text.trim() ? (p.s.colon ? `${text.slice(0, 2)}:${text.slice(2)}` : text.trim()) : "éteint";
      };
    } else if (view === "relay") {
      const bulb = add(h("div", { class: "mfa-bulb" }, h("i")));
      update = (p) => { const on = p.plugged && p.s.on; bulb.classList.toggle("on", on); read.textContent = on ? "relais fermé : charge alimentée" : "relais ouvert"; };
    } else if (view === "driver") {
      const left = wheel("var(--mfa-accent)");
      const right = wheel("var(--mfa-accent)");
      add(h("div", { class: "mfa-wheels" }, left, right));
      update = (p) => {
        const g = p.plugged && !p.s.standby ? p.s.left : 0;
        const d = p.plugged && !p.s.standby ? p.s.right : 0;
        for (const [w, v] of [[left, g], [right, d]]) {
          w.style.setProperty("--spd", v ? `${(2.4 - (Math.abs(v) / 255) * 2).toFixed(2)}s` : "0s");
          w.style.setProperty("--dir", v < 0 ? "reverse" : "normal");
          w.classList.toggle("on", v !== 0);
        }
        read.textContent = `gauche ${g > 0 ? "+" : ""}${g} · droite ${d > 0 ? "+" : ""}${d}`;
      };
    } else if (view === "switch") {
      const bar = h("i");
      add(h("div", { class: "mfa-bar" }, bar));
      update = (p) => { const lvl = p.plugged ? p.s.level : 0; bar.style.width = `${(lvl / 255) * 100}%`; read.textContent = lvl ? `conduit : ${Math.round((lvl / 255) * 100)} % (PWM ${lvl}/255)` : "bloqué"; };
    } else if (view === "load") {
      const fan = add(h("div", { class: `mfa-fan mfa-${def.component}` }, h("i"), h("i"), h("i")));
      update = (p, sim, loads) => {
        const v = loads[p.name] || 0;
        fan.style.setProperty("--spd", v ? `${(2.4 - (Math.abs(v) / 255) * 2).toFixed(2)}s` : "0s");
        fan.style.setProperty("--dir", v < 0 ? "reverse" : "normal");
        fan.classList.toggle("on", v !== 0);
        read.textContent = v ? `tourne : ${Math.round((Math.abs(v) / 255) * 100)} %${v < 0 ? " (marche arrière)" : ""}` : "à l'arrêt";
      };
    } else if (view === "stepper") {
      const node = add(wokwiOr(def, "wokwi-stepper-motor", () => h("div", { class: "mfa-dial" }, h("i"))));
      update = (p) => {
        const angle = (((p.s.position % 2048) + 2048) % 2048) * (360 / 2048);
        if (node.tagName === "WOKWI-STEPPER-MOTOR") node.angle = angle; else node.style.setProperty("--a", `${angle}deg`);
        read.textContent = `position ${p.s.position} pas (${Math.round(angle)}°)`;
      };
    } else if (view === "sd") {
      const pre = add(h("pre", { class: "mfa-file" }));
      update = (p) => {
        const files = Object.entries(p.s.files);
        const [name, content] = files[0] || ["", ""];
        pre.textContent = content ? `${name}\n${content.trim().split("\n").slice(-4).join("\n")}` : "carte vide";
        read.textContent = content ? `${content.trim().split("\n").length} lignes écrites` : "";
      };
    } else if (view === "button") {
      const node = add(wokwiOr(def, def.wokwi || "wokwi-pushbutton", fallbackChip.bind(null, def)));
      update = (p) => { if ("pressed" in node) node.pressed = !!(p.v.pressed || p.v.touch); read.textContent = p.v.pressed || p.v.touch ? "appuyé" : "relâché"; };
    } else {
      const node = add(wokwiOr(def, def.wokwi, fallbackChip.bind(null, def)));
      update = (p) => { read.textContent = p.modeled ? "" : `non modélisé${p.s.last ? ` : ${p.s.last}` : ""}`; };
      wrap.dataset.wokwi = node.tagName.toLowerCase();
    }
    function wokwi(d, type, fb) { return wokwiOr(d, type, fb); }
    return { node: h("div", { class: "mfa-visual-box" }, wrap, read), update };
  }

  // ------------------------------------------------------------------ contrôles des capteurs
  function makeControls(getPart, inputs, remember) {
    const box = h("div", { class: "mfa-controls" });
    for (const inp of inputs) {
      if (inp.type === "slider") {
        const out = h("output", { text: `${inp.value} ${inp.unit}` });
        const range = h("input", {
          type: "range", min: inp.min, max: inp.max, step: inp.step, value: inp.value, "aria-label": inp.label,
          oninput: (e) => { const v = Number(e.target.value); getPart().set(inp.key, v); out.textContent = `${v} ${inp.unit}`; remember(inp.key, v); },
        });
        box.append(h("label", { class: "mfa-slider" }, h("span", { text: inp.label }), out, range));
      } else if (inp.type === "toggle") {
        const cb = h("input", { type: "checkbox", onchange: (e) => { getPart().set(inp.key, e.target.checked); remember(inp.key, e.target.checked); } });
        box.append(h("label", { class: "mfa-toggle" }, cb, h("span", { text: inp.label })));
      } else if (inp.type === "button") {
        const press = (e) => { e.preventDefault(); getPart().press(inp.key); btn.setAttribute("aria-pressed", "true"); };
        const release = () => { getPart().release(inp.key); btn.setAttribute("aria-pressed", "false"); };
        const btn = h("button", {
          type: "button", class: "mfa-btn", text: inp.label, "aria-pressed": "false",
          onpointerdown: press, onpointerup: release, onpointerleave: release, onpointercancel: release,
          onkeydown: (e) => { if ((e.key === " " || e.key === "Enter") && !e.repeat) press(e); },
          onkeyup: (e) => { if (e.key === " " || e.key === "Enter") release(); },
        });
        box.append(btn);
      } else if (inp.type === "choice") {
        const group = h("div", { class: "mfa-choice", role: "group", "aria-label": inp.label }, h("span", { text: inp.label }));
        for (const [value, label] of inp.options) group.append(h("button", { type: "button", class: "mfa-btn small", text: label, onclick: () => getPart().fire(inp.key, value) }));
        box.append(group);
      }
    }
    return box;
  }

  // ------------------------------------------------------------------ atelier
  function mount(host, payload, options) {
    const opts = Object.assign({ startPlugged: false, autostart: true }, options || {});
    const wiring = payload.wiring || { pins: [], board: { labels: [], buses: {} } };
    const board = wiring.board;
    const state = { speed: 1, paused: false, plugged: {}, choices: {}, values: {}, sound: false, soundIndex: 0, serialLen: 0 };
    let sim = null;
    let raf = 0;
    let audio = null;

    host.textContent = "";
    host.classList.add("mfa");

    const timeEl = h("span", { class: "mfa-time", text: "00:00.0" });
    const countEl = h("span", { class: "mfa-count", role: "status" });
    const pauseBtn = h("button", { type: "button", class: "mfa-btn", text: "Pause", onclick: () => { state.paused = !state.paused; if (sim) sim.paused = state.paused; pauseBtn.textContent = state.paused ? "Reprendre" : "Pause"; pauseBtn.setAttribute("aria-pressed", String(state.paused)); } });
    const speeds = [1, 10, 60].map((v) => h("button", { type: "button", class: "mfa-btn small", text: `×${v}`, "aria-pressed": String(v === 1), onclick: (e) => { state.speed = v; if (sim) sim.speed = v; speeds.forEach((b) => b.setAttribute("aria-pressed", String(b === e.currentTarget))); } }));
    const soundBtn = h("button", { type: "button", class: "mfa-btn small", text: "Son : non", "aria-pressed": "false", onclick: () => { state.sound = !state.sound; soundBtn.textContent = `Son : ${state.sound ? "oui" : "non"}`; soundBtn.setAttribute("aria-pressed", String(state.sound)); if (state.sound && !audio && typeof AudioContext !== "undefined") audio = new AudioContext(); } });
    const toolbar = h("div", { class: "mfa-toolbar" },
      h("button", { type: "button", class: "mfa-btn primary", text: "Tout brancher", onclick: () => plugAll(true) }),
      h("button", { type: "button", class: "mfa-btn", text: "Tout débrancher", onclick: () => plugAll(false) }),
      h("span", { class: "mfa-sep" }),
      pauseBtn, ...speeds,
      h("button", { type: "button", class: "mfa-btn", text: "Recommencer", onclick: () => restart() }),
      soundBtn, timeEl);
    const errorBox = h("p", { class: "mfa-error", role: "alert", hidden: true });
    const boardArt = hasWokwi() && board.wokwi && customElements.get(board.wokwi) ? h("div", { class: "mfa-board-art" }, h(board.wokwi)) : null;
    const boardBox = h("div", { class: "mfa-board" },
      boardArt,
      h("div", {}, h("strong", { text: payload.boardName || board.name || payload.board }), h("span", { text: ` · logique ${board.logicV || ""} V` }), countEl));
    const grid = h("div", { class: "mfa-grid" });
    // rôle « log » : sortie qui défile ; aria-live off pour ne pas faire lire chaque ligne à voix haute
    const serial = h("pre", { class: "mfa-serial", role: "log", "aria-live": "off", "aria-label": "Moniteur série", tabindex: "0" });
    const webBox = h("div", { class: "mfa-web", hidden: !payload.wifi });
    const webFrame = h("iframe", { title: "Page web du projet", sandbox: "" });
    webBox.append(h("button", { type: "button", class: "mfa-btn", text: "Ouvrir la page du projet sur le téléphone", onclick: () => sim && sim.request() }), h("div", { class: "mfa-phone" }, webFrame));

    host.append(
      toolbar, errorBox, boardBox, grid,
      h("div", { class: "mfa-bottom" }, h("div", { class: "mfa-serial-box" }, h("h4", { text: "Moniteur série" }), serial), webBox),
      h("p", { class: "mfa-note", text: "Simulation du comportement : la logique du projet (son code C++ traduit en JavaScript) et un modèle de chaque composant. Le microcontrôleur lui-même n'est pas émulé (timings, bus I2C, mémoire) : pour cela, ouvre le projet dans Wokwi." }),
    );

    // -- cartes des composants
    const cards = {};
    const pinsByPart = {};
    for (const pin of wiring.pins) (pinsByPart[pin.part] = pinsByPart[pin.part] || []).push(pin);
    const pinOptions = board.labels.map((l) => {
      const hint = l.kind === "power" ? `${l.volts} V` : l.kind === "ground" ? "masse" : [l.inputOnly && "entrée seule", l.reserved && "réservée", !(l.caps || []).includes("adc") ? "" : "ADC"].filter(Boolean).join(", ");
      return [l.label, hint ? `${l.label} (${hint})` : l.label];
    });

    // une simulation « témoin » pour connaître la vue et les contrôles de chaque modèle
    const probe = new MFSim.Simulation({ ...payload, code: "return {setup: async () => {}, loop: async () => {}};" });

    for (const def of payload.parts) {
      const model = probe.parts[def.name];
      const extra = payload.extra || [];
      const visual = makeVisual(def, model.view, extra);
      const chip = h("span", { class: "mfa-status" });
      const pins = pinsByPart[def.name] || [];
      const pinRows = pins.map((pin) => {
        const feedback = h("span", { class: "mfa-fb" });
        const select = h("select", {
          "aria-label": `${def.name} broche ${pin.pin}`,
          onchange: (e) => { state.choices[`${def.name}.${pin.pin}`] = e.target.value; refreshWiring(); },
        }, h("option", { value: "", text: "— à brancher —" }), ...pinOptions.map(([v, t]) => h("option", { value: v, text: t })));
        return { pin, select, feedback, row: h("li", {}, h("code", { text: pin.pin }), h("small", { text: ROLE_LABELS[pin.role] || pin.role }), h("span", { text: "→" }), select, feedback) };
      });
      const wiringBox = pins.length
        ? h("details", { class: "mfa-wiring", open: !opts.startPlugged }, h("summary", { text: `Brancher ${pins.length} broche${pins.length > 1 ? "s" : ""}` }), h("ul", {}, ...pinRows.map((r) => r.row)))
        : h("p", { class: "mfa-passive", text: model.view === "load" ? "Se branche sur le pilote ou le transistor du montage." : "Pièce passive : pas de broche de la carte." });
      const controls = makeControls(() => sim.parts[def.name], model.inputs, (k, v) => { (state.values[def.name] = state.values[def.name] || {})[k] = v; });
      const card = h("article", { class: "mfa-card", "data-part": def.name },
        h("header", {}, h("h4", {}, h("code", { text: def.name }), " ", h("span", { text: def.label })), chip),
        visual.node, controls, wiringBox);
      // le clavier Wokwi et le bouton Wokwi pilotent directement le modèle
      card.addEventListener("button-press", (e) => {
        if (e.detail && e.detail.key !== undefined) sim.parts[def.name].fire("key", e.detail.key);
        else if (model.view === "button") sim.parts[def.name].press(model.inputs[0].key);
      });
      card.addEventListener("button-release", () => { if (model.view === "button") sim.parts[def.name].release(model.inputs[0].key); });
      grid.append(card);
      cards[def.name] = { def, visual, chip, pinRows, card, hasPins: pins.length > 0 };
    }

    function refreshWiring() {
      const taken = {};
      for (const c of Object.values(cards)) {
        for (const r of c.pinRows) {
          const v = state.choices[`${c.def.name}.${r.pin.pin}`];
          if (v && r.pin.role !== "power" && r.pin.role !== "ground") {
            const res = v === r.pin.expected;
            if (res) taken[v] = `${c.def.name}.${r.pin.pin}`;
          }
        }
      }
      let plugged = 0;
      for (const c of Object.values(cards)) {
        let ok = true;
        for (const r of c.pinRows) {
          const chosen = state.choices[`${c.def.name}.${r.pin.pin}`] || "";
          r.select.value = chosen;
          const others = Object.fromEntries(Object.entries(taken).filter(([, who]) => who !== `${c.def.name}.${r.pin.pin}`));
          const res = checkPin(r.pin, chosen, board, others, c.def.supply);
          r.feedback.textContent = res.msg;
          r.feedback.className = `mfa-fb ${chosen ? (res.ok ? "ok" : "err") : ""}`;
          r.select.classList.toggle("ok", res.ok);
          r.select.classList.toggle("err", !!chosen && !res.ok);
          ok = ok && res.ok;
        }
        state.plugged[c.def.name] = ok;
        if (ok) plugged += 1;
        c.chip.textContent = ok ? (c.hasPins ? "branché" : "prêt") : "à brancher";
        c.chip.className = `mfa-status ${ok ? "ok" : ""}`;
        c.card.classList.toggle("unplugged", !ok);
        if (sim && sim.parts[c.def.name]) sim.parts[c.def.name].plugged = ok;
      }
      const total = Object.keys(cards).length;
      countEl.textContent = ` · ${plugged}/${total} composant${total > 1 ? "s" : ""} branché${total > 1 ? "s" : ""}`;
    }

    function plugAll(on) {
      for (const c of Object.values(cards)) for (const r of c.pinRows) state.choices[`${c.def.name}.${r.pin.pin}`] = on ? r.pin.expected : "";
      refreshWiring();
    }

    function restart() {
      if (sim) sim.stop();
      errorBox.hidden = true;
      state.serialLen = 0;
      state.soundIndex = 0;
      serial.textContent = "";
      sim = new MFSim.Simulation({ ...payload, plugged: false });
      sim.paused = state.paused;
      for (const [name, values] of Object.entries(state.values)) for (const [k, v] of Object.entries(values)) sim.parts[name].v[k] = v;
      for (const [name, ok] of Object.entries(state.plugged)) if (sim.parts[name]) sim.parts[name].plugged = ok;
      const current = sim;
      sim.run({ realtime: true, speed: state.speed }).catch((err) => {
        if (current !== sim) return;
        errorBox.textContent = `Erreur dans la simulation : ${err && err.message ? err.message : err}`;
        errorBox.hidden = false;
      });
    }

    function beep(freq, ms) {
      if (!audio) return;
      const osc = audio.createOscillator();
      const gain = audio.createGain();
      osc.type = "square";
      osc.frequency.value = Math.max(40, Math.min(8000, freq));
      gain.gain.value = 0.04;
      osc.connect(gain).connect(audio.destination);
      osc.start();
      osc.stop(audio.currentTime + Math.max(0.02, ms / 1000 / state.speed));
    }

    let lastFrame = 0;
    function frame(t) {
      raf = requestAnimationFrame(frame);
      if (!sim || t - lastFrame < 50) return;
      lastFrame = t;
      timeEl.textContent = fmtTime(sim.now);
      const loads = sim.loads();
      for (const c of Object.values(cards)) c.visual.update(sim.parts[c.def.name], sim, loads);
      if (sim.serial.length !== state.serialLen) {
        state.serialLen = sim.serial.length;
        const atBottom = serial.scrollTop + serial.clientHeight >= serial.scrollHeight - 8;
        serial.textContent = sim.serial.slice(-4000);
        if (atBottom) serial.scrollTop = serial.scrollHeight;
      }
      if (sim.web.page && webFrame.dataset.body !== sim.web.page.body) {
        webFrame.dataset.body = sim.web.page.body;
        webFrame.srcdoc = sim.web.page.body;
      }
      while (state.soundIndex < sim.sounds.length) {
        const s = sim.sounds[state.soundIndex++];
        if (state.sound && sim.parts[s.part] && sim.parts[s.part].plugged) beep(s.freq, s.ms);
      }
      if (sim.sounds.length > 500) { sim.sounds.splice(0, 400); state.soundIndex = Math.max(0, state.soundIndex - 400); }
    }

    if (boardArt) {
      // les cartes Wokwi sont dessinées à l'échelle réelle : réduction pour tenir dans 170 × 120 px
      requestAnimationFrame(() => requestAnimationFrame(() => {
        const el = boardArt.firstChild;
        const r = el.getBoundingClientRect();
        if (r.width && r.height) {
          const k = Math.min(170 / r.width, 120 / r.height, 1);
          el.style.transform = `scale(${k})`;
          boardArt.style.width = `${Math.ceil(r.width * k)}px`;
          boardArt.style.height = `${Math.ceil(r.height * k)}px`;
        }
      }));
    }
    if (opts.startPlugged) plugAll(true); else refreshWiring();
    if (opts.autostart) restart();
    raf = requestAnimationFrame(frame);

    return {
      get sim() { return sim; },
      plugAll,
      restart,
      choose(part, pin, label) { state.choices[`${part}.${pin}`] = label; refreshWiring(); },
      destroy() { cancelAnimationFrame(raf); if (sim) sim.stop(); host.textContent = ""; },
    };
  }

  return { mount, checkPin };
});
