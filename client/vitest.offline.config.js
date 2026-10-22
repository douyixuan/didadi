import {defineConfig} from 'vitest/config';
export default defineConfig({test:{
  environment:'jsdom',
  include:['src/App.test.jsx','src/messageHistory.test.js','src/documentReferences.test.js','src/localDrafts.test.js','src/taskResult.test.js','src/WorkspaceSearch.test.jsx','src/Attachments.test.jsx','src/QuotedMessage.test.jsx','src/SourceViewer.test.jsx','src/SourceFileTree.test.jsx','src/matrixFetch.test.js'],
  setupFiles:['./src/test-setup.js','./src/offlineTransportSetup.js'],
}});
