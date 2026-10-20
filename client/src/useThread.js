import {useEffect,useRef,useState} from 'react';
import {mergeMessages} from './messageHistory';
import {errorText} from './api';

export function useThread(api,room,root,beforePrepend=()=>{}){
 const prepend=useRef(beforePrepend);prepend.current=beforePrepend;
 const [snapshot,setSnapshot]=useState(null),actions=useRef({});
 useEffect(()=>{
  if(!api?.threadPage||!room||!root){actions.current={};return;}
  let stopped=false,refreshing=false,loadingOlder=false,initialized=false,revision=0,current=[],cursor=null,original=null,error='',olderError='',notice='';
  const publish=()=>{if(!stopped)setSnapshot({room,root,events:original?[original,...current]:[],cursor,error,olderError,notice,loading:!initialized&&refreshing,loadingOlder});};
  async function refresh(){if(stopped||refreshing)return;refreshing=true;publish();try{
   const page=await api.threadPage(room,root);if(stopped)return;
   const gap=initialized&&current.length&&page.events.length&&!current.some(old=>page.events.some(next=>old.id===next.id));
   original=page.root;
   if(!initialized||gap||!current.length){current=page.events;cursor=page.previousCursor;if(gap){revision++;notice='Thread replies advanced beyond the loaded page. Load earlier thread replies again to reconnect history.';}}
   else current=mergeMessages(current,page.events);
   initialized=true;error='';
  }catch(failure){if(!stopped)error=errorText(failure);}finally{refreshing=false;publish();}}
  async function older(){if(stopped||loadingOlder||!cursor)return;loadingOlder=true;olderError='';publish();const from=cursor,expected=revision;try{
   const page=await api.threadPage(room,root,from);if(stopped||expected!==revision)return;
   original=page.root;const merged=mergeMessages(page.events,current);if(merged.length!==current.length)prepend.current();current=merged;cursor=page.previousCursor===from?null:page.previousCursor;if(page.events.length)notice='';
  }catch(failure){if(!stopped&&expected===revision)olderError=errorText(failure);}finally{loadingOlder=false;publish();}}
  actions.current={refresh,older};refresh();const timer=setInterval(refresh,2500);
  return()=>{stopped=true;clearInterval(timer);actions.current={};};
 },[api,room,root]);
 const current=snapshot?.room===room&&snapshot?.root===root?snapshot:null;
 return {...current,events:current?.events||[],loading:current?current.loading:Boolean(api?.threadPage&&root),refresh:()=>actions.current.refresh?.(),older:()=>actions.current.older?.()};
}
