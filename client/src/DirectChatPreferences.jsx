import React,{useEffect,useRef,useState} from 'react';
import {errorText} from './api';
export function DirectChatPreferences({api,revision=0,onRefresh=()=>{}}){
 const [state,setState]=useState(null),[error,setError]=useState(''),[busy,setBusy]=useState(false),seq=useRef(0),alive=useRef(true),lock=useRef(false);
 async function refresh(){const id=++seq.current;try{const value=await api.directChats();if(alive.current&&id===seq.current){setState(value);setError('')}}catch(e){if(alive.current&&id===seq.current){setState(null);setError(errorText(e))}}}
 useEffect(()=>{alive.current=true;refresh();const timer=setInterval(refresh,10000);return()=>{alive.current=false;++seq.current;clearInterval(timer)}},[api,revision]);
 async function retry(room){if(lock.current)return;lock.current=true;setBusy(true);setError('');try{await api.retryDirect(room);await refresh();await onRefresh()}catch(e){if(alive.current)setError(errorText(e))}finally{lock.current=false;if(alive.current)setBusy(false)}}
 return <section className="direct-preferences" aria-label="Direct-chat preferences"><h3>Direct-chat preferences</h3><p>Personal Matrix labels · no access changes</p>{state&&<p>{Object.keys(state.mapped).length} marked direct for you</p>}{state?.pending.map(item=><div key={item.room}><p>Room created · direct label pending for {item.peer}</p><button disabled={busy} onClick={()=>retry(item.room)}>Retry direct label</button></div>)}<button disabled={busy} onClick={refresh}>Refresh direct labels</button>{error&&<p role="alert">{error}</p>}</section>
}
