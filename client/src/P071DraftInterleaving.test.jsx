// Deterministic DOM/storage only. Fake CAS does not prove real concurrent Git writes.
import React from 'react';
import {render,within,fireEvent,waitFor} from '@testing-library/react';
import {expect,it,vi} from 'vitest';
vi.mock('./api',()=>({connect:()=>{throw Error('No transport')},errorText:error=>error.message}));
vi.mock('./BlockEditor',()=>({BlockEditor:React.forwardRef(function Editor({value,onChange,disabled},ref){
  React.useImperativeHandle(ref,()=>({markdown:()=>value}));
  return <textarea aria-label="Markdown document" value={value} disabled={disabled} onChange={e=>onChange(e.target.value)}/>;
})}));
import {Documents} from './App';
it('P071: conflict A and failed B recover separate original bases; saving B never clears unresolved A',async()=>{
  const base='a'.repeat(40),room='!draft-test:invalid',mineA='# A conflict 中文',mineB='# B network 中文';
  // Equal initial blobs expose draft keys incorrectly based on blob instead of path.
  const files=new Map(['A.md','B.md'].map(name=>[name,{name,content:'# '+name,blob:base,commit:'c'.repeat(40),writable:true}]));
  let failB=true;
  const api={session:{userId:'@draft-test:invalid',agentId:'@unused:invalid'},
    document:vi.fn(async(_room,_commit,name)=>({...files.get(name)})),history:vi.fn(async()=>({commits:[]})),
    saveDocument:vi.fn(async(_room,content,expected,_operation,name)=>{
      if(name==='B.md'&&failB){failB=false;throw new TypeError('Synthetic pre-write network failure');}
      const before=files.get(name);
      if(expected!==before.blob)throw Object.assign(Error('Synthetic stale base'),{status:409,data:{status:'conflict'}});
      const next={...before,content,blob:'d'.repeat(40),commit:'e'.repeat(40)};files.set(name,next);
      return {status:'saved',path:name,blob:next.blob,commit:next.commit};
    })};
  const mount=name=>{const v=render(<Documents api={api} room={room} name={name} mode="edit" onSent={()=>{}}/>);return {...v,q:within(v.container)};};
  const edit=(v,text)=>fireEvent.change(v.q.getByLabelText('Markdown document'),{target:{value:text}});
  const save=v=>fireEvent.click(v.q.getByRole('button',{name:'Save changes'}));
  const a=mount('A.md'),b=mount('B.md');
  await a.q.findByLabelText('Markdown document');await b.q.findByLabelText('Markdown document');
  edit(a,mineA);edit(b,mineB);
  await a.q.findByText(/Unsaved draft kept/);await b.q.findByText(/Unsaved draft kept/);
  files.set('A.md',{...files.get('A.md'),content:'# A external writer',blob:'b'.repeat(40)});
  save(a);await a.q.findByText('This document has a newer version');
  save(b);await b.q.findByText('Synthetic pre-write network failure');
  expect(a.q.getByLabelText('Markdown document')).toHaveValue(mineA);
  expect(b.q.getByLabelText('Markdown document')).toHaveValue(mineB);
  expect(b.q.getByLabelText('Markdown document')).toBeDisabled();
  expect(api.saveDocument.mock.calls.map(c=>[c[2],c[4]])).toEqual([[base,'A.md'],[base,'B.md']]);
  a.unmount();b.unmount();
  // A remount retaining jsdom localStorage approximates refresh, not browser/server restart.
  const ra=mount('A.md'),rb=mount('B.md');
  await ra.q.findByLabelText('Local draft recovery');await rb.q.findByLabelText('Local draft recovery');
  expect(ra.q.getByLabelText('Markdown document')).toHaveValue('# A external writer');
  expect(rb.q.getByLabelText('Markdown document')).toHaveValue('# B.md');
  expect(ra.q.getByText(mineA,{selector:'pre'})).toBeInTheDocument();
  expect(ra.q.queryByText(mineB,{selector:'pre'})).not.toBeInTheDocument();
  expect(rb.q.getByText(mineB,{selector:'pre'})).toBeInTheDocument();
  expect(rb.q.queryByText(mineA,{selector:'pre'})).not.toBeInTheDocument();
  expect(api.saveDocument).toHaveBeenCalledTimes(2); // Recovery must not auto-save.
  for(const v of [ra,rb]){
    await waitFor(()=>expect(v.q.getByRole('button',{name:'Restore local draft'})).toBeEnabled());
    fireEvent.click(v.q.getByRole('button',{name:'Restore local draft'}));
  }
  await waitFor(()=>expect(ra.q.getByLabelText('Markdown document')).toHaveValue(mineA));
  await waitFor(()=>expect(rb.q.getByLabelText('Markdown document')).toHaveValue(mineB));
  save(ra);await ra.q.findByText('This document has a newer version');
  expect(api.saveDocument.mock.calls[2][2]).toBe(base); // Do not adopt the external writer's base.
  save(rb);await rb.q.findByText(/Saved directly to Git/);
  expect(api.saveDocument.mock.calls[3][2]).toBe(base);
  expect(files.get('A.md').content).toBe('# A external writer');expect(files.get('B.md').content).toBe(mineB);
  ra.unmount();rb.unmount();
  const finalA=mount('A.md'),finalB=mount('B.md');
  await finalA.q.findAllByLabelText('Local draft recovery');await finalB.q.findByLabelText('Markdown document');
  // Restoring conservatively retains the original plus the restored working copy.
  expect(finalA.q.getAllByText(mineA,{selector:'pre'}).length).toBeGreaterThan(0);
  expect(finalA.q.queryByText(mineB,{selector:'pre'})).not.toBeInTheDocument();
  expect(finalB.q.queryByLabelText('Local draft recovery')).not.toBeInTheDocument();
  expect(finalB.q.getByLabelText('Markdown document')).toHaveValue(mineB);
  expect(api.saveDocument).toHaveBeenCalledTimes(4);
});
