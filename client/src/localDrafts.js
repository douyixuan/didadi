import {useMemo, useState, useRef} from 'react';

const PREFIX='didadi:document-draft:v1:';
export const MAX_DRAFT_BYTES=65536;
export const MAX_DRAFT_RECORDS=16;
const MAX_TOTAL_BYTES=1048576;
const bytes=value=>new TextEncoder().encode(value).length;
const unavailable='Local draft storage is unavailable. Keep this page open and export your draft before closing.';
export function draftContext(session,room){
  if(!session?.userId||!room)return null;
  return JSON.stringify([session.synthetic?'synthetic':'matrix',session.userId,room,'demo.md']);
}
export class LocalDraftStore {
  constructor(context,storage=()=>window.localStorage){this.context=context;this.storage=storage;this.id=crypto.randomUUID();}
  transaction(action){
    if(!navigator.locks?.request)return Promise.reject(new Error('This browser cannot coordinate local drafts safely. Keep this page open and export before closing.'));
    return navigator.locks.request('didadi-document-drafts-v1',()=>action());
  }
  list(){
    if(!this.context)return [];
    const storage=this.storage(),result=[];
    for(let i=0;i<storage.length;i++){
      const key=storage.key(i);if(!key?.startsWith(PREFIX))continue;
      const raw=storage.getItem(key);let value;try{value=JSON.parse(raw);}catch{throw new Error('A local draft cannot be read. Export current edits before clearing browser storage.');}
      if(value?.context!==this.context)continue;
      if(value.version!==1||typeof value.content!=='string'||bytes(value.content)>MAX_DRAFT_BYTES||(value.baseBlob!==null&&typeof value.baseBlob!=='string')||!Number.isFinite(value.updated)||key!==PREFIX+value.id)throw new Error('A local draft cannot be read. Export current edits before clearing browser storage.');
      result.push({...value,key,raw});
    }
    return result.sort((a,b)=>b.updated-a.updated);
  }
  write(content,baseBlob){
    if(!this.context)throw new Error('Local draft recovery needs a known user and room. Export your edits before closing.');
    if(bytes(content)>MAX_DRAFT_BYTES)throw new Error('This draft exceeds the 64 KiB local recovery limit. Export it before closing.');
    const storage=this.storage(),key=PREFIX+this.id;
    const value={version:1,id:this.id,context:this.context,content,baseBlob:baseBlob??null,updated:Date.now()};
    const raw=JSON.stringify(value);let count=0,total=bytes(key)+bytes(raw);
    for(let i=0;i<storage.length;i++){
      const other=storage.key(i);if(!other?.startsWith(PREFIX)||other===key)continue;
      count++;total+=bytes(other)+bytes(storage.getItem(other)||'');
    }
    if(count>=MAX_DRAFT_RECORDS||total>MAX_TOTAL_BYTES)throw new Error('Local draft storage is full. Export or discard old local drafts before closing.');
    storage.setItem(key,raw);return {...value,key,raw};
  }
  remove(record){
    const storage=this.storage();
    if(storage.getItem(record.key)!==record.raw)throw new Error('That local draft changed in another tab. Reload this page before discarding it.');
    storage.removeItem(record.key);
  }
}
export function useLocalDrafts(context){
  const store=useMemo(()=>new LocalDraftStore(context),[context]);
  const [records,setRecords]=useState([]),[warning,setWarning]=useState(''),[saved,setSaved]=useState(false),[working,setWorking]=useState(false);
  const own=useMemo(()=>({current:null,restored:[]}),[store]),pending=useRef(0);
  async function run(action){pending.current++;setWorking(true);try{const value=await store.transaction(action);setWarning('');return value??true;}catch(error){setWarning(error?.name==='Error'?error.message:unavailable);setSaved(false);return false;}finally{pending.current--;setWorking(pending.current>0);}}
  function refresh(){return run(()=>setRecords(store.list().filter(record=>record.id!==store.id)));}
  function persist(content,baseBlob){setSaved(false);return run(()=>{own.current=store.write(content,baseBlob);setSaved(true);});}
  function discard(record){return run(()=>{store.remove(record);setRecords(items=>items.filter(item=>item.key!==record.key));own.restored=own.restored.filter(item=>item.key!==record.key);});}
  async function restore(record){if(!await persist(record.content,record.baseBlob))return false;own.restored=own.restored.filter(item=>item.key!==record.key).concat(record);setRecords(items=>items.filter(item=>item.key!==record.key));return true;}
  function checkpoint(content,baseBlob){return run(()=>{const record=store.write(content,baseBlob);store.id=crypto.randomUUID();own.current=null;own.restored=own.restored.filter(item=>item.key!==record.key).concat(record);setSaved(false);setRecords(store.list().filter(item=>item.id!==store.id));return record;});}
  function clear(){return run(()=>{
    const storage=store.storage(),targets=[own.current,...own.restored].filter(Boolean);
    for(const record of targets){const raw=storage.getItem(record.key);if(raw!==null&&raw!==record.raw)throw new Error('A recovered draft changed in another tab. Its newer copy has been kept.');}
    for(const record of targets)if(storage.getItem(record.key)!==null)store.remove(record);
    own.current=null;own.restored=[];setSaved(false);setRecords(store.list().filter(record=>record.id!==store.id));
  });}
  return {records,warning,saved,working,refresh,persist,discard,restore,clear,checkpoint};
}
