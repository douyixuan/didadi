import {$node,$proseAsync} from '@milkdown/kit/utils';
import {parserCtx,serializerCtx,schemaCtx,ParserReady,SerializerReady} from '@milkdown/kit/core';
import {Plugin} from '@milkdown/kit/prose/state';
import {SourceDocument,frontMatter} from './sourceMarkdown';

// A textblock, not an embedded editor: selection, composition, undo and paste
// remain ordinary ProseMirror operations. HTML is displayed only as inert text.
export const sourceNode=$node('didadi_source',()=>({
  group:'block',content:'text*',marks:'',code:true,defining:true,isolating:true,
  attrs:{kind:{default:'source'}},
  parseDOM:[{tag:'pre[data-didadi-source]',preserveWhitespace:'full',getAttrs:dom=>({kind:dom.dataset.didadiSource})}],
  toDOM:node=>['pre',{'data-didadi-source':node.attrs.kind,class:'raw-source-block','aria-label':`Markdown source: ${node.attrs.kind}`},['code',0]],
  parseMarkdown:{match:node=>node.type==='didadiSource',runner:(state,node,type)=>{state.openNode(type,{kind:node.kind});state.addText(node.value);state.closeNode()}},
  toMarkdown:{match:node=>node.type.name==='didadi_source',runner:(state,node)=>state.addNode('html',undefined,node.textContent)},
}));

export const boundaryNode=$node('didadi_boundary',()=>({
  group:'block',atom:true,selectable:false,
  parseDOM:[{tag:'div[data-didadi-boundary]'}],
  toDOM:()=>['div',{'data-didadi-boundary':'',hidden:true,'aria-hidden':'true'}],
  parseMarkdown:{match:node=>node.type==='didadiBoundary',runner:(state,node,type)=>state.addNode(type)},
  toMarkdown:{match:node=>node.type.name==='didadi_boundary',runner:state=>state.addNode('html',undefined,'<!-- -->')},
}));

export function sourcePreservation(onDocument=()=>{}){
  return $proseAsync(async ctx=>{
    await ctx.wait(ParserReady);await ctx.wait(SerializerReady);
    const document=new SourceDocument(ctx.get(parserCtx),ctx.get(serializerCtx),sourceNode.type(ctx),ctx.get(schemaCtx));
    ctx.set(parserCtx,value=>document.parse(value));
    ctx.set(serializerCtx,value=>document.serialize(value));
    onDocument(document);
    // History reuses immutable content fragments for whole-document replacement.
    // Keep source metadata with those fragments, including leading/blank text.
    const sourceSnapshots=new WeakMap();
    return new Plugin({state:{init:()=>null,apply(tr,value,old){const before=document.documents.get(old.doc);if(before)sourceSnapshots.set(old.doc.content,before);document.track(tr,old.doc);const source=tr.getMeta('didadi-source-paste')||sourceSnapshots.get(tr.doc.content);if(source){document.documents.set(tr.doc,source);sourceSnapshots.set(tr.doc.content,source);}return value}},props:{handleDOMEvents:{paste(view,event){
      const text=event.clipboardData?.getData('text/plain'),selection=view.state.selection;
      // Whole-document Markdown paste must use the same parser as Git loads.
      // Leave partial selection, HTML-only paste and ordinary prose to Crepe.
      if(!view.editable||typeof text!=='string'||!frontMatter(text)||selection.from>1||selection.to<view.state.doc.content.size-1)return false;
      const parsed=document.parse(text),info=document.documents.get(parsed);
      const transaction=view.state.tr.replaceWith(0,view.state.doc.content.size,parsed.content).setMeta('didadi-source-paste',info).setMeta('paste',true).setMeta('uiEvent','paste');
      view.dispatch(transaction.scrollIntoView());event.preventDefault();return true;
    }},nodeViews:{didadi_source(node){
      if(node.attrs.kind!=='front matter')return null;
      const dom=documentGlobal('details'),summary=documentGlobal('summary'),pre=documentGlobal('pre'),contentDOM=documentGlobal('code');
      dom.className='source-properties';summary.textContent='Properties · Markdown front matter';summary.contentEditable='false';pre.append(contentDOM);dom.append(summary,pre);
      return {dom,contentDOM};
    }}}});
  },'DidadiSourceReady');
}
function documentGlobal(tag){return globalThis.document.createElement(tag)}
