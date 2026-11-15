export function documentVersion(event,agentId,synthetic=false,humanId=null,path='demo.md'){
  const receipt=event?.content?.['org.didadi.document.commit'];
  if(receipt!==undefined)return typeof receipt?.author==='string'&&(synthetic||receipt.author.startsWith('@'))&&event?.sender===receipt.author&&receipt.version===1&&receipt.path===path&&(synthetic?/^sample-[a-z0-9-]+$/:/^[a-f0-9]{40}$/).test(receipt.commit)?receipt.commit:null;
  if(event?.sender!==agentId)return null;
  const content=event.content||{},body=content.body;
  if(typeof body!=='string'||content['m.relates_to']?.rel_type!=='m.thread')return null;
  if(synthetic)return /^Saved browser snapshot: (sample-[a-z0-9-]+)$/.exec(body)?.[1]||null;
  if(typeof content['org.didadi.task']?.id!=='string')return null;
  const outcome=content['org.didadi.task.result'];
  if(outcome!==undefined)return outcome?.version===1&&['saved','read'].includes(outcome.status)&&outcome.path===path&&/^[a-f0-9]{40}$/.test(outcome.commit)?outcome.commit:null;
  if(path!=='demo.md')return null;
  return /^(?:Saved demo\.md\nGit commit: |demo\.md at Git commit: )([a-f0-9]{40})(?=\n|$)/.exec(body)?.[1]||null;
}

// Canonical source links remain portable Markdown. Only the document's own
// workspace can be opened in-app; the existing API still authorizes the read.
export function documentSourceReference(href,room){
 try{
  if(typeof href!=='string'||typeof room!=='string'||!room.startsWith('!'))return null;
  const url=new URL(href);
  if(url.protocol!=='https:'||url.hostname!=='matrix.to'||url.port||url.username||url.password||url.pathname!=='/'||url.search||!url.hash.startsWith('#/')||url.hash.includes('?'))return null;
  const parts=url.hash.slice(2).split('/');if(parts.length!==2)return null;
  const [sourceRoom,event]=parts.map(decodeURIComponent);
  if(['/','\\','?','#'].some(character=>event.includes(character)))return null;
  if(sourceRoom!==room||!event.startsWith('$')||event.length<2||event.length>1024||/[\s\u0000-\u001f\u007f]/.test(event))return null;
  return {room:sourceRoom,event};
 }catch{return null;}
}
