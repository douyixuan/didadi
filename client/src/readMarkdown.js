import {unified} from 'unified';
import remarkParse from 'remark-parse';
import remarkGfm from 'remark-gfm';
import {frontMatter} from './sourceMarkdown';

const parser=unified().use(remarkParse).use(remarkGfm);
function plainText(node){
  if(node.type==='text'||node.type==='inlineCode')return node.value;
  if(node.type==='image')return node.alt||'';
  return (node.children||[]).map(plainText).join('');
}
// Presentation only: do not round-trip or rewrite the saved Markdown.
export function readMarkdown(source){
  const properties=frontMatter(source);
  const content=source.slice(properties.length);
  const nodes=parser.parse(content).children;
  const heading=nodes.find(node=>node.type==='heading'&&node.depth===1);
  const hidden=nodes.filter(node=>node===heading||node.type==='html'&&node.value==='<!-- didadi:empty-paragraph -->');
  let body=content;
  for(const node of hidden.reverse())body=body.slice(0,node.position.start.offset)+body.slice(node.position.end.offset);
  return {title:heading?plainText(heading):'Untitled document',properties,body};
}
