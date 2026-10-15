import {$node,$proseAsync} from '@milkdown/kit/utils';
import {parserCtx,serializerCtx,schemaCtx,ParserReady,SerializerReady} from '@milkdown/kit/core';
import {Plugin} from '@milkdown/kit/prose/state';
import {SourceDocument} from './sourceMarkdown';

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
    return new Plugin({state:{init:()=>null,apply(tr,value,old){document.track(tr,old.doc);return value}},props:{nodeViews:{didadi_source(node){
      if(node.attrs.kind!=='front matter')return null;
      const dom=documentGlobal('details'),summary=documentGlobal('summary'),pre=documentGlobal('pre'),contentDOM=documentGlobal('code');
      dom.className='source-properties';summary.textContent='Properties · Markdown front matter';summary.contentEditable='false';pre.append(contentDOM);dom.append(summary,pre);
      return {dom,contentDOM};
    }}}});
  },'DidadiSourceReady');
}
function documentGlobal(tag){return globalThis.document.createElement(tag)}
