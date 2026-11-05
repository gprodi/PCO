// Photo du stock : l'appareil photo du téléphone s'ouvre directement ; les pièces reconnues
// s'ajoutent au stock en un geste.
import { useEffect, useState } from 'react';
import { Icon, Status, message } from '../ui.jsx';

export default function Photo({ client, onChange }) {
  const [file, setFile] = useState(null);
  const [preview, setPreview] = useState(null);
  const [result, setResult] = useState(null);
  const [state, setState] = useState(null);
  useEffect(() => () => preview && URL.revokeObjectURL(preview), [preview]);

  function pick(e) {
    const f = e.target.files?.[0] ?? null;
    setFile(f);
    setResult(null);
    setPreview(f ? URL.createObjectURL(f) : null);
  }
  async function analyse() {
    setState({ text: 'Analyse de la photo…' });
    try {
      const r = await client.scan(file);
      setResult(r);
      setState({ text: `${r.items.length} composant(s) reconnu(s), ${r.unknown.length} à identifier.` });
    } catch (err) {
      setState({ text: message(err), error: true });
    }
  }
  async function keep() {
    try {
      await client.addBulk(result.items.map((i) => ({ component_id: i.component_id, quantity: i.quantity })), 'photo');
      setState({ text: 'Composants reconnus ajoutés au stock.' });
      onChange();
    } catch (err) {
      setState({ text: message(err), error: true });
    }
  }
  return (
    <>
      <header className="page-head">
        <p className="eyebrow">Mon stock</p>
        <h1>Photographier mon stock</h1>
        <p className="lede">Étale tes composants sur une surface claire. La photo est analysée puis oubliée ; sa position GPS est retirée avant l'analyse.</p>
      </header>
      <div className="photo-layout">
        <div className="card">
          <label className="drop" htmlFor="f-photo">
            <Icon name="photo" size={32} />
            <span>{file ? file.name : 'Prendre ou choisir une photo'}</span>
          </label>
          <input id="f-photo" className="sr-file" type="file" accept="image/*" capture="environment" onChange={pick} />
          {preview && <img className="preview" src={preview} alt="Aperçu de la photo choisie" />}
          <button className="btn" type="button" onClick={analyse} disabled={!file}>Analyser la photo</button>
          <Status state={state} />
        </div>
        {result && (
          <div className="card">
            <h2>Résultat</h2>
            {result.items.length === 0 && <p>Aucun composant reconnu avec certitude.</p>}
            <ul className="items">
              {result.items.map((i, k) => (
                <li key={k}><span className="qty">{i.quantity}</span><span className="item-name">{i.label || i.component_id}<small>confiance {Math.round(i.confidence * 100)} %</small></span></li>
              ))}
              {result.unknown.map((u, k) => (
                <li key={`u${k}`} className="muted"><span className="qty">{u.quantity}</span><span className="item-name">À identifier : {u.label}</span></li>
              ))}
            </ul>
            {result.items.length > 0 && <button className="btn" type="button" onClick={keep}>Ajouter les composants reconnus</button>}
            <p className="small muted">Modèle : {result.model_version} · {result.latency_ms} ms</p>
          </div>
        )}
      </div>
    </>
  );
}
