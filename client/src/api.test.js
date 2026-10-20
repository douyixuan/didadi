import {describe,it,expect,vi} from 'vitest';
import {messagePage} from './api';
describe('Matrix history cursors',()=>{
 it('continues through a filtered empty page when the server cursor advances',async()=>{const client={createMessagesRequest:vi.fn().mockResolvedValue({chunk:[],start:'a',end:'b'})};expect(await messagePage(client,'!room','a')).toEqual({events:[],previousCursor:'b'});expect(client.createMessagesRequest.mock.calls[0].slice(0,3)).toEqual(['!room','a',50]);});
 it('stops for absent or nonadvancing end cursors',async()=>{for(const response of [{chunk:[]},{chunk:[],start:'a',end:'a'}]){const client={createMessagesRequest:vi.fn().mockResolvedValue(response)};expect((await messagePage(client,'!room','a')).previousCursor).toBeNull();}});
});
