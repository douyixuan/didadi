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
