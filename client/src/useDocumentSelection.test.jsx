import {act,renderHook} from '@testing-library/react';
import {beforeEach,expect,it,vi} from 'vitest';
import {useDocumentSelection} from './useDocumentSelection';
const api=userId=>({session:{userId,synthetic:true},documents:vi.fn()});
const files=[{name:'demo.md'},{name:'Notes.md'}];
beforeEach(()=>localStorage.clear());
it('restores only after a confirmed list and survives a new adapter',()=>{
 const a=api('alice'),first=renderHook(()=>useDocumentSelection(a,'room'));
 act(()=>first.result.current.acceptList(files));act(()=>first.result.current.choose('Notes.md'));first.unmount();
 const restoredApi=api('alice'),next=renderHook(()=>useDocumentSelection(restoredApi,'room'));
 expect(next.result.current.name).toBe(null);
 act(()=>next.result.current.acceptList(files));expect(next.result.current.name).toBe('Notes.md');
});
it('isolates room, identity and stale callbacks, including a mutated session',()=>{
 const a=api('alice');const hook=renderHook(({room})=>useDocumentSelection(a,room),{initialProps:{room:'one'}});
 act(()=>hook.result.current.acceptList(files));act(()=>hook.result.current.choose('Notes.md'));const stale=hook.result.current;
 hook.rerender({room:'two'});act(()=>stale.choose('Notes.md'));expect(hook.result.current.name).toBe(null);
 act(()=>hook.result.current.acceptList(files));expect(hook.result.current.name).toBe('demo.md');
 a.session.userId='bob';hook.rerender({room:'one'});act(()=>hook.result.current.acceptList(files));expect(hook.result.current.name).toBe('demo.md');
 a.session.userId='alice';hook.rerender({room:'one'});act(()=>hook.result.current.acceptList(files));expect(hook.result.current.name).toBe('Notes.md');
});
it('falls back from missing paths without deleting isolated draft records',()=>{
 const a=api('alice'),hook=renderHook(()=>useDocumentSelection(a,'room'));
 localStorage.setItem('isolated-draft','keep');act(()=>hook.result.current.acceptList(files));act(()=>hook.result.current.choose('Notes.md'));
 act(()=>hook.result.current.acceptList([{name:'demo.md'}]));expect(hook.result.current.name).toBe('demo.md');expect(localStorage.getItem('isolated-draft')).toBe('keep');
 expect(hook.result.current.warning).toMatch(/unavailable/);
});
it('does not replace selection on an unconfirmed list and protects unsafe drafts',()=>{
 const a=api('alice'),hook=renderHook(()=>useDocumentSelection(a,'room'));
 act(()=>hook.result.current.acceptList(files));act(()=>hook.result.current.choose('Notes.md'));
 expect(()=>act(()=>hook.result.current.acceptList(null))).toThrow(/unconfirmed/);
 expect(hook.result.current.name).toBe('Notes.md');
 act(()=>hook.result.current.acceptList([{name:'demo.md'}],true));expect(hook.result.current.name).toBe('Notes.md');expect(hook.result.current.warning).toMatch(/Export/);
});
it('does not substitute a default document after room access denial',()=>{
 const a=api('alice'),hook=renderHook(()=>useDocumentSelection(a,'room'));
 act(()=>hook.result.current.acceptList(files));act(()=>hook.result.current.choose('Notes.md'));
 act(()=>hook.result.current.deny('Notes.md',403));expect(hook.result.current.name).toBe(null);expect(hook.result.current.names).toEqual([]);
 act(()=>hook.result.current.retry());act(()=>hook.result.current.acceptList(files));expect(hook.result.current.name).toBe('demo.md');
});
it('keeps a storage error visible while leaving draft storage untouched',()=>{
 const a=api('alice'),hook=renderHook(()=>useDocumentSelection(a,'room'));const spy=vi.spyOn(Storage.prototype,'setItem').mockImplementation(()=>{throw Error('quota')});
 act(()=>hook.result.current.acceptList(files));expect(hook.result.current.name).toBe('demo.md');expect(hook.result.current.warning).toMatch(/cannot be stored/);spy.mockRestore();
});
it('ignores a denied response for a document that is no longer selected',()=>{
 const a=api('alice'),hook=renderHook(()=>useDocumentSelection(a,'room'));act(()=>hook.result.current.acceptList(files));
 act(()=>hook.result.current.choose('Notes.md'));act(()=>hook.result.current.deny('demo.md',403));expect(hook.result.current.name).toBe('Notes.md');
});
it('disables the legacy default after access denial instead of reopening it',()=>{
 const a=api('alice');delete a.documents;const hook=renderHook(()=>useDocumentSelection(a,'room'));expect(hook.result.current.name).toBe('demo.md');act(()=>hook.result.current.deny('demo.md',403));expect(hook.result.current.name).toBe(null);act(()=>hook.result.current.retry());expect(hook.result.current.name).toBe('demo.md');
});
