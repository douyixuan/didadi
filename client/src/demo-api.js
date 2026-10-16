// Synthetic UI preview only. No network, credentials, Matrix server or Git repository.
const KEY='didadi-synthetic-preview-v1';
export function createDemo(storage=localStorage) {
  const initial={rooms:[{id:'sample-room',name:'Product notes',agentJoined:true}],events:{},tasks:{},transactions:{},versions:[{commit:'sample-initial',blob:'sample-initial',content:'---\ntitle: Didadi workspace\nstatus: sample\n---\n\n# Getting started with Didadi\n\nA shared space for documents, conversations, and external Agents.\n\n## Try this preview\n\n- Edit this document and save a browser snapshot.\n- Open Discussion and mention the example Agent.\n- Explore version history.\n\n## Markdown stays yours\n\n| Feature | Try it |\n| :--- | :--- |\n| 表格 | Edit a cell |\n| Source | Keep original formatting |\n\n<details><summary>Custom Markdown</summary>\nThis source block stays intact while you edit ordinary text above.\n</details>\n\nThis is synthetic sample data stored in your browser. No Matrix or Git backend is connected.'}]};
  const read=()=>JSON.parse(storage.getItem(KEY)||JSON.stringify(initial));
  const write=s=>storage.setItem(KEY,JSON.stringify(s));
  const session={synthetic:true,userId:'sample-user',agentId:'sample-agent',initialRoom:'sample-room'};
  return {session,
    async rooms(){return read().rooms},
    async timeline(room){return read().events[room]||[]},
    async createRoom(name,operation){const s=read();const key='room:'+operation;if(s.transactions[key])return s.transactions[key];const result={room_id:'sample-'+crypto.randomUUID()};s.rooms.push({id:result.room_id,name,agentJoined:true});s.transactions[key]=result;write(s);return result},
    async document(room,commit){const versions=read().versions;const doc=commit?versions.find(v=>v.commit===commit):versions[0];if(!doc)throw Error('Sample version not found');return {...doc}},
    async history(){return {commits:read().versions.map(v=>v.commit)}},
    async task(room,id){return {task:read().tasks[id]}},
    async send(room,content,txn){const s=read(),key=room+':'+txn;if(s.transactions[key])return s.transactions[key];const id='sample-'+crypto.randomUUID(),result={event_id:id};const timeline=s.events[room]||=[];timeline.push({id,sender:session.userId,time:Date.now(),content});
      if(content['m.mentions']?.user_ids?.includes(session.agentId)){
        const command=content['org.didadi.document'];let outcome=null,body='Browser example Agent received: '+content.body;
        if(command?.action==='write'){
          if(command.base_blob!==s.versions[0].blob){body='Document conflict: a newer browser snapshot exists';outcome={version:1,status:'conflict',reason:'stale_version'};}
          else {const version='sample-'+crypto.randomUUID();s.versions.unshift({commit:version,blob:version,content:command.content});body='Saved browser snapshot: '+version;outcome={version:1,status:'saved',path:'demo.md',commit:version,blob:version};}
        } else if(command?.action==='read'){body='Browser snapshot:\n'+(command.commit?s.versions.find(v=>v.commit===command.commit):s.versions[0])?.content;outcome={version:1,status:'read'};}
        s.tasks[id]={status:'done',body,outcome};timeline.push({id:id+'-reply',sender:session.agentId,time:Date.now(),content:{body,...(outcome?{'org.didadi.task.result':outcome}:{}),'m.relates_to':{rel_type:'m.thread',event_id:id}}});
      }s.transactions[key]=result;write(s);return result;
    }
  };
}
