import {describe,it,expect} from 'vitest';
import {mergeMessages} from './messageHistory';
describe('Matrix message page continuity',()=>{it('keeps chronology and updates duplicate IDs without dropping equal-time neighbours',()=>{
 const old={id:'a',time:1,content:{body:'old'}};expect(mergeMessages([old,{id:'b',time:1}],[{id:'c',time:2},{...old,content:{body:'new'}}]).map(x=>x.id)).toEqual(['a','b','c']);expect(mergeMessages([old],[{...old,content:{body:'new'}}])[0].content.body).toBe('new');
});it('retains Matrix stream order when timestamps go backwards',()=>{expect(mergeMessages([{id:'old',time:1000}],[{id:'new',time:1}]).map(x=>x.id)).toEqual(['old','new'])});});
