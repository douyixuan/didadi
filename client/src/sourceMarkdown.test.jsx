import React,{createRef} from 'react';
import {render,screen,act,fireEvent,waitFor} from '@testing-library/react';
import {describe,it,expect,vi} from 'vitest';
import {BlockEditor} from './BlockEditor';
import {sourceBlocks} from './sourceMarkdown';
async function open(source){const ref=createRef(),onChange=vi.fn(),rendered=render(<BlockEditor value={source} onChange={onChange} ref={ref}/>);const dom=await screen.findByRole('textbox',{name:'Document body'});return {ref,onChange,dom,...rendered}}
async function edit(element,value){await act(async()=>{element.textContent=value;fireEvent.input(element.closest('.ProseMirror'),{inputType:'insertText',data:value})})}
describe('source preserving editing',()=>{
 it.each(['\n','\r\n'])('edits a list item without changing markers, siblings or gaps (%j)',async nl=>{
  const source=['','## 中文','','- first','- **second**','', '', '~~~js','a();','~~~','','<div>原样</div>','','end',''].join(nl);
  const {ref,dom}=await open(source);await edit(dom.querySelector('li p'),'first EDIT');await waitFor(()=>expect(ref.current.markdown()).toContain('first EDIT'));
  expect(ref.current.markdown()).toBe(source.replace('first','first EDIT'));
 });
 it('edits raw CRLF source without changing other line endings',async()=>{
  const source='# 标题\r\n\r\n```js title=keep\r\nx()\r\ny()\r\n```\r\n\r\nAfter\r\n';
  const {ref,dom,unmount}=await open(source);const code=dom.querySelector('pre[data-didadi-source] code');await edit(code,code.textContent.replace('x()','changed()'));await waitFor(()=>expect(ref.current.markdown()).toContain('changed()'));const saved=ref.current.markdown();expect(saved).toBe(source.replace('x()','changed()'));unmount();const reopened=await open(saved);expect(reopened.ref.current.markdown()).toBe(saved);
 });
 it('preserves fence spelling and whitespace when editing a different paragraph',async()=>{
  const source='Title\n=====\n\nParagraph  with  spaces.\n\n~~~~python\nx = 1\n~~~~\n\n* a\n* b';
  const {ref,dom,unmount}=await open(source);await edit(dom.querySelector('p'),'Edited  with  spaces.');await waitFor(()=>expect(ref.current.markdown()).toContain('Edited'));
  const saved=ref.current.markdown();expect(saved).toBe(source.replace('Paragraph','Edited'));unmount();const reopened=await open(saved);expect(reopened.ref.current.markdown()).toBe(saved);expect(reopened.dom.querySelector('h1')).toHaveTextContent('Title');
 });
 it('keeps references and metadata local and inert; raw text edits undo',async()=>{
  const source='---\ntitle: 中文\n---\n\nHello.\n\nUse [ref][id] and <kbd>X</kbd>.\n\n[id]: https://example.invalid "标题"\n\n```js title="keep"\nx()\n```\n';
  const {ref,dom}=await open(source);expect(dom.querySelector('.source-properties summary')).toHaveTextContent('Properties');expect(dom.querySelector('kbd')).toBeNull();expect(dom.querySelectorAll('pre')).toHaveLength(4);
  const raw=dom.querySelector('pre[data-didadi-source] code');await edit(raw,raw.textContent.replace('Use','Read'));await waitFor(()=>expect(ref.current.markdown()).toContain('Read [ref]'));expect(ref.current.markdown()).toBe(source.replace('Use','Read'));
  fireEvent.click(screen.getByRole('button',{name:'Undo',exact:true}));expect(ref.current.markdown()).toBe(source);
 });
 it('edits a GFM table cell while preserving the other rows and surrounding source',async()=>{
  const source='# Table\n\n| Left | Right |\n| :--- | ---: |\n| one | two |\n| 三 | 四 |\n\nEnd.\n';const {ref,dom}=await open(source);expect(dom.querySelector('table')).not.toBeNull();await edit(dom.querySelector('td p'),'changed');await waitFor(()=>expect(ref.current.markdown()).toContain('changed'));expect(ref.current.markdown()).toBe(source.replace('one','changed'));
 });
 it('preserves repeated equal blocks with different source spelling through edit and undo',async()=>{
  const source='- same\n\n<!-- boundary -->\n\n* same\n\nText\n';const {ref,dom}=await open(source);await edit(dom.querySelectorAll('li p')[1],'changed');await waitFor(()=>expect(ref.current.markdown()).toContain('changed'));expect(ref.current.markdown()).toBe(source.replace('* same','* changed'));fireEvent.click(screen.getByRole('button',{name:'Undo',exact:true}));expect(ref.current.markdown()).toBe(source);
 });
 it('splits front matter without losing CRLF or trailing blank lines',()=>{const source='---\r\nx: 1\r\n---\r\n\r\nText\r\n\r\n';const parts=sourceBlocks(source);expect(parts.before+parts.blocks.map(b=>b.source+b.after).join('')).toBe(source);expect(parts.blocks[0].kind).toBe('front matter')});
});

describe('Markdown structural boundaries',()=>{
 it('keeps duplicated ordered lists separate with their starting numbers on reopen',async()=>{
  const {ref,dom,unmount}=await open('1. a\n2. b\n');fireEvent.click(screen.getByRole('button',{name:'Duplicate block'}));expect(dom.querySelectorAll('ol')).toHaveLength(2);
  const saved=ref.current.markdown();expect(saved).toContain('<!-- -->');unmount();const reopened=await open(saved);expect(reopened.dom.querySelectorAll('ol')).toHaveLength(2);expect(reopened.dom.querySelectorAll('ol')[1].getAttribute('start')||'1').toBe('1');expect(reopened.ref.current.markdown()).toBe(saved);
 });
});

it('retains a setext heading underline after replacing its text through the DOM',async()=>{
 const source='Original\n========\n\nUnchanged.\n';const {ref,dom}=await open(source);
 await edit(dom.querySelector('h1'),'Replaced');await waitFor(()=>expect(ref.current.markdown()).toContain('Replaced'));expect(ref.current.markdown()).toBe(source.replace('Original','Replaced'));
});
