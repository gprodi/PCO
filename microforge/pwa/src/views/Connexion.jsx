// Connexion et création de compte, à côté de l'établi.
import { useState } from 'react';
import Bench from '../bench.jsx';
import { Status, message } from '../ui.jsx';

export default function Connexion({ client, onLogged }) {
  const [mode, setMode] = useState('login');
  const [busy, setBusy] = useState(false);
  const [state, setState] = useState(null);
  async function submit(e) {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    setBusy(true);
    setState({ text: mode === 'login' ? 'Connexion…' : 'Création du compte…' });
    try {
      if (mode === 'register') {
        await client.register({
          username: f.get('username'), email: f.get('email'), password: f.get('password'),
          city: f.get('city'), consent: f.get('consent') === 'on',
        });
      }
      await client.login(f.get('username'), f.get('password'));
      onLogged();
    } catch (err) {
      setState({ text: message(err), error: true });
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="login">
      <section className="login-intro" aria-labelledby="t-intro">
        <p className="eyebrow">MicroForge</p>
        <h1 id="t-intro">Ton stock de composants devient des projets.</h1>
        <p className="lede">Idées par thème, câblage broche par broche, code Arduino prêt à téléverser.</p>
        <Bench />
      </section>
      <section className="card login-form" aria-labelledby="t-connexion">
        <h2 id="t-connexion">{mode === 'login' ? 'Connexion' : 'Créer un compte'}</h2>
        <form className="form" onSubmit={submit}>
          <label htmlFor="f-username">Pseudo{mode === 'register' ? ' (3 à 40 caractères)' : ' ou e-mail'}</label>
          <input id="f-username" name="username" autoComplete="username" required minLength={3} />
          {mode === 'register' && (
            <>
              <label htmlFor="f-email">E-mail</label>
              <input id="f-email" name="email" type="email" autoComplete="email" required />
            </>
          )}
          <label htmlFor="f-password">Mot de passe{mode === 'register' ? ' (10 caractères min., lettres et chiffres)' : ''}</label>
          <input id="f-password" name="password" type="password" required minLength={mode === 'register' ? 10 : 1}
            autoComplete={mode === 'register' ? 'new-password' : 'current-password'} />
          {mode === 'register' && (
            <>
              <label htmlFor="f-city">Ville (facultatif)</label>
              <input id="f-city" name="city" autoComplete="address-level2" />
              <label className="check" htmlFor="f-consent"><input id="f-consent" name="consent" type="checkbox" />
                J'accepte que mes photos corrigées servent à améliorer le modèle (facultatif)</label>
            </>
          )}
          <button className="btn" type="submit" disabled={busy}>{mode === 'login' ? 'Se connecter' : 'Créer mon compte'}</button>
          <button className="btn ghost" type="button" onClick={() => { setMode(mode === 'login' ? 'register' : 'login'); setState(null); }}>
            {mode === 'login' ? 'Créer un compte' : "J'ai déjà un compte"}
          </button>
        </form>
        <Status state={state} />
      </section>
    </div>
  );
}
