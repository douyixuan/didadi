// Presentation metadata never controls task completion, retries or authorization.
export function taskState(task) {
  const status=task?.status;
  if(['done','failed','cancelled'].includes(status))return {label:{done:'Completed',failed:'Failed',cancelled:'Cancelled'}[status],detail:'',connection:''};
  if(status==='reconnecting')return {label:'Task status unavailable',detail:'Reconnecting. Your request and draft are kept; no new task is sent.',connection:''};
  if(!task||status==='queued')return {label:'Waiting for Gateway acceptance',detail:'The existing request is being checked. No duplicate request is sent.',connection:''};
  const supported=['waiting','verifying','running','retry_wait'].includes(task.phase);
  if(!supported&&status!=='unverified')return {label:'Task state unconfirmed',detail:'The Gateway has not provided current lease metadata. Your existing request is kept.',connection:''};
  const phase=supported?task.phase:'verifying';
  let label={waiting:'Waiting for runtime',verifying:'Awaiting access confirmation',running:'In progress · lease held',retry_wait:'Waiting to retry'}[phase];
  const count=Number.isInteger(task.attempts)&&task.attempts>0?`Attempt ${task.attempts}${Number.isInteger(task.max_attempts)&&task.max_attempts>0?` of ${task.max_attempts}`:''}. `:'';
  let detail={waiting:'No active task lease is held.',verifying:'Room access must be confirmed before the task can be dispatched.',running:'A runtime holds the current lease. A lease does not prove ongoing execution progress.',retry_wait:'The existing task is retained for another claim.'}[phase];
  if(phase==='verifying'&&task.verification_reason==='legacy_lease_unconfirmed'){label='Lease state unconfirmed';detail='A lease from an earlier Gateway version is still valid. Its execution state is unconfirmed until completion or expiry.';}
  if(phase==='running'&&Number.isFinite(task.lease_expires_at)&&Number.isFinite(task.observed_at))detail+=` Lease expires in ${Math.max(0,Math.ceil(task.lease_expires_at-task.observed_at))} seconds at the last server check.`;
  if(phase==='retry_wait'){
    const reason={lease_expired:'The previous lease expired.',runtime_error:'The runtime reported an error.',room_unavailable:'Room access could not be checked.',delivery_forbidden:'Reply permission could not be verified.'}[task.retry_reason];
    if(reason)detail=reason+' '+detail;
    if(task.retry_limit_reached)detail='Retry limit reached. The Gateway will finalize this task on the next claim check; no further execution will be leased.';
    else if(Number.isFinite(task.next_retry_at)&&Number.isFinite(task.observed_at))detail+=task.next_retry_at>task.observed_at?` Retry eligible in ${Math.ceil(task.next_retry_at-task.observed_at)} seconds at the last server check.`:' Ready to be reclaimed at the last server check.';
  }
  const runtime=task.runtime;
  const connections={connected:'WebSocket runtime connected.',disconnected:'WebSocket runtime disconnected. Existing leases remain in force.',unknown:'WebSocket runtime connection is unconfirmed. HTTP runtimes are not tracked here.'};
  const connection=runtime?.transport==='websocket'&&Object.hasOwn(connections,runtime.state)?connections[runtime.state]:'';
  return {label,detail:count+detail,connection};
}
