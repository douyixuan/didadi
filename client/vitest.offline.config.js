import {defineConfig} from 'vitest/config';
export default defineConfig({test:{
  environment:'jsdom',
  include:['src/App.test.jsx','src/messageHistory.test.js','src/documentReferences.test.js','src/localDrafts.test.js','src/taskResult.test.js','src/WorkspaceSearch.test.jsx','src/Attachments.test.jsx','src/QuotedMessage.test.jsx','src/SourceViewer.test.jsx','src/SourceFileTree.test.jsx','src/RoomPeople.test.jsx','src/roomMembers.test.js','src/RoomCreator.test.jsx','src/DirectChatPreferences.test.jsx','src/SessionContract.test.jsx','src/matrixFetch.test.js','src/authApi.test.js','src/SignIn.test.jsx'],
  setupFiles:['./src/test-setup.js','./src/offlineTransportSetup.js'],
}});
