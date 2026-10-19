// Reply text is presentation only. Missing/unknown results never imply a save.
export function taskResult(value, action, synthetic=false) {
  if(!value||value.version!==1||!['saved','read','conflict','rejected'].includes(value.status))return null;
  if(Object.keys(value).some(key=>!['version','status','path','commit','blob','reason'].includes(key)))return null;
  if('reason' in value&&(!['conflict','rejected'].includes(value.status)||!['stale_version','invalid_request','source_not_granted'].includes(value.reason)))return null;
  const reference=v=>typeof v==='string'&&(synthetic?/^sample-[a-z0-9-]+$/.test(v):/^[a-f0-9]{40}$/.test(v));
  if(value.status==='saved'&&(action==='read'||value.path!=='demo.md'||!reference(value.commit)||!reference(value.blob)))return null;
  if(value.status==='read'&&action!=='read')return null;
  if(['path','commit','blob'].some(key=>key in value)&&(!['saved','read'].includes(value.status)||value.path!=='demo.md'||!reference(value.commit)||!reference(value.blob)))return null;
  return value;
}
