import {beforeEach,describe,it,expect,vi} from 'vitest';
import {LocalDraftStore,draftContext,MAX_DRAFT_RECORDS} from './localDrafts';
const context=draftContext({userId:'@alice:local'},'!docs:local');
beforeEach(()=>localStorage.clear());
describe('bounded local document drafts',()=>{
 it('survives a new editor and isolates user, room, document mode',()=>{
  const first=new LocalDraftStore(context);first.write('---\ntitle: 中文\n---\n# Draft\r\n\\*exact*','a'.repeat(40));
  expect(new LocalDraftStore(context).list()[0].content).toBe('---\ntitle: 中文\n---\n# Draft\r\n\\*exact*');
  for(const other of [draftContext({userId:'@bob:local'},'!docs:local'),draftContext({userId:'@alice:local'},'!other:local'),draftContext({userId:'@alice:local',synthetic:true},'!docs:local')])expect(new LocalDraftStore(other).list()).toEqual([]);
 });
 it('keeps concurrent tabs separate and refuses stale deletes',()=>{
  const first=new LocalDraftStore(context),second=new LocalDraftStore(context);const old=first.write('one','a');second.write('two','a');
  expect(first.list().map(r=>r.content).sort()).toEqual(['one','two']);first.write('newer one','a');
  expect(()=>second.remove(old)).toThrow(/changed in another tab/);expect(first.list().map(r=>r.content)).toContain('newer one');
 });
 it('bounds UTF-8 bytes and total record count without evicting drafts',()=>{
  expect(()=>new LocalDraftStore(context).write('界'.repeat(21846),'a')).toThrow(/64 KiB/);
  for(let i=0;i<MAX_DRAFT_RECORDS;i++)new LocalDraftStore(context).write(String(i),'a');
  expect(()=>new LocalDraftStore(context).write('extra','a')).toThrow(/full/);expect(new LocalDraftStore(context).list()).toHaveLength(MAX_DRAFT_RECORDS);
 });
 it('propagates denied and quota storage failures without a network fallback',()=>{
  const denied=new LocalDraftStore(context,()=>{throw new DOMException('denied','SecurityError');});expect(()=>denied.list()).toThrow();
  const storage={length:0,setItem:vi.fn(()=>{throw new DOMException('full','QuotaExceededError');})};
  expect(()=>new LocalDraftStore(context,()=>storage).write('draft','a')).toThrow();expect(storage.setItem).toHaveBeenCalledOnce();
 });
 it('requires context and refuses malformed matching records',()=>{
  expect(()=>new LocalDraftStore(null).write('draft','a')).toThrow(/known user and room/);
  const store=new LocalDraftStore(context),record=store.write('draft','a');localStorage.setItem(record.key,JSON.stringify({...record,version:99}));expect(()=>store.list()).toThrow(/cannot be read/);
 });
});

it('enforces aggregate storage capacity and does not delete any existing record',()=>{
 localStorage.clear();for(let i=0;i<15;i++)new LocalDraftStore(context).write('x'.repeat(65536),'a');
 expect(()=>new LocalDraftStore(context).write('x'.repeat(65536),'a')).toThrow(/full/);
 expect(new LocalDraftStore(context).list()).toHaveLength(15);
});
it('serializes cooperating tab writes and stale deletes under the same Web Lock',async()=>{
 localStorage.clear();const owner=new LocalDraftStore(context),other=new LocalDraftStore(context);
 const old=await owner.transaction(()=>owner.write('old','a'));
 const write=owner.transaction(()=>owner.write('new','a'));
 const remove=other.transaction(()=>other.remove(old));await write;await expect(remove).rejects.toThrow(/changed in another tab/);
 expect(owner.list()[0].content).toBe('new');
});
it('warns rather than hiding malformed JSON and refuses unsupported coordination',async()=>{
 localStorage.clear();const store=new LocalDraftStore(context);const record=store.write('draft','a');localStorage.setItem(record.key,'{broken');
 expect(()=>store.list()).toThrow(/cannot be read/);
 const locks=navigator.locks;Object.defineProperty(navigator,'locks',{configurable:true,value:undefined});
 try{await expect(store.transaction(()=>store.write('unsafe','a'))).rejects.toThrow(/cannot coordinate/);}finally{Object.defineProperty(navigator,'locks',{configurable:true,value:locks});}
});
