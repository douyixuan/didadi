import {it,expect} from 'vitest';
import {readFileSync,mkdirSync,writeFileSync} from 'node:fs';
import {Crepe} from '@milkdown/crepe';
import {editorViewCtx} from '@milkdown/kit/core';
import {sourceNode,boundaryNode,sourcePreservation} from './sourcePlugin';

it('reports pinned large-document serialization latency after real view edits',async()=>{
 const report=[];
 for(const file of ['NVIDIA__cutlass/05.md','microsoft__vscode-docs/03.md']){
  const source=readFileSync('test-corpus/real/'+file,'utf8'),host=document.createElement('div');document.body.append(host);let model;
  const crepe=new Crepe({root:host,defaultValue:source,features:{[Crepe.Feature.Table]:true,[Crepe.Feature.ImageBlock]:false,[Crepe.Feature.Latex]:false,[Crepe.Feature.AI]:false}});
  crepe.editor.use(sourceNode).use(boundaryNode).use(sourcePreservation(value=>{model=value}));await crepe.create();
  try{crepe.editor.action(ctx=>{
   const view=ctx.get(editorViewCtx);
   // Measure an uncached serializer pass even if Crepe used it during setup.
   if(model.results)model.results.delete(view.state.doc);if(model.pieces)model.pieces=new WeakMap();
   const start=performance.now(),initial=model.serialize(view.state.doc),firstUncachedSerialize=performance.now()-start;expect(initial).toBe(source);
   const untouched=[];for(let i=0;i<10;i++){const start=performance.now();const saved=model.serialize(view.state.doc);untouched.push(performance.now()-start);expect(saved).toBe(source)}
   const stats=values=>({mean:values.reduce((a,b)=>a+b,0)/values.length,max:Math.max(...values),samples:values});
   const entry={file,lines:source.split('\n').length,firstUncachedSerialize,untouched:stats(untouched)};
   for(const table of [false,true]){
    let position=null;view.state.doc.descendants((node,pos)=>{
     if(position!==null||!node.isText||node.text.length<8)return;const resolved=view.state.doc.resolve(pos);
     const parents=Array.from({length:resolved.depth},(_,i)=>resolved.node(i+1).type.name);
     if(resolved.parent.type.name==='paragraph'&&!parents.includes('didadi_source')&&parents.includes('table')===table)position=pos+2;
    });
    if(position===null){if(!table)throw Error('Missing paragraph benchmark target');continue}
    const edits=[];
    for(let i=0;i<10;i++){
     view.dispatch(view.state.tr.insertText('x',position+i));const start=performance.now();const saved=model.serialize(view.state.doc);edits.push(performance.now()-start);expect(saved).toContain('x'.repeat(i+1));
    }
    entry[table?'tableKeystroke':'paragraphKeystroke']=stats(edits);
   }
   report.push(entry);
  })}finally{await crepe.destroy();host.remove()}
 }
 mkdirSync('.local',{recursive:true});writeFileSync('.local/source-performance.json',JSON.stringify(report,null,2)+'\n');
 for(const entry of report){expect(entry.untouched.mean).toBeLessThan(5);expect(entry.paragraphKeystroke.mean).toBeLessThan(16);if(entry.tableKeystroke)expect(entry.tableKeystroke.mean).toBeLessThan(16)}
 console.log('SOURCE PERFORMANCE',JSON.stringify(report));
},60000);
