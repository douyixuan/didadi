import {unified} from 'unified';
import remarkParse from 'remark-parse';
import remarkGfm from 'remark-gfm';
const parser=unified().use(remarkParse).use(remarkGfm);
// Comparison helper for semantic regression tests; source spelling is preserved separately.
export function semanticMarkdown(value){
  function clean(node){const {position,spread,...rest}=node;return {...rest,...(rest.children?{children:rest.children.map(clean)}:{})}}
  return clean(parser.parse(value));
}
