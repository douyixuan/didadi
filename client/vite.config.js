import {defineConfig} from 'vite';
export default defineConfig({build:{rollupOptions:{input:{app:'index.html',session:'session-contract.html'}}},test:{environment:'jsdom',setupFiles:['./src/test-setup.js']}});
