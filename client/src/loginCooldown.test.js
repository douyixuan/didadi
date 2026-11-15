import {expect,it} from 'vitest';
import {loginCooldown} from '../scripts/login_cooldown.mjs';
it('waits a genuine default Synapse refill interval rather than repeatedly retrying at 45 seconds',()=>{
  expect(loginCooldown({retry_after_ms:333334})).toBe(333834);
  expect(loginCooldown({retry_after_ms:60000})).toBeGreaterThanOrEqual(60000);
});
it('fails explicitly when the server cooldown cannot fit the remaining bounded budget',()=>{
  expect(()=>loginCooldown({retry_after_ms:333334},100000)).toThrow(/no authentication outcome proven/);
});
it('uses a finite fallback when no valid server delay is supplied',()=>{
  for(const value of [undefined,null,-1,'','not-a-number'])expect(loginCooldown({retry_after_ms:value})).toBe(12000);
});
