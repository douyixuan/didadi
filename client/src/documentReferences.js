export function documentVersion(event,agentId,synthetic=false,humanId=null){
  const receipt=event?.content?.['org.didadi.document.commit'];
  if(receipt!==undefined)return event?.sender===humanId&&receipt?.author===humanId&&receipt.version===1&&receipt.path==='demo.md'&&(synthetic?/^sample-[a-z0-9-]+$/:/^[a-f0-9]{40}$/).test(receipt.commit)?receipt.commit:null;
  if(event?.sender!==agentId)return null;
  const content=event.content||{},body=content.body;
  if(typeof body!=='string'||content['m.relates_to']?.rel_type!=='m.thread')return null;
  if(synthetic)return /^Saved browser snapshot: (sample-[a-z0-9-]+)$/.exec(body)?.[1]||null;
  if(typeof content['org.didadi.task']?.id!=='string')return null;
  const outcome=content['org.didadi.task.result'];
  if(outcome!==undefined)return outcome?.version===1&&['saved','read'].includes(outcome.status)&&outcome.path==='demo.md'&&/^[a-f0-9]{40}$/.test(outcome.commit)?outcome.commit:null;
  return /^(?:Saved demo\.md\nGit commit: |demo\.md at Git commit: )([a-f0-9]{40})(?=\n|$)/.exec(body)?.[1]||null;
}
