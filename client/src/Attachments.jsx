import React,{useRef,useState} from 'react';
import {errorText} from './api';
const LIMIT=5*1024*1024;

export function AttachmentComposer({api,room,replyTo,onSent}){
 const drafts=useRef(new Map()),input=useRef(null),currentRoom=useRef(room),[,render]=useState(0);currentRoom.current=room;
 let draft=drafts.current.get(room);if(!draft){draft={file:null,busy:false,uncertain:false,error:'',operation:null,root:null};drafts.current.set(room,draft);}
 const update=()=>render(value=>value+1);
 function select(event){const file=event.target.files?.[0];if(!file)return;if(file.size>LIMIT){draft.error='Attachments must be at most 5 MiB.';event.target.value='';update();return;}draft.file=file;draft.operation=null;draft.error='';draft.uncertain=false;update();}
 async function send(event){event.preventDefault();if(!draft.file||draft.busy)return;const sourceRoom=room,active=draft;if(!active.operation){active.operation=crypto.randomUUID();active.root=replyTo||null;}active.busy=true;active.error='';update();try{
  const result=await api.uploadAttachment(sourceRoom,active.file,active.operation,active.root);if(result.status!=='sent'||(typeof result.event_id!=='string'||!result.event_id.startsWith('$')||result.event_id.length>512))throw new Error('Attachment result is unconfirmed. Retry the same file.');active.file=null;active.operation=null;active.uncertain=false;if(input.current&&currentRoom.current===sourceRoom)input.current.value='';onSent(result.event_id,false,sourceRoom);
 }catch(error){active.error=errorText(error)+' Your file selection is kept.';active.uncertain=!(error.status>=400&&error.status<500);}finally{active.busy=false;update();}}
 if(!api.uploadAttachment)return null;
 return <form className="attachment-composer" aria-label="File attachment" onSubmit={send}>
  <label>Attach file <input aria-label="Attach file" type="file" ref={input} key={room} disabled={draft.busy||draft.uncertain} onChange={select}/></label>
  {draft.file&&<div><span>{draft.file.name} · {draft.file.size} bytes</span><button type="submit" disabled={draft.busy}>{draft.busy?'Sending attachment…':'Send attachment'}</button><button type="button" disabled={draft.busy||draft.uncertain} onClick={()=>{draft.file=null;draft.operation=null;if(input.current)input.current.value='';update();}}>Clear file</button></div>}
  {draft.uncertain&&<p role="status">The result is uncertain. Retry the same file and original thread before choosing another file.</p>}{draft.error&&<p role="alert">{draft.error}</p>}
 </form>;
}

export function FileAttachment({api,room,event}){
 const [busy,setBusy]=useState(false),[error,setError]=useState(''),lock=useRef(false);const name=typeof event.content.filename==='string'?event.content.filename:typeof event.content.body==='string'?event.content.body:'attachment';
 async function download(){if(lock.current)return;lock.current=true;setBusy(true);setError('');try{const file=await api.downloadAttachment(room,event.id);const url=URL.createObjectURL(file.blob),link=document.createElement('a');try{link.href=url;link.download=file.name;document.body.append(link);link.click();}finally{link.remove();setTimeout(()=>URL.revokeObjectURL(url),1000);}}catch(failure){setError(errorText(failure)+' Retry download.');}finally{lock.current=false;setBusy(false);}}
 return <div className="file-attachment"><strong>{name}</strong>{typeof event.content.info?.size==='number'&&<small>{event.content.info.size} bytes</small>}{api.downloadAttachment?<button disabled={busy} onClick={download}>{busy?'Downloading…':'Download '+name}</button>:<p>File download requires the local backend.</p>}{error&&<p role="alert">{error}</p>}</div>;
}
