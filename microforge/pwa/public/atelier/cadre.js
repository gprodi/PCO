// Pont entre la page Projet et l'atelier virtuel (cadre isolé, origine opaque).
// Reçoit la charge du projet par postMessage, monte l'atelier, renvoie sa hauteur pour éviter une
// double barre de défilement. N'accepte que les messages de la page qui contient le cadre.
(function () {
  'use strict';
  var host = document.getElementById('atelier');
  var wait = document.getElementById('attente');
  var current = null;

  function tell(message) { window.parent.postMessage(message, '*'); }

  var lastHeight = 0;
  function reportHeight() {
    var h = Math.ceil(document.documentElement.getBoundingClientRect().height);
    if (h !== lastHeight) { lastHeight = h; tell({ type: 'mf-atelier-height', height: h }); }
  }

  function valid(p) {
    return p && typeof p === 'object' && typeof p.code === 'string' && Array.isArray(p.parts)
      && p.wiring && Array.isArray(p.wiring.pins) && p.wiring.board && Array.isArray(p.wiring.board.labels);
  }

  function fail(text) {
    host.textContent = '';
    var p = document.createElement('p');
    p.className = 'cadre-erreur';
    p.setAttribute('role', 'alert');
    p.textContent = text;
    host.appendChild(p);
  }

  window.addEventListener('message', function (event) {
    if (event.source !== window.parent) return;
    var msg = event.data;
    if (!msg || msg.type !== 'mf-atelier') return;
    if (msg.theme === 'light' || msg.theme === 'dark') document.documentElement.dataset.theme = msg.theme;
    else delete document.documentElement.dataset.theme;
    if (current) { current.destroy(); current = null; }
    host.textContent = '';
    wait.hidden = true;
    if (!valid(msg.payload)) { fail('Atelier indisponible pour ce projet.'); reportHeight(); return; }
    try {
      current = window.MFAtelier.mount(host, msg.payload);
    } catch (err) {
      fail('Atelier indisponible : ' + String(err && err.message || err));
    }
    reportHeight();
  });

  if (typeof ResizeObserver !== 'undefined') new ResizeObserver(reportHeight).observe(document.body);
  tell({ type: 'mf-atelier-ready' });
})();
