import React, {useState} from 'react';
import {matrixSignIn} from './authApi';

export function SignIn({onSignedIn}) {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  async function submit(event) {
    event.preventDefault();
    if (busy || !username.trim() || !password) return;
    setBusy(true);
    setError('');
    try {
      await matrixSignIn(username.trim(), password);
      setPassword('');
      await onSignedIn();
    } catch (failure) {
      setPassword('');
      setError(failure.message || 'Unable to sign in.');
    } finally {
      setBusy(false);
    }
  }
  return <main className="matrix-login" aria-label="Matrix sign in">
    <div className="login-heading"><h1>Didadi</h1><p>Sign in with your Matrix account</p></div>
    <form onSubmit={submit}>
      <label htmlFor="matrix-username">Matrix user ID</label>
      <input id="matrix-username" autoComplete="username" autoCapitalize="none"
        spellCheck={false} placeholder="@alice:localhost" value={username}
        onChange={event=>setUsername(event.target.value)} required disabled={busy}/>
      <label htmlFor="matrix-password">Password</label>
      <input id="matrix-password" type="password" autoComplete="current-password"
        value={password} onChange={event=>setPassword(event.target.value)}
        required disabled={busy}/>
      {error&&<p className="login-error" role="alert">{error}</p>}
      <button className="primary" disabled={busy||!username.trim()||!password}>
        {busy?'Signing in…':'Sign in'}
      </button>
    </form>
    <p className="login-notice">Local Matrix workspace. No demo account, OAuth redirect or browser-stored access token.</p>
  </main>;
}
