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
  const heading=parser.parse(content).children.find(node=>node.type==='heading'&&node.depth===1);
  return {title:heading?plainText(heading):'Untitled document',properties,
    body:heading?content.slice(0,heading.position.start.offset)+content.slice(heading.position.end.offset):content};
}
