import React, {useEffect, useMemo, useRef, useState} from 'react';
import {connect, errorText} from './api';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import {BlockEditor} from './BlockEditor';
import {readMarkdown} from './readMarkdown';
import {BookOpen, Search, ChevronDown, ChevronRight, FileText, MessageSquare, Bot, History, Plus, ArrowUp, X, Check, AlertCircle, RefreshCw, Bold, Italic, Heading2, List, Code2} from 'lucide-react';
const short = value => value?.slice(0,10) || 'not created';

export function Composer({onSend, busyRoom, agentId, replyTo, clearReply, onSent, defaultMention=true}) {
  const [text,setText]=useState('');
  const [mention,setMention]=useState(defaultMention);
  useEffect(()=>setMention(defaultMention),[defaultMention]);
  const [busy,setBusy]=useState(false);
  const [error,setError]=useState('');
  const attempt=useRef(null), lock=useRef(false),drafts=useRef({}),currentRoom=useRef(busyRoom);
  currentRoom.current=busyRoom;
  useEffect(()=>{setText(drafts.current[busyRoom]||'');setError('');},[busyRoom]);
  async function send(event) {
    event.preventDefault();
    if(lock.current || !text.trim()) return;
    lock.current=true; setBusy(true); setError('');
    const content={msgtype:'m.text',body:text,'m.mentions':{user_ids:mention?[agentId]:[]}};
    if(replyTo) content['m.relates_to']={rel_type:'m.thread',event_id:replyTo};
    const key=JSON.stringify([busyRoom,content]);
    if(attempt.current?.key!==key) attempt.current={key,id:crypto.randomUUID()};
    try { const result=await onSend(content,attempt.current.id); if(currentRoom.current===busyRoom){setText('');clearReply();} delete drafts.current[busyRoom];attempt.current=null;
       onSent(result.event_id,mention,busyRoom); }
    catch(error){setError(errorText(error));}
    finally {lock.current=false;setBusy(false);}
  }
  return <form className="composer" onSubmit={send}>
    {replyTo&&<div className="reply-banner">Reply in thread {short(replyTo)} <button type="button" onClick={clearReply}>Cancel reply</button></div>}
    <label className="sr-only" htmlFor="message">Message</label>
    <textarea id="message" value={text} onChange={e=>{setText(e.target.value);drafts.current[busyRoom]=e.target.value;}} placeholder="Write a message to this room…" maxLength={4000} disabled={busy}/>
    <div className="composer-actions"><label><input type="checkbox" checked={mention} onChange={e=>setMention(e.target.checked)} disabled={busy}/> Mention example Agent</label><button disabled={busy||!text.trim()}>{busy?'Sending…':<>Send <ArrowUp size={15}/></>}</button></div>
    {error&&<p className="error" role="alert">{error} <span>Retry sends the same request; your draft is kept.</span></p>}
  </form>;
}

export function Documents({api,room,onSent,mode='read',setMode=()=>{},historyOpen=false,onCloseHistory=()=>{},onMeta=()=>{}}) {
  const [snapshot,setSnapshot]=useState(null),[draft,setDraft]=useState(''),[history,setHistory]=useState([]);
  const [error,setError]=useState(''),[notice,setNotice]=useState(''),[busy,setBusy]=useState(false),[historical,setHistorical]=useState(false);
  const [pending,setPending]=useState(null),[conflict,setConflict]=useState(false),[recoveryDraft,setRecoveryDraft]=useState(null);
  const lock=useRef(false),attempt=useRef(null), mounted=useRef(true),loadSequence=useRef(0);
  const [reading,setReading]=useState(false);
  const editor=useRef(null);
  const [editorRevision,setEditorRevision]=useState(0),[composing,setComposing]=useState(false);
  useEffect(()=>setComposing(false),[mode,editorRevision]);
  const presentation=useMemo(()=>readMarkdown(draft),[draft]);
  const title=snapshot?presentation.title:'demo.md';
  useEffect(()=>onMeta({title,dirty:Boolean(snapshot&&draft!==(snapshot.content||'')),busy,historical}),[title,draft,snapshot,busy,historical]);
  const roomRef=useRef(room);roomRef.current=room;
  async function load(commit, preserveDraft=false) {
    const sequence=++loadSequence.current;setReading(true);setError('');
    try {const [doc,versions]=await Promise.all([api.document(roomRef.current,commit),api.history(roomRef.current)]);
      if(!mounted.current||sequence!==loadSequence.current)return;if(preserveDraft&&draft!==(snapshot?.content||''))setRecoveryDraft(draft);setSnapshot(doc);setDraft(doc.content||'');setEditorRevision(v=>v+1);setHistory(versions.commits);setHistorical(Boolean(commit));setConflict(false);setNotice('');}
    catch(e){if(sequence===loadSequence.current)setError(errorText(e));}
    finally{if(sequence===loadSequence.current)setReading(false);}
  }
  useEffect(()=>{if(!room)return;mounted.current=true;load();return()=>{mounted.current=false};},[api,Boolean(room)]);
  useEffect(()=>{
    if(!pending)return;
    let cancelled=false, checking=false;
    async function check(){if(checking)return;checking=true;
      try {const result=await api.task(pending.room,pending.id);
        if(!cancelled&&result.task?.status==='failed'){
          setPending(null);setBusy(false);lock.current=false;attempt.current=null;
          const reasons={room_forbidden:'The Agent no longer has access to this room.',delivery_forbidden:'The Agent cannot reply to this room.',attempts_exhausted:'The task reached its retry limit.',room_unavailable:'The room could not be verified.',runtime_error:'The external runtime could not finish the task.'};
          setError((reasons[result.task.last_error]||'The task stopped before completion.')+' Your draft is kept. Restore access or fix the runtime, then retry.');
        }else if(!cancelled&&result.task?.status==='done'){
          setPending(null);setBusy(false);lock.current=false;
          const body=result.task.body||'';
          if(body.startsWith('Document conflict:')){setConflict(true);setError('A newer document version exists. Your edits are preserved. Load latest to merge.');}
          else if(body.startsWith('Document request rejected:'))setError(body);
          else {if(body.startsWith('Saved'))setRecoveryDraft(null);await load(undefined,!body.startsWith('Saved'));setNotice(body.startsWith('Saved')?(api.session.synthetic?'Saved in this browser. No Git backend is connected.':'Saved to Git. The Agent posted a version receipt in the room.'):(api.session.synthetic?'Example Agent read the browser snapshot.':'Agent read the Git version. See the room timeline.'));}
        }
      }catch(e){if(!cancelled)setError(errorText(e)+' Waiting to reconnect; your draft is kept.');}
      finally{checking=false;}}
    check();const timer=setInterval(check,1200);return()=>{cancelled=true;clearInterval(timer)};
  },[pending,api]);
  async function submit(action){
    const latestDraft=mode==='edit'?(editor.current?.markdown()??draft):draft;
    if(action==='write'&&latestDraft.length>6000){setError('Document text must contain at most 6000 characters. Your draft is kept.');return;}
    if(action==='write')setDraft(latestDraft);
    if(lock.current||!snapshot||composing)return;lock.current=true;setBusy(true);setError('');setNotice('');
    const command=action==='write'?{action,content:latestDraft,base_blob:snapshot.blob}:{action, ...(historical?{commit:snapshot.commit}:{})};
    const content={msgtype:'m.text',body:action==='write'?'Save demo.md from workspace':'Read demo.md from Git',
      'm.mentions':{user_ids:[api.session.agentId]},'org.didadi.document':command};
    const key=JSON.stringify([room,content]);if(attempt.current?.key!==key)attempt.current={key,id:crypto.randomUUID()};
    try {const result=await api.send(room,content,attempt.current.id);attempt.current=null;
      setPending({room,id:result.event_id});onSent(result.event_id,true,room);}
    catch(e){setError(errorText(e));setBusy(false);lock.current=false;}
  }
  const dirty=snapshot&&draft!==(snapshot.content||'');
  const bodyMarkdown=presentation.body;
  return <section className="document-surface" aria-label="Git document editor">
    <div className="document-statusbar"><span className={historical?'historical-label':'save-state'}>
      {!snapshot?(error?'Document unavailable':'Loading document…'):reading?'Loading version…':historical?<><History size={14}/> Historical version</>:busy?<><RefreshCw size={14} className="spin"/> Saving through example Agent…</>:dirty?'Unsaved changes':<><Check size={14}/> All changes saved</>}</span>
      <div>{mode==='edit'&&<button className="primary compact" onClick={()=>submit('write')} disabled={busy||reading||composing||!snapshot}>Save changes</button>}</div>
    </div>
    {historical&&<div className="state-banner historical-banner"><History size={17}/><span>You’re viewing an earlier version. Editing it may return a conflict.</span><button onClick={()=>load(undefined,true)}>Back to latest</button></div>}
    {error&&<div className="state-banner warning" role="alert"><AlertCircle size={18}/><div><strong>{conflict?'This document has a newer version':'Couldn’t complete the request'}</strong><p>{error}</p></div>{conflict?<button onClick={()=>load(undefined,true)}>Load latest to merge</button>:<button onClick={()=>snapshot?submit('write'):load()}>Retry</button>}</div>}
    {notice&&<div className="state-banner success" role="status"><Check size={17}/><span>{notice}</span></div>}
    {pending&&<p className="quiet-status" role="status">Your request is queued. The example runtime will post the result in the room.</p>}
    {recoveryDraft!==null&&<div className="state-banner warning"><div><strong>Your previous draft is preserved</strong><p>Compare it with the latest version below, then merge your changes.</p><textarea aria-label="Preserved draft" readOnly value={recoveryDraft}/></div><button onClick={()=>{setDraft(recoveryDraft);setEditorRevision(v=>v+1);setMode('edit')}}>Restore previous draft</button></div>}
    <div className="document-scroll"><div className="document-page">
      {snapshot?<><div className="page-eyebrow"><FileText size={16}/><span>Workspace document</span></div>{mode!=='edit'&&<h1 className="document-title">{title}</h1>}
        <div className="page-byline"><span className="tiny-avatar">D</span><span>Shared workspace</span><span className="byline-dot"/><span>{api.session.synthetic?'Browser-only snapshot':'Stored in Git'}</span></div>
        {mode==='edit'?<><BlockEditor key={editorRevision} ref={editor} value={draft} onChange={setDraft} onComposingChange={setComposing} disabled={busy||reading}/>
          <div className="editor-foot"><span>{draft.length} / 6000 characters · Markdown-backed blocks</span><button onClick={()=>load(undefined,true)} disabled={busy}>Load latest</button></div>
        </>:<div className="markdown-body">{presentation.properties&&<details className="document-properties"><summary>Properties · Markdown front matter</summary><pre>{presentation.properties}</pre></details>}{draft?<ReactMarkdown remarkPlugins={[remarkGfm]}>{bodyMarkdown}</ReactMarkdown>:<div className="empty-document"><p>A quiet space for your first document.</p><button className="primary" onClick={()=>setMode('edit')}>Start writing</button></div>}</div>}
        <div className="document-bottom"><span><BookOpen size={14}/> demo.md</span><button onClick={()=>submit('read')} disabled={busy}>Ask example Agent to read</button></div>
      </>:error?<div className="document-unavailable"><FileText size={30}/><h2>This document is temporarily unavailable</h2><p>Your workspace is still open. Retry above to load the document.</p></div>:<div className="document-skeleton" role="status" aria-label="Loading document"><div/><div/><div/><div/><p>Loading document…</p></div>}
    </div></div>
    {historyOpen&&<aside className="history-panel" aria-label="Version history"><header><h2>Version history</h2><button aria-label="Close history" onClick={onCloseHistory}><X size={17}/></button></header><p>{api.session.synthetic?'Sample snapshots stored in this browser.':'Every version is a fixed Git snapshot.'}</p>{history.length?history.map((commit,i)=><button className="history-row" key={commit} onClick={()=>load(commit,true)} disabled={busy||reading}><span className="version-dot"/><div><strong>{i===0?'Current version':'Previous version'}</strong><code>{short(commit)}</code></div><ChevronRight size={15}/></button>):<div className="panel-empty">Your first save creates the first version.</div>}</aside>}
  </section>;
}

function MessageBody({body=''}) {
  if(body.startsWith('Saved demo.md\nGit commit:'))return <><p>Document saved.</p><details className="receipt-details"><summary>Version details</summary><pre>{body.split('\n').slice(1).join('\n')}</pre></details></>;
  if(body.startsWith('demo.md at Git commit:'))return <><p>{body.split('\n').slice(2).join('\n')}</p><details className="receipt-details"><summary>Read version</summary><code>{body.split('\n')[0]}</code></details></>;
  return <p>{body}</p>;
}

export function App({connector=connect}) {
  const [api,setApi]=useState(null),[error,setError]=useState(''),[rooms,setRooms]=useState([]),[room,setRoom]=useState('');
  const [events,setEvents]=useState([]),[timelineError,setTimelineError]=useState(''),[replyTo,setReplyTo]=useState(null),[filter,setFilter]=useState(null);
  const [tasks,setTasks]=useState([]),[newName,setNewName]=useState(''),[creating,setCreating]=useState(false),[online,setOnline]=useState(false);
  const [panel,setPanel]=useState(null),[mode,setMode]=useState('read'),[historyOpen,setHistoryOpen]=useState(false);
  const [docMeta,setDocMeta]=useState({title:'Workspace document'}),[search,setSearch]=useState(''),[navOpen,setNavOpen]=useState(false);
  const searchRef=useRef(null);
  const timelineRef=useRef(null);
  useEffect(()=>{if(timelineRef.current)timelineRef.current.scrollTop=timelineRef.current.scrollHeight;},[events.length,filter,panel]);
  const roomCurrent=useRef(room);roomCurrent.current=room;
  useEffect(()=>{if(room&&location.protocol.startsWith('http')){const url=new URL(location.href);url.searchParams.set('room',room);window.history.replaceState({},'',url);}},[room]);
  const createAttempt=useRef(null),createLock=useRef(false);
  async function start(){setError('');try{const next=await connector();const list=await next.rooms();setApi(next);setRooms(list);const requested=new URLSearchParams(location.search).get('room');setRoom(list.some(r=>r.id===requested)?requested:(next.session.initialRoom||list[0]?.id||''));setOnline(true);}catch(e){setError(errorText(e));}}
  useEffect(()=>{start();},[connector]);
  async function refreshRooms(){try{const list=await api.rooms();setRooms(list);}catch(e){setError(errorText(e));}}
  useEffect(()=>{if(!api||!room)return;let stopped=false,inFlight=false;setEvents([]);setReplyTo(null);setFilter(null);
    async function refresh(){if(inFlight)return;inFlight=true;try{const result=await api.timeline(room);if(!stopped){setEvents(result);setTimelineError('');setOnline(true);}}
      catch(e){if(!stopped){setTimelineError(errorText(e));setOnline(false);}}finally{inFlight=false}}
    refresh();const timer=setInterval(refresh,2000);return()=>{stopped=true;clearInterval(timer)};
  },[api,room]);
  useEffect(()=>{if(!api)return;const timer=setInterval(refreshRooms,10000);return()=>clearInterval(timer)},[api]);
  useEffect(()=>{if(!api||!tasks.some(t=>t.status!=='done'))return;let cancelled=false;
    const timer=setInterval(async()=>{const next=await Promise.all(tasks.map(async t=>{if(t.status==='done')return t;try{const result=await api.task(t.room,t.id);return {...t,status:result.task?.status||'queued',body:result.task?.body};}catch{return {...t,status:'reconnecting'};}}));if(!cancelled)setTasks(next);},1500);
    return()=>{cancelled=true;clearInterval(timer)};
  },[api,tasks]);
  function sent(id,mentioned,sourceRoom=roomCurrent.current){if(mentioned)setTasks(old=>[{id,room:sourceRoom,status:'queued'},...old.filter(t=>t.id!==id)].slice(0,8));}
  async function createRoom(e){e.preventDefault();if(createLock.current||!newName.trim())return;createLock.current=true;setCreating(true);setError('');
    if(createAttempt.current?.name!==newName)createAttempt.current={name:newName,id:crypto.randomUUID()};
    try{const result=await api.createRoom(newName,createAttempt.current.id);await refreshRooms();setRoom(result.room_id);setNewName('');createAttempt.current=null;}
    catch(e){setError(errorText(e));}finally{createLock.current=false;setCreating(false)}}
  if(!api)return <main className="startup"><BookOpen size={30}/><h1>Didadi</h1><p>{error||'Opening your workspace…'}</p>{error&&<button className="primary" onClick={start}>Retry connection</button>}<span>Local workspace · example Agent, no LLM</span></main>;
  const selected=rooms.find(r=>r.id===room);
  const displayed=events.filter(e=>!filter||e.id===filter||e.content['m.relates_to']?.event_id===filter);
  return <>{api.session.synthetic&&<div className="preview-banner" role="note">Interactive UI preview · synthetic browser-only data · no Matrix/Git backend or LLM</div>}<div className="workspace"><aside className={'sidebar '+(navOpen?'nav-open':'')}>
    <div className="workspace-switch"><span className="workspace-logo"><BookOpen size={19}/></span><strong>Didadi</strong><ChevronDown size={15}/><span className="local-pill">{api.session.synthetic?'Preview':'Local'}</span></div>
    <div className="workspace-search"><Search size={16}/><input ref={searchRef} aria-label="Search workspace" placeholder="Search workspace" value={search} onChange={e=>setSearch(e.target.value)}/></div>
    <div className="nav-section"><div className="section-heading"><span>Documents</span><span className="count">1</span></div>
      <button className="tree-collection" onClick={()=>{setMode('read');setNavOpen(false)}}><ChevronDown size={14}/><BookOpen size={16}/><span>Workspace</span></button>
      {(!search||docMeta.title.toLowerCase().includes(search.toLowerCase())||'demo.md'.includes(search.toLowerCase()))&&<button className="document-tree-item selected" onClick={()=>{setMode('read');setNavOpen(false)}}><FileText size={16}/><span>{docMeta.title}</span></button>}
      {search&&!docMeta.title.toLowerCase().includes(search.toLowerCase())&&!'demo.md'.includes(search.toLowerCase())&&<p className="nav-empty">No matching document</p>}
    </div>
    <div className="nav-section rooms-section"><div className="section-heading"><span>Rooms</span><button aria-label="Refresh rooms" onClick={refreshRooms}><RefreshCw size={13}/></button></div>
      <nav aria-label="Rooms">{rooms.filter(r=>r.name.toLowerCase().includes(search.toLowerCase())).map(r=><button className={'room '+(r.id===room?'room-selected':'')} key={r.id} onClick={()=>{setRoom(r.id);setNavOpen(false)}}><MessageSquare size={15}/><span>{r.name}</span></button>)}</nav>
      <form className="new-room" onSubmit={createRoom}><input aria-label="New local room name" value={newName} onChange={e=>setNewName(e.target.value)} placeholder="New local room" maxLength={60} disabled={creating}/><button disabled={creating||!newName.trim()} aria-label="Create local room"><Plus size={16}/></button></form>
    </div>
    <div className="sidebar-bottom"><button className="agent-nav" onClick={()=>setPanel('agent')}><Bot size={17}/><span>Example Agent<small>Echo runtime · no LLM</small></span><span className="available-dot"/></button><div className="session-note"><span className={'available-dot '+(!online?'offline':'')}/>{online?(api.session.synthetic?'Browser-only preview':'Connected to local workspace'):'Reconnecting to workspace'}</div></div>
  </aside>
  <main className="main"><header className="workspace-header"><button className="mobile-nav" aria-label="Toggle navigation" onClick={()=>setNavOpen(!navOpen)}><BookOpen size={18}/></button><div className="breadcrumbs"><BookOpen size={15}/><span>Workspace</span><ChevronRight size={13}/><strong>demo.md</strong></div><div className="header-actions"><div className="mode-switch"><button aria-pressed={mode==='read'} onClick={()=>setMode('read')}>Read</button><button aria-pressed={mode==='edit'} onClick={()=>setMode('edit')}>Edit</button></div><span className="header-divider"/><button className={historyOpen?'active':''} aria-label="Version history" onClick={()=>setHistoryOpen(!historyOpen)}><History size={17}/></button><button className={panel==='discussion'?'active':''} onClick={()=>setPanel(panel==='discussion'?null:'discussion')}><MessageSquare size={17}/><span>Discussion</span></button><button className={panel==='agent'?'active':''} onClick={()=>setPanel(panel==='agent'?null:'agent')}><Bot size={17}/><span>Agent</span></button></div></header>
    {api.session.qa&&<div className="qa-banner">Visual regression capture · {api.session.qa} · isolated adapter</div>}
    {error&&<div className="global-error" role="alert"><AlertCircle size={16}/>{error}<button onClick={()=>setError('')} aria-label="Dismiss error"><X size={15}/></button></div>}
    <div className="content-layout"><Documents api={api} room={room} onSent={sent} mode={mode} setMode={setMode} historyOpen={historyOpen} onCloseHistory={()=>setHistoryOpen(false)} onMeta={setDocMeta}/>
      <aside className={'collaboration-panel '+(!panel?'panel-closed':'')} aria-label="Collaboration panel"><header className="panel-heading"><div><h2>{panel==='agent'?'Example Agent':'Discussion'}</h2><span>{selected?.name||'Room'}</span></div><button aria-label="Close collaboration panel" onClick={()=>setPanel(null)}><X size={18}/></button></header>
        <div className="panel-tabs"><button className={panel==='discussion'?'active':''} onClick={()=>setPanel('discussion')}>Messages</button><button className={panel==='agent'?'active':''} onClick={()=>setPanel('agent')}>Example Agent</button></div>
        {panel==='agent'&&<div className="agent-disclosure"><Bot size={18}/><div><strong>Deterministic example</strong><p>Repeats messages and handles explicit Git requests. No LLM or intelligent editing is connected.</p></div></div>}
        {filter&&<div className="reply-banner">Thread {short(filter)}<button onClick={()=>setFilter(null)}>All messages</button></div>}
        {timelineError&&<div className="panel-error" role="alert">{timelineError} Your draft is preserved; reconnecting automatically.</div>}
        <div className="timeline" ref={timelineRef} aria-live="polite">{!displayed.length?<div className="panel-empty"><MessageSquare size={25}/><h3>Start a conversation</h3><p>Discuss this workspace, or mention the example Agent to see a real response.</p></div>:displayed.map(event=>{
          const agent=event.sender===api.session.agentId,relation=event.content['m.relates_to'];
          const root=relation?.rel_type==='m.thread'?relation.event_id:event.id;
          return <article className={'message '+(agent?'agent':'')} key={event.id}><span className={'avatar '+(agent?'agent-avatar':'')}>{agent?<Bot size={15}/>:'Y'}</span><div className="message-main"><div className="message-meta"><strong>{agent?'Example Agent':event.sender===api.session.userId?'You':event.sender.split(':')[0]}</strong><time>{new Date(event.time||Date.now()).toLocaleTimeString([],{hour:'2-digit',minute:'2-digit'})}</time></div>{relation?.rel_type==='m.thread'&&<button className="thread-link" onClick={()=>setFilter(root)}>Reply in thread</button>}<MessageBody body={event.content.body}/><div className="message-actions"><button onClick={()=>setReplyTo(root)}>Reply</button><button onClick={()=>setFilter(root)}>View thread</button></div></div></article>;
        })}</div>
        <details className="task-details"><summary>Agent activity {tasks.filter(t=>t.room===room).length?`(${tasks.filter(t=>t.room===room).length})`:''}</summary>{tasks.filter(t=>t.room===room).map(t=><div key={t.id} className="task">{t.status==='done'?<Check size={13}/>:<RefreshCw size={13}/>}<span>{t.status==='done'?'Completed':t.status}</span><code>{short(t.id)}</code></div>)}{!tasks.filter(t=>t.room===room).length&&<p>No tasks sent in this session.</p>}</details>
        <Composer busyRoom={room} agentId={api.session.agentId} onSend={(content,id)=>api.send(room,content,id)} onSent={sent} replyTo={replyTo} clearReply={()=>setReplyTo(null)} defaultMention={panel==='agent'}/>
      </aside>
    </div>
  </main></div></>;
}
