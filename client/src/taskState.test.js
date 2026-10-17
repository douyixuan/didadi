import {it,expect} from 'vitest';
import {taskState} from './taskState';
it('distinguishes real scheduling phases without using reply text or inferring execution from connectivity',()=>{
 for(const [phase,label] of Object.entries({waiting:'Waiting for runtime',verifying:'Awaiting access confirmation',running:'In progress · lease held',retry_wait:'Waiting to retry'}))expect(taskState({status:'pending',phase}).label).toBe(label);
 expect(taskState({status:'pending',phase:'waiting',runtime:{transport:'websocket',state:'connected'}}).label).toBe('Waiting for runtime');
 expect(taskState({status:'done',phase:'running'}).label).toBe('Completed');expect(taskState(null).label).toBe('Waiting for Gateway acceptance');
});
it('uses the server observation for retry timing and labels unknown connections honestly',()=>{
 const state=taskState({status:'pending',phase:'retry_wait',attempts:2,max_attempts:8,retry_reason:'lease_expired',next_retry_at:103,observed_at:100,runtime:{transport:'websocket',state:'unknown'}});
 expect(state.detail).toContain('Attempt 2 of 8');expect(state.detail).toContain('previous lease expired');expect(state.detail).toContain('in 3 seconds');expect(state.connection).toContain('unconfirmed');
 expect(taskState({status:'pending',phase:'retry_wait',next_retry_at:99,observed_at:100}).detail).toContain('Ready to be reclaimed');
});
it('does not present stale execution or connection facts during a failed status poll',()=>{
 const state=taskState({status:'reconnecting',phase:'running',runtime:{transport:'websocket',state:'connected'}});
 expect(state.label).toBe('Task status unavailable');expect(state.connection).toBe('');expect(state.detail).toContain('no new task');
});
it('does not promise another execution after the retry budget is exhausted',()=>{
 const state=taskState({status:'pending',phase:'retry_wait',attempts:8,max_attempts:8,retry_limit_reached:true,next_retry_at:1,observed_at:100});
 expect(state.detail).toContain('no further execution will be leased');expect(state.detail).not.toContain('Ready to be reclaimed');
});
it('does not imply active room checks for an unconfirmed lease migrated from an old Gateway',()=>{
 const state=taskState({status:'pending',phase:'verifying',verification_reason:'legacy_lease_unconfirmed'});
 expect(state.label).toBe('Lease state unconfirmed');expect(state.detail).toContain('earlier Gateway version');
});

it('does not infer an idle runtime when an older Gateway omits lease metadata',()=>{
 const state=taskState({status:'pending',attempts:1});expect(state.label).toBe('Task state unconfirmed');expect(state.detail).not.toContain('No active');
});
