// Acceptance-runner timing only. Never shorten a genuine Synapse retry_after_ms.
export function loginCooldown(body,elapsed=0,budget=420000) {
  const reported=body?.retry_after_ms;
  const pause=Number.isFinite(reported)&&reported>=0?Math.max(1500,reported+500):12000;
  if(pause>budget-elapsed)throw new Error('Matrix login cooldown exceeds the bounded acceptance budget; no authentication outcome proven');
  return pause;
}
