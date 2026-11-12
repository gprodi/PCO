/*
 * Missions de l'atelier virtuel MicroForge : des défis validés par le simulateur lui-même.
 *
 * Une mission = une action de l'utilisateur (régler un capteur, appuyer, présenter un badge,
 * ouvrir la page web) puis un résultat attendu dans une fenêtre de temps virtuel (une LED
 * s'allume, la sirène sonne, le relais se ferme, l'écran affiche une valeur…). Deux missions
 * automatiques existent pour chaque projet : brancher sans l'aide « Tout brancher », et faire
 * tourner la simulation 60 s sans erreur.
 *
 * Le même fichier sert dans le navigateur (atelier) et dans Node (tests : chaque mission doit
 * réussir avec son action et échouer sans elle).
 */
(function (root, factory) {
  if (typeof module === "object" && module.exports) module.exports = factory();
  else root.MFMissions = factory();
})(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  const FENETRE_MS = 3000;

  function egal(a, b) {
    if (Array.isArray(a) && Array.isArray(b)) return a.length === b.length && a.every((x, i) => egal(x, b[i]));
    return a === b;
  }

  function compare(a, op, b) {
    switch (op || "==") {
      case "==": return egal(a, b);
      case "!=": return !egal(a, b);
      case "<": return a < b;
      case "<=": return a <= b;
      case ">": return a > b;
      case ">=": return a >= b;
      default: throw new Error(`opérateur inconnu : ${op}`);
    }
  }

  /** « contient » : sous-chaîne d'un texte, d'une des lignes d'un écran, ou élément d'un tableau. */
  function contient(valeur, cible) {
    if (typeof valeur === "string") return valeur.includes(String(cible));
    if (Array.isArray(valeur)) return valeur.some((v) => (typeof v === "string" ? v.includes(String(cible)) : egal(v, cible)));
    return false;
  }

  function compteurs(sim) {
    const appuis = {};
    const evenements = {};
    for (const [nom, p] of Object.entries(sim.parts)) {
      appuis[nom] = p.presses || 0;
      evenements[nom] = p.fired || 0;
    }
    return { appuis, evenements, requetes: sim.web.total || 0 };
  }

  function actionFaite(action, sim, base) {
    if (!action) return true;
    if (action.tous) return action.tous.every((a) => actionFaite(a, sim, base));
    if (action.requete !== undefined) return (sim.web.total || 0) - base.requetes >= 1;
    const p = sim.parts[action.part];
    if (!p) return false;
    if (action.regle !== undefined) return compare(p.v[action.regle], action.op, action.valeur);
    if (action.appui !== undefined) return (p.presses || 0) - (base.appuis[action.part] || 0) >= (action.fois || 1);
    if (action.evenement !== undefined) return (p.fired || 0) - (base.evenements[action.part] || 0) >= (action.fois || 1);
    return false;
  }

  function attenduOk(att, sim, arme) {
    if (att.tous) return att.tous.every((a) => attenduOk(a, sim, arme));
    if (att.serie !== undefined || att.motif !== undefined) {
      const nouveaux = sim.serialTotal - arme.serialTotal;
      const texte = nouveaux <= 0 ? "" : sim.serial.slice(Math.max(0, sim.serial.length - nouveaux));
      return att.motif !== undefined ? new RegExp(att.motif).test(texte) : texte.includes(att.serie);
    }
    if (att.page !== undefined) return !!(sim.web.page && sim.web.page.body.includes(att.page));
    if (att.charge !== undefined) return compare(sim.loads()[att.charge] || 0, att.op || ">", att.valeur === undefined ? 0 : att.valeur);
    if (att.sons !== undefined) {
      return sim.sounds.filter((s) => s.part === att.part && s.at >= arme.t).length >= att.sons;
    }
    if (att.silence_ms !== undefined) {
      if (sim.now - arme.t < att.silence_ms) return false;
      return !sim.sounds.some((s) => s.part === att.part && s.at > sim.now - att.silence_ms);
    }
    const p = sim.parts[att.part];
    if (!p) return false;
    const valeur = p.s[att.etat];
    if (att.contient !== undefined) return contient(valeur, att.contient);
    return compare(valeur, att.op, att.valeur);
  }

  class Suivi {
    /**
     * @param {Array} missions  missions du projet (charge de l'atelier)
     * @param {object} options  { faites: [id…], contexte: () => ({ branche, aide }), onReussite: (mission) => {} }
     */
    constructor(missions, options) {
      const opts = options || {};
      this.missions = missions || [];
      this.contexte = opts.contexte || (() => ({ branche: true, aide: false }));
      this.onReussite = opts.onReussite || (() => {});
      this.etat = {};
      for (const m of this.missions) this.etat[m.id] = { faite: false, arme: null, okDepuis: null };
      for (const id of opts.faites || []) if (this.etat[id]) this.etat[id].faite = true;
      this._detacher = null;
    }

    reussies() {
      return this.missions.filter((m) => this.etat[m.id].faite).map((m) => m.id);
    }

    disponible(m) {
      return !this.etat[m.id].faite && (!m.apres || (this.etat[m.apres] && this.etat[m.apres].faite));
    }

    /** Nouvelle simulation (démarrage, « Recommencer ») : les missions repartent de zéro. */
    attacher(sim) {
      if (this._detacher) this._detacher();
      this.sim = sim;
      this.debut = sim.now;
      for (const e of Object.values(this.etat)) { e.arme = null; e.okDepuis = null; e.base = compteurs(sim); e.ouverte = false; }
      this._detacher = sim.observe(() => this.verifier(), 10);
    }

    detacher() {
      if (this._detacher) this._detacher();
      this._detacher = null;
    }

    /** Pour les tests : arme une mission comme si son action venait d'avoir lieu. */
    armer(id) {
      const sim = this.sim;
      this.etat[id].arme = { t: sim.now, serialTotal: sim.serialTotal };
    }

    _reussir(m) {
      this.etat[m.id].faite = true;
      this.onReussite(m);
    }

    /** Appelé par l'atelier quand le branchement change (mission « brancher sans aide »). */
    branchement() {
      const ctx = this.contexte();
      for (const m of this.missions) {
        if (m.auto === "branchement" && this.disponible(m) && ctx.branche && !ctx.aide) this._reussir(m);
      }
    }

    verifier() {
      const sim = this.sim;
      if (!sim) return;
      const ctx = this.contexte();
      for (const m of this.missions) {
        const e = this.etat[m.id];
        if (!this.disponible(m)) { e.ouverte = false; continue; }
        if (!e.ouverte) {
          // Mission qui vient de se débloquer : les appuis faits pour la précédente ne comptent pas.
          e.ouverte = true;
          e.base = compteurs(sim);
          e.arme = null;
          e.okDepuis = null;
        }
        if (m.auto === "branchement") {
          if (ctx.branche && !ctx.aide) this._reussir(m);
          continue;
        }
        if (m.auto === "simulation") {
          if (ctx.branche && !sim.error && sim.now - this.debut >= (m.duree_ms || 60000)) this._reussir(m);
          continue;
        }
        if (!ctx.branche) { e.arme = null; e.okDepuis = null; continue; } // missions : montage complet
        if (!e.arme && actionFaite(m.action, sim, e.base)) e.arme = { t: sim.now, serialTotal: sim.serialTotal };
        if (!e.arme) continue;
        if (attenduOk(m.attendu, sim, e.arme)) {
          if (e.okDepuis === null) e.okDepuis = sim.now;
          if (sim.now - e.okDepuis >= (m.attendu.duree_ms || 0)) { this._reussir(m); continue; }
        } else {
          e.okDepuis = null;
        }
        if (sim.now - e.arme.t > (m.fenetre_ms || FENETRE_MS)) {
          // Trop tard : il faut refaire l'action (les appuis déjà comptés ne valent plus).
          e.arme = null;
          e.okDepuis = null;
          e.base = compteurs(sim);
        }
      }
    }
  }

  return { Suivi, actionFaite, attenduOk, compare, contient, FENETRE_MS, version: "1.0" };
});
