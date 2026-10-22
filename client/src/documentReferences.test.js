import {it,expect} from 'vitest';
import {documentVersion} from './documentReferences';
const commit='a'.repeat(40);
const event={sender:'@agent',content:{body:'Saved demo.md\nGit commit: '+commit+'\nBlob: '+'b'.repeat(40),'m.relates_to':{rel_type:'m.thread',event_id:'$request'},'org.didadi.task':{id:'$request'}}};
it('accepts only a version receipt from the managed Agent and its task thread',()=>{
 expect(documentVersion(event,'@agent')).toBe(commit);
 expect(documentVersion({...event,sender:'@human'},'@agent')).toBeNull();
 const missing=structuredClone(event);delete missing.content['org.didadi.task'];expect(documentVersion(missing,'@agent')).toBeNull();
 const plain=structuredClone(event);delete plain.content['m.relates_to'];expect(documentVersion(plain,'@agent')).toBeNull();
 for(const text of ['../escape','<script>bad</script>','a'.repeat(41),'A'.repeat(40)]){
  const bad=structuredClone(event);bad.content.body='Saved demo.md\nGit commit: '+text;expect(documentVersion(bad,'@agent')).toBeNull();
 }
});
it('keeps synthetic snapshot references explicitly separate from Git receipts',()=>{
 const sample={sender:'sample-agent',content:{body:'Saved browser snapshot: sample-123-abc','m.relates_to':{rel_type:'m.thread',event_id:'sample-request'}}};
 expect(documentVersion(sample,'sample-agent',true)).toBe('sample-123-abc');
 expect(documentVersion(sample,'sample-agent',false)).toBeNull();
 expect(documentVersion(event,'@agent',true)).toBeNull();
});

it('reads structured receipts independently of translated prose and never falls back on an unknown version',()=>{
 const typed=structuredClone(event);typed.content.body='已保存';typed.content['org.didadi.task.result']={version:1,status:'saved',path:'demo.md',commit,blob:'b'.repeat(40)};
 expect(documentVersion(typed,'@agent')).toBe(commit);
 typed.content.body=event.content.body;typed.content['org.didadi.task.result'].version=2;
 expect(documentVersion(typed,'@agent')).toBeNull();
});

it('opens a direct human receipt without a task or English body, but rejects a spoofed author',()=>{
 const receipt={sender:'@human',content:{body:'版本已保存','org.didadi.document.commit':{version:1,path:'demo.md',commit,blob:'b'.repeat(40),author:'@human'}}};
 expect(documentVersion(receipt,'@agent',false,'@human')).toBe(commit);
 expect(documentVersion({...receipt,sender:'@other'},'@agent',false,'@human')).toBeNull();
});


it('requires a matching document path before opening a named receipt',()=>{
 const receipt={sender:'@human',content:{body:'Saved','org.didadi.document.commit':{version:1,path:'设计/Notes.md',commit,blob:'b'.repeat(40),author:'@human'}}};
 expect(documentVersion(receipt,'@agent',false,'@human','设计/Notes.md')).toBe(commit);
 expect(documentVersion(receipt,'@agent',false,'@human','Other.md')).toBeNull();
 expect(documentVersion(event,'@agent',false,'@human','设计/Notes.md')).toBeNull();
});
