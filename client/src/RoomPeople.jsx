import React,{useEffect,useRef,useState} from 'react';
import {errorText} from './api';
export function RoomPeople({api,room,name,onClose}){
  const [state,setState]=useState(null),[revision,setRevision]=useState(0),dialog=useRef(null);
  useEffect(()=>{const previous=document.activeElement;dialog.current?.focus();return()=>{if(previous?.isConnected)previous.focus();}},[]);
  useEffect(()=>{let stopped=false;setState({room,loading:true});api.members(room).then(members=>{if(!stopped)setState({room,members});},error=>{if(!stopped)setState({room,error:errorText(error)});});return()=>{stopped=true}},[api,room,revision]);
  useEffect(()=>{if(dialog.current&&!dialog.current.contains(document.activeElement))dialog.current.focus();},[state]);
  const current=state?.room===room?state:null,members=current?.members||[];
  function keyDown(event){if(event.key==='Escape'){event.preventDefault();onClose();}if(event.key==='Tab'){const buttons=[...dialog.current.querySelectorAll('button')].filter(button=>!button.disabled),first=buttons[0],last=buttons.at(-1);if(event.shiftKey&&(document.activeElement===first||document.activeElement===dialog.current)){event.preventDefault();last?.focus();}else if(!event.shiftKey&&(document.activeElement===last||document.activeElement===dialog.current)){event.preventDefault();first?.focus();}}}
  return <div className="people-overlay"><section className="room-people" role="dialog" aria-modal="true" aria-label="Room people" tabIndex={-1} ref={dialog} onKeyDown={keyDown}><header><h2>People · {name||'Current room'}</h2><button onClick={onClose}>Close people</button></header><p>Current identity: <code>{api.session.userId}</code></p><p>Read only · refresh to check membership changes</p><button disabled={!current||current.loading} onClick={()=>setRevision(value=>value+1)}>Refresh people</button>
  {(!current||current.loading)?<p role="status">Loading people…</p>:current.error?<p role="alert">{current.error} <button onClick={()=>setRevision(value=>value+1)}>Retry people</button></p>:<><p>{members.filter(member=>member.membership==='join').length} joined · {members.filter(member=>member.membership==='invite').length} invited</p><ul>{members.map(member=><li key={member.id}><strong>{member.name}</strong><code>{member.id}</code><span>{member.id===api.session.userId?'You':member.id===api.session.agentId?'Example Agent':''}</span><span>{member.membership==='join'?'Joined':'Invited'}</span></li>)}</ul>{!members.length&&<p>No joined or invited people are visible.</p>}</>}
  </section></div>;
}
