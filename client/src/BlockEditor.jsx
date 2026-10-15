import React,{forwardRef,useEffect,useImperativeHandle,useRef,useState} from 'react';
import {sourceNode,boundaryNode,sourcePreservation} from './sourcePlugin';
import {Crepe} from '@milkdown/crepe';
import {editorViewCtx,serializerCtx} from '@milkdown/kit/core';
import {$prose} from '@milkdown/kit/utils';
import {Plugin,TextSelection} from '@milkdown/kit/prose/state';
import {uploadConfig} from '@milkdown/kit/plugin/upload';
import {undo,redo} from '@milkdown/kit/prose/history';
import '@milkdown/crepe/theme/common/style.css';
import '@milkdown/crepe/theme/frame.css';

// Crepe owns the editing state. React receives Markdown only; no editor JSON is persisted.
const RichBlockEditor=forwardRef(function RichBlockEditor({value,onChange,disabled=false,onComposingChange=()=>{}},ref){
  const root=useRef(null),instance=useRef(null),touched=useRef(false),change=useRef(onChange),initial=useRef(value);
  const [ready,setReady]=useState(false),[failure,setFailure]=useState('');
  change.current=onChange;
  const read=()=>instance.current&&touched.current?instance.current.getMarkdown():initial.current;
  useImperativeHandle(ref,()=>({markdown:read}));
  useEffect(()=>{
    let disposed=false;
    const crepe=new Crepe({root:root.current,defaultValue:initial.current,features:{
      [Crepe.Feature.ImageBlock]:false,[Crepe.Feature.Table]:true,[Crepe.Feature.Latex]:false,
      [Crepe.Feature.AI]:false,[Crepe.Feature.TopBar]:true,
    },featureConfigs:{[Crepe.Feature.BlockEdit]:{advancedGroup:{image:null,math:null}},[Crepe.Feature.TopBar]:{buildTopBar(builder){for(const group of builder.build())for(const item of group.items){if(item.icon){const label=item.key.replaceAll('-',' ');item.icon=item.icon.replace('<svg',`<svg role="img" aria-label="${label}"`);}}}}}});
    crepe.editor.use(sourceNode).use(boundaryNode).use(sourcePreservation());
    crepe.editor.config(ctx=>ctx.update(uploadConfig.key,config=>({...config,uploader:async()=>[]})));
    crepe.editor.use($prose(ctx=>new Plugin({view:()=>({update(view,previous){
      if(!disposed&&instance.current===crepe&&!view.state.doc.eq(previous.doc)){touched.current=true;change.current(ctx.get(serializerCtx)(view.state.doc));}
    }})})));
    const creating=crepe.create().then(()=>{
      if(disposed)return crepe.destroy();instance.current=crepe;crepe.setReadonly(disabled);setReady(true);
      crepe.editor.action(ctx=>{const dom=ctx.get(editorViewCtx).dom;dom.setAttribute('aria-label','Document body');dom.setAttribute('role','textbox');dom.setAttribute('aria-multiline','true')});
    }).catch(error=>{if(!disposed)setFailure('Editor could not open: '+error.message)});
    return()=>{disposed=true;instance.current=null;creating.then(()=>crepe.destroy()).catch(()=>{})};
  },[]);
  useEffect(()=>{if(ready)instance.current?.setReadonly(disabled)},[disabled,ready]);
  function history(command){instance.current?.editor.action(ctx=>{const view=ctx.get(editorViewCtx);command(view.state,view.dispatch);view.focus()})}
  function blockAction(action){instance.current?.editor.action(ctx=>{
    const view=ctx.get(editorViewCtx),{state}=view,{$from}=state.selection;
    if(!$from.depth)return;
    const pos=$from.before(1),node=$from.node(1),index=$from.index(0);let tr=state.tr,target=pos;
    if(action==='duplicate'){target=pos+node.nodeSize;tr=tr.insert(target,node)}
    if(action==='delete'){tr=tr.delete(pos,pos+node.nodeSize);target=Math.min(pos,tr.doc.content.size)}
    if(action==='up'&&index>0){target=pos-state.doc.child(index-1).nodeSize;tr=tr.delete(pos,pos+node.nodeSize).insert(target,node)}
    if(action==='down'&&index<state.doc.childCount-1){target=pos+state.doc.child(index+1).nodeSize;tr=tr.delete(pos,pos+node.nodeSize).insert(target,node)}
    if(tr.docChanged){tr=tr.setSelection(TextSelection.near(tr.doc.resolve(Math.min(target+1,tr.doc.content.size))));view.dispatch(tr.scrollIntoView());view.focus()}
  })}
  return <div className="block-editor" onCompositionStartCapture={()=>onComposingChange(true)} onCompositionEndCapture={()=>onComposingChange(false)}>
    <div className="block-editor-help"><span>Type / for blocks · drag the ⋮⋮ handle to reorder</span><button type="button" aria-label="Undo" disabled={!ready||disabled} onClick={()=>history(undo)}>Undo</button><button type="button" aria-label="Redo" disabled={!ready||disabled} onClick={()=>history(redo)}>Redo</button></div>
    <div className="block-actions" aria-label="Current block actions">{[['duplicate','Duplicate block'],['delete','Delete block'],['up','Move block up'],['down','Move block down']].map(([action,label])=><button key={action} type="button" disabled={!ready||disabled} onMouseDown={e=>e.preventDefault()} onClick={()=>blockAction(action)}>{label}</button>)}</div>
    {!ready&&!failure&&<p role="status">Opening block editor…</p>}{failure&&<p role="alert">{failure}</p>}<div ref={root}/>
  </div>;
});

export const BlockEditor=RichBlockEditor;
