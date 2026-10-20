import {QuotedMessage,replyBody} from './QuotedMessage';
import {AttachmentComposer,FileAttachment} from './Attachments';
import {WorkspaceSearch} from './WorkspaceSearch';
import {useThread} from './useThread';
import React, {useEffect, useMemo, useRef, useState} from 'react';
import {connect, errorText} from './api';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import {BlockEditor} from './BlockEditor';
import {readMarkdown} from './readMarkdown';
import {documentVersion} from './documentReferences';
import {taskResult} from './taskResult';
import {taskState} from './taskState';
import {mergeMessages} from './messageHistory';
import {downloadMarkdown} from './downloadMarkdown';
import {draftContext,useLocalDrafts} from './localDrafts';
import {BookOpen, Search, ChevronDown, ChevronRight, FileText, MessageSquare, Bot, History, Plus, ArrowUp, X, Check, AlertCircle, RefreshCw, Bold, Italic, Heading2, List, Code2} from 'lucide-react';
const short = value => value?.slice(0,10) || 'not created';

export function Composer({onSend, busyRoom, agentId, replyTo, clearReply, onSent, defaultMention=true,quote=null,clearQuote=()=>{}}) {
  const [text,setText]=useState('');
  const [mention,setMention]=useState(defaultMention);
  useEffect(()=>setMention(defaultMention),[defaultMention]);
  const [busy,setBusy]=useState(false);
  const [error,setError]=useState('');
  const attempt=useRef({}), lock=useRef(false),drafts=useRef({}),currentRoom=useRef(busyRoom);
  currentRoom.current=busyRoom;
  useEffect(()=>{setText(drafts.current[busyRoom]||'');setError('');},[busyRoom]);
  const frozen=attempt.current[busyRoom]?.uncertain?attempt.current[busyRoom]:null;
  const shownQuote=frozen?frozen.quote:quote;
  const shownReply=frozen?frozen.replyTo:replyTo;
  async function send(event) {
    event.preventDefault();
    if(lock.current || !text.trim()) return;
    lock.current=true; setBusy(true); setError('');
    let content={msgtype:'m.text',body:text,'m.mentions':{user_ids:mention?[agentId]:[]}};
    if(replyTo) content['m.relates_to']={rel_type:'m.thread',event_id:replyTo};
    if(quote) content['m.relates_to']={...content['m.relates_to'],'m.in_reply_to':{event_id:quote.id}};
    const key=JSON.stringify([busyRoom,content]);
    if(!attempt.current[busyRoom]?.uncertain && attempt.current[busyRoom]?.key!==key) attempt.current[busyRoom]={key,id:crypto.randomUUID(),content,quote,replyTo};
    const operation=attempt.current[busyRoom];content=operation.content;
    try { const result=await onSend(content,operation.id); if(currentRoom.current===busyRoom){setText('');clearReply();clearQuote();} delete drafts.current[busyRoom];delete attempt.current[busyRoom];
       onSent(result.event_id,content['m.mentions'].user_ids.length>0,busyRoom); }
    catch(error){const status=error.httpStatus||error.status;operation.uncertain=!(status>=400&&status<500&&status!==408);if(currentRoom.current===busyRoom)setError(errorText(error));}
    finally {lock.current=false;setBusy(false);}
  }
  return <form className="composer" onSubmit={send}>
    {shownQuote&&<div className="reply-banner">Quoting {shownQuote.sender}: {replyBody(shownQuote.content).slice(0,160)} <button type="button" disabled={busy||Boolean(frozen)} onClick={clearQuote}>Cancel quote</button></div>}
    {shownReply&&<div className="reply-banner">Reply in thread {short(shownReply)} <button type="button" disabled={busy||Boolean(frozen)} onClick={clearReply}>Cancel reply</button></div>}
    <label className="sr-only" htmlFor="message">Message</label>
    <textarea id="message" value={text} onChange={e=>{setText(e.target.value);drafts.current[busyRoom]=e.target.value;}} placeholder="Write a message to this room…" maxLength={4000} disabled={busy||Boolean(frozen)}/>
    <div className="composer-actions"><label><input type="checkbox" checked={mention} onChange={e=>setMention(e.target.checked)} disabled={busy||Boolean(frozen)}/> Mention example Agent</label><button disabled={busy||!text.trim()}>{busy?'Sending…':<>Send <ArrowUp size={15}/></>}</button></div>
    {frozen&&<p role="status">The send result is unknown. Retry keeps the original message and references.</p>}
    {error&&<p className="error" role="alert">{error} <span>Retry sends the same request; your draft is kept.</span></p>}
  </form>;
}

export function Documents(props){
  const context=draftContext(props.api.session,props.room,props.name||'demo.md');
  return <DocumentWorkspace key={context||'unknown'} {...props} localContext={context}/>;
}

function DocumentWorkspace({localContext,api,room,onSent,name='demo.md',externalBusy=false,mode='read',setMode=()=>{},historyOpen=false,onCloseHistory=()=>{},onMeta=()=>{},requestedVersion=null,onDiscussVersion=()=>{},canDiscussVersion=false}) {
  const localDrafts=useLocalDrafts(localContext);
  useEffect(()=>{localDrafts.refresh();},[localContext]);
  const [draftTransition,setDraftTransition]=useState(false),transitionLock=useRef(false);
  const [draftBase,setDraftBase]=useState(undefined),recoveryBase=useRef(null);
  const [snapshot,setSnapshot]=useState(null),[draft,setDraft]=useState(''),[history,setHistory]=useState([]);
  const [error,setError]=useState(''),[notice,setNotice]=useState(''),[operationBusy,setBusy]=useState(false),[historical,setHistorical]=useState(false),[readRetry,setReadRetry]=useState(null);
  const busy=operationBusy||externalBusy;
  const [pending,setPending]=useState(null),[taskProgress,setTaskProgress]=useState(null),[taskPollError,setTaskPollError]=useState(''),[conflict,setConflict]=useState(false),[recoveryDraft,setRecoveryDraft]=useState(null);
  const [sourceChoice,setSourceChoice]=useState(''),[mergeConflict,setMergeConflict]=useState(null),[remoteRecovery,setRemoteRecovery]=useState(null);
  const directRequest=useRef(null);const [directUncertain,setDirectUncertain]=useState(false);
  const [cancelledAction,setCancelledAction]=useState(null),[unresolvedResult,setUnresolvedResult]=useState(false);
  const exportDocument=value=>downloadMarkdown(value,...(name==='demo.md'?[]:[name.split('/').at(-1)]));
  const sources=(api.session.repositoryReads||[]).filter(source=>source.room===room);
  const source=sources.find(item=>JSON.stringify([item.repository,item.path,item.commit])===sourceChoice)||sources[0];
  const lock=useRef(false),attempt=useRef(null), mounted=useRef(true),loadSequence=useRef(0);
  const lastCommand=useRef({action:'write',repository:null});
  const [reading,setReading]=useState(false);
  const editor=useRef(null);
  const [editorRevision,setEditorRevision]=useState(0),[composing,setComposing]=useState(false);
  useEffect(()=>setComposing(false),[mode,editorRevision]);
  const presentation=useMemo(()=>readMarkdown(draft),[draft]);
  const title=snapshot?(presentation.title||name):name;
  useEffect(()=>onMeta({title,commit:snapshot?.commit,blob:snapshot?.blob,recoveryPending:Boolean(localDrafts.warning||localDrafts.records.length||recoveryDraft!==null),reading,composing,dirty:Boolean(snapshot&&draft!==(snapshot.content||'')),busy:busy||directUncertain||draftTransition,draftWorking:localDrafts.working,draftUnsafe:Boolean(snapshot&&draft!==(snapshot.content||'')&&localDrafts.warning),historical}),[title,draft,snapshot,busy,directUncertain,draftTransition,historical,reading,composing,localDrafts.working,localDrafts.warning,localDrafts.records,recoveryDraft]);
  const roomRef=useRef(room);roomRef.current=room;
  async function load(commit, preserveDraft=false) {
    if(directRequest.current||transitionLock.current)return;
    const sequence=++loadSequence.current;setReading(true);setError('');setReadRetry(null);setCancelledAction(null);
    try {const [doc,versions]=await Promise.all([api.document(roomRef.current,commit,...(name==='demo.md'?[]:[name])),api.history(roomRef.current,...(name==='demo.md'?[]:[name]))]);
      if(!mounted.current||sequence!==loadSequence.current)return;if(preserveDraft&&draft!==(snapshot?.content||'')){recoveryBase.current=(draftBase===undefined?snapshot?.blob:draftBase);if(!await localDrafts.checkpoint(draft,recoveryBase.current))throw new Error('Cannot switch versions safely while local draft storage is unavailable. Your current draft is kept; export it before retrying.');if(!mounted.current||sequence!==loadSequence.current)return;setRecoveryDraft(draft);}setDraftBase(undefined);setSnapshot(doc);setUnresolvedResult(false);setDraft(doc.content||'');setEditorRevision(v=>v+1);setHistory(versions.commits);setHistorical(Boolean(commit));setConflict(false);setMergeConflict(null);setRemoteRecovery(null);setNotice('');}
    catch(e){if(sequence===loadSequence.current){setError(errorText(e));setRemoteRecovery(e.data?.status==='remote_diverged'?e.data.recovery:null);setReadRetry({commit,preserveDraft})}}
    finally{if(sequence===loadSequence.current)setReading(false);}
  }
  useEffect(()=>{if(!room)return;mounted.current=true;load();return()=>{mounted.current=false};},[api,Boolean(room)]);
  useEffect(()=>{if(requestedVersion)load(requestedVersion.commit,true)},[requestedVersion]);
  useEffect(()=>{
    if(!pending)return;
    let cancelled=false, checking=false;
    async function check(){if(checking)return;checking=true;
      try {const result=await api.task(pending.room,pending.id);
        if(!cancelled){setTaskProgress(result.task);setTaskPollError('');}
        if(!cancelled&&['failed','cancelled'].includes(result.task?.status)){
          setPending(null);setBusy(false);lock.current=false;attempt.current=null;
          const reasons={task_cancelled:'The task was cancelled.',room_forbidden:'The Agent no longer has access to this room.',delivery_forbidden:'The Agent cannot reply to this room.',attempts_exhausted:'The task reached its retry limit.',room_unavailable:'The room could not be verified.',runtime_error:'The external runtime could not finish the task.'};
          if(result.task.status==='cancelled'){setError('');setCancelledAction(lastCommand.current);}
          else setError((reasons[result.task.last_error]||'The task stopped before completion.')+' Your draft is kept. Restore access or fix the runtime, then retry.');
        }else if(!cancelled&&result.task?.status==='done'){
          setPending(null);setBusy(false);lock.current=false;
          const outcome=taskResult(result.task.outcome,lastCommand.current.action,api.session.synthetic);
          if(!outcome){setUnresolvedResult(true);setError('The runtime returned no supported document result. Your draft is kept. Load latest to inspect Git before sending another request.');setReadRetry({preserveDraft:true,unsupportedResult:true});}
          else if(outcome.status==='conflict'){setConflict(true);setError('A newer document version exists. Your edits are preserved. Load latest to merge.');}
          else if(outcome.status==='rejected')setError(lastCommand.current.repository?'Repository request rejected: check the granted file and requested action.':'Document request rejected: check the action, content and version.');
          else {const saved=outcome.status==='saved';if(saved){setRecoveryDraft(null);localDrafts.clear();}await load(undefined,!saved);setNotice(saved?(api.session.synthetic?'Saved in this browser. No Git backend is connected.':'Saved to Git. The Agent posted a version receipt in the room.'):(api.session.synthetic?'Example Agent read the browser snapshot.':'Agent read through the scoped API. The room contains metadata only.'));}
        }
      }catch(e){if(!cancelled)setTaskPollError(errorText(e)+' Waiting to reconnect; your draft is kept.');}
      finally{checking=false;}}
    check();const timer=setInterval(check,1200);return()=>{cancelled=true;clearInterval(timer)};
  },[pending,api]);
  async function saveDirect(retry=false){
    if(externalBusy||transitionLock.current||(directUncertain&&!retry))return;
    const latest=directRequest.current?.content??(mode==='edit'?(editor.current?.markdown()??draft):draft);
    if(lock.current||reading||unresolvedResult||!snapshot||snapshot.writable===false||composing)return;
    if(new TextEncoder().encode(latest).length>65536){lastCommand.current={action:'write',repository:null};setReadRetry(null);setConflict(false);setError('Document text must contain at most 64 KiB of UTF-8. Your draft is kept.');return;}
    setDraft(latest);lock.current=true;setBusy(true);setError('');setConflict(false);setReadRetry(null);setMergeConflict(null);setNotice('');setCancelledAction(null);
    if(!directRequest.current)directRequest.current={room,content:latest,base_blob:(draftBase===undefined?snapshot.blob:draftBase),operation:crypto.randomUUID()};
    const fixed=directRequest.current;
    lastCommand.current={action:'write',repository:null};
    try{
      const saved=await api.saveDocument(fixed.room,fixed.content,fixed.base_blob,fixed.operation,...(name==='demo.md'?[]:[name]));
      if(saved.status!=='saved'||(saved.path??'demo.md')!==name||!taskResult({version:1,status:'saved',path:name,commit:saved.commit,blob:saved.blob},'write',api.session.synthetic,name))throw new Error('The document service returned an unknown save result. Retry the same request with your draft kept.');
      if(saved.merged!==undefined&&typeof saved.merged!=='boolean'||saved.merged&&(typeof saved.content!=='string'||new TextEncoder().encode(saved.content).length>65536))throw new Error('Merged save result is incomplete. Retry the same request to recover the committed text.');
      const committedContent=saved.merged?saved.content:fixed.content;
      setDraft(committedContent);if(saved.merged)setEditorRevision(v=>v+1);
      directRequest.current=null;setDirectUncertain(false);setRecoveryDraft(null);localDrafts.clear();
      setSnapshot({...snapshot,content:committedContent,commit:saved.commit,blob:saved.blob});setHistorical(false);
      await load(undefined,false);
      setNotice(api.session.synthetic?'Saved in this browser. No Git backend is connected.':saved.merged?('Merged non-overlapping edits with the latest Git version. Saved to Git.'+(saved.receipt_pending?' The discussion receipt is pending.':'')):saved.receipt_pending?'Saved to Git. The discussion receipt is pending; Load latest retries delivery.':'Saved directly to Git. A version receipt is available in the workspace discussion.');
    }catch(e){if(e.status>=400&&e.status<500){directRequest.current=null;setDirectUncertain(false);}else setDirectUncertain(true);if(e.status===409&&e.data?.status==='conflict'){setMergeConflict(typeof e.data.conflict_markdown==='string'?e.data.conflict_markdown:null);setConflict(true);setError('A newer document version exists. Your edits are preserved. Load latest to merge.');}else {setError(errorText(e));setRemoteRecovery(e.data?.status==='remote_diverged'?e.data.recovery:null);}}
    finally{setBusy(false);lock.current=false;}
  }
  async function submit(action,repository=null){
    if(transitionLock.current)return;
    if(action==='write'&&!repository&&api.saveDocument)return saveDirect();
    const latestDraft=mode==='edit'?(editor.current?.markdown()??draft):draft;
    if(action==='write'&&latestDraft.length>6000){setError('Document text must contain at most 6000 characters. Your draft is kept.');return;}
    if(action==='write')setDraft(latestDraft);
    if(lock.current||reading||unresolvedResult||!snapshot||composing||(repository&&action==='report'&&(historical||recoveryDraft!==null||latestDraft!==(snapshot.content||''))))return;lock.current=true;setBusy(true);setError('');setReadRetry(null);setMergeConflict(null);setNotice('');setCancelledAction(null);
    lastCommand.current={action,repository};
    const command=repository?{action,repository:repository.repository,path:repository.path,...(action==='report'?{base_blob:snapshot.blob}:{})}:action==='write'?{action,content:latestDraft,base_blob:(draftBase===undefined?snapshot.blob:draftBase)}:{action, ...(historical?{commit:snapshot.commit}:{})};
    const content={msgtype:'m.text',body:repository?(action==='report'?'Replace demo.md with a deterministic source file report; no LLM.':'Read an explicitly granted source file; no LLM.'):action==='write'?'Save demo.md from workspace':'Read demo.md from Git',
      'm.mentions':{user_ids:[api.session.agentId]},[repository?'org.didadi.repository':'org.didadi.document']:command};
    const key=JSON.stringify([room,content]);if(attempt.current?.key!==key)attempt.current={key,id:crypto.randomUUID()};
    try {const result=await api.send(room,content,attempt.current.id);attempt.current=null;
      setTaskProgress(null);setTaskPollError('');setPending({room,id:result.event_id});onSent(result.event_id,true,room);}
    catch(e){setError(errorText(e));setBusy(false);lock.current=false;}
  }
  function editDraft(value){if(transitionLock.current)return;setDraft(value);localDrafts.persist(value,(draftBase===undefined?snapshot?.blob:draftBase));}
  const dirty=snapshot&&draft!==(snapshot.content||'');
  async function draftAction(action){
    if(transitionLock.current||busy||draftTransition||reading||composing||directUncertain)return;
    transitionLock.current=true;setDraftTransition(true);
    try{await action();}finally{transitionLock.current=false;if(mounted.current)setDraftTransition(false);}
  }
  function restoreLocal(record){if(!snapshot||dirty||recoveryDraft!==null)return;return draftAction(async()=>{if(await localDrafts.restore(record)&&mounted.current){setDraftBase(record.baseBlob);setDraft(record.content);setEditorRevision(v=>v+1);setMode('edit')}});}
  function restorePrevious(value){if(dirty)return;return draftAction(async()=>{if(await localDrafts.persist(value,recoveryBase.current)&&mounted.current){setDraftBase(recoveryBase.current);setDraft(value);setEditorRevision(v=>v+1);setMode('edit')}});}
  function discardCurrent(){return draftAction(async()=>{if(await localDrafts.clear()&&mounted.current){setRecoveryDraft(null);setDraftBase(undefined);setDraft(snapshot.content||'');setEditorRevision(v=>v+1)}});}

  const bodyMarkdown=presentation.body;
  return <section className="document-surface" aria-label="Git document editor">
    <div className="document-statusbar"><span className={historical?'historical-label':'save-state'}>
      {!snapshot?(error?'Document unavailable':'Loading document…'):reading?'Loading version…':historical?<><History size={14}/> Historical version</>:busy?<><RefreshCw size={14} className="spin"/> {api.saveDocument?'Saving directly to Git…':'Saving through example Agent…'}</>:dirty?'Unsaved changes':<><Check size={14}/> All changes saved</>}</span>
      <div>{mode==='edit'&&<button className="primary compact" onClick={()=>submit('write')} disabled={busy||draftTransition||reading||composing||unresolvedResult||directUncertain||!snapshot||snapshot.writable===false}>Save changes</button>}</div>
    </div>
    {snapshot?.writable===false&&<p className="quiet-status" role="status">Read-only document. Room power level 50 is required to save.</p>}
    {directUncertain&&<p className="quiet-status" role="status">Editing is paused while this save is uncertain. Retry sends the exact original request. Your draft is kept.</p>}
    {historical&&<div className="state-banner historical-banner"><History size={17}/><span>You’re viewing an earlier version. Editing it may return a conflict.</span><button disabled={busy||draftTransition||reading||directUncertain} onClick={()=>load(undefined,true)}>Back to latest</button></div>}
    {error&&<div className="state-banner warning" role="alert"><AlertCircle size={18}/><div><strong>{remoteRecovery?'Git histories need operator reconciliation':conflict?'This document has a newer version':'Couldn’t complete the request'}</strong><p>{error}</p>{remoteRecovery&&<details><summary>Retained Git versions</summary><p>Your draft and both Git histories are kept. Export your draft if needed. The workspace operator must review and reconcile the histories before retrying. Retrying does not merge or overwrite them.</p><dl><dt>Local commit</dt><dd><code>{remoteRecovery.local_commit}</code></dd><dt>Remote commit</dt><dd><code>{remoteRecovery.remote_commit}</code></dd><dt>Common base</dt><dd><code>{remoteRecovery.merge_base||'No common base; manual investigation required'}</code></dd></dl></details>}</div>{conflict?<button onClick={()=>load(undefined,true)}>Load latest to merge</button>:<button onClick={()=>directUncertain?saveDirect(true):readRetry?load(readRetry.commit,readRetry.preserveDraft):snapshot?submit(lastCommand.current.action,lastCommand.current.repository):load()}>{remoteRecovery?'Retry after reconciliation':readRetry?.unsupportedResult?'Load latest':'Retry'}</button>}</div>}
    {mergeConflict!==null&&<details className="document-properties"><summary>Overlapping edit details · review only</summary><p>Conflict markers are not saved. Merge your draft with the latest version before saving.</p><textarea aria-label="Conflicting changes" readOnly value={mergeConflict}/></details>}
    {cancelledAction&&<div className="state-banner cancelled-banner" role="status"><Check size={18}/><div><strong>Task cancelled</strong><p>The task was cancelled. Your draft is kept. {cancelledAction.action==='write'?'Choose Save changes to start a new save task.':cancelledAction.action==='report'?'Choose Replace document with file report to start a new report task.':cancelledAction.repository?'Choose Ask Agent to read source to start a new source read task.':'Choose Ask example Agent to read to start a new document read task.'} Cancellation does not undo a change already saved by the runtime.</p></div></div>}
    {notice&&<div className="state-banner success" role="status"><Check size={17}/><span>{notice}</span></div>}
    {pending&&<div className="quiet-status" role="status" aria-label="Document task progress"><strong>{taskState(taskPollError?{status:'reconnecting'}:taskProgress).label}</strong><p>{taskState(taskPollError?{status:'reconnecting'}:taskProgress).detail}</p>{!taskPollError&&taskState(taskProgress).connection&&<p>{taskState(taskProgress).connection}</p>}</div>}
    {pending&&taskPollError&&<p role="alert">{taskPollError}</p>}
    {localDrafts.warning&&<p className="quiet-status" role="alert">{localDrafts.warning}</p>}
    {localDrafts.saved&&!localDrafts.working&&<p className="quiet-status" >Unsaved draft kept on this browser only. Not encrypted; browser storage may be cleared. </p>}
    {localDrafts.working&&<p className="quiet-status">Updating local recovery… Keep this page open until complete.</p>}
    {(dirty||recoveryDraft!==null)&&<button disabled={busy||draftTransition||reading||directUncertain||composing||localDrafts.working} onClick={discardCurrent}>Discard current draft</button>}
    {draftBase!==undefined&&draftBase!==snapshot?.blob&&<p className="quiet-status" role="alert">This draft is based on an older Git version. Saving keeps that base and may conflict. Review and merge the latest text before confirming. <button disabled={busy||draftTransition||reading||directUncertain||composing} onClick={()=>setDraftBase(snapshot.blob)}>I reviewed and merged latest Git text</button></p>}
    <div className="document-scroll">
      {localDrafts.records.map(record=><section className="preserved-draft" aria-label="Local draft recovery" key={record.key}>
        <h2>Unsaved draft found on this browser</h2><p>Git remains the saved version. This local copy is not encrypted or synced. {(!snapshot||record.baseBlob!==snapshot.blob)?'Git has changed since this draft began. Review and merge the latest text before saving.':'Restore to continue editing; nothing is saved to Git automatically.'}</p>
        <details><summary>Review local Markdown</summary><pre>{record.content}</pre></details>
        <button disabled={!snapshot||busy||draftTransition||reading||composing||directUncertain||localDrafts.working||dirty||recoveryDraft!==null} onClick={()=>restoreLocal(record)}>Restore local draft</button>
        <button disabled={busy||draftTransition||reading||composing||directUncertain} onClick={()=>localDrafts.discard(record)}>Discard local draft</button><button disabled={composing} onClick={()=>exportDocument(record.content)}>Export local draft</button>
      </section>)}
      {recoveryDraft!==null&&<PreservedDraft value={recoveryDraft} disabled={busy||draftTransition||reading||composing||directUncertain||localDrafts.working||dirty} onRestore={restorePrevious}/>}
      <div className="document-page">
      {snapshot?<><div className="page-eyebrow"><FileText size={16}/><span>Workspace document · {name}</span></div>{mode!=='edit'&&<h1 className="document-title">{title}</h1>}
        <div className="page-byline"><span className="tiny-avatar">D</span><span>Shared workspace</span><span className="byline-dot"/><span>{api.session.synthetic?'Browser-only snapshot':'Stored in Git'}</span></div>
        {mode==='edit'?<><BlockEditor key={editorRevision} ref={editor} value={draft} onChange={editDraft} onComposingChange={setComposing} disabled={busy||draftTransition||reading||directUncertain}/>
          <div className="editor-foot"><span>{api.saveDocument?`${new TextEncoder().encode(draft).length} / 65536 UTF-8 bytes`:`${draft.length} / 6000 characters`} · Markdown-backed blocks</span><button onClick={()=>load(undefined,true)} disabled={busy||draftTransition||reading||directUncertain}>Load latest</button></div>
        </>:<div className="markdown-body">{presentation.properties&&<details className="document-properties"><summary>Properties · Markdown front matter</summary><pre>{presentation.properties}</pre></details>}{draft?<ReactMarkdown remarkPlugins={[remarkGfm]}>{bodyMarkdown}</ReactMarkdown>:<div className="empty-document"><p>A quiet space for your first document.</p><button className="primary" onClick={()=>setMode('edit')}>Start writing</button></div>}</div>}
        <div className="document-bottom"><span><BookOpen size={14}/> {name}</span><button onClick={()=>onDiscussVersion(snapshot.commit)} disabled={busy||draftTransition||reading||!canDiscussVersion} title={canDiscussVersion?'Open the thread containing this version receipt':'No receipt for this version in the loaded discussion'}>View version discussion</button><button title="Download the current Markdown, including unsaved edits" onClick={()=>exportDocument(mode==='edit'?(editor.current?.markdown()??draft):draft)} disabled={busy||draftTransition||reading||composing}>Export Markdown</button><button onClick={()=>submit('read')} disabled={name!=='demo.md'||busy||draftTransition||reading||unresolvedResult||directUncertain}>Ask example Agent to read</button></div>
        {name!=='demo.md'&&<p className="quiet-status">Human edits and history use this document. Example Agent document actions currently target demo.md only.</p>}
        {name==='demo.md'&&sources.length>0&&<details className="document-properties"><summary>Read-only source repository</summary><p>Explicitly granted files at a fixed Git commit. Deterministic inventory; no LLM analysis.</p><label>Source file <select aria-label="Granted source file" value={source?JSON.stringify([source.repository,source.path,source.commit]):''} onChange={event=>setSourceChoice(event.target.value)} disabled={busy||draftTransition||reading}>{sources.map(item=><option key={JSON.stringify([item.repository,item.path,item.commit])} value={JSON.stringify([item.repository,item.path,item.commit])}>{item.repository} / {item.path}</option>)}</select></label><p>Source commit: <code>{source?.commit}</code></p><div className="document-bottom"><button disabled={busy||draftTransition||reading||composing||unresolvedResult||directUncertain} onClick={()=>submit('read',source)}>Ask Agent to read source</button><button disabled={busy||draftTransition||reading||composing||unresolvedResult||directUncertain||snapshot.writable===false||dirty||historical||recoveryDraft!==null} onClick={()=>submit('report',source)}>Replace document with file report</button></div>{(dirty||historical||recoveryDraft!==null)&&<p>Resolve and save any preserved draft, then return to the latest version before replacing this document. Earlier Git versions remain available.</p>}</details>}
      </>:error?<div className="document-unavailable"><FileText size={30}/><h2>This document is temporarily unavailable</h2><p>Your workspace is still open. Retry above to load the document.</p></div>:<div className="document-skeleton" role="status" aria-label="Loading document"><div/><div/><div/><div/><p>Loading document…</p></div>}
    </div></div>
    {historyOpen&&<aside className="history-panel" aria-label="Version history"><header><h2>Version history</h2><button aria-label="Close history" onClick={onCloseHistory}><X size={17}/></button></header><p>{api.session.synthetic?'Sample snapshots stored in this browser.':'Every version is a fixed Git snapshot.'}</p>{history.length?history.map((commit,i)=><button className="history-row" key={commit} onClick={()=>load(commit,true)} disabled={busy||draftTransition||reading||directUncertain}><span className="version-dot"/><div><strong>{i===0?'Current version':'Previous version'}</strong><code>{short(commit)}</code></div><ChevronRight size={15}/></button>):<div className="panel-empty">Your first save creates the first version.</div>}</aside>}
  </section>;
}


export function PreservedDraft({value,onRestore,disabled=false}) {
  const presentation=useMemo(()=>readMarkdown(value),[value]);
  return <section className="preserved-draft" aria-label="Preserved draft recovery">
    <div className="recovery-heading"><div><h2>Your previous draft is preserved</h2><p>Read the preview, then restore it to merge with the latest version. Restore it to continue editing. Local recovery status is shown above; export a copy if storage is unavailable. Nothing is saved until you choose Save changes.</p></div><button disabled={disabled} onClick={()=>onRestore(value)}>Restore previous draft</button></div>
    <details className="recovery-preview" open><summary>Draft reading preview</summary><div className="markdown-body"><h3>{presentation.title}</h3><ReactMarkdown remarkPlugins={[remarkGfm]}>{presentation.body}</ReactMarkdown></div></details>
    <details className="recovery-source"><summary>Original Markdown · exact preserved text</summary><p>Markdown escapes and character references are source syntax. Restore keeps this exact text, including spacing and front matter.</p><textarea aria-label="Preserved draft" readOnly value={value}/></details>
  </section>;
}

function MessageBody({body='',version,onOpenVersion,disabled=false}) {
  if(version)return <><p>Document version available.</p><button className="thread-link" disabled={disabled} onClick={()=>onOpenVersion(version)}>Open document version</button><details className="receipt-details"><summary>Version details</summary><pre>{body}</pre></details></>;
  return <p>{body}</p>;
}

export function App({connector=connect}) {
  const [api,setApi]=useState(null),[error,setError]=useState(''),[rooms,setRooms]=useState([]),[room,setRoom]=useState('');
  const [quote,setQuote]=useState(null);
  const [events,setEvents]=useState([]),[timelineError,setTimelineError]=useState(''),[roomsError,setRoomsError]=useState(''),[replyTo,setReplyTo]=useState(null),[filter,setFilter]=useState(null);
  const [olderCursor,setOlderCursor]=useState(null),[loadingOlder,setLoadingOlder]=useState(false),[historyError,setHistoryError]=useState(''),[historyNotice,setHistoryNotice]=useState('');
  const loadOlderAction=useRef(null),historyScroll=useRef(null);
  const [tasks,setTasks]=useState([]),[newName,setNewName]=useState(''),[creating,setCreating]=useState(false),[online,setOnline]=useState(false);
  const [panel,setPanel]=useState(null),[mode,setMode]=useState('read'),[historyOpen,setHistoryOpen]=useState(false),[requestedVersion,setRequestedVersion]=useState(null);
  const [documentNames,setDocumentNames]=useState([{name:'demo.md'}]),[activeDocument,setActiveDocument]=useState('demo.md'),[newDocumentName,setNewDocumentName]=useState(''),[documentCreating,setDocumentCreating]=useState(false),[documentsError,setDocumentsError]=useState('');
  const [moveName,setMoveName]=useState(''),[documentMoving,setDocumentMoving]=useState(false),[moveError,setMoveError]=useState('');
  const moveAttempt=useRef(null),moveLock=useRef(false);
  const [selectedMessages,setSelectedMessages]=useState([]),[messagesDocumentName,setMessagesDocumentName]=useState(''),[fromMessagesBusy,setFromMessagesBusy]=useState(false),[fromMessagesUncertain,setFromMessagesUncertain]=useState(false),[fromMessagesNotice,setFromMessagesNotice]=useState('');
  const fromMessagesAttempt=useRef(null),fromMessagesLock=useRef(false);
  useEffect(()=>setSelectedMessages([]),[room]);
  const documentCreateAttempt=useRef(null),documentCreateLock=useRef(false),documentsSequence=useRef(0);
  const [docMeta,setDocMeta]=useState({title:'Workspace document'}),[search,setSearch]=useState(''),[navOpen,setNavOpen]=useState(false);
  const latestDocMeta=useRef(docMeta);latestDocMeta.current=docMeta;
  const [searchOpen,setSearchOpen]=useState(false);
  const searchRef=useRef(null);
  const timelineRef=useRef(null);
  const thread=useThread(api,room,filter,()=>{const node=timelineRef.current;if(node)historyScroll.current={height:node.scrollHeight,top:node.scrollTop};});
  useEffect(()=>{const node=timelineRef.current;if(!node)return;if(historyScroll.current){const before=historyScroll.current;historyScroll.current=null;node.scrollTop=before.top+node.scrollHeight-before.height;}else node.scrollTop=node.scrollHeight;},[filter&&api?.threadPage?thread.events.length:events.length,filter,panel]);
  const roomsFailed=useRef(false),roomsRefreshing=useRef(false);
  const roomCurrent=useRef(room);roomCurrent.current=room;
  useEffect(()=>{if(room&&location.protocol.startsWith('http')){const url=new URL(location.href);url.searchParams.set('room',room);window.history.replaceState({},'',url);}},[room]);
  const createAttempt=useRef(null),createLock=useRef(false);
  async function start(){setError('');try{const next=await connector();const list=await next.rooms();setApi(next);setRooms(list);const requested=new URLSearchParams(location.search).get('room');setRoom(list.some(r=>r.id===requested)?requested:(next.session.initialRoom||list[0]?.id||''));setOnline(true);refreshDocuments(next);}catch(e){setError(errorText(e));}}
  useEffect(()=>{start();},[connector]);
  async function refreshDocuments(current=api){
    if(!current?.documents)return;
    const sequence=++documentsSequence.current;
    try{const result=await current.documents(current.session.documentRoom||current.session.initialRoom);if(sequence!==documentsSequence.current)return;setDocumentNames(result.documents);setDocumentsError('');}
    catch(error){if(sequence!==documentsSequence.current)return;setDocumentsError(errorText(error)+' Document list could not be refreshed; your current document and drafts are kept.');}
  }
  useEffect(()=>{if(api)refreshDocuments();},[api,docMeta.commit]);
  function openDocument(name){if(documentMoving||documentCreating||docMeta.busy||docMeta.reading||docMeta.composing||docMeta.draftWorking||docMeta.draftUnsafe)return;setRequestedVersion(null);setActiveDocument(name);setMode('read');setNavOpen(false);return true;}
  async function createDocument(event){event.preventDefault();if(fromMessagesBusy||documentMoving||documentCreateLock.current||!newDocumentName.trim()||docMeta.busy||docMeta.reading||docMeta.composing||docMeta.draftWorking||docMeta.draftUnsafe)return;
    documentCreateLock.current=true;setDocumentCreating(true);setDocumentsError('');const name=newDocumentName;
    if(documentCreateAttempt.current?.name!==name)documentCreateAttempt.current={name,operation:crypto.randomUUID()};
    try{const created=await api.createDocument(api.session.documentRoom||api.session.initialRoom,name,documentCreateAttempt.current.operation);if(created.status!=='saved'||created.path!==name||!/^[a-f0-9]{40}$/.test(created.commit))throw new Error('Document creation is unconfirmed. Retry the same request.');await refreshDocuments();setDocumentNames(old=>old.some(item=>item.name===name)?old:[...old,{name,blob:created.blob,commit:created.commit}]);setNewDocumentName('');documentCreateAttempt.current=null;const current=latestDocMeta.current;if(current.busy||current.reading||current.composing||current.draftWorking||current.draftUnsafe||current.dirty){setDocumentsError('Document created. Finish or export your current edits before opening it from the list.');return;}setRequestedVersion(null);setActiveDocument(name);setMode('edit');}
    catch(error){setDocumentsError(errorText(error)+' The requested document name is kept. Retry the same request or open an existing document.');}
    finally{documentCreateLock.current=false;setDocumentCreating(false);}
  }
  async function moveDocument(event){event.preventDefault();if(moveLock.current||!moveName.trim())return;
    if(!moveAttempt.current&&(fromMessagesBusy||documentCreating||docMeta.busy||docMeta.reading||docMeta.composing||docMeta.draftWorking||docMeta.dirty||docMeta.recoveryPending||docMeta.historical||!docMeta.blob))return;
    if(!moveAttempt.current)moveAttempt.current={source:activeDocument,name:moveName,base_blob:docMeta.blob,operation:crypto.randomUUID()};
    const attempt=moveAttempt.current;moveLock.current=true;setDocumentMoving(true);setMoveError('');
    try{const moved=await api.moveDocument(documentRoom,attempt);if(moved.status!=='saved'||moved.path!==attempt.name||moved.blob!==attempt.base_blob||!/^[a-f0-9]{40}$/.test(moved.commit))throw new Error('Move result is unconfirmed. Retry the same request.');await refreshDocuments();setDocumentNames(old=>[...old.filter(item=>item.name!==attempt.source&&item.name!==attempt.name),{name:attempt.name,blob:moved.blob,commit:moved.commit}]);setRequestedVersion(null);setActiveDocument(attempt.name);setMode('read');setMoveName('');moveAttempt.current=null;setDocumentMoving(false);}
    catch(error){if(error.status>=400&&error.status<500){moveAttempt.current=null;setDocumentMoving(false);}setMoveError(errorText(error)+' Keep this page open. Retry the same move to confirm its result.');}
    finally{moveLock.current=false;}
  }
  async function createFromMessages(event){event.preventDefault();if(fromMessagesLock.current||documentCreating||documentMoving||!messagesDocumentName.trim()||room!==documentRoom||(!fromMessagesAttempt.current&&!selectedMessages.length))return;
    if(!fromMessagesAttempt.current)fromMessagesAttempt.current={room,name:messagesDocumentName,events:[...selectedMessages],operation:crypto.randomUUID()};
    const attempt=fromMessagesAttempt.current;fromMessagesLock.current=true;setFromMessagesBusy(true);setFromMessagesNotice('');
    try{const created=await api.fromMessages(attempt);if(created.status!=='saved'||created.path!==attempt.name||!/^[a-f0-9]{40}$/.test(created.commit))throw new Error('Document creation is unconfirmed. Retry the same selection.');await refreshDocuments();setDocumentNames(old=>old.some(item=>item.name===attempt.name)?old:[...old,{name:attempt.name,blob:created.blob,commit:created.commit}]);setSelectedMessages([]);setMessagesDocumentName('');setFromMessagesUncertain(false);fromMessagesAttempt.current=null;const current=latestDocMeta.current;if(current.busy||current.reading||current.composing||current.draftWorking||current.draftUnsafe||current.dirty){setFromMessagesNotice('Document created. Finish your current edits, then open it from the list.');return;}setRequestedVersion(null);setActiveDocument(attempt.name);setMode('read');setFromMessagesNotice('Document created with source-message links.');}
    catch(error){const known=error.status>=400&&error.status<500;if(known)fromMessagesAttempt.current=null;setFromMessagesUncertain(!known);setFromMessagesNotice(errorText(error)+(known?' Your selection is kept.':' Retry the same selection to confirm the result.'));}
    finally{fromMessagesLock.current=false;setFromMessagesBusy(false);}
  }
  async function refreshRooms(){if(roomsRefreshing.current)return;roomsRefreshing.current=true;try{const list=await api.rooms();setRooms(list);roomsFailed.current=false;setRoomsError('');}catch(e){roomsFailed.current=true;setRoomsError(errorText(e));}finally{roomsRefreshing.current=false;}}
  useEffect(()=>{if(!api||!room)return;let stopped=false,inFlight=false,initialized=false,olderBusy=false,revision=0,current=[],cursor=null;
    setEvents([]);setReplyTo(null);setQuote(null);setFilter(null);setOlderCursor(null);setLoadingOlder(false);setHistoryError('');setHistoryNotice('');historyScroll.current=null;
    async function refresh(){if(inFlight)return;inFlight=true;try{
      const page=api.timelinePage?await api.timelinePage(room):{events:await api.timeline(room),previousCursor:null};
      if(!stopped){
        const gap=initialized&&current.length&&page.events.length&&!current.some(old=>page.events.some(next=>old.id===next.id));
        if(!initialized||gap){current=page.events;cursor=page.previousCursor;initialized=true;if(gap){revision++;setHistoryNotice('Recent messages advanced beyond the loaded page. Load earlier messages again to reconnect history.');}}
        else current=mergeMessages(current,page.events);
        setEvents(current);setOlderCursor(cursor);setTimelineError('');setOnline(true);if(roomsFailed.current)refreshRooms();
      }
    }catch(e){if(!stopped){setTimelineError(errorText(e));setOnline(false);}}finally{inFlight=false}}
    const older=async()=>{if(stopped||olderBusy||!cursor||!api.timelinePage)return;olderBusy=true;setLoadingOlder(true);setHistoryError('');const expected=revision,from=cursor;
      try{const page=await api.timelinePage(room,from);if(stopped||expected!==revision)return;
        const merged=mergeMessages(page.events,current),node=timelineRef.current;if(node&&merged.length!==current.length)historyScroll.current={height:node.scrollHeight,top:node.scrollTop};
        current=merged;cursor=page.previousCursor===from?null:page.previousCursor;setEvents(current);setOlderCursor(cursor);if(page.events.length)setHistoryNotice('');
      }catch(e){if(!stopped&&expected===revision)setHistoryError(errorText(e)+' Earlier messages were not loaded. Retry; your messages and draft are kept.');}
      finally{olderBusy=false;if(!stopped)setLoadingOlder(false);}
    };
    loadOlderAction.current=older;refresh();const timer=setInterval(refresh,2000);return()=>{stopped=true;clearInterval(timer);if(loadOlderAction.current===older)loadOlderAction.current=null};
  },[api,room]);
  useEffect(()=>{if(!api)return;const timer=setInterval(refreshRooms,10000);return()=>clearInterval(timer)},[api]);
  useEffect(()=>{if(!api||!tasks.some(t=>!['done','failed','cancelled'].includes(t.status)))return;let cancelled=false,inFlight=false;
    const timer=setInterval(async()=>{if(inFlight)return;inFlight=true;const next=await Promise.all(tasks.map(async t=>{if(['done','failed','cancelled'].includes(t.status))return t;try{const result=await api.task(t.room,t.id);return result.task?{...t,...result.task}:{...t,status:'queued',phase:null};}catch{return {...t,status:'reconnecting'};}}));if(!cancelled)setTasks(next);inFlight=false;},1500);
    return()=>{cancelled=true;clearInterval(timer)};
  },[api,tasks]);
  function updateTask(id,patch){setTasks(old=>old.map(task=>task.id===id?{...task,...patch}:task))}
  async function cancelTask(task){
    updateTask(task.id,{cancelling:true,controlError:''});
    try{const result=await api.cancel(task.room,task.id);updateTask(task.id,{status:result.status})}
    catch(error){updateTask(task.id,{controlError:errorText(error)})}
    finally{updateTask(task.id,{cancelling:false})}
  }
  async function taskHistory(task){
    updateTask(task.id,{historyBusy:true,controlError:''});
    try{const result=await api.audit(task.room,task.id);updateTask(task.id,{history:result.events})}
    catch(error){updateTask(task.id,{controlError:errorText(error)})}
    finally{updateTask(task.id,{historyBusy:false})}
  }
  function sent(id,mentioned,sourceRoom=roomCurrent.current){if(mentioned)setTasks(old=>[{id,room:sourceRoom,status:'queued'},...old.filter(t=>t.id!==id)].slice(0,8));}
  async function createRoom(e){e.preventDefault();if(createLock.current||!newName.trim())return;createLock.current=true;setCreating(true);setError('');
    if(createAttempt.current?.name!==newName)createAttempt.current={name:newName,id:crypto.randomUUID()};
    try{const result=await api.createRoom(newName,createAttempt.current.id);await refreshRooms();setRoom(result.room_id);setNewName('');createAttempt.current=null;}
    catch(e){setError(errorText(e));}finally{createLock.current=false;setCreating(false)}}
  if(!api)return <main className="startup"><BookOpen size={30}/><h1>Didadi</h1><p>{error||'Opening your workspace…'}</p>{error&&<button className="primary" onClick={start}>Retry connection</button>}<span>Local workspace · example Agent, no LLM</span></main>;
  const selected=rooms.find(r=>r.id===room);
  const documentRoom=api.session.documentRoom||api.session.initialRoom||room;
  const displayed=filter&&api?.threadPage?thread.events:events.filter(e=>!filter||e.id===filter||e.content['m.relates_to']?.event_id===filter);
  return <>{searchOpen&&<WorkspaceSearch api={api} room={room} documentRoom={documentRoom} initialQuery={search} onClose={()=>setSearchOpen(false)} onDocument={result=>{if(!openDocument(result.name))return false;setRequestedVersion({commit:result.commit});return true;}} onMessage={result=>{setRoom(result.room);setPanel('discussion');setFilter(result.content['m.relates_to']?.rel_type==='m.thread'?result.content['m.relates_to'].event_id:result.id);return true;}}/>}{api.session.synthetic&&<div className="preview-banner" role="note">Interactive UI preview · synthetic browser-only data · no Matrix/Git backend or LLM</div>}<div className="workspace"><aside className={'sidebar '+(navOpen?'nav-open':'')}>
    <div className="workspace-switch"><span className="workspace-logo"><BookOpen size={19}/></span><strong>Didadi</strong><ChevronDown size={15}/><span className="local-pill">{api.session.synthetic?'Preview':'Local'}</span></div>
    <div className="workspace-search"><Search size={16}/><input ref={searchRef} aria-label="Search workspace" placeholder="Search workspace" value={search} onChange={e=>setSearch(e.target.value)}/></div>
    <div className="nav-section"><div className="section-heading"><span>Documents</span><span className="count">{documentNames.length}</span></div>
      <button className="tree-collection" onClick={()=>{setMode('read');setNavOpen(false)}}><ChevronDown size={14}/><BookOpen size={16}/><span>Workspace</span></button>
      {documentNames.filter(item=>!search||item.name.toLowerCase().includes(search.toLowerCase())||(item.name===activeDocument&&docMeta.title.toLowerCase().includes(search.toLowerCase()))).map(item=><button key={item.name} className={'document-tree-item '+(item.name===activeDocument?'selected':'')} aria-current={item.name===activeDocument?'page':undefined} aria-label={item.name+(item.name===activeDocument?', current document':'')} title={item.name===activeDocument?docMeta.title:item.name} disabled={documentMoving||documentCreating||docMeta.busy||docMeta.reading||docMeta.composing||docMeta.draftWorking||docMeta.draftUnsafe} onClick={()=>openDocument(item.name)}><FileText size={16}/><span className="document-identity"><strong>{item.name}</strong>{item.name===activeDocument&&<small>{docMeta.dirty?'Draft title: ':'Title: '}{docMeta.title}</small>}</span></button>)}
      {search&&!documentNames.some(item=>item.name.toLowerCase().includes(search.toLowerCase())||(item.name===activeDocument&&docMeta.title.toLowerCase().includes(search.toLowerCase())))&&<p className="nav-empty">No matching document</p>}
      {api.createDocument&&<form className="new-room" onSubmit={createDocument}><input aria-label="New document path" value={newDocumentName} onChange={event=>setNewDocumentName(event.target.value)} placeholder="New document.md" disabled={documentMoving||documentCreating||docMeta.busy||docMeta.reading||docMeta.composing||docMeta.draftWorking||docMeta.draftUnsafe}/><button aria-label="Create document" disabled={documentCreating||!newDocumentName.trim()||docMeta.busy||docMeta.reading||docMeta.composing||docMeta.draftWorking||docMeta.draftUnsafe}><Plus size={16}/></button></form>}
      {api.moveDocument&&<form className="new-room" onSubmit={moveDocument}><input aria-label="Move document to path" value={moveName} onChange={event=>setMoveName(event.target.value)} placeholder="Move or rename to.md" disabled={documentMoving}/><button aria-label="Move document" disabled={!moveName.trim()||documentCreating||(!moveAttempt.current&&(docMeta.busy||docMeta.reading||docMeta.composing||docMeta.draftWorking||docMeta.dirty||docMeta.recoveryPending||docMeta.historical||!docMeta.blob))}>Move</button></form>}
      {api.moveDocument&&docMeta.recoveryPending&&<p className="quiet-status">Restore or export and discard local recovery drafts before moving this document.</p>}
      {moveError&&<p role="alert">{moveError}</p>}
      {documentsError&&<p role="alert">{documentsError}<button onClick={()=>refreshDocuments()}>Refresh documents</button></p>}
    </div>
    <div className="nav-section rooms-section"><div className="section-heading"><span>Rooms</span><button aria-label="Refresh rooms" onClick={refreshRooms}><RefreshCw size={13}/></button></div>
      <nav aria-label="Rooms">{rooms.filter(r=>r.name.toLowerCase().includes(search.toLowerCase())).map(r=><button className={'room '+(r.id===room?'room-selected':'')} key={r.id} onClick={()=>{setRoom(r.id);setNavOpen(false)}}><MessageSquare size={15}/><span>{r.name}</span></button>)}</nav>
      <form className="new-room" onSubmit={createRoom}><input aria-label="New local room name" value={newName} onChange={e=>setNewName(e.target.value)} placeholder="New local room" maxLength={60} disabled={creating}/><button disabled={creating||!newName.trim()} aria-label="Create local room"><Plus size={16}/></button></form>
    </div>
    <div className="sidebar-bottom"><button className="agent-nav" onClick={()=>setPanel('agent')}><Bot size={17}/><span>Example Agent<small>Echo runtime · no LLM</small></span></button><div className="session-note"><span className={'available-dot '+(!online?'offline':'')}/>{online?(api.session.synthetic?'Browser-only preview':'Connected to local workspace'):'Reconnecting to workspace'}</div></div>
  </aside>
  <main className="main"><header className="workspace-header"><button className="mobile-nav" aria-label="Toggle navigation" onClick={()=>setNavOpen(!navOpen)}><BookOpen size={18}/></button><div className="breadcrumbs"><BookOpen size={15}/><span>Workspace</span><ChevronRight size={13}/><strong>{activeDocument}</strong></div><div className="header-actions">{api.searchMessages&&api.searchDocuments&&<button aria-label="Open full-text search" onClick={()=>setSearchOpen(true)}><Search size={17}/><span>Search</span></button>}<div className="mode-switch"><button aria-pressed={mode==='read'} onClick={()=>setMode('read')}>Read</button><button aria-pressed={mode==='edit'} onClick={()=>setMode('edit')}>Edit</button></div><span className="header-divider"/><button className={historyOpen?'active':''} aria-label="Version history" onClick={()=>setHistoryOpen(!historyOpen)}><History size={17}/></button><button className={panel==='discussion'?'active':''} onClick={()=>setPanel(panel==='discussion'?null:'discussion')}><MessageSquare size={17}/><span>Discussion</span></button><button className={panel==='agent'?'active':''} onClick={()=>setPanel(panel==='agent'?null:'agent')}><Bot size={17}/><span>Agent</span></button></div></header>
    {api.session.qa&&<div className="qa-banner">Visual regression capture · {api.session.qa} · isolated adapter</div>}
    {roomsError&&<div className="global-error" role="alert">Room list is reconnecting: {roomsError}</div>}
    {error&&<div className="global-error" role="alert"><AlertCircle size={16}/>{error}<button onClick={()=>setError('')} aria-label="Dismiss error"><X size={15}/></button></div>}
    <div className="content-layout"><Documents api={api} externalBusy={documentMoving} name={activeDocument} room={documentRoom} onSent={sent} mode={mode} setMode={setMode} historyOpen={historyOpen} onCloseHistory={()=>setHistoryOpen(false)} onMeta={setDocMeta} requestedVersion={requestedVersion} canDiscussVersion={Boolean(docMeta.commit)&&events.some(event=>documentVersion(event,api.session.agentId,api.session.synthetic,api.session.userId,activeDocument)===docMeta.commit)} onDiscussVersion={commit=>{const event=events.find(event=>documentVersion(event,api.session.agentId,api.session.synthetic,api.session.userId,activeDocument)===commit);if(event){setPanel('discussion');setFilter(event.content['m.relates_to']?.event_id||event.id)}}}/>
      <aside className={'collaboration-panel '+(!panel?'panel-closed':'')} aria-label="Collaboration panel"><header className="panel-heading"><div><h2>{panel==='agent'?'Example Agent':'Discussion'}</h2><span>{selected?.name||'Room'}</span></div><button aria-label="Close collaboration panel" onClick={()=>setPanel(null)}><X size={18}/></button></header>
        <div className="panel-tabs"><button className={panel==='discussion'?'active':''} onClick={()=>setPanel('discussion')}>Messages</button><button className={panel==='agent'?'active':''} onClick={()=>setPanel('agent')}>Example Agent</button></div>
        {panel==='agent'&&<div className="agent-disclosure"><Bot size={18}/><div><strong>Deterministic example</strong><p>Repeats messages and handles explicit Git requests. No LLM or intelligent editing is connected.</p></div></div>}
        {api.fromMessages&&<form className="message-document-form" onSubmit={createFromMessages}><p>{selectedMessages.length} messages selected · copies source text with links</p><input aria-label="Document path from messages" value={messagesDocumentName} onChange={event=>setMessagesDocumentName(event.target.value)} placeholder="Discussion notes.md" disabled={fromMessagesBusy||fromMessagesUncertain}/><button disabled={fromMessagesBusy||documentCreating||documentMoving||room!==documentRoom||!messagesDocumentName.trim()||(!fromMessagesAttempt.current&&!selectedMessages.length)}>Create document from messages</button>{room!==documentRoom&&<p>Choose the workspace discussion to create a document.</p>}{fromMessagesNotice&&<p role="status">{fromMessagesNotice}</p>}</form>}
        {filter&&<div className="reply-banner"><span>Thread {short(filter)}</span> · <span>{api.threadPage?'Thread history · load earlier replies':'Loaded messages only'}</span><button onClick={()=>setFilter(null)}>All messages</button></div>}
        {timelineError&&<div className="panel-error" role="alert">{timelineError} Your draft is preserved; reconnecting automatically.</div>}
        <div className="timeline" ref={timelineRef} aria-live="polite">
          {filter&&api.threadPage&&<>{thread.loading&&<p role="status">Loading thread…</p>}{thread.error&&<p role="alert">{thread.error} <button onClick={thread.refresh}>Retry thread</button></p>}{thread.olderError&&<p role="alert">{thread.olderError} <button onClick={thread.older}>Retry earlier thread replies</button></p>}{thread.notice&&<p role="status">{thread.notice}</p>}{thread.cursor&&<button disabled={thread.loadingOlder} onClick={thread.older}>{thread.loadingOlder?'Loading thread replies…':'Load earlier thread replies'}</button>}</>}
          {!filter&&olderCursor&&<button disabled={loadingOlder} onClick={()=>loadOlderAction.current?.()}>{loadingOlder?'Loading earlier messages…':'Load earlier messages'}</button>}
          {!filter&&historyError&&<p role="alert">{historyError}</p>}{!filter&&historyNotice&&<p role="status">{historyNotice}</p>}
          {!displayed.length?<div className="panel-empty"><MessageSquare size={25}/><h3>{filter?'No thread messages loaded':'Start a conversation'}</h3><p>{filter?'Retry the thread request or return to all messages.':'Discuss this workspace, or mention the example Agent to see a real response.'}</p></div>:displayed.map(event=>{
          const agent=event.sender===api.session.agentId,relation=event.content['m.relates_to'];
          const root=relation?.rel_type==='m.thread'?relation.event_id:event.id;
          return <article className={'message '+(agent?'agent':'')} key={event.id}><span className={'avatar '+(agent?'agent-avatar':'')}>{agent?<Bot size={15}/>:'Y'}</span><div className="message-main"><div className="message-meta"><strong>{agent?'Example Agent':event.sender===api.session.userId?'You':event.sender.split(':')[0]}</strong><time>{new Date(event.time||Date.now()).toLocaleTimeString([],{hour:'2-digit',minute:'2-digit'})}</time></div>{relation?.rel_type==='m.thread'&&<button className="thread-link" onClick={()=>setFilter(root)}>Reply in thread</button>}{relation?.['m.in_reply_to']?.event_id&&<QuotedMessage key={room+event.id} api={api} room={room} id={relation['m.in_reply_to'].event_id} onOpen={setFilter}/>} {event.content.msgtype==='m.file'?<FileAttachment api={api} room={room} event={event}/>:<MessageBody body={replyBody(event.content)} version={documentVersion(event,api.session.agentId,api.session.synthetic,api.session.userId,activeDocument)} disabled={docMeta.busy||docMeta.reading||docMeta.composing} onOpenVersion={commit=>{setRequestedVersion({commit});setMode('read');setHistoryOpen(true)}}/>}<div className="message-actions">{api.fromMessages&&<label><input type="checkbox" aria-label={'Select message '+event.id} checked={selectedMessages.includes(event.id)} disabled={Boolean(event.content.msgtype&&!['m.text','m.notice','m.emote'].includes(event.content.msgtype))||fromMessagesBusy||fromMessagesUncertain||room!==documentRoom||(!selectedMessages.includes(event.id)&&selectedMessages.length>=20)} onChange={eventChange=>setSelectedMessages(old=>eventChange.target.checked?[...old,event.id]:old.filter(id=>id!==event.id))}/>Select</label>}<button onClick={()=>{setQuote(null);setReplyTo(root)}}>Reply</button>{api.message&&<button onClick={()=>{setQuote(event);setReplyTo(relation?.rel_type==='m.thread'?root:null)}}>Quote</button>}<button onClick={()=>setFilter(root)}>View thread</button></div></div></article>;
        })}</div>
        <details className="task-details"><summary>Agent activity {tasks.filter(t=>t.room===room).length?`(${tasks.filter(t=>t.room===room).length})`:''}</summary>{tasks.filter(t=>t.room===room).map(t=><div key={t.id} className="task-control"><div className="task">{t.status==='done'?<Check size={13}/>:['failed','cancelled'].includes(t.status)?<AlertCircle size={13}/>:<RefreshCw size={13}/>}<span>{taskState(t).label}</span><code>{short(t.id)}</code></div>{!['done','failed','cancelled'].includes(t.status)&&<p className="quiet-status">{taskState(t).detail} {taskState(t).connection}</p>}
          {!api.session.synthetic&&<div className="message-actions"><button disabled={t.cancelling||!['pending','unverified'].includes(t.status)} onClick={()=>cancelTask(t)}>{t.cancelling?'Cancelling…':'Cancel task'}</button><button disabled={t.historyBusy} onClick={()=>taskHistory(t)}>View execution history</button></div>}
          {t.controlError&&<p role="alert">{t.controlError}</p>}
          {t.history&&<ol aria-label="Task execution history">{t.history.length?t.history.map(entry=><li key={entry.sequence}><span>{({accepted:'Accepted',leased:'Lease granted',result_ready:'Result recorded',completed:'Reply delivered',retry_scheduled:'Retry scheduled',failed:'Failed',cancelled:'Cancelled'})[entry.action]||entry.action}</span>{({room_forbidden:'Room access revoked',delivery_forbidden:'Reply permission revoked',task_cancelled:'Cancelled by request',attempts_exhausted:'Retry limit reached',runtime_error:'Runtime error',room_unavailable:'Room temporarily unavailable'})[entry.reason]&&<span> · {({room_forbidden:'Room access revoked',delivery_forbidden:'Reply permission revoked',task_cancelled:'Cancelled by request',attempts_exhausted:'Retry limit reached',runtime_error:'Runtime error',room_unavailable:'Room temporarily unavailable'})[entry.reason]}</span>}<time> · {new Date(entry.at*1000).toLocaleTimeString()}</time></li>):<li>This task has no recorded execution history.</li>}</ol>}
        </div>)}{!tasks.filter(t=>t.room===room).length&&<p>No tasks sent in this session.</p>}</details>
        <AttachmentComposer api={api} room={room} replyTo={replyTo} onSent={sent}/>
        <Composer busyRoom={room} agentId={api.session.agentId} onSend={(content,id)=>api.send(room,content,id)} onSent={sent} replyTo={replyTo} clearReply={()=>setReplyTo(null)} quote={quote} clearQuote={()=>setQuote(null)} defaultMention={panel==='agent'}/>
      </aside>
    </div>
  </main></div></>;
}
