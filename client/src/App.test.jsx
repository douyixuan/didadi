import React from 'react';
import {act,fireEvent,render,screen,waitFor} from '@testing-library/react';
import {describe,it,expect,vi} from 'vitest';
vi.mock('./api',()=>({connect:vi.fn(),errorText:error=>error.message}));
vi.mock('./BlockEditor',()=>({BlockEditor:React.forwardRef(function TestEditor({value,onChange,disabled},ref){React.useImperativeHandle(ref,()=>({markdown:()=>value}));return <textarea aria-label="Markdown document" disabled={disabled} value={value} onChange={e=>onChange(e.target.value)}/>})}));
vi.mock('./downloadMarkdown',()=>({downloadMarkdown:vi.fn()}));
import {downloadMarkdown} from './downloadMarkdown';
import {App,Composer,Documents} from './App';
const doc={name:'demo.md',content:'# Team handbook\n\nA real document.',blob:'a'.repeat(40),commit:'b'.repeat(40)};
function fixture(){return {session:{agentId:'@agent',userId:'@user:local',initialRoom:'!room'},
  rooms:vi.fn().mockResolvedValue([{id:'!room',name:'Workspace',agentJoined:true}]),timeline:vi.fn().mockResolvedValue([]),
  document:vi.fn().mockResolvedValue(doc),history:vi.fn().mockResolvedValue({commits:[doc.commit,'c'.repeat(40)]}),
  send:vi.fn().mockResolvedValue({event_id:'$saved'}),task:vi.fn().mockResolvedValue({task:{status:'done',body:'Saved demo.md'}}),createRoom:vi.fn()};}
const idle=()=>{};
describe('reliable message operations',()=>{
  it('prevents repeated submit while pending',async()=>{let resolve;const send=vi.fn(()=>new Promise(r=>resolve=r));
    render(<Composer onSend={send} busyRoom="!room" agentId="@agent" clearReply={idle} onSent={idle}/>);
    fireEvent.change(screen.getByLabelText('Message'),{target:{value:'hello'}});const form=screen.getByRole('button',{name:'Send'}).closest('form');
    fireEvent.submit(form);fireEvent.submit(form);expect(send).toHaveBeenCalledTimes(1);
    await act(async()=>resolve({event_id:'$one'}));expect(screen.getByLabelText('Message')).toHaveValue('');
  });
  it('preserves failed draft and reuses the transaction ID when retrying',async()=>{const send=vi.fn().mockRejectedValueOnce(new Error('Backend offline')).mockResolvedValue({event_id:'$one'});
    render(<Composer onSend={send} busyRoom="!room" agentId="@agent" clearReply={idle} onSent={idle}/>);
    fireEvent.change(screen.getByLabelText('Message'),{target:{value:'keep this draft'}});fireEvent.click(screen.getByRole('button',{name:'Send'}));
    await screen.findByRole('alert');expect(screen.getByLabelText('Message')).toHaveValue('keep this draft');fireEvent.click(screen.getByRole('button',{name:'Send'}));
    await waitFor(()=>expect(send).toHaveBeenCalledTimes(2));expect(send.mock.calls[0][1]).toBe(send.mock.calls[1][1]);
  });
});
describe('document-first workspace',()=>{
  it('shows the document as the primary reading surface with collaboration closed',async()=>{const api=fixture();render(<App connector={async()=>api}/>);
    await screen.findByRole('heading',{name:'Team handbook'});expect(screen.queryByLabelText('Markdown document')).not.toBeInTheDocument();
    expect(screen.getByLabelText('Collaboration panel')).toHaveClass('panel-closed');expect(api.document).toHaveBeenCalledWith('!room',undefined);
    fireEvent.click(screen.getByRole('button',{name:'Edit',exact:true}));expect(screen.getByLabelText('Markdown document')).toHaveValue(doc.content);
  });
  it('shows loading, then a recoverable document failure',async()=>{const api=fixture();let reject;api.document.mockImplementationOnce(()=>new Promise((_,r)=>reject=r));
    render(<Documents api={api} room="!room" onSent={idle}/>);expect(screen.getByRole('status',{name:'Loading document'})).toBeInTheDocument();
    await act(async()=>reject(new Error('Document service unavailable')));expect(screen.getByRole('alert')).toHaveTextContent('Document service unavailable');
    fireEvent.click(screen.getByRole('button',{name:'Retry'}));await screen.findByRole('heading',{name:'Team handbook'});
  });
  it('keeps edits on send failure and retries the exact save transaction',async()=>{const api=fixture();api.send.mockRejectedValueOnce(new Error('Network failed'));
    render(<Documents api={api} room="!room" onSent={idle} mode="edit"/>);await screen.findByLabelText('Markdown document');
    fireEvent.change(screen.getByLabelText('Markdown document'),{target:{value:'# Keep my edits'}});fireEvent.click(screen.getByRole('button',{name:'Save changes'}));
    await screen.findByRole('alert');expect(screen.getByLabelText('Markdown document')).toHaveValue('# Keep my edits');
    fireEvent.click(screen.getByRole('button',{name:'Retry'}));await waitFor(()=>expect(api.send).toHaveBeenCalledTimes(2));
    expect(api.send.mock.calls[0][2]).toBe(api.send.mock.calls[1][2]);
  });
  it('preserves the draft on a real task conflict and reloads only on explicit action',async()=>{const api=fixture();api.task.mockResolvedValue({task:{status:'done',body:'Document conflict: newer version'}});
    render(<Documents api={api} room="!room" onSent={idle} mode="edit"/>);await screen.findByLabelText('Markdown document');
    fireEvent.change(screen.getByLabelText('Markdown document'),{target:{value:'# My unsaved version'}});fireEvent.click(screen.getByRole('button',{name:'Save changes'}));
    await screen.findByText('This document has a newer version');expect(screen.getByLabelText('Markdown document')).toHaveValue('# My unsaved version');
    fireEvent.click(screen.getByRole('button',{name:'Load latest to merge'}));await waitFor(()=>expect(screen.getByLabelText('Markdown document')).toHaveValue(doc.content));expect(screen.getByLabelText('Preserved draft')).toHaveValue('# My unsaved version');
  });
  it('preserves unsaved edits when an Agent reads the document',async()=>{const api=fixture();api.task.mockResolvedValue({task:{status:'done',body:'demo.md at Git commit: sample'}});
    render(<Documents api={api} room="!room" onSent={idle} mode="edit"/>);await screen.findByLabelText('Markdown document');
    fireEvent.change(screen.getByLabelText('Markdown document'),{target:{value:'# Unsaved read draft'}});fireEvent.click(screen.getByRole('button',{name:'Ask example Agent to read'}));
    await screen.findByLabelText('Preserved draft');expect(screen.getByLabelText('Preserved draft')).toHaveValue('# Unsaved read draft');
  });
  it('opens an immutable version and keeps raw HTML inert',async()=>{const api=fixture();api.document.mockImplementation(async(room,commit)=>({...doc,commit:commit||doc.commit,content:'# Safe document\n\n<script>bad()</script>'}));
    render(<Documents api={api} room="!room" onSent={idle} historyOpen/>);await screen.findByRole('heading',{name:'Safe document'});
    fireEvent.click(screen.getByRole('button',{name:/Previous version/}));await screen.findByText('Historical version');
    expect(api.document).toHaveBeenLastCalledWith('!room','c'.repeat(40));expect(document.querySelector('script')).toBeNull();
  });
});

describe('editing and navigation regressions',()=>{
  it('keeps unsent message drafts when changing rooms',()=>{const props={onSend:vi.fn(),agentId:'@agent',clearReply:idle,onSent:idle};
    const view=render(<Composer {...props} busyRoom="!one"/>);fireEvent.change(screen.getByLabelText('Message'),{target:{value:'room one draft'}});
    view.rerender(<Composer {...props} busyRoom="!two"/>);expect(screen.getByLabelText('Message')).toHaveValue('');
    view.rerender(<Composer {...props} busyRoom="!one"/>);expect(screen.getByLabelText('Message')).toHaveValue('room one draft');
  });
  it('does not create two document operations on repeated save clicks',async()=>{const api=fixture();let resolve;api.send.mockImplementation(()=>new Promise(r=>resolve=r));
    render(<Documents api={api} room="!room" onSent={idle} mode="edit"/>);await screen.findByLabelText('Markdown document');
    const save=screen.getByRole('button',{name:'Save changes'});fireEvent.click(save);fireEvent.click(save);expect(api.send).toHaveBeenCalledTimes(1);
    await act(async()=>resolve({event_id:'$one'}));
  });
});


it('unlocks a failed save task and keeps the draft for an explicit new retry',async()=>{
 const api=fixture();api.task.mockResolvedValue({task:{status:'failed',last_error:'room_forbidden'}});
 render(<Documents api={api} room="!room" onSent={idle} mode="edit"/>);
 await screen.findByLabelText('Markdown document');
 fireEvent.change(screen.getByLabelText('Markdown document'),{target:{value:'# Keep terminal failure draft'}});
 fireEvent.click(screen.getByRole('button',{name:'Save changes'}));
 await screen.findByText(/The Agent no longer has access/);
 expect(screen.getByLabelText('Markdown document')).toHaveValue('# Keep terminal failure draft');
 expect(screen.getByRole('button',{name:'Save changes'})).toBeEnabled();
 fireEvent.click(screen.getByRole('button',{name:'Save changes'}));
 await waitFor(()=>expect(api.send).toHaveBeenCalledTimes(2));
 expect(api.send.mock.calls[0][2]).not.toBe(api.send.mock.calls[1][2]);
});

it('opens a receipt version without losing a draft and returns to its original discussion',async()=>{
 const api=fixture(),commit='c'.repeat(40);
 const receipt={id:'$receipt',sender:'@agent',time:1,content:{body:'Saved demo.md\nGit commit: '+commit+'\nBlob: '+'d'.repeat(40),'m.relates_to':{rel_type:'m.thread',event_id:'$original'},'org.didadi.task':{id:'$original'}}};
 api.timeline.mockResolvedValue([receipt,{id:'$unrelated',sender:'@user:local',content:{body:'Unrelated message'}}]);
 api.document.mockImplementation(async(room,version)=>version?{...doc,commit:version,content:'# Referenced document\n\nImmutable body.'}:doc);
 render(<App connector={async()=>api}/>);
 await screen.findByRole('heading',{name:'Team handbook'});
 fireEvent.click(screen.getByRole('button',{name:'Edit',exact:true}));
 fireEvent.change(screen.getByLabelText('Markdown document'),{target:{value:'# Unsaved current draft'}});
 fireEvent.click(screen.getByRole('button',{name:'Discussion',exact:true}));
 fireEvent.click(await screen.findByRole('button',{name:'Open document version'}));
 await screen.findByRole('heading',{name:'Referenced document'});
 expect(api.document).toHaveBeenLastCalledWith('!room',commit);
 expect(screen.getByLabelText('Preserved draft')).toHaveValue('# Unsaved current draft');
 const back=screen.getByRole('button',{name:'View version discussion'});await waitFor(()=>expect(back).toBeEnabled());fireEvent.click(back);
 expect(screen.getByText('Thread $original')).toBeInTheDocument();
 expect(screen.queryByText('Unrelated message')).toBeNull();
});

it('does not invent a discussion for an empty Git repository or an ordinary message',async()=>{
 const api=fixture();api.document.mockResolvedValue({...doc,content:'',commit:null,blob:null});
 api.timeline.mockResolvedValue([{id:'$plain',sender:'@human',content:{body:'Ordinary discussion'}}]);
 render(<App connector={async()=>api}/>);
 await screen.findByRole('heading',{name:'Untitled document'});
 expect(screen.getByRole('button',{name:'View version discussion'})).toBeDisabled();
 expect(screen.queryByRole('button',{name:'Open document version'})).toBeNull();
});

it('retries a failed receipt read as the same immutable read and never saves the draft',async()=>{
 const api=fixture(),commit='c'.repeat(40);let reads=0;
 api.timeline.mockResolvedValue([{id:'$receipt',sender:'@agent',content:{body:'Saved demo.md\nGit commit: '+commit,'m.relates_to':{rel_type:'m.thread',event_id:'$root'},'org.didadi.task':{id:'$root'}}}]);
 api.document.mockImplementation(async(room,version)=>{
  if(version&&++reads===1)throw new Error('Historical read unavailable');
  return version?{...doc,commit:version,content:'# Recovered version'}:doc;
 });
 render(<App connector={async()=>api}/>);await screen.findByRole('heading',{name:'Team handbook'});
 fireEvent.click(screen.getByRole('button',{name:'Edit',exact:true}));
 fireEvent.change(screen.getByLabelText('Markdown document'),{target:{value:'# Do not save my draft'}});
 fireEvent.click(screen.getByRole('button',{name:'Discussion',exact:true}));
 fireEvent.click(await screen.findByRole('button',{name:'Open document version'}));
 await screen.findByText('Historical read unavailable');
 fireEvent.click(screen.getByRole('button',{name:'Retry',exact:true}));
 await screen.findByRole('heading',{name:'Recovered version'});
 expect(api.document).toHaveBeenLastCalledWith('!room',commit);
 expect(api.send).not.toHaveBeenCalled();expect(screen.getByLabelText('Preserved draft')).toHaveValue('# Do not save my draft');
});

it('exports the full current draft, including front matter, without saving or rendering HTML',async()=>{
 const api=fixture();const source='---\ntitle: Export\n---\n# Export\n\n<details>raw source</details>\n';
 api.document.mockResolvedValue({...doc,content:source});
 render(<Documents api={api} room="!room" onSent={idle} mode="edit"/>);
 await screen.findByLabelText('Markdown document');
 const edited=source+'\nUnsaved 中文 draft.\n';
 fireEvent.change(screen.getByLabelText('Markdown document'),{target:{value:edited}});
 fireEvent.click(screen.getByRole('button',{name:'Export Markdown'}));
 expect(downloadMarkdown).toHaveBeenLastCalledWith(edited);expect(api.send).not.toHaveBeenCalled();
 expect(screen.getByLabelText('Markdown document')).toHaveValue(edited);
});
it('exports the exact historical Markdown instead of the title-stripped read presentation',async()=>{
 const api=fixture();const source='---\nkey: value\n---\n# Historical\n\nBody.\n';
 api.document.mockResolvedValue({...doc,content:source});
 render(<Documents api={api} room="!room" onSent={idle} historyOpen/>);
 await screen.findByRole('heading',{name:'Historical'});
 fireEvent.click(screen.getByRole('button',{name:/Previous version/}));
 await screen.findByText('Historical version');
 fireEvent.click(screen.getByRole('button',{name:'Export Markdown'}));
 expect(downloadMarkdown).toHaveBeenLastCalledWith(source);expect(api.send).not.toHaveBeenCalled();
});
