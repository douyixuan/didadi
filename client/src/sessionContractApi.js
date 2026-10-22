// Deliberately separate from the Matrix adapter. These identifiers are fictional.
export function sessionContractApi(fetchFn=fetch){
 async function request(route,session,body){
  const response=await fetchFn('/api/session-contract/'+route,{method:body===undefined?'GET':'POST',headers:{'Content-Type':'application/json',...(session?{'X-Fictional-Session':session.session_id,'X-Fictional-CSRF':session.csrf}:{})},...(body===undefined?{}:{body:JSON.stringify(body)})});
  const data=await response.json();if(!response.ok){const error=new Error(data.error||'Fictional service unavailable.');error.status=response.status;throw error}return data;
 }
 return {login:(identity,device)=>request('login',null,{fixture_identity:identity,fixture_device:device}),workspace:session=>request('workspace',session),save:(session,body)=>request('document',session,body),logout:session=>request('logout',session,{scope:'current_device'})};
}
