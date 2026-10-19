import {it,expect} from 'vitest';
import {taskResult} from './taskResult';
const saved={version:1,status:'saved',path:'demo.md',commit:'a'.repeat(40),blob:'b'.repeat(40)};
it('uses typed results independently of any human display text',()=>{
 expect(taskResult(saved,'write')).toEqual(saved);expect(taskResult(saved,'report')).toEqual(saved);
 expect(taskResult(saved,'read')).toBeNull();expect(taskResult({version:1,status:'read'},'read')).toEqual({version:1,status:'read'});
});
it('rejects unknown schemas, invalid references and unexpected metadata',()=>{
 for(const value of [undefined,{version:2,status:'saved'},{version:true,status:'read'},
  {...saved,content:'body'},{...saved,blob:'bad'},{version:1,status:'read',path:'../secret'},
  {version:1,status:'conflict',reason:[]},{version:1,status:'rejected',reason:'arbitrary'},
  {version:1,status:'read',reason:'stale_version'}])expect(taskResult(value,'write')).toBeNull();
 expect(taskResult({version:1,status:'read',path:'../secret'},'read')).toBeNull();
 expect(taskResult({...saved,commit:'sample-123',blob:'sample-123'},'write')).toBeNull();
 expect(taskResult({...saved,commit:'sample-123',blob:'sample-123'},'write',true)).not.toBeNull();
});
