// Mon stock : ce que l'on possède, rangé par catégorie, et l'ajout d'une pièce.
import { useCallback, useEffect, useMemo, useState } from 'react';
import { CATEGORIES, Icon, Status, message, plural } from '../ui.jsx';

export default function Stock({ client, workshop, onChange }) {
  const [items, setItems] = useState(null);
  const [state, setState] = useState(null);
  const { names, categoryOf, boards, components } = workshop;

  const load = useCallback(async () => {
    try {
      setItems(await client.inventory());
    } catch (err) {
      setState({ text: message(err), error: true });
    }
  }, [client]);
  useEffect(() => { load(); }, [load]);

  const groups = useMemo(() => {
    const g = new Map();
    for (const i of items ?? []) {
      const cat = categoryOf[i.component_id] ?? 'autre';
      if (!g.has(cat)) g.set(cat, []);
      g.get(cat).push(i);
    }
    return [...g.entries()].sort(([a], [b]) => (a === 'carte' ? -1 : b === 'carte' ? 1 : a.localeCompare(b)));
  }, [items, categoryOf]);

  async function add(e) {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    try {
      await client.addItem({ component_id: f.get('component'), quantity: Number(f.get('quantity')), location: f.get('location') || '' });
      setState({ text: `Ajouté : ${names[f.get('component')] ?? f.get('component')}.` });
      await load();
      onChange();
    } catch (err) {
      setState({ text: message(err), error: true });
    }
  }
  async function remove(i) {
    try {
      await client.deleteItem(i.id);
      setState({ text: `Retiré : ${names[i.component_id] ?? i.component_id}.` });
      await load();
      onChange();
    } catch (err) {
      setState({ text: message(err), error: true });
    }
  }
  const total = (items ?? []).reduce((s, i) => s + i.quantity, 0);

  return (
    <>
      <header className="page-head">
        <p className="eyebrow">Inventaire</p>
        <h1>Mon stock</h1>
        <p className="lede">{items == null ? 'Chargement…' : `${plural(total, 'pièce', 'pièces')}, ${plural(items.length, 'ligne', 'lignes')}.`}</p>
        <a className="btn ghost" href="#photo"><Icon name="photo" size={18} /> Photographier mon stock</a>
      </header>

      <div className="stock-layout">
        <form className="card form" onSubmit={add} aria-labelledby="t-ajout">
          <h2 id="t-ajout">Ajouter une pièce</h2>
          <label htmlFor="f-component">Composant</label>
          <select id="f-component" name="component" required defaultValue="">
            <option value="" disabled>Choisir…</option>
            <optgroup label="Cartes">
              {boards.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
            </optgroup>
            <optgroup label="Composants">
              {components.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
            </optgroup>
          </select>
          <div className="two">
            <div>
              <label htmlFor="f-quantity">Quantité</label>
              <input id="f-quantity" name="quantity" type="number" min="1" max="999" defaultValue="1" required />
            </div>
            <div>
              <label htmlFor="f-location">Emplacement</label>
              <input id="f-location" name="location" placeholder="tiroir 2…" />
            </div>
          </div>
          <button className="btn" type="submit"><Icon name="plus" size={16} /> Ajouter au stock</button>
          <Status state={state} />
        </form>

        <div className="stock-list">
          {items?.length === 0 && (
            <div className="card empty">
              <h2>Ton stock est vide</h2>
              <p>Ajoute une carte (Arduino, ESP32…) et quelques composants : les idées réalisables apparaîtront dans Explorer.</p>
            </div>
          )}
          {groups.map(([cat, list]) => (
            <section key={cat} className="card group" aria-labelledby={`g-${cat}`}>
              <h2 id={`g-${cat}`}>{CATEGORIES[cat] ?? 'Autres'} <span className="count">{list.reduce((s, i) => s + i.quantity, 0)}</span></h2>
              <ul className="items">
                {list.map((i) => (
                  <li key={i.id}>
                    <span className="qty" aria-label={`quantité ${i.quantity}`}>{i.quantity}</span>
                    <span className="item-name">{names[i.component_id] ?? i.component_id}
                      {i.location && <small>{i.location}</small>}
                    </span>
                    <button className="icon-btn" type="button" onClick={() => remove(i)} aria-label={`Retirer ${names[i.component_id] ?? i.component_id}`}>Retirer</button>
                  </li>
                ))}
              </ul>
            </section>
          ))}
        </div>
      </div>
    </>
  );
}
