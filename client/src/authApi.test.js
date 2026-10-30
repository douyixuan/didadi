import {describe, it, expect, vi} from 'vitest';
import {matrixSignIn} from './authApi';

describe('Matrix password sign-in (injected transport, no network)', () => {
  it('posts only to the local auth route and does not expose a token', async () => {
    const send = vi.fn().mockResolvedValue({ok:true,json:async()=>({userId:'@alice:local'})});
    expect(await matrixSignIn('@alice:local','secret',send)).toEqual({userId:'@alice:local'});
    expect(send).toHaveBeenCalledWith('/api/auth/login',expect.objectContaining({
      method:'POST',credentials:'same-origin',
      headers:expect.objectContaining({'X-Didadi-Login':'1'}),
    }));
    const [route, options]=send.mock.calls[0];
    expect(JSON.parse(options.body)).toEqual({username:'@alice:local',password:'secret'});
    expect(JSON.stringify(await matrixSignIn('@alice:local','secret',send))).not.toContain('secret');
  });
  it('rejects authentication failures without silently using a fixture identity', async () => {
    const send=vi.fn().mockResolvedValue({ok:false,status:401,json:async()=>({error:'Matrix rejected the username or password.'})});
    await expect(matrixSignIn('alice','invalid',send)).rejects.toMatchObject({status:401});
  });
});
