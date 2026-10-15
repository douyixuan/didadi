import {beforeAll,afterAll,it,expect} from 'vitest';
import {readFileSync,mkdirSync,writeFileSync} from 'node:fs';
import {resolve} from 'node:path';
import {createHash} from 'node:crypto';
import {diffLines} from 'diff';
import {Crepe} from '@milkdown/crepe';
import {editorViewCtx} from '@milkdown/kit/core';
import {EditorState} from '@milkdown/kit/prose/state';
import {undo} from '@milkdown/kit/prose/history';
import {sourceNode,boundaryNode,sourcePreservation} from './sourcePlugin';
import {sourceBlocks} from './sourceMarkdown';
const manifest=JSON.parse(readFileSync(resolve('test-corpus/manifest.json'),'utf8')).filter(item=>/\/\d\d\.md$/.test(item.file));
const edgeCases={
 'mixed':'---\ntitle: 中文\n---\n\n# Heading\n\nNormal **text**.\n\n| A | B |\n| - | - |\n| 一 | 二 |\n\n<details>source</details>\n\n[ref][x]\n\n[x]: https://example.invalid\n\n~~~js title="keep"\nx();\n~~~\n',
 'list-boundaries':'* same\n\n<!-- gap -->\n\n- same\n\n1. one\n2. two\n\n    indented code\n\nEnd',
 'crlf':'\r\n# 中文\r\n\r\n- first\r\n- second\r\n\r\n~~~js\r\nx()\r\n~~~\r\n',
 'empty':'','whitespace':' \n\t\n\n','no-newline':'Paragraph without newline','html':'<script>alert("not executed")</script>\n\nNormal text.\n',
 'footnote-math':'Text[^1] and $x$.\n\n[^1]: footnote\n\n$$\nx^2\n$$\n',
 'escaped':'# Title\n\nUse \\*literal\\* and &amp; entities.\n\nOther.\n',
};
const corpus=[...manifest.map(item=>({...item,source:readFileSync(resolve('test-corpus',item.file),'utf8')})),...Object.entries(edgeCases).map(([file,source])=>({file:'edge/'+file,source}))];
let crepe,model,host;
beforeAll(async()=>{host=document.createElement('div');document.body.append(host);crepe=new Crepe({root:host,defaultValue:'',features:{[Crepe.Feature.Table]:true,[Crepe.Feature.ImageBlock]:false,[Crepe.Feature.Latex]:false,[Crepe.Feature.AI]:false}});crepe.editor.use(sourceNode).use(boundaryNode).use(sourcePreservation(value=>{model=value}));await crepe.create()},30000);
afterAll(async()=>{await crepe?.destroy();host?.remove()});
it('runs the pinned corpus through the real editor parser, edit, save and reopen',()=>{
 const report={files:corpus.length,blockEditor:0,wholeDocumentTextarea:0,lossy:0,unstable:0,firstSaveRewrittenLines:0,editedFiles:0,unrelatedEditedSaveLines:0,rawBlocks:0,totalBlocks:0,editedBlocks:0,filesWithRichBlocks:0};const failures=[];
 for(const item of corpus){try{
  if(item.sha256)expect(createHash('sha256').update(item.source).digest('hex')).toBe(item.sha256);
  const doc=model.parse(item.source);
  crepe.editor.action(ctx=>{const view=ctx.get(editorViewCtx);view.updateState(EditorState.create({doc,plugins:view.state.plugins}));expect(view.dom.classList.contains('ProseMirror')).toBe(true);expect(view.dom.querySelector('.source-fallback')).toBeNull();expect(model.serialize(view.state.doc)).toBe(item.source)});
  report.blockEditor++;
  if(Array.from({length:doc.childCount},(_,i)=>doc.child(i)).some(n=>n.type!==model.rawType&&n.type.name!=='didadi_boundary'&&n.content.size>0))report.filesWithRichBlocks++;
  doc.forEach(n=>{report.totalBlocks++;if(n.type===model.rawType)report.rawBlocks++});
  const saved=model.serialize(doc);if(saved!==item.source){report.lossy++;report.firstSaveRewrittenLines+=diffLines(item.source,saved).filter(p=>p.removed).reduce((sum,p)=>sum+p.count,0);throw Error('no-op bytes changed')}
  if(model.serialize(model.parse(saved))!==saved){report.unstable++;throw Error('reopen unstable')}
  // Insert real text into an existing text node. Match the exact original source
  // position, so a whole-block reserialization cannot pass as zero diff noise.
  const parts=sourceBlocks(item.source),targets=[];
  doc.forEach((node,pos,index)=>{if(!parts.blocks[index])return;let target=null;node.descendants((leaf,offset)=>{
   if(target||!leaf.isText||leaf.text.length<3)return;
   const at=parts.blocks[index].source.indexOf(leaf.text);
   if(at>=0){let middle=Math.max(1,Math.floor(leaf.text.length/2));if(/[\uDC00-\uDFFF]/.test(leaf.text[middle]))middle--;target={pos:pos+offset+1+middle,sourceOffset:parts.blocks[index].start+at+middle};}
  });if(target)targets.push(target)});
  if(targets.length)report.editedFiles++;
  for(const target of targets){
   const tr=EditorState.create({doc}).tr.insertText(' EDIT',target.pos);model.track(tr,doc);const edited=model.serialize(tr.doc);
   const expected=item.source.slice(0,target.sourceOffset)+' EDIT'+item.source.slice(target.sourceOffset);
   report.editedBlocks++;if(edited!==expected){report.unrelatedEditedSaveLines+=diffLines(expected,edited).filter(p=>p.removed).reduce((sum,p)=>sum+p.count,0);throw Error('edited save differs from exact insertion at '+target.pos+' '+JSON.stringify(diffLines(expected,edited).filter(p=>p.added||p.removed).slice(0,4)))}
   const reopened=model.parse(edited);if(model.serialize(reopened)!==edited){report.unstable++;throw Error('edited reopen unstable')}
   expect(reopened.textContent).toContain(' EDIT');
  }
 }catch(error){failures.push(`${item.file}: ${error.message}`)}}
 const result={...report,wholeDocumentFallbackPercent:100*report.wholeDocumentTextarea/report.files,failures};
 mkdirSync('.local',{recursive:true});writeFileSync('.local/markdown-roundtrip.json',JSON.stringify(result,null,2)+'\n');
 process.stdout.write('PINNED MARKDOWN CORPUS '+JSON.stringify(result)+'\n');
 expect(failures,failures.join('\n')).toEqual([]);expect(report.blockEditor).toBe(report.files);expect(report.editedFiles).toBeGreaterThan(25);
 expect(report.wholeDocumentTextarea/report.files).toBeLessThan(.05);expect(report.lossy).toBe(0);expect(report.unstable).toBe(0);expect(report.firstSaveRewrittenLines).toBe(0);expect(report.unrelatedEditedSaveLines).toBe(0);
},180000);

it('restores whitespace-only source after typing and undo',()=>{
 const source=' \r\n\t\r\n';const doc=model.parse(source),state=EditorState.create({doc});
 const typed=state.tr.insertText('x',1);model.track(typed,doc);const cleared=EditorState.create({doc:typed.doc}).tr.delete(1,2);model.track(cleared,typed.doc);expect(model.serialize(cleared.doc)).toBe(source);
});
it('keeps empty paragraphs in the view without writing editor markers',()=>{
 const source='A\n\nB\n',doc=model.parse(source),empty=doc.type.schema.nodes.paragraph.create();
 for(const count of [1,2,5]){
  const tr=EditorState.create({doc}).tr.insert(doc.firstChild.nodeSize,Array(count).fill(empty));model.track(tr,doc);
  const saved=model.serialize(tr.doc);expect(saved).toBe(source);expect(saved).not.toContain('didadi:');
  expect(model.parse(saved).childCount).toBe(2);
 }
});
it('reads legacy empty markers unchanged but removes them after a real edit',()=>{
 const source='A\n\n<!-- didadi:empty-paragraph -->\n\nB\n',doc=model.parse(source);
 expect(doc.childCount).toBe(3);expect(model.serialize(doc)).toBe(source);
 const tr=EditorState.create({doc}).tr.insertText(' edit',2);model.track(tr,doc);
 const saved=model.serialize(tr.doc);expect(saved).not.toContain('didadi:');expect(saved).toBe('A edit\n\nB\n');
 expect(model.serialize(model.parse(saved))).toBe(saved);
});
it.each(['~~~js','~~~js title=keep'])('closes an originally unclosed fence %s before a newly appended block',fence=>{
 const doc=model.parse(fence+'\nx()'),paragraph=doc.type.schema.nodes.paragraph.create(null,doc.type.schema.text('Outside'));
 const tr=EditorState.create({doc}).tr.insert(doc.content.size,paragraph);model.track(tr,doc);
 const saved=model.serialize(tr.doc),reopened=model.parse(saved);
 expect(reopened.childCount).toBe(2);expect(reopened.child(0).textContent).toBe(fence.includes('title=')?fence+'\nx()\n~~~':'x()');expect(reopened.child(1).textContent).toBe('Outside');
});
it('does not fuse lists after deleting their intervening source block',()=>{
 const doc=model.parse('1. a\n\n<!-- separation -->\n\n1. b\n');
 const tr=EditorState.create({doc}).tr.delete(doc.firstChild.nodeSize,doc.firstChild.nodeSize+doc.child(1).nodeSize);model.track(tr,doc);
 const saved=model.serialize(tr.doc),reopened=model.parse(saved);const lists=[];reopened.forEach(n=>{if(n.type.name==='ordered_list')lists.push(n)});
 expect(lists).toHaveLength(2);expect(lists.map(n=>n.attrs.order)).toEqual([1,1]);
});

it('preserves unedited list lines when Enter splits a different item',()=>{
 const source='+ one\n+ two  \n+ three\n',doc=model.parse(source),tr=EditorState.create({doc}).tr.split(4,2);model.track(tr,doc);
 const saved=model.serialize(tr.doc);expect(saved).toBe('+ o\n+ ne\n+ two  \n+ three\n');const reopened=model.parse(saved);expect(reopened.firstChild.childCount).toBe(4);expect(reopened.firstChild.textContent).toBe('onetwothree');
});

it.each(['+','-','*','01)','1.'])('preserves unedited sibling source in %s lists across split and join',marker=>{
 const source=marker+' one\n'+marker+' two  \n'+marker+' three\n',doc=model.parse(source),split=EditorState.create({doc}).tr.split(4,2);model.track(split,doc);
 const saved=model.serialize(split.doc);expect(saved).toContain(marker+' two  \n'+marker+' three\n');expect(model.parse(saved).firstChild.childCount).toBe(4);
 const join=EditorState.create({doc:split.doc}).tr.join(6,2);model.track(join,split.doc);const joined=model.serialize(join.doc);expect(joined).toContain(marker+' two  \n'+marker+' three\n');expect(model.parse(joined).firstChild.childCount).toBe(3);
});
it('retains the container source when deleting its first list item',()=>{
 const source='+ one\n+ two  \n+ three\n',doc=model.parse(source),list=doc.firstChild;
 const tr=EditorState.create({doc}).tr.delete(1,1+list.firstChild.nodeSize);model.track(tr,doc);
 expect(model.serialize(tr.doc)).toBe('+ two  \n+ three\n');
});

it('restores legacy bytes after typing and undo in the real Crepe view',()=>{
 const source='A\n\n<!-- didadi:empty-paragraph -->\n\n~~~js\nx()\n~~~\n';
 crepe.editor.action(ctx=>{
  const view=ctx.get(editorViewCtx),doc=model.parse(source);
  view.updateState(EditorState.create({doc,plugins:view.state.plugins}));
  view.dispatch(view.state.tr.insertText(' EDIT',2));
  expect(model.serialize(view.state.doc)).not.toContain('didadi:empty-paragraph');
  expect(undo(view.state,view.dispatch)).toBe(true);
  expect(model.serialize(view.state.doc)).toBe(source);
 });
});
