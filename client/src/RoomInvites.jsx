import React, {useEffect, useState} from 'react';
import {errorText} from './api';

// Invitations are a separate state from joined rooms: never render their
// timelines, attachments or cached messages until Matrix confirms the join.
export function RoomInvites({api, onJoined}) {
  const [invites, setInvites] = useState([]);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState('');
  const [loading, setLoading] = useState(false);
  async function refresh() {
    setLoading(true); setError('');
    try { setInvites(await api.invites()); }
    catch (err) { setInvites([]); setError(errorText(err)); }
    finally { setLoading(false); }
  }
  useEffect(() => { refresh(); }, [api]);
  async function join(room) {
    if (busy) return;
    setBusy(room); setError('');
    try {
      const result = await api.joinRoom(room);
      if (result?.room !== room || result.joined !== true) {
        throw new Error('The Matrix join has not been confirmed. Refresh invitations and retry.');
      }
      setInvites(previous => previous.filter(item => item.room !== room));
      await onJoined(room);
    } catch (err) { setError(errorText(err)); }
    finally { setBusy(''); }
  }
  return <section className="room-invites" aria-label="Matrix invitations">
    <div className="section-heading"><span>Invitations</span>
      <button type="button" onClick={refresh} disabled={loading || Boolean(busy)}
        aria-label="Refresh invitations">Refresh</button></div>
    {loading && <p role="status">Checking Matrix invitations…</p>}
    {error && <p role="alert">{error}</p>}
    {!loading && !invites.length && !error && <p>No pending invitations</p>}
    {invites.map(item => <div key={item.room} className="room-invite">
      <span>{item.name}</span>
      <button type="button" disabled={Boolean(busy)} onClick={() => join(item.room)}
        aria-label={`Join invitation ${item.name}`}>{busy===item.room?'Joining…':'Join'}</button>
    </div>)}
  </section>;
}
