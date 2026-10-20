// Test-fixture transport: honor throttling without changing the request or server limits.
export async function matrixFetch(url,options={},policy={}){
  const fetchFn=policy.fetchFn||fetch,sleep=policy.sleep||(ms=>new Promise(resolve=>setTimeout(resolve,ms))),now=policy.now||Date.now;
  const maxWaitMs=policy.maxWaitMs??60000,maxAttempts=policy.maxAttempts??8,started=now();
  for(let attempt=0;;attempt++){
    const response=await fetchFn(url,options);
    if(response.status!==429||attempt+1>=maxAttempts)return response;
    let data;try{data=await response.clone().json();}catch{}
    const hints=[];if(Number.isFinite(data?.retry_after_ms)&&data.retry_after_ms>=0)hints.push(data.retry_after_ms);
    const header=response.headers.get('Retry-After');if(header){const numeric=Number(header),value=Number.isFinite(numeric)?numeric*1000:Date.parse(header)-now();if(Number.isFinite(value)&&value>=0)hints.push(value);}
    const wait=Math.max(100,...(hints.length?hints:[2000]));
    if(now()-started+wait>maxWaitMs)return response;
    await sleep(wait);
  }
}
