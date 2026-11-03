import React, { useState } from 'react';
import { Navbar, ActiveTab } from './components/Navbar';
import { DashboardView } from './views/DashboardView';
import { DocumentsView } from './views/DocumentsView';
import { ChatView } from './views/ChatView';
import { EvaluationView } from './views/EvaluationView';
import { SettingsView } from './views/SettingsView';
import { SourceInspectorModal } from './components/SourceInspectorModal';
import { CitationItem } from './types/api';

export const App: React.FC = () => {
  const [activeTab, setActiveTab] = useState<ActiveTab>('dashboard');
  const [activeCitation, setActiveCitation] = useState<CitationItem | null>(null);

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col font-sans">
      {/* Top Navbar */}
      <Navbar activeTab={activeTab} onTabChange={setActiveTab} />

      {/* Main Workspace Body */}
      <main className="flex-1 max-w-7xl w-full mx-auto p-4 sm:p-6 lg:p-8">
        {activeTab === 'dashboard' && <DashboardView onNavigate={setActiveTab} />}
        {activeTab === 'documents' && <DocumentsView onInspectCitation={setActiveCitation} />}
        {activeTab === 'chat' && <ChatView onInspectCitation={setActiveCitation} />}
        {activeTab === 'evaluation' && <EvaluationView />}
        {activeTab === 'settings' && <SettingsView />}
      </main>

      {/* Global Source Inspector Modal */}
      <SourceInspectorModal
        citation={activeCitation}
        onClose={() => setActiveCitation(null)}
      />
    </div>
  );
};

export default App;

