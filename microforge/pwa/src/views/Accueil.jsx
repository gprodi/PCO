// Accueil : l'établi animé, l'état de l'atelier (stock, projets réalisables), le parcours en
// 7 étapes et la vitrine de vrais projets open source.
import { useEffect, useState } from 'react';
import Bench from '../bench.jsx';
import { Dots, Icon, Status, message, plural } from '../ui.jsx';

export default function Accueil({ client, workshop, onGenerate }) {
  const [insp, setInsp] = useState(null);
  const [ready, setReady] = useState(null);
  const [state, setState] = useState(null);
  const inv = workshop.summary;

  useEffect(() => {
    (async () => {
      try {
        setInsp(await client.inspiration());
      } catch (err) {
        setState({ text: message(err), error: true });
      }
    })();
  }, [client]);
  useEffect(() => {
    if (!inv) return;
    client.suggest(inv, 30).then((s) => setReady(s.filter((x) => x.feasible_now).length)).catch(() => setReady(null));
  }, [client, inv]);

  const pieces = inv ? Object.values(inv).reduce((s, n) => s + n, 0) : null;
  const c = insp?.chiffres;

  return (
    <>
      <section className="hero" aria-labelledby="t-hero">
        <div className="hero-text">
          <p className="eyebrow">Atelier électronique</p>
          <h1 id="t-hero">Tes composants deviennent des projets qui marchent.</h1>
          <p className="lede">
            Dis ce que tu as dans tes tiroirs : MicroForge propose des montages réalisables, choisit les
            broches, vérifie les tensions et écrit le code Arduino.
          </p>
          <div className="actions">
            <a className="btn" href="#explorer">Explorer les idées <Icon name="fleche" size={16} /></a>
            <a className="btn ghost" href="#photo"><Icon name="photo" size={18} /> Photographier mon stock</a>
          </div>
          {c && (
            <ul className="facts" aria-label="Le catalogue">
              <li><b>{c.modeles_generables}</b> projets générables</li>
              <li><b>{c.idees}</b> idées</li>
              <li><b>{c.themes}</b> thèmes</li>
              <li><b>{c.composants}</b> composants</li>
              <li><b>{c.cartes}</b> cartes</li>
            </ul>
          )}
        </div>
        <Bench />
      </section>

      <section className="atelier" aria-labelledby="t-atelier">
        <h2 id="t-atelier" className="sr">Ton atelier</h2>
        <a className="tile" href="#stock">
          <span className="tile-label">Ton stock</span>
          <b>{pieces == null ? '…' : plural(pieces, 'pièce', 'pièces')}</b>
          <span className="tile-more">{pieces ? 'Voir et compléter' : 'Ajoute tes premiers composants'}</span>
        </a>
        <a className="tile" href="#explorer">
          <span className="tile-label">Réalisables maintenant</span>
          <b>{ready == null ? '…' : plural(ready, 'projet', 'projets')}</b>
          <span className="tile-more">Voir les idées par thème</span>
        </a>
        <a className="tile" href="#copilote">
          <span className="tile-label">Une question ?</span>
          <b>Copilote</b>
          <span className="tile-more">Broches, tensions, compatibilités</span>
        </a>
      </section>
      <Status state={state} />

      {insp && (
        <section aria-labelledby="t-parcours">
          <h2 id="t-parcours">Le parcours, de la première LED au robot</h2>
          <p className="lede">Sept étapes ; chaque projet ouvre son câblage et son code.</p>
          <ol className="path">
            {insp.parcours.map((e) => (
              <li key={e.etape} className="step">
                <span className="step-n" aria-hidden="true">{e.etape}</span>
                <div className="step-body">
                  <h3>{e.titre}</h3>
                  <p>{e.objectif}</p>
                  <ul className="chips" aria-label="Notions">
                    {e.notions.map((n) => <li key={n} className="chip">{n}</li>)}
                  </ul>
                  <div className="step-projects">
                    {e.projets.map((p) => (
                      <button key={p.id} type="button" className="link-btn" onClick={() => onGenerate(p.id, false, p.titre)}>
                        {p.titre} <Dots n={p.difficulte} />
                      </button>
                    ))}
                  </div>
                </div>
              </li>
            ))}
          </ol>
        </section>
      )}

      {insp && (
        <section aria-labelledby="t-vitrine">
          <h2 id="t-vitrine">Ils l'ont construit</h2>
          <p className="lede">De vrais projets open source, et par quoi commencer pour y arriver.</p>
          <div className="grid">
            {insp.vitrine.map((v) => (
              <article className="card showcase" key={v.nom}>
                <div className="meta"><span className="pill">{v.categorie}</span><span className="pill">{v.carte}</span></div>
                <h3>{v.nom}</h3>
                <p>{v.description}</p>
                <p className="small muted">Commencer par :</p>
                <div className="step-projects">
                  {v.commencer_par.map((p) => (
                    <button key={p.id} type="button" className="link-btn" onClick={() => onGenerate(p.id, false, p.titre)}>{p.titre}</button>
                  ))}
                </div>
                <a className="ext" href={v.url} target="_blank" rel="noopener noreferrer">Voir {v.nom} <Icon name="lien" size={14} /></a>
              </article>
            ))}
          </div>
        </section>
      )}
    </>
  );
}
