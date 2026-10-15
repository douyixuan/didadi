import {unified} from 'unified';
import remarkParse from 'remark-parse';
import remarkGfm from 'remark-gfm';
import {diffChars,diffArrays} from 'diff';

const parser=unified().use(remarkParse).use(remarkGfm);
const emptyParagraph='<!-- didadi:empty-paragraph -->';
const supported=new Set(['paragraph','heading','list','listItem','blockquote','code','thematicBreak','text','strong','emphasis','delete','inlineCode','link','break','table','tableRow','tableCell']);
function needsSource(node){
  return !supported.has(node.type)||(node.type==='code'&&node.meta)||node.children?.some(needsSource);
}
// Offsets are UTF-16, as are JS slicing and remark positions. Keep every gap byte.
export function sourceBlocks(source){
  const front=/^(?:\uFEFF)?---[ \t]*\r?\n[\s\S]*?\r?\n(?:---|\.\.\.)[ \t]*(?=\r?\n|$)/.exec(source);
  const prefix=front?.[0]||'';
  const tree=parser.parse(source.slice(prefix.length));
  const blocks=tree.children.map(node=>({start:node.position.start.offset+prefix.length,end:node.position.end.offset+prefix.length,raw:!!needsSource(node),kind:node.type}));
  if(prefix)blocks.unshift({start:0,end:prefix.length,raw:true,kind:'front matter'});
  return {blocks:blocks.map((block,index)=>({...block,source:source.slice(block.start,block.end),after:source.slice(block.end,blocks[index+1]?.start??source.length)})),before:source.slice(0,blocks[0]?.start??source.length)};
}

// Apply a semantic serializer delta to the original spelling. Equal canonical
// characters map to original offsets; edited syntax is accepted only when the
// editor parser proves that the patched source represents the requested node.
export function patchSource(original,canonical,next,valid){
  if(canonical===next)return original;
  const offsets=new Map();let c=0,s=0;
  for(const part of diffChars(canonical,original)){
    if(part.added){s+=part.value.length;continue}
    if(part.removed){c+=part.value.length;continue}
    for(let i=0;i<=part.value.length;i++)offsets.set(c+i,s+i);
    c+=part.value.length;s+=part.value.length;
  }
  const edits=[];let pos=0;
  for(const part of diffChars(canonical,next)){
    if(part.added){const previous=edits.at(-1);if(previous&&previous.end===pos)previous.text+=part.value;else edits.push({start:pos,end:pos,text:part.value});}
    else if(part.removed){edits.push({start:pos,end:pos+part.value.length,text:''});pos+=part.value.length;}
    else pos+=part.value.length;
  }
  let patched=original;
  for(const edit of edits.reverse()){
    const start=offsets.get(edit.start),end=offsets.get(edit.end);
    if(start===undefined||end===undefined||start>end)return null;
    patched=patched.slice(0,start)+edit.text+patched.slice(end);
  }
  return valid(patched)?patched:null;
}

// When Enter/split changes a block's tree, preserve the spelling of canonical
// lines that survived the edit. Reparse validation rejects a guessed alignment
// if restoring a marker, indentation or hard-break would change semantics.
function patchLines(original,canonical,next,valid){
  const lines=value=>(value.match(/[^\n]*\n|[^\n]+$/g)||[]).map(line=>({text:line.replace(/\r?\n$/,''),eol:line.endsWith('\r\n')?'\r\n':line.endsWith('\n')?'\n':''}));
  const source=lines(original),before=lines(canonical),after=lines(next);
  const key=line=>line.text.trim().replace(/^(?:[*+-]|\d+[.)])\s+/,'').replace(/^(`{3,}|~{3,}).*$/,'FENCE');
  const sourceAt=new Map(),previousAt=new Map();let sourceIndex=0,beforeIndex=0;
  for(const part of diffArrays(source.map(key),before.map(key))){
    if(part.added)beforeIndex+=part.value.length;
    else if(part.removed)sourceIndex+=part.value.length;
    else for(let i=0;i<part.value.length;i++)sourceAt.set(beforeIndex++,sourceIndex++);
  }
  let oldIndex=0,newIndex=0;
  for(const part of diffArrays(before.map(key),after.map(key))){
    if(part.added)newIndex+=part.value.length;
    else if(part.removed)oldIndex+=part.value.length;
    else for(let i=0;i<part.value.length;i++)previousAt.set(newIndex++,oldIndex++);
  }
  const marker=/^( *)([*+-]|\d+[.)])([ \t]+)/,newline=original.includes('\r\n')?'\r\n':'\n';
  const restored=after.map((line,index)=>{
    const old=previousAt.get(index),at=sourceAt.get(old);
    if(at!==undefined)return {text:source[at].text,eol:source[at].eol||newline};
    let text=line.text;const prefix=marker.exec(text);
    if(prefix){
      // Use an original marker at the same canonical nesting depth. Only the
      // marker/spacing is borrowed; ordered-list digits still follow the edit.
      for(let i=0;i<before.length;i++){
        const match=marker.exec(before[i].text),sourceLine=source[sourceAt.get(i)],originalPrefix=sourceLine&&marker.exec(sourceLine.text);
        if(match&&originalPrefix&&match[1]===prefix[1]&&/^\d/.test(match[2])===/^\d/.test(prefix[2])){
          const bullet=/^\d/.test(prefix[2])?prefix[2].slice(0,-1).padStart(originalPrefix[2].length-1,'0')+originalPrefix[2].at(-1):originalPrefix[2];text=originalPrefix[1]+bullet+originalPrefix[3]+text.slice(prefix[0].length);break;
        }
      }
    }
    return {text,eol:newline};
  });
  const patched=restored.map((line,index)=>line.text+(index<restored.length-1?line.eol:'')).join('');
  return valid(patched)?patched:null;
}

function patchRawSource(original,next){
  const normalized=original.replace(/\r\n?/g,'\n'),offsets=[];let index=0;
  for(let i=0;i<original.length;i++){
    offsets[index++]=i;if(original[i]==='\r'&&original[i+1]==='\n')i++;
  }
  offsets[index]=original.length;
  let old=0,result='';const newline=original.includes('\r\n')?'\r\n':'\n';
  for(const part of diffChars(normalized,next)){
    if(part.added)result+=part.value.replace(/\n/g,newline);
    else if(part.removed)old+=part.value.length;
    else {result+=original.slice(offsets[old],offsets[old+part.value.length]);old+=part.value.length;}
  }
  return result;
}

export class SourceDocument {
  constructor(parse,serialize,rawType,schema){this.parseRich=parse;this.serializeRich=serialize;this.rawType=rawType;this.schema=schema;this.origins=new WeakMap();this.documents=new WeakMap();this.richCache=new Map();}
  layout(node){return {type:node.type.name,children:Array.from({length:node.childCount},(_,index)=>this.layout(node.child(index)))}}
  equivalent(left,right){
    const clean=node=>{
      const attrs={...node.attrs};
      // Milkdown derives labels from list position on parse. A PM split keeps
      // the previous label until reparse; it is not document content.
      if(node.type.name==='list_item')delete attrs.label;
      return {type:node.type.name,attrs,text:node.text,marks:node.marks.map(mark=>mark.toJSON()),children:Array.from({length:node.childCount},(_,i)=>clean(node.child(i)))};
    };
    return JSON.stringify(clean(left))===JSON.stringify(clean(right));
  }
  canonical(node){return this.serializeRich(this.schema.topNodeType.create(null,[node])).replace(/\n$/,'');}
  parse(source){
    const parts=sourceBlocks(source),nodes=[];
    for(const block of parts.blocks){
      let node;
      if(block.source==='<!-- -->')node=this.schema.nodes.didadi_boundary.create();
      else if(block.source===emptyParagraph)node=this.schema.nodes.paragraph.create();
      else if(block.raw)node=this.rawType.create({kind:block.kind},block.source?this.schema.text(block.source.replace(/\r\n?/g,'\n')):null);
      else {
        let cached=this.richCache.get(block.source);
        if(!cached){
          const parsed=this.parseRich(block.source);
          cached={doc:parsed,canonical:parsed.childCount===1?this.canonical(parsed.firstChild):null};
          this.richCache.set(block.source,cached);
          if(this.richCache.size>512)this.richCache.delete(this.richCache.keys().next().value);
        }
        const doc=cached.doc;
        // A parser extension must not silently split/drop a source slice.
        if(doc.childCount!==1)node=this.rawType.create({kind:'source'},this.schema.text(block.source));
        else node=doc.firstChild.type.create(doc.firstChild.attrs,doc.firstChild.content,doc.firstChild.marks);
      }
      this.origins.set(node,{...block,node,canonical:node.type===this.rawType?block.source:(this.richCache.get(block.source)?.canonical??this.canonical(node))});nodes.push(node);
    }
    if(!nodes.length)nodes.push(this.schema.nodes.paragraph.create());
    const doc=this.schema.topNodeType.create(null,nodes);this.documents.set(doc,{before:parts.before,source,blank:!parts.blocks.length});return doc;
  }
  patchText(origin,node){
    const before=[],after=[];
    const shape=value=>{
      const walk=n=>{if(n.isText){value.push(n.text);return {type:'text',marks:n.marks.map(m=>m.toJSON())}}return {type:n.type.name,attrs:n.attrs,children:Array.from({length:n.childCount},(_,i)=>walk(n.child(i)))}};
      return walk;
    };
    if(JSON.stringify(shape(before)(origin.node))!==JSON.stringify(shape(after)(node)))return null;
    let cursor=0,patched='',changed=false;
    for(let i=0;i<before.length;i++){
      const at=origin.source.indexOf(before[i],cursor);if(at<0)return null;
      patched+=origin.source.slice(cursor,at)+after[i];cursor=at+before[i].length;changed ||= before[i]!==after[i];
    }
    if(!changed)return null;
    patched+=origin.source.slice(cursor);
    try {const parsed=this.parseRich(patched);return parsed.childCount===1&&this.equivalent(parsed.firstChild,node)?patched:null}catch{return null}
  }
  track(transaction,previous){
    if(!transaction.docChanged)return;
    const info=this.documents.get(previous);
    if(info)this.documents.set(transaction.doc,info);
    previous.forEach((node,pos)=>{
      const origin=this.origins.get(node);if(!origin)return;
      const mapped=transaction.mapping.mapResult(pos+Math.min(1,node.nodeSize-1),1);
      if(mapped.deleted)return;
      const resolved=transaction.doc.resolve(Math.min(mapped.pos,transaction.doc.content.size));
      const candidate=resolved.depth?resolved.node(1):transaction.doc.nodeAt(mapped.pos);
      if(candidate&&!this.origins.has(candidate))this.origins.set(candidate,origin);
    });
  }
  serialize(doc){
    const info=this.documents.get(doc);
    if(doc.childCount===1&&doc.firstChild.type.name==='paragraph'&&!doc.firstChild.content.size)return info?.blank?info.source:'';
    const pieces=[];doc.forEach((node,pos,index)=>{
      const origin=this.origins.get(node);
      // Crepe adds a final empty typing paragraph. A real original blank file
      // remains represented by document metadata; typed/deleted content does not.
      if(!origin&&node.type.name==='paragraph'&&!node.content.size&&pieces.length&&index===doc.childCount-1)return;
      let text;
      if(node.type.name==='didadi_boundary')text='<!-- -->';
      else if(node.type.name==='paragraph'&&!node.content.size&&!origin)text=emptyParagraph;
      else if(node.type===this.rawType)text=origin?patchRawSource(origin.source,node.textContent):node.textContent;
      else if(origin&&node.eq(origin.node))text=origin.source;
      else {
        const canonical=this.canonical(node);
        const valid=source=>{
          try {const parsed=this.parseRich(source);return parsed.childCount===1&&this.equivalent(parsed.firstChild,node)}catch{return false}
        };
        if(origin){
          const structural=JSON.stringify(this.layout(origin.node))!==JSON.stringify(this.layout(node));
          text=this.patchText(origin,node);
          if(text===null)text=structural?
            patchLines(origin.source,origin.canonical,canonical,valid)??patchSource(origin.source,origin.canonical,canonical,valid):
            patchSource(origin.source,origin.canonical,canonical,valid)??patchLines(origin.source,origin.canonical,canonical,valid);
        }else text=null;
        text??=canonical;
      }
      pieces.push({text,after:origin?.after,origin,node});
    });
    let result=info?.before||'';
    pieces.forEach((piece,index)=>{
      const next=pieces[index+1];
      if(next&&(piece.node.type.name==='code_block'||piece.node.type===this.rawType&&piece.node.attrs.kind==='code')){
        const fence=/^(`{3,}|~{3,})[^\r\n]*(?:\r?\n|$)/.exec(piece.text);
        if(fence){
          const lines=piece.text.split(/\r?\n/),closing=new RegExp('^ {0,3}'+fence[1][0]+'{'+fence[1].length+',} *$');
          if(!lines.slice(1).some(line=>closing.test(line)))piece.text+='\n'+fence[1];
        }
      }
      result+=piece.text;
      if(next){
        const adjacent=piece.origin&&next.origin&&piece.origin.end+piece.origin.after.length===next.origin.start;
        let separator=adjacent?piece.origin.after:'\n\n';
        const unchanged=adjacent&&piece.node.eq(piece.origin.node)&&next.node.eq(next.origin.node);
        if(!unchanged){
          const left=sourceBlocks(piece.text).blocks,right=sourceBlocks(next.text).blocks;
          if(sourceBlocks(piece.text+separator+next.text).blocks.length<left.length+right.length){
            separator='\n\n';
            if(sourceBlocks(piece.text+separator+next.text).blocks.length<left.length+right.length)separator='\n\n<!-- -->\n\n';
          }
        }
        result+=separator;
      }else result+=piece.after??(piece.text?'\n':'');
    });
    return result;
  }
}
