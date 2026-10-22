import React,{useEffect,useRef,useState} from 'react';
import {errorText} from './api';

export function WorkspaceSearch({api,room,documentRoom,initialQuery='',onDocument,onMessage,onClose}){
 const context=JSON.stringify([room,documentRoom]);
 const [query,setQuery]=useState(initialQuery),[mode,setMode]=useState('messages'),[snapshot,setSnapshot]=useState(null);
 const sequence=useRef(0),locked=useRef(false),dialog=useRef(null),input=useRef(null);
 useEffect(()=>{input.current?.focus();},[]);
 useEffect(()=>{sequence.current++;locked.current=false;setSnapshot(null);return()=>{sequence.current++;locked.current=false;};},[context]);
 const current=snapshot?.context===context&&snapshot.mode===mode?snapshot:null;
 async function search(target=mode,more=false){
  if(locked.current)return;
  const term=more?current?.query:query;if(!term?.trim())return;
  const cursor=more?current?.cursor:null,commit=more?current?.commit:null,expected=++sequence.current;locked.current=true;
  setSnapshot(old=>more?{...old,loading:true,error:''}:{context,mode:target,query:term,results:[],cursor:null,commit:null,loading:true,error:'',skipped:0});
  try{
   const page=target==='messages'?await api.searchMessages(room,term,cursor):await api.searchDocuments(documentRoom,term,cursor,commit);
   if(expected!==sequence.current)return;
   const incoming=target==='messages'?page.events:page.results;
   setSnapshot(old=>{const items=new Map();for(const item of [...(more?old.results:[]),...incoming])items.set(target==='messages'?item.id:item.name,item);return {...old,results:[...items.values()],loading:false,error:'',cursor:target==='messages'?page.next_batch:page.next_path,commit:page.commit??null,skipped:(more?old.skipped:0)+(page.skipped_documents||0)};});
  }catch(error){if(expected===sequence.current)setSnapshot(old=>({...old,loading:false,error:errorText(error)}));}
  finally{if(expected===sequence.current)locked.current=false;}
 }
 function changeMode(next){if(next===mode)return;sequence.current++;locked.current=false;setMode(next);setSnapshot(null);if(query.trim())search(next);}
 function choose(item){const opened=mode==='documents'?onDocument(item):onMessage(item);if(opened===false){setSnapshot(old=>({...old,error:'Finish the current document operation before opening this result.'}));return;}onClose();}
 function keys(event){if(event.key==='Escape'){event.stopPropagation();onClose();}if(event.key==='Tab'){const nodes=[...dialog.current.querySelectorAll('button,input,[href]')].filter(node=>!node.disabled&&node.tabIndex>=0),first=nodes[0],last=nodes.at(-1);if(event.shiftKey&&document.activeElement===first){event.preventDefault();last?.focus();}else if(!event.shiftKey&&document.activeElement===last){event.preventDefault();first?.focus();}}}
 return <div className="search-backdrop"><section className="search-dialog" role="dialog" aria-modal="true" aria-label="Search messages and document text" ref={dialog} onKeyDown={keys}>
  <header><h2>Search body text</h2><button onClick={onClose}>Close search</button></header>
  <form onSubmit={event=>{event.preventDefault();search();}}><label htmlFor="body-search-query">Search term</label><input id="body-search-query" aria-label="Search body text" ref={input} value={query} onChange={event=>setQuery(event.target.value)} maxLength={512}/><button disabled={current?.loading||!query.trim()}>Search</button></form>
  <div className="search-tabs"><button aria-pressed={mode==='messages'} onClick={()=>changeMode('messages')}>Messages</button><button aria-pressed={mode==='documents'} onClick={()=>changeMode('documents')}>Documents</button></div>
  <p className="quiet-status">{mode==='messages'?'Message bodies in the current allowed room · Matrix search':'Markdown bodies in the granted document repository · fixed Git snapshot'}</p>
  {current?.query&&<p>Results for “{current.query}”</p>}{current?.loading&&<p role="status">Searching…</p>}{current?.error&&<p role="alert">{current.error}</p>}
  {current&&!current.loading&&!current.error&&!current.results.length&&!current.cursor&&<p>No matching body text.</p>}
  <ol className="search-results">{current?.results.map(item=><li key={mode==='messages'?item.id:item.name}><button onClick={()=>choose(item)}>{mode==='documents'?`${item.name} · line ${item.line}`:item.sender}</button><p>{mode==='documents'?item.excerpt:item.content.body}</p>{mode==='documents'&&<small>Open matched version {item.commit.slice(0,10)}</small>}</li>)}</ol>
  {current?.skipped>0&&<p role="status">{current.skipped} files exceeded the supported 64 KiB or text encoding limit and were skipped.</p>}
  {current?.cursor&&<button disabled={current.loading} onClick={()=>search(mode,true)}>Load more results</button>}{current?.error&&!current.cursor&&<button disabled={current.loading} onClick={()=>search()}>Retry search</button>}
 </section></div>;
}
