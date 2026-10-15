import React from 'react';
import {render,screen,fireEvent,waitFor} from '@testing-library/react';
import {it,expect,vi} from 'vitest';
import {Documents} from './App';
import {readMarkdown} from './readMarkdown';

it('renders front matter as collapsed properties and the first H1 once, without changing source',async()=>{
 const content='---\r\nOrder: 3\r\nArea: editor\r\n---\r\n# Basic *editing*\r\n\r\nText.\r\n';
 const api={session:{synthetic:true,agentId:'@agent'},document:async()=>({content,commit:'a',blob:'b'}),history:async()=>({commits:[]}),send:vi.fn().mockResolvedValue({event_id:'$save'}),task:async()=>({task:{status:'done',body:'Saved demo.md'}})};
 const {container,rerender}=render(<Documents api={api} room="!room" onSent={()=>{}}/>);
 await screen.findByRole('heading',{name:'Basic editing',level:1});
 expect(container.querySelectorAll('h1')).toHaveLength(1);
 expect(container.querySelector('hr')).toBeNull();expect(container.querySelector('h2')).toBeNull();
 const properties=container.querySelector('details.document-properties');
 expect(properties).not.toHaveAttribute('open');expect(properties).toHaveTextContent('Order: 3');
 expect(container.querySelector('.markdown-body')).toHaveTextContent('Text.');
 rerender(<Documents api={api} room="!room" mode="edit" onSent={()=>{}}/>);
 await screen.findByRole('textbox',{name:'Document body'});
 fireEvent.click(screen.getByRole('button',{name:'Save changes'}));
 await waitFor(()=>expect(api.send).toHaveBeenCalled());
 expect(api.send.mock.calls[0][1]['org.didadi.document'].content).toBe(content);
});
it('uses only top-level AST headings and supports Setext without disturbing other source',()=>{
 const source='```md\n# Fake\n```\n\n> # Also fake\n\nReal title\n==========\n\n# Later section\n';
 const view=readMarkdown(source);
 expect(view.title).toBe('Real title');expect(view.properties).toBe('');
 expect(view.body).toBe(source.replace('Real title\n==========',''));
});
it('keeps no-front-matter documents and inert HTML intact for safe rendering',()=>{
 expect(readMarkdown('# Title\n\nBody.')).toEqual({title:'Title',properties:'',body:'\n\nBody.'});
 expect(readMarkdown('No title\n\n<script>bad()</script>').body).toContain('<script>bad()</script>');
 expect(readMarkdown('No title').title).toBe('Untitled document');
});
