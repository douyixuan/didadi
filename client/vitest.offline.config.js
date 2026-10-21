import {defineConfig} from 'vitest/config';
export default defineConfig({test:{
  environment:'jsdom',
  include:['src/App.test.jsx','src/messageHistory.test.js'],
  setupFiles:['./src/test-setup.js','./src/offlineTransportSetup.js'],
}});
