import React from 'react';
import {act,fireEvent,render,screen,waitFor} from '@testing-library/react';
import {describe,it,expect,vi} from 'vitest';
vi.mock('./api',()=>({connect:vi.fn(),errorText:error=>error.message}));
vi.mock('./BlockEditor',()=>({BlockEditor:React.forwardRef(function TestEditor({value,onChange,disabled},ref){React.useImperativeHandle(ref,()=>({markdown:()=>value}));return <textarea aria-label="Markdown document" disabled={disabled} value={value} onChange={e=>onChange(e.target.value)}/>})}));
vi.mock('./downloadMarkdown',()=>({downloadMarkdown:vi.fn()}));
import {downloadMarkdown} from './downloadMarkdown';
import {App,Composer,Documents,PreservedDraft} from './App';
const doc={name:'demo.md',content:'# Team handbook\n\nA real document.',blob:'a'.repeat(40),commit:'b'.repeat(40)};
function fixture(){return {session:{agentId:'@agent',userId:'@user:local',initialRoom:'!room'},
  rooms:vi.fn().mockResolvedValue([{id:'!room',name:'Workspace',agentJoined:true}]),timeline:vi.fn().mockResolvedValue([]),
  document:vi.fn().mockResolvedValue(doc),history:vi.fn().mockResolvedValue({commits:[doc.commit,'c'.repeat(40)]}),
  send:vi.fn().mockResolvedValue({event_id:'$saved'}),task:vi.fn().mockResolvedValue({task:{status:'done',body:'保存成功（任意展示文本）',outcome:{version:1,status:'saved',path:'demo.md',commit:doc.commit,blob:doc.blob}}}),createRoom:vi.fn()};}
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
  it('preserves the draft on a real task conflict and reloads only on explicit action',async()=>{const api=fixture();api.task.mockResolvedValue({task:{status:'done',body:'发生冲突',outcome:{version:1,status:'conflict'}}});
    render(<Documents api={api} room="!room" onSent={idle} mode="edit"/>);await screen.findByLabelText('Markdown document');
    fireEvent.change(screen.getByLabelText('Markdown document'),{target:{value:'# My unsaved version'}});fireEvent.click(screen.getByRole('button',{name:'Save changes'}));
    await screen.findByText('This document has a newer version');expect(screen.getByLabelText('Markdown document')).toHaveValue('# My unsaved version');
    fireEvent.click(screen.getByRole('button',{name:'Load latest to merge'}));await waitFor(()=>expect(screen.getByLabelText('Markdown document')).toHaveValue(doc.content));expect(screen.getByLabelText('Preserved draft')).toHaveValue('# My unsaved version');
  });
  it('preserves unsaved edits when an Agent reads the document',async()=>{const api=fixture();api.task.mockResolvedValue({task:{status:'done',body:'读取完成',outcome:{version:1,status:'read'}}});
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

it('cancels an accepted save without losing its draft and displays persistent execution history',async()=>{
 const api=fixture();let cancelled=false;
 api.task.mockImplementation(async()=>({task:{status:cancelled?'cancelled':'pending',last_error:cancelled?'task_cancelled':null}}));
 api.cancel=vi.fn(async()=>{cancelled=true;return {status:'cancelled',cancelled:true}});
 api.audit=vi.fn(async()=>({events:[{sequence:1,action:'accepted',at:1,attempt:0},{sequence:2,action:'cancelled',at:2,attempt:1,reason:'task_cancelled'}]}));
 render(<App connector={async()=>api}/>);await screen.findByRole('heading',{name:'Team handbook'});
 fireEvent.click(screen.getByRole('button',{name:'Edit',exact:true}));
 fireEvent.change(screen.getByLabelText('Markdown document'),{target:{value:'# Cancel keeps this draft'}});
 fireEvent.click(screen.getByRole('button',{name:'Save changes'}));
 fireEvent.click(screen.getByRole('button',{name:'Discussion',exact:true}));
 fireEvent.click(screen.getByText(/Agent activity/));
 const cancel=await screen.findByRole('button',{name:'Cancel task'});
 await waitFor(()=>expect(cancel).toBeEnabled(),{timeout:4000});fireEvent.click(cancel);
 await screen.findByText(/The task was cancelled/,{}, {timeout:4000});
 expect(api.cancel).toHaveBeenCalledWith('!room','$saved');
 expect(screen.getByLabelText('Markdown document')).toHaveValue('# Cancel keeps this draft');
 expect(screen.getByRole('button',{name:'Save changes'})).toBeEnabled();
 expect(screen.getByRole('button',{name:'Cancel task'})).toBeDisabled();
 fireEvent.click(screen.getByRole('button',{name:'View execution history'}));
 await screen.findByRole('list',{name:'Task execution history'});
 expect(screen.getByText('Accepted')).toBeInTheDocument();expect(api.audit).toHaveBeenCalledWith('!room','$saved');
},7000);

it('sends only the selected granted source request and retries a rejection as a read',async()=>{
 const api=fixture();api.session.repositoryReads=[{repository:'fixture',path:'main.py',commit:'a'.repeat(40),room:'!room'},
  {repository:'other-room',path:'private.py',commit:'b'.repeat(40),room:'!other'}];
 api.task.mockResolvedValue({task:{status:'done',body:'权限不符',outcome:{version:1,status:'rejected',reason:'source_not_granted'}}});
 render(<Documents api={api} room="!room" onSent={idle}/>);
 await screen.findByRole('heading',{name:'Team handbook'});
 expect(screen.getByLabelText('Granted source file')).toHaveTextContent('fixture / main.py');
 expect(screen.getByLabelText('Granted source file')).not.toHaveTextContent('private.py');
 fireEvent.click(screen.getByRole('button',{name:'Read source in discussion'}));
 await screen.findByText(/Repository request rejected:/);
 expect(api.send.mock.calls[0][1]['org.didadi.repository']).toEqual({action:'read',repository:'fixture',path:'main.py'});
 fireEvent.click(screen.getByRole('button',{name:'Retry',exact:true}));
 await waitFor(()=>expect(api.send).toHaveBeenCalledTimes(2));
 expect(api.send.mock.calls[1][1]['org.didadi.repository'].action).toBe('read');
 expect(api.send.mock.calls[1][1]['org.didadi.document']).toBeUndefined();
});

it('protects an unsaved draft and uses the current blob for explicit report replacement',async()=>{
 const api=fixture();api.session.repositoryReads=[{repository:'fixture',path:'main.py',commit:'a'.repeat(40),room:'!room'}];
 api.task.mockResolvedValue({task:{status:'done',body:'报告已写入',outcome:{version:1,status:'saved',path:'demo.md',commit:'c'.repeat(40),blob:doc.blob}}});
 const view=render(<Documents api={api} room="!room" mode="edit" onSent={idle}/>);
 await screen.findByLabelText('Markdown document');
 fireEvent.change(screen.getByLabelText('Markdown document'),{target:{value:'# Unsaved source report draft'}});
 expect(screen.getByRole('button',{name:'Replace document with file report'})).toBeDisabled();
 expect(api.send).not.toHaveBeenCalled();
 fireEvent.change(screen.getByLabelText('Markdown document'),{target:{value:doc.content}});
 const report=screen.getByRole('button',{name:'Replace document with file report'});
 await waitFor(()=>expect(report).toBeEnabled());fireEvent.click(report);
 await waitFor(()=>expect(api.send).toHaveBeenCalledTimes(1));
 expect(api.send.mock.calls[0][1]['org.didadi.repository']).toEqual({action:'report',repository:'fixture',path:'main.py',base_blob:doc.blob});
});

it('retains a preserved draft and blocks report replacement after loading latest',async()=>{
 const api=fixture();api.session.repositoryReads=[{repository:'fixture',path:'main.py',commit:'a'.repeat(40),room:'!room'}];
 render(<Documents api={api} room="!room" mode="edit" onSent={idle}/>);
 await screen.findByLabelText('Markdown document');
 fireEvent.change(screen.getByLabelText('Markdown document'),{target:{value:'# Keep my recovered draft'}});
 fireEvent.click(screen.getByRole('button',{name:'Load latest',exact:true}));
 await screen.findByLabelText('Preserved draft');
 expect(screen.getByLabelText('Markdown document')).toHaveValue(doc.content);
 expect(screen.getByRole('button',{name:'Replace document with file report'})).toBeDisabled();
 fireEvent.click(screen.getByRole('button',{name:'Replace document with file report'}));
 expect(api.send).not.toHaveBeenCalled();
 expect(screen.getByLabelText('Preserved draft')).toHaveValue('# Keep my recovered draft');
 fireEvent.click(screen.getByRole('button',{name:'Restore previous draft'}));
 expect(screen.getByLabelText('Markdown document')).toHaveValue('# Keep my recovered draft');
});


it('keeps the fixed document identity while an unsaved H1 changes',async()=>{
 const api=fixture();render(<App connector={async()=>api}/>);
 await screen.findByRole('heading',{name:'Team handbook'});
 const current=screen.getByRole('button',{name:'demo.md, current document'});
 expect(current).toHaveAttribute('aria-current','page');
 expect(current).toHaveTextContent('demo.md');await waitFor(()=>expect(current).toHaveTextContent('Title: Team handbook'));
 fireEvent.click(screen.getByRole('button',{name:'Edit',exact:true}));
 fireEvent.change(screen.getByLabelText('Markdown document'),{target:{value:'# DRAFT-QA changed title'}});
 await waitFor(()=>expect(current).toHaveTextContent('Draft title: DRAFT-QA changed title'));
 expect(current.querySelector('strong')).toHaveTextContent('demo.md');
 expect(document.querySelector('.breadcrumbs strong')).toHaveTextContent('demo.md');
 expect(api.send).not.toHaveBeenCalled();
});

it('treats cancellation as a separate status and starts one explicit new save',async()=>{
 const api=fixture();api.task.mockResolvedValue({task:{status:'cancelled',last_error:'task_cancelled'}});
 render(<Documents api={api} room="!room" onSent={idle} mode="edit"/>);
 await screen.findByLabelText('Markdown document');
 const source='# Keep cancelled draft';
 fireEvent.change(screen.getByLabelText('Markdown document'),{target:{value:source}});
 fireEvent.click(screen.getByRole('button',{name:'Save changes'}));
 await screen.findByText('Task cancelled');
 expect(screen.getByRole('status')).toHaveTextContent('Choose Save changes to start a new save task.');
 expect(screen.queryByRole('alert')).toBeNull();expect(screen.queryByRole('button',{name:'Retry',exact:true})).toBeNull();
 expect(screen.getByLabelText('Markdown document')).toHaveValue(source);
 let resolve;api.send.mockImplementationOnce(()=>new Promise(r=>resolve=r));
 const save=screen.getByRole('button',{name:'Save changes'});fireEvent.click(save);fireEvent.click(save);
 expect(api.send).toHaveBeenCalledTimes(2);expect(screen.queryByText('Task cancelled')).toBeNull();
 expect(api.send.mock.calls[1][2]).not.toBe(api.send.mock.calls[0][2]);
 expect(api.send.mock.calls[1][1]['org.didadi.document'].content).toBe(source);
 await act(async()=>resolve({event_id:'$new'}));
});

it.each([['read','Read source in discussion','Choose Read source in discussion'],['report','Replace document with file report','Choose Replace document with file report']])('explains the explicit next action after a cancelled source %s',async(action,button,hint)=>{
 const api=fixture();api.session.repositoryReads=[{repository:'fixture',path:'main.py',commit:'a'.repeat(40),room:'!room'}];
 api.task.mockResolvedValue({task:{status:'cancelled',last_error:'task_cancelled'}});
 render(<Documents api={api} room="!room" onSent={idle}/>);await screen.findByRole('heading',{name:'Team handbook'});
 fireEvent.click(screen.getByRole('button',{name:button}));await screen.findByText('Task cancelled');
 expect(screen.getByRole('status')).toHaveTextContent(hint);expect(screen.queryByRole('button',{name:'Retry',exact:true})).toBeNull();
 expect(api.send).toHaveBeenCalledTimes(1);expect(api.send.mock.calls[0][1]['org.didadi.repository'].action).toBe(action);
});

it('previews recovered syntax safely but restores and exports the original bytes',async()=>{
 const api=fixture();render(<Documents api={api} room="!room" onSent={idle} mode="edit"/>);
 await screen.findByLabelText('Markdown document');
 const source='---\r\nkey: exact\r\n---\r\n# &#x20;Draft title\r\n\r\nKeep &#x20; spacing.\r\n\r\n<script>window.bad=1</script>\r\n';
 fireEvent.change(screen.getByLabelText('Markdown document'),{target:{value:source}});
 // DOM textarea input normalizes line endings; capture the exact state the editor emitted.
 const preserved=screen.getByLabelText('Markdown document').value;
 fireEvent.click(screen.getByRole('button',{name:'Load latest',exact:true}));
 await screen.findByLabelText('Preserved draft recovery');
 const recovery=screen.getByLabelText('Preserved draft recovery');
 expect(recovery.closest('.document-scroll')).not.toBeNull();
 expect(recovery.querySelector('.recovery-source')).not.toHaveAttribute('open');
 expect(recovery.querySelector('.recovery-preview')).toHaveAttribute('open');
 expect(recovery.querySelector('.markdown-body')).toHaveTextContent('Keep spacing.');
 expect(recovery.querySelector('script')).toBeNull();
 expect(recovery.querySelector('.recovery-source textarea').value).toBe(preserved);
 fireEvent.click(screen.getByRole('button',{name:'Restore previous draft'}));
 expect(screen.getByLabelText('Markdown document')).toHaveValue(preserved);
 fireEvent.click(screen.getByRole('button',{name:'Export Markdown'}));
 expect(downloadMarkdown).toHaveBeenLastCalledWith(preserved);expect(api.send).not.toHaveBeenCalled();
});


it('passes preserved CRLF, Unicode, entities and escapes to restore byte for byte',()=>{
 const source='---\r\nkey: exact\r\n---\r\n# &#x20;草稿\r\n\r\nLiteral &#x20; and \\*escaped\\* spaces.\r\n';
 const restore=vi.fn();render(<PreservedDraft value={source} onRestore={restore}/>);
 fireEvent.click(screen.getByRole('button',{name:'Restore previous draft'}));
 expect(restore).toHaveBeenCalledWith(source);
 expect(new TextEncoder().encode(restore.mock.calls[0][0])).toEqual(new TextEncoder().encode(source));
});

it('does not restore a preserved draft during a version load',async()=>{
 const api=fixture();render(<Documents api={api} room="!room" onSent={idle} mode="edit"/>);
 await screen.findByLabelText('Markdown document');
 fireEvent.change(screen.getByLabelText('Markdown document'),{target:{value:'# Preserved before load'}});
 fireEvent.click(screen.getByRole('button',{name:'Load latest',exact:true}));await screen.findByLabelText('Preserved draft recovery');
 let resolve;api.document.mockImplementationOnce(()=>new Promise(r=>resolve=r));
 fireEvent.click(screen.getByRole('button',{name:'Load latest',exact:true}));
 expect(screen.getByRole('button',{name:'Restore previous draft'})).toBeDisabled();
 fireEvent.click(screen.getByRole('button',{name:'Restore previous draft'}));
 expect(screen.getByLabelText('Markdown document')).toHaveValue(doc.content);
 await act(async()=>resolve(doc));
 expect(screen.getByRole('button',{name:'Restore previous draft'})).toBeEnabled();
 expect(screen.getByLabelText('Preserved draft')).toHaveValue('# Preserved before load');
});


it.each([undefined,{version:2,status:'saved'},{version:1,status:'saved',path:'demo.md',commit:'invalid',blob:'invalid'}])('keeps a draft on an unsupported result and loads Git without sending a second task',async outcome=>{
 const api=fixture();api.task.mockResolvedValue({task:{status:'done',body:'Saved demo.md',outcome}});
 render(<Documents api={api} room="!room" onSent={idle} mode="edit"/>);await screen.findByLabelText('Markdown document');
 fireEvent.change(screen.getByLabelText('Markdown document'),{target:{value:'# Keep unsupported draft'}});
 fireEvent.click(screen.getByRole('button',{name:'Save changes'}));await screen.findByText(/runtime returned no supported/);
 expect(screen.getByLabelText('Markdown document')).toHaveValue('# Keep unsupported draft');
 expect(screen.queryByRole('button',{name:'Retry',exact:true})).toBeNull();
 expect(screen.getByRole('button',{name:'Save changes'})).toBeDisabled();fireEvent.click(screen.getByRole('button',{name:'Save changes'}));
 const load=screen.getAllByRole('button',{name:'Load latest',exact:true})[0];fireEvent.click(load);
 await screen.findByLabelText('Preserved draft');expect(screen.getByLabelText('Preserved draft')).toHaveValue('# Keep unsupported draft');
 expect(api.send).toHaveBeenCalledTimes(1);
});


it('keeps the unsupported-result write guard until a latest-version read actually succeeds',async()=>{
 const api=fixture();api.task.mockResolvedValue({task:{status:'done',body:'Saved legacy'}});
 render(<Documents api={api} room="!room" onSent={idle} mode="edit"/>);await screen.findByLabelText('Markdown document');
 fireEvent.change(screen.getByLabelText('Markdown document'),{target:{value:'# Unknown completion'}});
 fireEvent.click(screen.getByRole('button',{name:'Save changes'}));await screen.findByText(/runtime returned no supported/);
 api.document.mockRejectedValueOnce(new Error('Git read unavailable'));
 fireEvent.click(screen.getAllByRole('button',{name:'Load latest',exact:true})[0]);await screen.findByText('Git read unavailable');
 expect(screen.getByRole('button',{name:'Save changes'})).toBeDisabled();
 fireEvent.click(screen.getByRole('button',{name:'Retry',exact:true}));await screen.findByLabelText('Preserved draft');
 expect(screen.getByRole('button',{name:'Save changes'})).toBeEnabled();
 expect(screen.getByLabelText('Preserved draft')).toHaveValue('# Unknown completion');expect(api.send).toHaveBeenCalledTimes(1);
});
