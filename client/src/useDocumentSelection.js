import {useRef,useState} from 'react';
const valid=name=>typeof name==='string'&&name.length>0&&name.length<=1024&&name.endsWith('.md')&&!name.includes('\0');
const keyFor=(api,room)=>api?.session?.userId&&room?JSON.stringify([api.session.synthetic?'synthetic':'matrix',api.session.userId,room]):null;
const prefix='didadi:document-selection:v1:';

// This preference never grants access. The current adapter's list must confirm it.
export function useDocumentSelection(api,room){
 const context=keyFor(api,room),live=useRef(null);
 if(!live.current||live.current.api!==api||live.current.context!==context)live.current={api,context,denied:new Set()};
 const scope=live.current,[record,setRecord]=useState(null);
 const current=record?.scope===scope?record:null;
 const legacy=Boolean(api&&!api.documents);
 const active=()=>live.current===scope;
 function persist(name){if(!context)return '';try{if(name)window.localStorage.setItem(prefix+context,JSON.stringify(name));else window.localStorage.removeItem(prefix+context);return '';}catch{return 'Current document selection cannot be stored on this browser. Your document drafts are separate.';}}
 function remembered(){if(!context)return null;try{const name=JSON.parse(window.localStorage.getItem(prefix+context)||'null');return valid(name)?name:null;}catch{return null;}}
 function acceptList(items,protectedDraft=false){
  if(!active())return;
  if(!Array.isArray(items)||items.some(item=>!valid(item?.name)))throw Error('Document list is unconfirmed. Retry.');
  setRecord(old=>{if(!active())return old;const state=old?.scope===scope?old:null,names=items.filter(item=>!scope.denied.has(item.name));const requested=state?.name||remembered();
   if(requested&&names.some(item=>item.name===requested))return {scope,name:requested,names,warning:state?.warning||'',ready:true};
   if(state?.name&&protectedDraft)return {...state,names,warning:'The selected document is unavailable. Export the current draft before leaving; its recovery data is kept.'};
   const name=names.find(item=>item.name==='demo.md')?.name||names[0]?.name||null;
   return {scope,name,names,ready:true,warning:persist(name)||(requested?'The previous document is unavailable. A listed document was selected; its isolated draft was not deleted.':'')};
  });
 }
 function choose(name){if(!active()||!valid(name))return;setRecord(old=>{if(!active())return old;const state=old?.scope===scope?old:{names:[]};return {...state,scope,name,ready:true,warning:persist(name)};});}
 function setNames(update){if(!active())return;setRecord(old=>{if(!active())return old;const state=old?.scope===scope?old:{scope,name:legacy?'demo.md':null,ready:legacy,warning:'',names:[]};return {...state,names:typeof update==='function'?update(state.names):update};});}
 function deny(name,status,protectedDraft=false){if(!active())return;setRecord(old=>{if(!active())return old;const state=old?.scope===scope?old:{scope,name:legacy?'demo.md':null,names:[]};if(state.name!==name)return state;scope.denied.add(name);if(protectedDraft)return {...state,warning:'Document access is unavailable. Export the current draft before leaving; recovery data is kept.'};const names=[401,403].includes(status)?[]:state.names.filter(item=>item.name!==name),fallback=names.find(item=>item.name==='demo.md')?.name||names[0]?.name||null;return {scope,names,name:fallback,ready:true,warning:persist(fallback)||'Document access is unavailable. Its isolated draft was kept; choose an available document or retry the list.'};});}
 function retry(){if(!active())return;scope.denied.clear();if(legacy)setRecord(null);}
 return {name:current?current.name:(legacy?'demo.md':null),names:current?.names??(legacy?[{name:'demo.md'}]:[]),ready:current?.ready??legacy,warning:current?.warning||'',choose,setNames,acceptList,deny,retry,scope,isCurrent:active};
}
