import {act,renderHook,waitFor} from '@testing-library/react';
import {it,expect,vi} from 'vitest';
import {useThread} from './useThread';

it('P0 ROOM-02 hides thread history and ignores an older-page result after Matrix revocation',async()=>{
  let finishOlder;
  const root={id:'$root'},secret={id:'$secret',content:{body:'Private message'}};
  const denied=Object.assign(new Error('Room membership revoked'),{httpStatus:403});
  const api={session:{liveMatrix:true},threadPage:vi.fn()
    .mockResolvedValueOnce({root,events:[secret],previousCursor:'older'})
    .mockImplementationOnce(()=>new Promise(resolve=>{finishOlder=resolve;}))
    .mockRejectedValueOnce(denied)};
  const {result,unmount}=renderHook(()=>useThread(api,'!private','$root'));
  try{
    await waitFor(()=>expect(result.current.events).toHaveLength(2));
    act(()=>{result.current.older();});
    await waitFor(()=>expect(finishOlder).toBeTypeOf('function'));
    await act(async()=>{await result.current.refresh();});
    expect(result.current.events).toEqual([]);
    expect(result.current.error).toMatch(/revoked/);
    await act(async()=>{finishOlder({root,events:[{id:'$old-secret',content:{body:'Stale secret'}}],previousCursor:null});});
    expect(result.current.events).toEqual([]);
  }finally{unmount();}
});
