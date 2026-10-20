import React,{useEffect,useState} from 'react';
import {errorText} from './api';

export function replyBody(content={}){
  const body=typeof content.body==='string'?content.body:'';
  if(!content['m.relates_to']?.['m.in_reply_to'])return body;
  if(!/^> <@[^>\n]+> /.test(body))return body;
  const lines=body.split('\n');while(lines[0]?.startsWith('> '))lines.shift();
  if(lines[0]==='')lines.shift();return lines.join('\n');
}
export function QuotedMessage({api,room,id,onOpen}){
  const [state,setState]=useState(null),[retry,setRetry]=useState(0);const context=room+'\0'+id;
  useEffect(()=>{let stopped=false;setState({context,loading:true});
    if(!api.message){setState({context,error:'Quoted source is unavailable in this preview.'});return;}
    api.message(room,id).then(event=>{if(!stopped)setState({context,event});},error=>{if(!stopped)setState({context,error:errorText(error)});});
    return ()=>{stopped=true;};
  },[api,room,id,retry]);
  const current=state?.context===context?state:null;
  return <blockquote className="quoted-message" aria-label="Quoted message">
    {(!current||current.loading)?<span>Loading quoted message…</span>:current.error?<><span role="alert">{current.error}</span><button onClick={()=>setRetry(value=>value+1)}>Retry quoted message</button></>:<><strong>{current.event.sender}</strong><p>{replyBody(current.event.content).slice(0,1000)||'Message content is unavailable.'}</p><button onClick={()=>onOpen(id)}>Open quoted source</button></>}
  </blockquote>;
}
