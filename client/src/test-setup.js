import '@testing-library/jest-dom/vitest';
import {cleanup} from '@testing-library/react';
import {afterEach} from 'vitest';
afterEach(async()=>{cleanup();await navigator.locks?.request('didadi-document-drafts-v1',()=>{});try{window.localStorage.clear();}catch{}});
if(!Range.prototype.getClientRects)Range.prototype.getClientRects=()=>[];
if(!Range.prototype.getBoundingClientRect)Range.prototype.getBoundingClientRect=()=>({top:0,left:0,right:0,bottom:0,width:0,height:0});
if(!HTMLElement.prototype.scrollIntoView)HTMLElement.prototype.scrollIntoView=()=>{};
if(!globalThis.IntersectionObserver)globalThis.IntersectionObserver=class{observe(){}unobserve(){}disconnect(){}};
if(!globalThis.ResizeObserver)globalThis.ResizeObserver=class{observe(){}unobserve(){}disconnect(){}};
if(!window.matchMedia)window.matchMedia=()=>({matches:false,addEventListener(){},removeEventListener(){}});

// jsdom lacks Web Locks. Serialize callbacks to exercise the browser coordination path.
let draftLock=Promise.resolve();
Object.defineProperty(navigator,'locks',{configurable:true,value:{request:(_name,action)=>{const result=draftLock.then(action);draftLock=result.catch(()=>{});return result;}}});
