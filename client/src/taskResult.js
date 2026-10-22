// Reply text is presentation only. Missing/unknown results never imply a save.
export function taskResult(value, action, synthetic=false,path='demo.md') {
  if(!value||value.version!==1||!['saved','read','conflict','rejected'].includes(value.status))return null;
  if(Object.keys(value).some(key=>!['version','status','path','commit','blob','reason','resource'].includes(key)))return null;
  if('reason' in value&&(!['conflict','rejected'].includes(value.status)||!['stale_version','invalid_request','source_not_granted'].includes(value.reason)))return null;
  if('resource' in value){const r=value.resource;if(value.status!=='read'||['path','commit','blob'].some(key=>key in value)||!r||Object.keys(r).sort().join(',')!=='blob,commit,kind,path,repository'||r.kind!=='repository'||typeof r.repository!=='string'||!r.repository.match(/^[A-Za-z0-9._-]{1,100}$/)||typeof r.path!=='string'||!r.path.length||r.path.length>1024||r.path.startsWith('/')||/[\\\r\n\0]/.test(r.path)||r.path.split('/').some(p=>['','.','..'].includes(p))||![r.commit,r.blob].every(v=>typeof v==='string'&&/^[a-f0-9]{40}$/.test(v)))return null;}
  const reference=v=>typeof v==='string'&&(synthetic?/^sample-[a-z0-9-]+$/.test(v):/^[a-f0-9]{40}$/.test(v));
  if(value.status==='saved'&&(action==='read'||value.path!==path||!reference(value.commit)||!reference(value.blob)))return null;
  if(value.status==='read'&&action!=='read')return null;
  if(['path','commit','blob'].some(key=>key in value)&&(!['saved','read'].includes(value.status)||value.path!==path||!reference(value.commit)||!reference(value.blob)))return null;
  return value;
}
