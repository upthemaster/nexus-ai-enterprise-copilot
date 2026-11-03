import React, { useState, useEffect, useRef } from 'react';
import {
  Send,
  Plus,
  Trash2,
  MessageSquare,
  Bot,
  User,
  Quote,
  Bookmark,
  ShieldAlert,
  Loader2,
  ChevronRight,
  Sliders,
} from 'lucide-react';
import { api } from '../api/client';
import {
  CitationItem,
  ConversationItem,
  ConversationMessage,
  WorkflowType,
} from '../types/api';

interface ChatViewProps {
  onInspectCitation: (citation: CitationItem) => void;
}

export const ChatView: React.FC<ChatViewProps> = ({ onInspectCitation }) => {
  const [conversations, setConversations] = useState<ConversationItem[]>([]);
  const [activeConvId, setActiveConvId] = useState<string | null>(null);
  const [messages, setMessages] = useState<ConversationMessage[]>([]);
  const [inputQuery, setInputQuery] = useState<string>('');
  const [loading, setLoading] = useState<boolean>(false);
  const [workflowType, setWorkflowType] = useState<WorkflowType>('auto');
  const [topK, setTopK] = useState<number>(5);
  const [showConfig, setShowConfig] = useState<boolean>(false);

  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Load conversation list
  const loadConversations = async () => {
    try {
      const list = await api.listConversations();
      setConversations(list);
      if (list.length > 0 && !activeConvId) {
        setActiveConvId(list[0].id);
      }
    } catch (err) {
      console.error('Failed to load conversations:', err);
    }
  };

  useEffect(() => {
    loadConversations();
  }, []);

  // Load messages when active conversation changes
  useEffect(() => {
    if (!activeConvId) {
      setMessages([]);
      return;
    }

    let isMounted = true;
    api.getConversation(activeConvId)
      .then((thread) => {
        if (isMounted) {
          setMessages(thread.messages || []);
        }
      })
      .catch((err) => {
        console.error('Failed to load thread messages:', err);
      });

    return () => {
      isMounted = false;
    };
  }, [activeConvId]);

  // Scroll to bottom
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, loading]);

  const handleCreateNewChat = async () => {
    try {
      const newConv = await api.createConversation('New Chat Session');
      setConversations([newConv, ...conversations]);
      setActiveConvId(newConv.id);
      setMessages([]);
    } catch (err: any) {
      alert(`Could not create conversation: ${err.message}`);
    }
  };

  const handleDeleteConversation = async (e: React.MouseEvent, id: string) => {
    e.stopPropagation();
    if (!window.confirm('Delete this chat thread and its history?')) return;
    try {
      await api.deleteConversation(id);
      const remaining = conversations.filter((c) => c.id !== id);
      setConversations(remaining);
      if (activeConvId === id) {
        setActiveConvId(remaining.length > 0 ? remaining[0].id : null);
      }
    } catch (err: any) {
      alert(`Could not delete conversation: ${err.message}`);
    }
  };

  const handleSendMessage = async (queryText?: string) => {
    const textToSend = queryText || inputQuery;
    if (!textToSend.trim() || loading) return;

    const userMessage: ConversationMessage = {
      id: `client_${Date.now()}`,
      conversation_id: activeConvId || '',
      role: 'user',
      content: textToSend,
      created_at: new Date().toISOString(),
    };

    setMessages((prev) => [...prev, userMessage]);
    setInputQuery('');
    setLoading(true);

    try {
      // Execute via LangGraph workflow orchestrator
      const res = await api.runWorkflow({
        query: textToSend,
        workflow_type: workflowType,
        conversation_id: activeConvId || undefined,
        top_k: topK,
      });

      const assistantMessage: ConversationMessage = {
        id: `assistant_${Date.now()}`,
        conversation_id: activeConvId || '',
        role: 'assistant',
        content: res.result || res.answer || '',
        citations: res.citations,
        insufficient_evidence: res.insufficient_evidence,
        created_at: new Date().toISOString(),
      };

      setMessages((prev) => [...prev, assistantMessage]);
      loadConversations();
    } catch (err: any) {
      const errorMessage: ConversationMessage = {
        id: `err_${Date.now()}`,
        conversation_id: activeConvId || '',
        role: 'assistant',
        content: `Error executing query: ${err.message || 'Server error'}`,
        insufficient_evidence: true,
        created_at: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, errorMessage]);
    } finally {
      setLoading(false);
    }
  };

  const samplePrompts = [
    'What is the capital expense approval limit under PROC-889?',
    'Summarize the IT security multi-factor authentication requirements.',
    'What are the critical incident escalation SLAs in the SRE runbook?',
    'What is the company policy regarding quantum computing hardware procurement?',
  ];

  return (
    <div className="flex h-[calc(100vh-8.5rem)] rounded-2xl border border-slate-800 bg-slate-900 overflow-hidden shadow-2xl animate-in fade-in duration-300">
      {/* Left Sidebar: Conversations */}
      <div className="w-64 border-r border-slate-800 bg-slate-950/60 flex flex-col">
        <div className="p-4 border-b border-slate-800">
          <button
            onClick={handleCreateNewChat}
            className="w-full flex items-center justify-center gap-2 rounded-xl bg-indigo-600 hover:bg-indigo-500 py-2.5 px-4 text-xs font-semibold text-white shadow-md shadow-indigo-600/20 transition-colors"
          >
            <Plus className="h-4 w-4" />
            New Conversation
          </button>
        </div>

        <div className="flex-1 overflow-y-auto p-2 space-y-1">
          {conversations.length === 0 ? (
            <div className="py-8 text-center text-xs text-slate-500">No active chats</div>
          ) : (
            conversations.map((conv) => {
              const isActive = activeConvId === conv.id;
              return (
                <div
                  key={conv.id}
                  onClick={() => setActiveConvId(conv.id)}
                  className={`group relative flex items-center justify-between rounded-xl p-2.5 text-xs cursor-pointer transition-colors ${
                    isActive
                      ? 'bg-slate-800 text-white font-medium'
                      : 'text-slate-400 hover:bg-slate-800/40 hover:text-slate-200'
                  }`}
                >
                  <div className="flex items-center gap-2.5 truncate pr-2">
                    <MessageSquare className="h-3.5 w-3.5 shrink-0 text-indigo-400" />
                    <span className="truncate">{conv.title}</span>
                  </div>

                  <button
                    onClick={(e) => handleDeleteConversation(e, conv.id)}
                    className="opacity-0 group-hover:opacity-100 p-1 text-slate-500 hover:text-rose-400 rounded transition-opacity"
                    title="Delete thread"
                  >
                    <Trash2 className="h-3 w-3" />
                  </button>
                </div>
              );
            })
          )}
        </div>
      </div>

      {/* Main Chat Pane */}
      <div className="flex-1 flex flex-col bg-slate-900">
        {/* Top Control Bar */}
        <div className="flex items-center justify-between border-b border-slate-800 px-6 py-3 bg-slate-850">
          <div className="flex items-center gap-3">
            <span className="text-xs font-semibold text-slate-400">Workflow Routing:</span>
            <div className="flex items-center gap-1 rounded-lg bg-slate-950 p-1 border border-slate-800 text-xs">
              {(['auto', 'qa', 'summarize', 'extract_risks'] as WorkflowType[]).map((mode) => (
                <button
                  key={mode}
                  onClick={() => setWorkflowType(mode)}
                  className={`px-2.5 py-1 rounded text-[11px] font-semibold transition-all ${
                    workflowType === mode
                      ? 'bg-indigo-600 text-white shadow-sm'
                      : 'text-slate-400 hover:text-slate-200'
                  }`}
                >
                  {mode === 'auto'
                    ? '⚡ Auto'
                    : mode === 'qa'
                    ? '🎯 Q&A'
                    : mode === 'summarize'
                    ? '📄 Summary'
                    : '⚠️ Risks'}
                </button>
              ))}
            </div>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={() => setShowConfig(!showConfig)}
              className="flex items-center gap-1 text-xs text-slate-400 hover:text-slate-200 p-1.5 rounded-lg border border-slate-800 hover:bg-slate-800"
              title="Retrieval Budget Settings"
            >
              <Sliders className="h-3.5 w-3.5 text-indigo-400" />
              <span>Top-K: {topK}</span>
            </button>
          </div>
        </div>

        {/* Config drawer */}
        {showConfig && (
          <div className="bg-slate-950 border-b border-slate-800 px-6 py-3 flex items-center justify-between text-xs">
            <div className="flex items-center gap-4">
              <span className="text-slate-400">Retrieval Candidate Budget (Top-K):</span>
              <input
                type="range"
                min="1"
                max="10"
                value={topK}
                onChange={(e) => setTopK(Number(e.target.value))}
                className="w-32 accent-indigo-500"
              />
              <span className="font-mono text-indigo-400 font-bold">{topK} chunks</span>
            </div>
            <span className="text-slate-500 text-[11px]">Hybrid RRF k=60 + Cross-Encoder Rerank</span>
          </div>
        )}

        {/* Message Transcript */}
        <div className="flex-1 overflow-y-auto p-6 space-y-6">
          {messages.length === 0 ? (
            <div className="max-w-xl mx-auto py-12 text-center space-y-4">
              <div className="flex h-14 w-14 mx-auto items-center justify-center rounded-2xl bg-indigo-500/10 text-indigo-400 border border-indigo-500/20">
                <Bot className="h-7 w-7" />
              </div>
              <div>
                <h3 className="text-base font-bold text-white">Ask anything grounded in internal documents</h3>
                <p className="mt-1 text-xs text-slate-400">
                  NexusAI retrieves verified evidence from indexed files and generates answers with clickable source citations.
                </p>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-left pt-4">
                {samplePrompts.map((p, i) => (
                  <button
                    key={i}
                    onClick={() => handleSendMessage(p)}
                    className="p-3 rounded-xl border border-slate-800 bg-slate-950/60 hover:border-indigo-500/40 hover:bg-slate-800/40 text-xs text-slate-300 transition-all flex items-start justify-between group"
                  >
                    <span>{p}</span>
                    <ChevronRight className="h-3.5 w-3.5 text-slate-600 group-hover:text-indigo-400 shrink-0 mt-0.5 ml-1" />
                  </button>
                ))}
              </div>
            </div>
          ) : (
            messages.map((m) => (
              <div
                key={m.id}
                className={`flex gap-4 ${m.role === 'user' ? 'justify-end' : 'justify-start'}`}
              >
                {m.role === 'assistant' && (
                  <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-xl bg-indigo-600 text-white shadow-md">
                    <Bot className="h-4 w-4" />
                  </div>
                )}

                <div
                  className={`max-w-2xl rounded-2xl p-4 text-xs space-y-3 ${
                    m.role === 'user'
                      ? 'bg-indigo-600 text-white shadow-md shadow-indigo-600/10'
                      : 'bg-slate-950 border border-slate-800 text-slate-200'
                  }`}
                >
                  {/* Explicit Abstention Alert */}
                  {m.insufficient_evidence && (
                    <div className="rounded-xl border border-amber-500/30 bg-amber-500/10 p-3 text-amber-300 flex items-start gap-2">
                      <ShieldAlert className="h-4 w-4 shrink-0 mt-0.5 text-amber-400" />
                      <div>
                        <span className="font-bold block text-amber-400">Explicit Abstention Guardrail:</span>
                        <p className="mt-0.5 text-[11px] leading-relaxed">
                          Evidence score fell below the sufficiency threshold (logit &lt; -6.0). The system abstained from answering to prevent hallucinations.
                        </p>
                      </div>
                    </div>
                  )}

                  {/* Main text */}
                  <div className="leading-relaxed whitespace-pre-wrap font-sans">
                    {m.content}
                  </div>

                  {/* Citations Footer */}
                  {m.citations && m.citations.length > 0 && (
                    <div className="pt-2 border-t border-slate-800/80">
                      <span className="text-[10px] uppercase font-bold tracking-wider text-slate-400 block mb-1.5">
                        Verified Sources ({m.citations.length})
                      </span>
                      <div className="flex flex-wrap gap-1.5">
                        {m.citations.map((c, i) => (
                          <button
                            key={i}
                            onClick={() => onInspectCitation(c)}
                            className="inline-flex items-center gap-1 rounded-md bg-slate-900 hover:bg-indigo-900/40 border border-slate-700 hover:border-indigo-500/50 px-2 py-0.5 text-[10px] text-indigo-300 transition-colors"
                            title="Click to inspect source passage in sidecar"
                          >
                            {c.is_direct_quote ? (
                              <Quote className="h-2.5 w-2.5 text-emerald-400" />
                            ) : (
                              <Bookmark className="h-2.5 w-2.5 text-sky-400" />
                            )}
                            <span className="font-mono">[{c.chunk_id}]</span>
                            <span className="text-slate-400">p.{c.page_number || 1}</span>
                          </button>
                        ))}
                      </div>
                    </div>
                  )}
                </div>

                {m.role === 'user' && (
                  <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-xl bg-slate-800 text-slate-300">
                    <User className="h-4 w-4" />
                  </div>
                )}
              </div>
            ))
          )}

          {loading && (
            <div className="flex items-center gap-3 text-xs text-slate-400">
              <div className="flex h-8 w-8 items-center justify-center rounded-xl bg-indigo-600/20 text-indigo-400 border border-indigo-500/30">
                <Loader2 className="h-4 w-4 animate-spin" />
              </div>
              <span>Executing hybrid retrieval, reranking, and generation...</span>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>

        {/* Input Bar */}
        <div className="border-t border-slate-800 p-4 bg-slate-850">
          <form
            onSubmit={(e) => {
              e.preventDefault();
              handleSendMessage();
            }}
            className="flex items-center gap-2"
          >
            <input
              type="text"
              placeholder="Ask a question about your documents, policies, or SLAs..."
              value={inputQuery}
              onChange={(e) => setInputQuery(e.target.value)}
              disabled={loading}
              className="flex-1 rounded-xl border border-slate-800 bg-slate-950 px-4 py-2.5 text-xs text-slate-200 placeholder-slate-500 focus:border-indigo-500 focus:outline-none disabled:opacity-50"
            />
            <button
              type="submit"
              disabled={loading || !inputQuery.trim()}
              className="flex h-10 w-10 items-center justify-center rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white shadow-md shadow-indigo-600/30 disabled:opacity-50 disabled:cursor-not-allowed transition-all"
            >
              <Send className="h-4 w-4" />
            </button>
          </form>
        </div>
      </div>
    </div>
  );
};
