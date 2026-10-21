// Offline CI regression configuration only. No product transport is allowed.
import {afterEach,beforeEach,expect,vi} from 'vitest';
let forbidden;
beforeEach(()=>{
  forbidden=vi.fn(()=>{throw new Error('Offline CI tests forbid transport')});
  vi.stubGlobal('fetch',forbidden);
  vi.stubGlobal('WebSocket',class{constructor(){forbidden()}});
  vi.stubGlobal('XMLHttpRequest',class{constructor(){forbidden()}});
  vi.stubGlobal('EventSource',class{constructor(){forbidden()}});
});
afterEach(()=>{expect(forbidden).not.toHaveBeenCalled();vi.unstubAllGlobals()});
