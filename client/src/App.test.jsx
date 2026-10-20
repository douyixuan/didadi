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
 fireEvent.click(screen.getByRole('button',{name:'Ask Agent to read source'}));
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
 await waitFor(()=>expect(screen.getByRole('button',{name:'Restore previous draft'})).toBeEnabled());fireEvent.click(screen.getByRole('button',{name:'Restore previous draft'}));
 await waitFor(()=>expect(screen.getByLabelText('Markdown document')).toHaveValue('# Keep my recovered draft'));
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
 expect(screen.getByText(/Choose Save changes/)).toHaveTextContent('Choose Save changes to start a new save task.');
 expect(screen.queryByRole('alert')).toBeNull();expect(screen.queryByRole('button',{name:'Retry',exact:true})).toBeNull();
 expect(screen.getByLabelText('Markdown document')).toHaveValue(source);
 let resolve;api.send.mockImplementationOnce(()=>new Promise(r=>resolve=r));
 const save=screen.getByRole('button',{name:'Save changes'});fireEvent.click(save);fireEvent.click(save);
 expect(api.send).toHaveBeenCalledTimes(2);expect(screen.queryByText('Task cancelled')).toBeNull();
 expect(api.send.mock.calls[1][2]).not.toBe(api.send.mock.calls[0][2]);
 expect(api.send.mock.calls[1][1]['org.didadi.document'].content).toBe(source);
 await act(async()=>resolve({event_id:'$new'}));
});

it.each([['read','Ask Agent to read source','Choose Ask Agent to read source'],['report','Replace document with file report','Choose Replace document with file report']])('explains the explicit next action after a cancelled source %s',async(action,button,hint)=>{
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
 expect(recovery).toHaveTextContent('Local recovery status is shown above');
 expect(recovery.closest('.document-scroll')).not.toBeNull();
 expect(recovery.querySelector('.recovery-source')).not.toHaveAttribute('open');
 expect(recovery.querySelector('.recovery-preview')).toHaveAttribute('open');
 expect(recovery.querySelector('.markdown-body')).toHaveTextContent('Keep spacing.');
 expect(recovery.querySelector('script')).toBeNull();
 expect(recovery.querySelector('.recovery-source textarea').value).toBe(preserved);
 await waitFor(()=>expect(screen.getByRole('button',{name:'Restore previous draft'})).toBeEnabled());fireEvent.click(screen.getByRole('button',{name:'Restore previous draft'}));
 await waitFor(()=>expect(screen.getByLabelText('Markdown document')).toHaveValue(preserved));
 fireEvent.click(screen.getByRole('button',{name:'Export Markdown'}));
 expect(downloadMarkdown).toHaveBeenLastCalledWith(preserved);expect(api.send).not.toHaveBeenCalled();
});


it('passes preserved CRLF, Unicode, entities and escapes to restore byte for byte',async()=>{
 const source='---\r\nkey: exact\r\n---\r\n# &#x20;草稿\r\n\r\nLiteral &#x20; and \\*escaped\\* spaces.\r\n';
 const restore=vi.fn();render(<PreservedDraft value={source} onRestore={restore}/>);
 await waitFor(()=>expect(screen.getByRole('button',{name:'Restore previous draft'})).toBeEnabled());fireEvent.click(screen.getByRole('button',{name:'Restore previous draft'}));
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


it('saves a large human draft directly without a Matrix command and retries the same operation',async()=>{
 const api=fixture();const text='# Direct save\n'+'中'.repeat(3000);
 api.saveDocument=vi.fn().mockRejectedValueOnce(new Error('Connection lost')).mockImplementation(async(room,content)=>{
  api.document.mockResolvedValue({...doc,content,commit:'c'.repeat(40),blob:'d'.repeat(40)});
  return {status:'saved',commit:'c'.repeat(40),blob:'d'.repeat(40),receipt_pending:false};
 });
 render(<Documents api={api} room="!room" onSent={idle} mode="edit"/>);await screen.findByLabelText('Markdown document');
 fireEvent.change(screen.getByLabelText('Markdown document'),{target:{value:text}});
 fireEvent.click(screen.getByRole('button',{name:'Save changes'}));await screen.findByText('Connection lost');
 expect(screen.getByLabelText('Markdown document')).toHaveValue(text);
 expect(screen.getByLabelText('Markdown document')).toBeDisabled();expect(screen.getByRole('button',{name:'Load latest',exact:true})).toBeDisabled();
 expect(screen.getByRole('button',{name:'Save changes'})).toBeDisabled();
 fireEvent.click(screen.getByRole('button',{name:'Retry',exact:true}));await screen.findByText(/Saved directly to Git/);
 expect(api.saveDocument).toHaveBeenCalledTimes(2);expect(api.saveDocument.mock.calls[0]).toEqual(api.saveDocument.mock.calls[1]);
 expect(api.send).not.toHaveBeenCalled();expect(api.task).not.toHaveBeenCalled();
});

it('keeps a direct-save conflict draft and treats a pending receipt as a successful save',async()=>{
 const api=fixture();const conflict=Object.assign(new Error('stale'),{status:409,data:{status:'conflict'}});
 api.saveDocument=vi.fn().mockRejectedValueOnce(conflict).mockImplementation(async(room,content)=>{
  api.document.mockResolvedValue({...doc,content});return {status:'saved',commit:doc.commit,blob:doc.blob,receipt_pending:true};
 });
 render(<Documents api={api} room="!room" onSent={idle} mode="edit"/>);await screen.findByLabelText('Markdown document');
 fireEvent.change(screen.getByLabelText('Markdown document'),{target:{value:'# Keep direct conflict'}});
 fireEvent.click(screen.getByRole('button',{name:'Save changes'}));await screen.findByText('This document has a newer version');
 expect(screen.getByLabelText('Markdown document')).toHaveValue('# Keep direct conflict');
 fireEvent.click(screen.getByRole('button',{name:'Load latest to merge'}));await screen.findByLabelText('Preserved draft');
 await waitFor(()=>expect(screen.getByRole('button',{name:'Restore previous draft'})).toBeEnabled());fireEvent.click(screen.getByRole('button',{name:'Restore previous draft'}));await waitFor(()=>expect(screen.getByRole('button',{name:'Save changes'})).toBeEnabled());fireEvent.click(screen.getByRole('button',{name:'Save changes'}));
 await screen.findByText(/discussion receipt is pending/);expect(screen.queryByRole('alert')).toBeNull();
 expect(api.send).not.toHaveBeenCalled();
});

it('blocks direct saves over the UTF-8 byte limit and for a read-only document',async()=>{
 const api=fixture();api.saveDocument=vi.fn();api.document.mockResolvedValue({...doc,writable:false});
 const view=render(<Documents api={api} room="!room" onSent={idle} mode="edit"/>);await screen.findByLabelText('Markdown document');
 expect(screen.getByRole('button',{name:'Save changes'})).toBeDisabled();expect(api.saveDocument).not.toHaveBeenCalled();view.unmount();
 api.document.mockResolvedValue(doc);render(<Documents api={api} room="!room" onSent={idle} mode="edit"/>);await screen.findByLabelText('Markdown document');
 fireEvent.change(screen.getByLabelText('Markdown document'),{target:{value:'中'.repeat(22000)}});
 fireEvent.click(screen.getByRole('button',{name:'Save changes'}));await screen.findByText(/at most 64 KiB/);expect(api.saveDocument).not.toHaveBeenCalled();
});

it('retries the direct save after a local size error instead of repeating the previous source task',async()=>{
 const api=fixture();api.session.repositoryReads=[{repository:'fixture',path:'main.py',commit:'a'.repeat(40),room:'!room'}];
 api.task.mockResolvedValue({task:{status:'done',outcome:{version:1,status:'rejected',reason:'source_not_granted'}}});
 api.saveDocument=vi.fn().mockImplementation(async(room,content)=>{
  api.document.mockResolvedValue({...doc,content});
  return {status:'saved',commit:doc.commit,blob:doc.blob,receipt_pending:false};
 });
 render(<Documents api={api} room="!room" mode="edit" onSent={idle}/>);await screen.findByLabelText('Markdown document');
 fireEvent.click(screen.getByRole('button',{name:'Ask Agent to read source'}));await screen.findByText(/Repository request rejected:/);
 fireEvent.change(screen.getByLabelText('Markdown document'),{target:{value:'中'.repeat(22000)}});
 fireEvent.click(screen.getByRole('button',{name:'Save changes'}));await screen.findByText(/at most 64 KiB/);
 expect(api.saveDocument).not.toHaveBeenCalled();expect(api.send).toHaveBeenCalledTimes(1);
 fireEvent.change(screen.getByLabelText('Markdown document'),{target:{value:'# Smaller preserved draft'}});
 fireEvent.click(screen.getByRole('button',{name:'Retry',exact:true}));
 await waitFor(()=>expect(api.saveDocument).toHaveBeenCalledTimes(1));
 expect(api.send).toHaveBeenCalledTimes(1);expect(api.saveDocument.mock.calls[0][1]).toBe('# Smaller preserved draft');
});

describe('local unsaved document recovery',()=>{
 it('reopens Git first and explicitly restores an exact local draft after remount',async()=>{
  const api=fixture(),source='---\ntitle: 本地\n---\n# Unsaved\n\\*exact*';
  const first=render(<Documents api={api} room="!room" mode="edit" onSent={idle}/>);await screen.findByLabelText('Markdown document');
  fireEvent.change(screen.getByLabelText('Markdown document'),{target:{value:source}});await screen.findByText(/Unsaved draft kept on this browser only/);first.unmount();
  render(<Documents api={api} room="!room" mode="edit" onSent={idle}/>);await screen.findByLabelText('Local draft recovery');
  expect(screen.getByLabelText('Markdown document')).toHaveValue(doc.content);expect(api.send).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole('button',{name:'Restore local draft'}));await waitFor(()=>expect(screen.getByLabelText('Markdown document')).toHaveValue(source));
  fireEvent.click(screen.getByRole('button',{name:'Export Markdown'}));expect(downloadMarkdown).toHaveBeenLastCalledWith(source);
 });
 it('does not restore another user or room when props change',async()=>{
  const api=fixture();const view=render(<Documents api={api} room="!room" mode="edit" onSent={idle}/>);await screen.findByLabelText('Markdown document');
  fireEvent.change(screen.getByLabelText('Markdown document'),{target:{value:'# Private Alice'}});
  const bob={...api,session:{...api.session,userId:'@bob:local'}};view.rerender(<Documents api={bob} room="!room" mode="edit" onSent={idle}/>);
  await waitFor(()=>expect(screen.getByLabelText('Markdown document')).toHaveValue(doc.content));expect(screen.queryByLabelText('Local draft recovery')).not.toBeInTheDocument();
  view.rerender(<Documents api={api} room="!different" mode="edit" onSent={idle}/>);await waitFor(()=>expect(api.document).toHaveBeenLastCalledWith('!different',undefined));expect(screen.queryByText('# Private Alice')).not.toBeInTheDocument();
 });
 it('keeps a conflicting draft across remount and clears restored copies after confirmed save',async()=>{
  const api=fixture();api.saveDocument=vi.fn().mockRejectedValueOnce(Object.assign(new Error('conflict'),{status:409,data:{status:'conflict'}})).mockResolvedValue({status:'saved',commit:doc.commit,blob:doc.blob});
  const first=render(<Documents api={api} room="!room" mode="edit" onSent={idle}/>);await screen.findByLabelText('Markdown document');
  fireEvent.change(screen.getByLabelText('Markdown document'),{target:{value:'# Keep after conflict'}});fireEvent.click(screen.getByRole('button',{name:'Save changes'}));await screen.findByText('This document has a newer version');first.unmount();
  api.document.mockResolvedValue({...doc,blob:'d'.repeat(40),content:'# New Git'});
  const second=render(<Documents api={api} room="!room" mode="edit" onSent={idle}/>);await screen.findByText(/Git has changed since this draft began/);
  fireEvent.click(screen.getByRole('button',{name:'Restore local draft'}));await waitFor(()=>expect(screen.getByLabelText('Markdown document')).toHaveValue('# Keep after conflict'));fireEvent.click(screen.getByRole('button',{name:'Save changes'}));await screen.findByText(/Saved directly to Git/);expect(api.saveDocument.mock.calls[1][2]).toBe(doc.blob);second.unmount();
  render(<Documents api={api} room="!room" mode="edit" onSent={idle}/>);await screen.findByLabelText('Markdown document');expect(screen.queryByLabelText('Local draft recovery')).not.toBeInTheDocument();
 });
 it('discards only a selected recovered draft without changing Git',async()=>{
  const api=fixture();const first=render(<Documents api={api} room="!room" mode="edit" onSent={idle}/>);await screen.findByLabelText('Markdown document');
  fireEvent.change(screen.getByLabelText('Markdown document'),{target:{value:'# discard me'}});first.unmount();
  render(<Documents api={api} room="!room" mode="edit" onSent={idle}/>);await screen.findByLabelText('Local draft recovery');fireEvent.click(screen.getByRole('button',{name:'Discard local draft'}));
  await waitFor(()=>expect(screen.queryByLabelText('Local draft recovery')).not.toBeInTheDocument());expect(screen.getByLabelText('Markdown document')).toHaveValue(doc.content);expect(api.send).not.toHaveBeenCalled();
 });
 it('keeps editing and export available when storage is denied',async()=>{
  const api=fixture();const spy=vi.spyOn(Storage.prototype,'setItem').mockImplementation(()=>{throw new DOMException('denied','SecurityError');});
  try{render(<Documents api={api} room="!room" mode="edit" onSent={idle}/>);await screen.findByLabelText('Markdown document');fireEvent.change(screen.getByLabelText('Markdown document'),{target:{value:'# Memory still works'}});
   await waitFor(()=>expect(screen.getByRole('alert')).toHaveTextContent('Local draft storage is unavailable'));expect(screen.getByLabelText('Markdown document')).toHaveValue('# Memory still works');
   fireEvent.click(screen.getByRole('button',{name:'Export Markdown'}));expect(downloadMarkdown).toHaveBeenLastCalledWith('# Memory still works');
  }finally{spy.mockRestore();}
 });
});

it('does not replace current edits with an older local draft and supports explicit current discard',async()=>{
 const api=fixture();const first=render(<Documents api={api} room="!room" mode="edit" onSent={idle}/>);await screen.findByLabelText('Markdown document');
 fireEvent.change(screen.getByLabelText('Markdown document'),{target:{value:'# older local'}});await screen.findByText(/Unsaved draft kept/);first.unmount();
 render(<Documents api={api} room="!room" mode="edit" onSent={idle}/>);await screen.findByLabelText('Local draft recovery');
 fireEvent.change(screen.getByLabelText('Markdown document'),{target:{value:'# current edits'}});
 expect(screen.getByRole('button',{name:'Restore local draft'})).toBeDisabled();expect(screen.getByLabelText('Markdown document')).toHaveValue('# current edits');
 await waitFor(()=>expect(screen.getByRole('button',{name:'Discard current draft'})).toBeEnabled());fireEvent.click(screen.getByRole('button',{name:'Discard current draft'}));
 await waitFor(()=>expect(screen.getByLabelText('Markdown document')).toHaveValue(doc.content));await waitFor(()=>expect(screen.getByRole('button',{name:'Restore local draft'})).toBeEnabled());
 fireEvent.click(screen.getByRole('button',{name:'Restore local draft'}));await waitFor(()=>expect(screen.getByLabelText('Markdown document')).toHaveValue('# older local'));
});
it('does not replace the editor after failed local recovery and can export the older copy',async()=>{
 const api=fixture();const first=render(<Documents api={api} room="!room" mode="edit" onSent={idle}/>);await screen.findByLabelText('Markdown document');
 fireEvent.change(screen.getByLabelText('Markdown document'),{target:{value:'# stored before denial'}});await screen.findByText(/Unsaved draft kept/);first.unmount();
 render(<Documents api={api} room="!room" mode="edit" onSent={idle}/>);await screen.findByLabelText('Local draft recovery');
 const spy=vi.spyOn(Storage.prototype,'setItem').mockImplementation(()=>{throw new DOMException('full','QuotaExceededError');});
 try{await waitFor(()=>expect(screen.getByRole('button',{name:'Restore local draft'})).toBeEnabled());fireEvent.click(screen.getByRole('button',{name:'Restore local draft'}));await screen.findByText(/Local draft storage is unavailable/);
  expect(screen.getByLabelText('Markdown document')).toHaveValue(doc.content);fireEvent.click(screen.getByRole('button',{name:'Export local draft'}));expect(downloadMarkdown).toHaveBeenLastCalledWith('# stored before denial');
 }finally{spy.mockRestore();}
});
it('only adopts latest Git as the restored save base after an explicit merge confirmation',async()=>{
 const api=fixture();const first=render(<Documents api={api} room="!room" mode="edit" onSent={idle}/>);await screen.findByLabelText('Markdown document');
 fireEvent.change(screen.getByLabelText('Markdown document'),{target:{value:'# old local'}});await screen.findByText(/Unsaved draft kept/);first.unmount();
 const latest='d'.repeat(40);api.document.mockResolvedValue({...doc,blob:latest,content:'# newer Git'});api.saveDocument=vi.fn().mockRejectedValueOnce(Object.assign(new Error('stale'),{status:409,data:{status:'conflict'}})).mockResolvedValue({status:'saved',commit:doc.commit,blob:latest});
 render(<Documents api={api} room="!room" mode="edit" onSent={idle}/>);await screen.findByLabelText('Local draft recovery');await waitFor(()=>expect(screen.getByRole('button',{name:'Restore local draft'})).toBeEnabled());
 fireEvent.click(screen.getByRole('button',{name:'Restore local draft'}));await waitFor(()=>expect(screen.getByLabelText('Markdown document')).toHaveValue('# old local'));fireEvent.click(screen.getByRole('button',{name:'Save changes'}));await screen.findByText('This document has a newer version');expect(api.saveDocument.mock.calls[0][2]).toBe(doc.blob);
 fireEvent.change(screen.getByLabelText('Markdown document'),{target:{value:'# merged old local and newer Git'}});fireEvent.click(screen.getByRole('button',{name:'I reviewed and merged latest Git text'}));fireEvent.click(screen.getByRole('button',{name:'Save changes'}));await screen.findByText(/Saved directly to Git/);expect(api.saveDocument.mock.calls[1][2]).toBe(latest);
});

it('keeps a preserved draft durable while editing the latest Git text',async()=>{
 const api=fixture();const first=render(<Documents api={api} room="!room" mode="edit" onSent={idle}/>);await screen.findByLabelText('Markdown document');
 fireEvent.change(screen.getByLabelText('Markdown document'),{target:{value:'# older preserved'}});fireEvent.click(screen.getByRole('button',{name:'Load latest',exact:true}));await screen.findByLabelText('Preserved draft');
 fireEvent.change(screen.getByLabelText('Markdown document'),{target:{value:'# new working copy'}});await screen.findByText(/Unsaved draft kept/);first.unmount();
 render(<Documents api={api} room="!room" mode="edit" onSent={idle}/>);await waitFor(()=>expect(screen.getAllByLabelText('Local draft recovery')).toHaveLength(2));
 expect(screen.getByText('# older preserved',{selector:'pre'})).toBeInTheDocument();expect(screen.getByText('# new working copy',{selector:'pre'})).toBeInTheDocument();
});
it.each(['restore','discard'])('locks only the %s transition while a browser storage lock is queued',async action=>{
 const api=fixture();const first=render(<Documents api={api} room="!room" mode="edit" onSent={idle}/>);await screen.findByLabelText('Markdown document');
 fireEvent.change(screen.getByLabelText('Markdown document'),{target:{value:'# queued copy'}});await screen.findByText(/Unsaved draft kept/);
 if(action==='restore'){first.unmount();render(<Documents api={api} room="!room" mode="edit" onSent={idle}/>);await screen.findByLabelText('Local draft recovery');await waitFor(()=>expect(screen.getByRole('button',{name:'Restore local draft'})).toBeEnabled());}
 const original=navigator.locks;let release;const gate=new Promise(resolve=>release=resolve);Object.defineProperty(navigator,'locks',{configurable:true,value:{request:(name,callback)=>gate.then(()=>original.request(name,callback))}});
 try{fireEvent.click(screen.getByRole('button',{name:action==='restore'?'Restore local draft':'Discard current draft'}));
  expect(screen.getByLabelText('Markdown document')).toBeDisabled();expect(screen.getByRole('button',{name:'Save changes'})).toBeDisabled();expect(screen.getByRole('button',{name:'Load latest',exact:true})).toBeDisabled();
  fireEvent.change(screen.getByLabelText('Markdown document'),{target:{value:'# must not enter during transition'}});
  await act(async()=>release());await waitFor(()=>expect(screen.getByLabelText('Markdown document')).toBeEnabled());
  expect(screen.getByLabelText('Markdown document')).toHaveValue(action==='restore'?'# queued copy':doc.content);expect(api.send).not.toHaveBeenCalled();
 }finally{release();Object.defineProperty(navigator,'locks',{configurable:true,value:original});}
});

it('does not switch away from current edits when checkpoint storage fails',async()=>{
 const api=fixture();const first=render(<Documents api={api} room="!room" mode="edit" onSent={idle}/>);await screen.findByLabelText('Markdown document');
 fireEvent.change(screen.getByLabelText('Markdown document'),{target:{value:'# durable original'}});await screen.findByText(/Unsaved draft kept/);
 api.document.mockResolvedValue({...doc,content:'# new Git snapshot'});const spy=vi.spyOn(Storage.prototype,'setItem').mockImplementation(()=>{throw new DOMException('full','QuotaExceededError');});
 try{fireEvent.click(screen.getByRole('button',{name:'Load latest',exact:true}));await screen.findByText(/Cannot switch versions safely/);expect(screen.getByLabelText('Markdown document')).toHaveValue('# durable original');}
 finally{spy.mockRestore();}
 first.unmount();render(<Documents api={api} room="!room" mode="edit" onSent={idle}/>);await screen.findByLabelText('Local draft recovery');expect(screen.getByText('# durable original',{selector:'pre'})).toBeInTheDocument();
});

it('clears the failed room refresh on reconnect while an exact uncertain save is retried',async()=>{
 const api=fixture(),intervals=new Map();api.rooms.mockResolvedValue([{id:'!room',name:'Workspace',agentJoined:true}]);
 const timer=vi.spyOn(globalThis,'setInterval').mockImplementation((callback,ms)=>{intervals.set(ms,callback);return 12345+ms;});
 api.saveDocument=vi.fn().mockRejectedValueOnce(new TypeError('fetch failed')).mockImplementation(async(_room,content)=>{api.document.mockResolvedValue({...doc,content});return {status:'saved',commit:doc.commit,blob:doc.blob};});
 try{render(<App connector={async()=>api}/>);await screen.findByRole('heading',{name:'Team handbook'});fireEvent.click(screen.getByRole('button',{name:'Edit',exact:true}));
  fireEvent.change(screen.getByLabelText('Markdown document'),{target:{value:'# Retry after reconnect'}});api.rooms.mockRejectedValueOnce(new TypeError('fetch failed'));
  await act(async()=>intervals.get(10000)());await screen.findByText(/Room list is reconnecting: fetch failed/);
  fireEvent.click(screen.getByRole('button',{name:'Save changes'}));await screen.findByText(/Editing is paused while this save is uncertain/);
  await act(async()=>intervals.get(2000)());await waitFor(()=>expect(screen.queryByText(/Room list is reconnecting/)).not.toBeInTheDocument());
  fireEvent.click(screen.getByRole('button',{name:'Retry',exact:true}));await screen.findByText(/Saved directly to Git/);
  expect(screen.queryByText('fetch failed')).not.toBeInTheDocument();expect(api.saveDocument.mock.calls[1]).toEqual(api.saveDocument.mock.calls[0]);
 }finally{timer.mockRestore();}
});

it('keeps unrelated failed room creation visible when background polling recovers',async()=>{
 const api=fixture(),intervals=new Map();api.createRoom.mockRejectedValue(new Error('Room creation denied'));
 const timer=vi.spyOn(globalThis,'setInterval').mockImplementation((callback,ms)=>{intervals.set(ms,callback);return 23456+ms;});
 try{render(<App connector={async()=>api}/>);await screen.findByRole('heading',{name:'Team handbook'});
  fireEvent.change(screen.getByLabelText('New local room name'),{target:{value:'denied room'}});fireEvent.click(screen.getByRole('button',{name:'Create local room'}));await screen.findByText('Room creation denied');
  api.rooms.mockRejectedValueOnce(new TypeError('fetch failed'));await act(async()=>intervals.get(10000)());await screen.findByText(/Room list is reconnecting/);
  await act(async()=>intervals.get(2000)());await waitFor(()=>expect(screen.queryByText(/Room list is reconnecting/)).not.toBeInTheDocument());expect(screen.getByText('Room creation denied')).toBeInTheDocument();
 }finally{timer.mockRestore();}
});

it('uses committed merged text when refresh fails so a later save cannot erase another writer',async()=>{
 const api=fixture(),merged='# Team handbook\n\nAlice and Bob changes.';api.saveDocument=vi.fn().mockImplementationOnce(async()=>{
  api.document.mockRejectedValueOnce(new Error('Latest refresh failed'));return {status:'saved',merged:true,content:merged,commit:'d'.repeat(40),blob:'e'.repeat(40)};
 }).mockImplementation(async(_room,content)=>{api.document.mockResolvedValue({...doc,content,blob:'f'.repeat(40)});return {status:'saved',commit:doc.commit,blob:'f'.repeat(40)};});
 render(<Documents api={api} room="!room" mode="edit" onSent={idle}/>);await screen.findByLabelText('Markdown document');fireEvent.change(screen.getByLabelText('Markdown document'),{target:{value:'# Only my submitted text'}});
 fireEvent.click(screen.getByRole('button',{name:'Save changes'}));await screen.findByText(/Merged non-overlapping edits/);expect(screen.getByLabelText('Markdown document')).toHaveValue(merged);
 fireEvent.change(screen.getByLabelText('Markdown document'),{target:{value:merged+'\nNext edit.'}});fireEvent.click(screen.getByRole('button',{name:'Save changes'}));await waitFor(()=>expect(api.saveDocument).toHaveBeenCalledTimes(2));
 expect(api.saveDocument.mock.calls[1][1]).toContain('Alice and Bob');expect(api.saveDocument.mock.calls[1][2]).toBe('e'.repeat(40));
});
it('shows overlapping conflict details without inserting conflict markers into the draft',async()=>{
 const api=fixture();api.saveDocument=vi.fn().mockRejectedValue(Object.assign(new Error('overlap'),{status:409,data:{status:'conflict',conflict_markdown:'<<<<<<< submitted\nMine\n=======\nTheirs\n>>>>>>> latest'}}));
 render(<Documents api={api} room="!room" mode="edit" onSent={idle}/>);await screen.findByLabelText('Markdown document');fireEvent.change(screen.getByLabelText('Markdown document'),{target:{value:'# My draft'}});fireEvent.click(screen.getByRole('button',{name:'Save changes'}));
 await screen.findByLabelText('Conflicting changes');expect(screen.getByLabelText('Conflicting changes')).toHaveAttribute('readonly');expect(screen.getByLabelText('Markdown document')).toHaveValue('# My draft');
 fireEvent.click(screen.getByRole('button',{name:'Load latest to merge'}));await screen.findByLabelText('Preserved draft');expect(screen.queryByLabelText('Conflicting changes')).not.toBeInTheDocument();
});

it('keeps an incomplete merged receipt uncertain rather than pairing submitted text with the new blob',async()=>{
 const api=fixture();api.saveDocument=vi.fn().mockResolvedValue({status:'saved',merged:true,commit:'d'.repeat(40),blob:'e'.repeat(40)});
 render(<Documents api={api} room="!room" mode="edit" onSent={idle}/>);await screen.findByLabelText('Markdown document');fireEvent.change(screen.getByLabelText('Markdown document'),{target:{value:'# original request'}});fireEvent.click(screen.getByRole('button',{name:'Save changes'}));
 await screen.findByText(/Merged save result is incomplete/);expect(screen.getByLabelText('Markdown document')).toHaveValue('# original request');expect(screen.getByLabelText('Markdown document')).toBeDisabled();
 fireEvent.click(screen.getByRole('button',{name:'Retry',exact:true}));await waitFor(()=>expect(api.saveDocument).toHaveBeenCalledTimes(2));expect(api.saveDocument.mock.calls[1]).toEqual(api.saveDocument.mock.calls[0]);
});

it('keeps the exact uncertain save and draft through operator reconciliation of remote histories',async()=>{
 const api=fixture(),recovery={local_commit:'d'.repeat(40),remote_commit:'e'.repeat(40),merge_base:doc.commit};
 api.saveDocument=vi.fn().mockRejectedValueOnce(Object.assign(new Error('Git histories diverged. Keep your draft and ask the operator.'),{status:503,data:{status:'remote_diverged',recovery}})).mockImplementationOnce(async()=>{
  api.document.mockResolvedValue({...doc,content:'# Reconciled both histories',blob:'f'.repeat(40),commit:'1'.repeat(40)});
  return {status:'saved',commit:'d'.repeat(40),blob:'2'.repeat(40)};
 });
 render(<Documents api={api} room="!room" mode="edit" onSent={idle}/>);await screen.findByLabelText('Markdown document');
 fireEvent.change(screen.getByLabelText('Markdown document'),{target:{value:'# Unsaved local draft'}});fireEvent.click(screen.getByRole('button',{name:'Save changes'}));
 await screen.findByText('Git histories need operator reconciliation');expect(screen.getByLabelText('Markdown document')).toHaveValue('# Unsaved local draft');expect(screen.getByLabelText('Markdown document')).toBeDisabled();
 expect(screen.queryByRole('button',{name:'Load latest to merge'})).toBeNull();fireEvent.click(screen.getByRole('button',{name:'Export Markdown'}));expect(downloadMarkdown).toHaveBeenLastCalledWith('# Unsaved local draft');
 expect(screen.getByText(recovery.local_commit)).toBeInTheDocument();expect(screen.getByText(recovery.remote_commit)).toBeInTheDocument();
 fireEvent.click(screen.getByRole('button',{name:'Retry after reconciliation'}));await waitFor(()=>expect(screen.getByLabelText('Markdown document')).toHaveValue('# Reconciled both histories'));
 expect(api.saveDocument.mock.calls[1]).toEqual(api.saveDocument.mock.calls[0]);expect(screen.queryByText('Git histories need operator reconciliation')).toBeNull();
});

it('allows exporting browser recovery drafts when divergence prevents the first Git load',async()=>{
 const api=fixture();const first=render(<Documents api={api} room="!room" mode="edit" onSent={idle}/>);await screen.findByLabelText('Markdown document');
 fireEvent.change(screen.getByLabelText('Markdown document'),{target:{value:'# Preserve across blocked reopen'}});
 await screen.findByText(/Unsaved draft kept on this browser only/);first.unmount();
 api.document.mockRejectedValue(Object.assign(new Error('Git histories diverged'),{status:503,data:{status:'remote_diverged',recovery:{local_commit:'d'.repeat(40),remote_commit:'e'.repeat(40),merge_base:doc.commit}}}));
 render(<Documents api={api} room="!room" mode="edit" onSent={idle}/>);await screen.findByText('Git histories need operator reconciliation');await screen.findByLabelText('Local draft recovery');
 expect(screen.getByRole('button',{name:'Restore local draft'})).toBeDisabled();fireEvent.click(screen.getByRole('button',{name:'Export local draft'}));expect(downloadMarkdown).toHaveBeenLastCalledWith('# Preserve across blocked reopen');expect(api.send).not.toHaveBeenCalled();
});

it('shows task lease/retry/connection observations and clears only a recovered task poll error',async()=>{
 const api=fixture();let current={status:'pending',phase:'waiting',attempts:0,runtime:{transport:'websocket',state:'unknown'}};let offline=false;
 api.task=vi.fn(async()=>{if(offline)throw new Error('Task poll offline');return {task:current}});
 const view=render(<Documents api={api} room="!room" mode="edit" onSent={idle}/>);await screen.findByLabelText('Markdown document');
 vi.useFakeTimers();
 try{
  await act(async()=>{fireEvent.change(screen.getByLabelText('Markdown document'),{target:{value:'# Kept while runtime reconnects'}});fireEvent.click(screen.getByRole('button',{name:'Save changes'}));});expect(screen.getByText('Waiting for runtime')).toBeInTheDocument();
  current={status:'pending',phase:'running',attempts:1,max_attempts:8,lease_expires_at:160,observed_at:100,runtime:{transport:'websocket',state:'connected'}};
  await act(async()=>vi.advanceTimersByTimeAsync(1300));expect(screen.getByText('In progress · lease held')).toBeInTheDocument();expect(screen.getByText('WebSocket runtime connected.')).toBeInTheDocument();
  current={...current,phase:'retry_wait',next_retry_at:160,observed_at:161,retry_reason:'lease_expired',runtime:{transport:'websocket',state:'disconnected'}};
  await act(async()=>vi.advanceTimersByTimeAsync(1300));expect(screen.getByText('Waiting to retry')).toBeInTheDocument();expect(screen.getByText(/previous lease expired/)).toBeInTheDocument();expect(screen.getByText(/WebSocket runtime disconnected/)).toBeInTheDocument();
  offline=true;await act(async()=>vi.advanceTimersByTimeAsync(1300));expect(screen.getByText('Task status unavailable')).toBeInTheDocument();expect(screen.getByText(/Task poll offline/)).toBeInTheDocument();expect(screen.queryByText(/WebSocket runtime disconnected/)).toBeNull();
  offline=false;current={...current,phase:'running',attempts:2,runtime:{transport:'websocket',state:'connected'}};
  await act(async()=>vi.advanceTimersByTimeAsync(1300));expect(screen.getByText('In progress · lease held')).toBeInTheDocument();expect(screen.queryByText(/Task poll offline/)).toBeNull();expect(screen.getByLabelText('Markdown document')).toHaveValue('# Kept while runtime reconnects');expect(api.send).toHaveBeenCalledTimes(1);
 }finally{view.unmount();vi.useRealTimers()}
});


describe('message history pagination',()=>{
 const message=(id,time)=>({id,sender:'@human',time,content:{body:id}});
 it('loads older pages once, deduplicates boundaries and keeps the message draft on retry',async()=>{
  const api=fixture();let resolve;
  api.timelinePage=vi.fn().mockResolvedValueOnce({events:[message('$recent',3)],previousCursor:'p1'})
   .mockRejectedValueOnce(new Error('History offline'))
   .mockImplementationOnce(()=>new Promise(r=>resolve=r));
  render(<App connector={async()=>api}/>);await screen.findByText('$recent');fireEvent.click(screen.getByRole('button',{name:'Discussion',exact:true}));
  fireEvent.change(screen.getByLabelText('Message'),{target:{value:'unsent draft'}});
  fireEvent.click(screen.getByRole('button',{name:'Load earlier messages'}));await screen.findByText(/History offline/);
  expect(screen.getByText('$recent')).toBeInTheDocument();expect(screen.getByLabelText('Message')).toHaveValue('unsent draft');
  const button=screen.getByRole('button',{name:'Load earlier messages'});fireEvent.click(button);fireEvent.click(button);expect(api.timelinePage).toHaveBeenCalledTimes(3);
  await act(async()=>resolve({events:[message('$older',1),message('$recent',3)],previousCursor:null}));
  expect(await screen.findByText('$older')).toBeInTheDocument();expect(screen.getAllByText('$recent')).toHaveLength(1);expect(screen.queryByRole('button',{name:'Load earlier messages'})).toBeNull();
  expect(api.timelinePage.mock.calls.slice(1)).toEqual([['!room','p1'],['!room','p1']]);
 });
 it('discards an old room pagination response after switching rooms',async()=>{
  const api=fixture();let resolve;api.rooms.mockResolvedValue([{id:'!room',name:'Workspace'},{id:'!other',name:'Other room'}]);
  api.timelinePage=vi.fn((room,from)=>from?new Promise(r=>resolve=r):Promise.resolve({events:[message(room==='!room'?'$first':'$other',2)],previousCursor:room==='!room'?'p1':null}));
  render(<App connector={async()=>api}/>);await screen.findByText('$first');fireEvent.click(screen.getByRole('button',{name:'Discussion',exact:true}));fireEvent.click(screen.getByRole('button',{name:'Load earlier messages'}));
  fireEvent.click(screen.getByRole('button',{name:'Other room',exact:true}));await screen.findByText('$other');
  await act(async()=>resolve({events:[message('$old-room-secret',1)],previousCursor:null}));expect(screen.queryByText('$old-room-secret')).toBeNull();expect(screen.queryByText('$first')).toBeNull();
 });
});


it('keeps loaded history on refresh and discards a pending page when a genuine recent gap resets history',async()=>{
 const api=fixture(),intervals=new Map();let resolve;
 const message=(id,time)=>({id,time,sender:'@human',content:{body:id}});
 api.timelinePage=vi.fn().mockResolvedValueOnce({events:[message('$recent-one',3)],previousCursor:'one'})
  .mockResolvedValueOnce({events:[message('$old-one',1)],previousCursor:'two'})
  .mockResolvedValueOnce({events:[message('$recent-one',3),message('$recent-two',4)],previousCursor:'new'})
  .mockImplementationOnce(()=>new Promise(r=>resolve=r))
  .mockResolvedValueOnce({events:[message('$after-gap',100)],previousCursor:'gap'})
  .mockResolvedValueOnce({events:[message('$gap-filled',90)],previousCursor:null});
 const timer=vi.spyOn(globalThis,'setInterval').mockImplementation((callback,ms)=>{intervals.set(ms,callback);return ms;});
 try{render(<App connector={async()=>api}/>);await screen.findByText('$recent-one');fireEvent.click(screen.getByRole('button',{name:'Discussion',exact:true}));
  fireEvent.click(screen.getByRole('button',{name:'Load earlier messages'}));await screen.findByText('$old-one');await act(async()=>intervals.get(2000)());await screen.findByText('$recent-two');expect(screen.getByText('$old-one')).toBeInTheDocument();
  fireEvent.click(screen.getByRole('button',{name:'Load earlier messages'}));await act(async()=>intervals.get(2000)());await screen.findByText('$after-gap');await screen.findByText(/Recent messages advanced/);
  await act(async()=>resolve({events:[message('$stale-page',0)],previousCursor:null}));expect(screen.queryByText('$stale-page')).toBeNull();expect(screen.queryByText('$old-one')).toBeNull();
  fireEvent.click(screen.getByRole('button',{name:'Load earlier messages'}));await screen.findByText('$gap-filled');expect(screen.queryByText(/Recent messages advanced/)).toBeNull();
 }finally{timer.mockRestore()}
});


it('merges an older response with messages that refreshed while it was loading',async()=>{
 const api=fixture(),intervals=new Map();let resolve;const message=id=>({id,sender:'@human',content:{body:id}});
 api.timelinePage=vi.fn().mockResolvedValueOnce({events:[message('$existing')],previousCursor:'old'})
  .mockImplementationOnce(()=>new Promise(r=>resolve=r)).mockResolvedValueOnce({events:[message('$existing'),message('$arrived')],previousCursor:'fresh'});
 const timer=vi.spyOn(globalThis,'setInterval').mockImplementation((callback,ms)=>{intervals.set(ms,callback);return ms;});
 try{render(<App connector={async()=>api}/>);await screen.findByText('$existing');fireEvent.click(screen.getByRole('button',{name:'Discussion',exact:true}));fireEvent.click(screen.getByRole('button',{name:'Load earlier messages'}));
  await act(async()=>intervals.get(2000)());await screen.findByText('$arrived');await act(async()=>resolve({events:[message('$earlier')],previousCursor:null}));await screen.findByText('$earlier');expect(screen.getByText('$arrived')).toBeInTheDocument();expect(screen.getAllByText('$existing')).toHaveLength(1);
 }finally{timer.mockRestore()}
});


it('creates and opens a named document, saving only its path and protecting pending saves from navigation',async()=>{
 const api=fixture();const documents=new Map([['demo.md',{...doc}]]);let pendingSave;
 api.documents=vi.fn(async()=>({documents:[...documents.keys()].map(name=>({name}))}));
 api.createDocument=vi.fn(async(_room,name)=>{documents.set(name,{...doc,name,content:'',blob:'d'.repeat(40)});return {path:name,status:'saved',commit:doc.commit,blob:doc.blob}});
 api.document.mockImplementation(async(_room,_commit,name='demo.md')=>documents.get(name));
 api.history.mockResolvedValue({commits:[doc.commit]});
 api.saveDocument=vi.fn((_room,content,_base,_operation,name='demo.md')=>new Promise(resolve=>pendingSave=()=>{documents.set(name,{...doc,name,content});resolve({status:'saved',path:name,commit:doc.commit,blob:doc.blob})}));
 render(<App connector={async()=>api}/>);await screen.findByRole('heading',{name:'Team handbook'});
 fireEvent.change(screen.getByLabelText('New document path'),{target:{value:'设计/Notes.md'}});fireEvent.click(screen.getByRole('button',{name:'Create document'}));
 await screen.findByRole('button',{name:'设计/Notes.md, current document'});const editor=await screen.findByLabelText('Markdown document');expect(editor).toHaveValue('');
 fireEvent.change(editor,{target:{value:'# Named notes'}});await screen.findByText(/Unsaved draft kept/);fireEvent.click(screen.getByRole('button',{name:'Save changes'}));
 expect(screen.getByRole('button',{name:'demo.md',exact:true})).toBeDisabled();await act(async()=>pendingSave());await screen.findByText(/Saved directly to Git/);
 expect(api.saveDocument.mock.calls[0][4]).toBe('设计/Notes.md');expect(documents.get('demo.md').content).toBe(doc.content);
 fireEvent.click(screen.getByRole('button',{name:'demo.md',exact:true}));await screen.findByRole('heading',{name:'Team handbook'});
 await waitFor(()=>expect(screen.getByRole('button',{name:'设计/Notes.md',exact:true})).toBeEnabled());fireEvent.click(screen.getByRole('button',{name:'设计/Notes.md',exact:true}));await screen.findByRole('heading',{name:'Named notes'});
});


it('keeps a confirmed created document accessible when refreshing its list fails',async()=>{
 const api=fixture();let created=false;
 api.documents=vi.fn(async()=>{if(created)throw new Error('Document list offline');return {documents:[{name:'demo.md'}]}});
 api.createDocument=vi.fn(async(_room,name)=>{created=true;return {status:'saved',path:name,commit:doc.commit,blob:doc.blob}});
 api.document.mockImplementation(async(_room,_version,name='demo.md')=>({...doc,name,content:name==='demo.md'?doc.content:'# Created despite list failure'}));
 render(<App connector={async()=>api}/>);await screen.findByRole('heading',{name:'Team handbook'});fireEvent.change(screen.getByLabelText('New document path'),{target:{value:'Created.md'}});fireEvent.click(screen.getByRole('button',{name:'Create document'}));
 await screen.findByRole('button',{name:'Created.md, current document'});await screen.findByText(/Document list offline/);fireEvent.click(screen.getByRole('button',{name:'demo.md',exact:true}));await screen.findByRole('heading',{name:'Team handbook'});expect(screen.getByRole('button',{name:'Created.md',exact:true})).toBeInTheDocument();
});

it('blocks document navigation when the dirty draft cannot be stored locally',async()=>{
 const api=fixture();api.documents=vi.fn(async()=>({documents:[{name:'demo.md'},{name:'Other.md'}]}));api.createDocument=vi.fn();
 render(<App connector={async()=>api}/>);await screen.findByRole('heading',{name:'Team handbook'});await screen.findByRole('button',{name:'Other.md',exact:true});fireEvent.click(screen.getByRole('button',{name:'Edit',exact:true}));
 const storage=vi.spyOn(Storage.prototype,'setItem').mockImplementation(()=>{throw new DOMException('Storage unavailable','SecurityError')});
 try{fireEvent.change(screen.getByLabelText('Markdown document'),{target:{value:'# Must not lose'}});await screen.findByText(/Local draft storage is unavailable/);await waitFor(()=>expect(screen.getByRole('button',{name:'Other.md',exact:true})).toBeDisabled());expect(screen.getByRole('button',{name:'Create document'})).toBeDisabled();expect(screen.getByLabelText('Markdown document')).toHaveValue('# Must not lose');}
 finally{storage.mockRestore()}
});

it('keeps the current editor when edits become unsafe during a delayed document create',async()=>{
 const api=fixture();let finish;api.documents=vi.fn(async()=>({documents:[{name:'demo.md'}]}));api.createDocument=vi.fn(()=>new Promise(resolve=>finish=resolve));
 render(<App connector={async()=>api}/>);await screen.findByRole('heading',{name:'Team handbook'});fireEvent.click(screen.getByRole('button',{name:'Edit',exact:true}));fireEvent.change(screen.getByLabelText('New document path'),{target:{value:'Delayed.md'}});fireEvent.click(screen.getByRole('button',{name:'Create document'}));
 const storage=vi.spyOn(Storage.prototype,'setItem').mockImplementation(()=>{throw new DOMException('Denied','SecurityError')});
 try{fireEvent.change(screen.getByLabelText('Markdown document'),{target:{value:'# Keep editor mounted'}});await screen.findByText(/Local draft storage is unavailable/);await act(async()=>finish({status:'saved',path:'Delayed.md',commit:doc.commit,blob:doc.blob}));await screen.findByText(/Document created. Finish or export/);expect(screen.getByLabelText('Markdown document')).toHaveValue('# Keep editor mounted');expect(screen.getByRole('button',{name:'Delayed.md',exact:true})).toBeDisabled();}
 finally{storage.mockRestore()}
});

it('moves a clean document and retries an uncertain move with the same source snapshot',async()=>{
 const api=fixture();let moved=false;
 api.documents=vi.fn(async()=>({documents:[{name:moved?'Archive/Renamed.md':'demo.md'}]}));
 api.document.mockImplementation(async(_room,_commit,name='demo.md')=>({...doc,name}));
 api.moveDocument=vi.fn().mockRejectedValueOnce(new Error('Response lost')).mockImplementationOnce(async()=>{moved=true;return {status:'saved',path:'Archive/Renamed.md',commit:doc.commit,blob:doc.blob}});
 render(<App connector={async()=>api}/>);await screen.findByRole('heading',{name:'Team handbook'});fireEvent.change(screen.getByLabelText('Move document to path'),{target:{value:'Archive/Renamed.md'}});
 await waitFor(()=>expect(screen.getByRole('button',{name:'Move document'})).toBeEnabled());fireEvent.click(screen.getByRole('button',{name:'Move document'}));await screen.findByText(/Response lost/);
 expect(screen.getByRole('button',{name:'demo.md, current document'})).toBeDisabled();expect(screen.getByLabelText('Move document to path')).toBeDisabled();
 fireEvent.click(screen.getByRole('button',{name:'Move document'}));await screen.findByRole('button',{name:'Archive/Renamed.md, current document'});expect(api.moveDocument.mock.calls[0]).toEqual(api.moveDocument.mock.calls[1]);expect(api.moveDocument.mock.calls[0][1].source).toBe('demo.md');expect(api.moveDocument.mock.calls[0][1].base_blob).toBe(doc.blob);
});

it('does not move a document with unsaved text',async()=>{
 const api=fixture();api.moveDocument=vi.fn();render(<App connector={async()=>api}/>);await screen.findByRole('heading',{name:'Team handbook'});fireEvent.click(screen.getByRole('button',{name:'Edit',exact:true}));fireEvent.change(screen.getByLabelText('Markdown document'),{target:{value:'# Must save first'}});fireEvent.change(screen.getByLabelText('Move document to path'),{target:{value:'Other.md'}});await screen.findByText(/Unsaved draft kept/);expect(screen.getByRole('button',{name:'Move document'})).toBeDisabled();expect(api.moveDocument).not.toHaveBeenCalled();
});

it('keeps recovery drafts accessible before allowing a document move',async()=>{
 const {LocalDraftStore,draftContext}=await import('./localDrafts');const api=fixture();api.moveDocument=vi.fn();const store=new LocalDraftStore(draftContext(api.session,'!room'));store.write('# Recovery still matters',doc.blob);
 render(<App connector={async()=>api}/>);await screen.findByRole('heading',{name:'Team handbook'});await screen.findByText(/Restore or export and discard local recovery/);fireEvent.change(screen.getByLabelText('Move document to path'),{target:{value:'Moved.md'}});expect(screen.getByRole('button',{name:'Move document'})).toBeDisabled();expect(screen.getByRole('button',{name:'Export local draft'})).toBeEnabled();expect(api.moveDocument).not.toHaveBeenCalled();
});
