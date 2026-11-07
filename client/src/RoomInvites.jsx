import React, {useEffect, useRef, useState} from 'react';
import {errorText} from './api';

// An invitation is not a joined room. Never reveal messages/attachments until
// Matrix confirms that this current user explicitly joined.
export function RoomInvites({api, onJoined}) {
  const [invites, setInvites] = useState([]);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState('');
  const [loading, setLoading] = useState(false);
  const revision = useRef(0);

  async function refresh() {
    const current = ++revision.current;
    setLoading(true); setError('');
    try {
      const result = await api.invites();
      if (current === revision.current) setInvites(result);
    } catch (err) {
      if (current === revision.current) {setInvites([]); setError(errorText(err));}
    } finally {
      if (current === revision.current) setLoading(false);
    }
  }

  useEffect(() => {
    setInvites([]);
    setBusy('');
    refresh();
    return () => {revision.current += 1;};
  }, [api]);

  async function join(room) {
    if (busy) return;
    const current = revision.current;
    setBusy(room); setError('');
    try {
      const result = await api.joinRoom(room);
      if (current !== revision.current) return;
      if (result?.room !== room || result.joined !== true) {
        throw new Error('The Matrix join has not been confirmed. Refresh invitations and retry.');
      }
      setInvites(previous => previous.filter(item => item.room !== room));
      await onJoined(room);
    } catch (err) {
      if (current === revision.current) setError(errorText(err));
    } finally {
      if (current === revision.current) setBusy('');
    }
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
      <button type="button" disabled={Boolean(busy) || loading} onClick={() => join(item.room)}
        aria-label={`Join invitation ${item.name}`}>{busy===item.room?'Joining…':'Join'}</button>
    </div>)}
  </section>;
}
