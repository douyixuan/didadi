import React,{useMemo} from 'react';
function treeFor(sources){
  const root=new Map();
  sources.forEach((source,index)=>{let children=root;const parts=[source.repository,...source.path.split('/')];
    parts.forEach((label,depth)=>{if(!children.has(label))children.set(label,{label,key:JSON.stringify(parts.slice(0,depth+1)),children:new Map()});const node=children.get(label);if(depth===parts.length-1)node.index=index;children=node.children;});
  });return root;
}
export function SourceFileTree({sources,selected,onSelect,disabled=false}){
  const root=useMemo(()=>treeFor(sources),[sources]);
  function nodes(children){return <ul>{[...children.values()].sort((a,b)=>a.label.localeCompare(b.label)).map(node=><li key={node.key}>
    {node.index!==undefined&&<button type="button" disabled={disabled} aria-current={node.index===selected?'true':undefined} aria-label={'Open '+sources[node.index].repository+' / '+sources[node.index].path} onClick={()=>onSelect(node.index)}>{node.label}</button>}
    {node.children.size>0&&<details open><summary>{node.label}</summary>{nodes(node.children)}</details>}
  </li>)}</ul>}
  return <nav className="source-file-tree" aria-label="Granted source files"><p>Folders contain granted files only.</p>{nodes(root)}</nav>;
}
