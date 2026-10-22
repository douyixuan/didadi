import {describe,it,expect,vi} from 'vitest';
import {messagePage} from './api';
describe('Matrix history cursors',()=>{
 it('continues through a filtered empty page when the server cursor advances',async()=>{const client={createMessagesRequest:vi.fn().mockResolvedValue({chunk:[],start:'a',end:'b'})};expect(await messagePage(client,'!room','a')).toEqual({events:[],previousCursor:'b'});expect(client.createMessagesRequest.mock.calls[0].slice(0,3)).toEqual(['!room','a',50]);});
 it('stops for absent or nonadvancing end cursors',async()=>{for(const response of [{chunk:[]},{chunk:[],start:'a',end:'a'}]){const client={createMessagesRequest:vi.fn().mockResolvedValue(response)};expect((await messagePage(client,'!room','a')).previousCursor).toBeNull();}});
});

import {threadPage} from './api';
import {MatrixEvent} from 'matrix-js-sdk';
it('loads an old root independently and keeps only its thread replies in Matrix stream order',async()=>{
 const event=(id,body,root='$root')=>new MatrixEvent({event_id:id,type:'m.room.message',sender:'@human',origin_server_ts:id==='$old'?900:1,content:{body,'m.relates_to':{rel_type:'m.thread',event_id:root}}});
 const client={relations:vi.fn().mockResolvedValue({originalEvent:event('$root','Old root'),events:[event('$new','New'),event('$foreign','Foreign','$other'),event('$old','Old')],nextBatch:'next'})};
 const result=await threadPage(client,'!room','$root','start');expect(result.root.content.body).toBe('Old root');expect(result.events.map(e=>e.id)).toEqual(['$old','$new']);expect(result.previousCursor).toBe('next');expect(client.relations).toHaveBeenCalledWith('!room','$root','m.thread','m.room.message',expect.objectContaining({from:'start',limit:50}));
});
it('retains advancing empty thread cursors and rejects an unavailable root',async()=>{
 const root=new MatrixEvent({event_id:'$root',type:'m.room.message',content:{body:'Root'}});const client={relations:vi.fn().mockResolvedValue({originalEvent:root,events:[],nextBatch:'next'})};expect((await threadPage(client,'!room','$root','start')).previousCursor).toBe('next');client.relations.mockResolvedValue({originalEvent:null,events:[]});await expect(threadPage(client,'!room','$root')).rejects.toThrow(/root is unavailable/);
});
