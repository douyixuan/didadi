import {it,expect} from 'vitest';
import {fireEvent} from '@testing-library/react';
import {Crepe} from '@milkdown/crepe';
import {editorViewCtx} from '@milkdown/kit/core';
import {AllSelection,TextSelection} from '@milkdown/kit/prose/state';
import {undo,redo} from '@milkdown/kit/prose/history';
import {sourceNode,boundaryNode,sourcePreservation} from './sourcePlugin';
const source='---\r\ntitle: "QA 中文"\r\ntags: [qa]\r\n---\r\n\r\n# QA export front matter\r\n\r\n中文 \\ escape *literal*.\r\n';
async function editor(run,initial='# Before\n'){const root=document.createElement('div');document.body.append(root);const crepe=new Crepe({root,defaultValue:initial});crepe.editor.use(sourceNode).use(boundaryNode).use(sourcePreservation());await crepe.create();try{await crepe.editor.action(ctx=>run(ctx.get(editorViewCtx),crepe));}finally{await crepe.destroy();root.remove();}}
function paste(view,text){fireEvent.paste(view.dom,{clipboardData:{getData:format=>format==='text/plain'?text:'',types:['text/plain'],files:[]}});}
it('preserves full-document pasted front matter and exact Markdown instead of a code fence',async()=>{
 await editor((view,crepe)=>{view.dispatch(view.state.tr.setSelection(new AllSelection(view.state.doc)));paste(view,source);
  expect(crepe.getMarkdown()).toBe(source);expect(view.dom.querySelector('.source-properties')).not.toBeNull();expect(view.dom.querySelector('h1')).toHaveTextContent('QA export front matter');
  expect(crepe.getMarkdown().startsWith('```')).toBe(false);undo(view.state,view.dispatch);expect(crepe.getMarkdown()).toBe('# Before\n');redo(view.state,view.dispatch);expect(crepe.getMarkdown()).toBe(source);
 });
});
it('does not treat a partial selection as a whole-document replacement',async()=>{
 await editor((view,crepe)=>{view.dispatch(view.state.tr.setSelection(TextSelection.create(view.state.doc,2,3)));paste(view,source);expect(crepe.getMarkdown()).not.toBe(source);expect(view.dom.textContent).toContain('B');});
});
it('does not mutate a read-only editor through the special paste path',async()=>{
 await editor((view,crepe)=>{crepe.setReadonly(true);view.dispatch(view.state.tr.setSelection(new AllSelection(view.state.doc)));paste(view,source);expect(crepe.getMarkdown()).toBe('# Before\n');});
});

it.each(['\n\n# Before\n','  \n\n','\uFEFF---\r\ntitle: before\r\n---\r\n\r\n# Earlier\r\n'])('undo restores exact prior full-document metadata: %j',async initial=>{
 await editor((view,crepe)=>{view.dispatch(view.state.tr.setSelection(new AllSelection(view.state.doc)));paste(view,source);expect(crepe.getMarkdown()).toBe(source);undo(view.state,view.dispatch);expect(crepe.getMarkdown()).toBe(initial);redo(view.state,view.dispatch);expect(crepe.getMarkdown()).toBe(source);},initial);
});
