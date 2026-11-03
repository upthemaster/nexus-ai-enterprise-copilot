import React, { useEffect, useState } from 'react';
import {
  FileText,
  MessageSquare,
  BarChart3,
  Cpu,
  Layers,
  ArrowRight,
  ShieldCheck,
  Clock,
  Sparkles,
} from 'lucide-react';
import { api } from '../api/client';
import { DocumentSummaryItem, ConversationItem } from '../types/api';
import { ActiveTab } from '../components/Navbar';

interface DashboardViewProps {
  onNavigate: (tab: ActiveTab) => void;
}

export const DashboardView: React.FC<DashboardViewProps> = ({ onNavigate }) => {
  const [documents, setDocuments] = useState<DocumentSummaryItem[]>([]);
  const [conversations, setConversations] = useState<ConversationItem[]>([]);
  const [totalChunks, setTotalChunks] = useState<number>(0);
  const [loading, setLoading] = useState<boolean>(true);

  useEffect(() => {
    let isMounted = true;
    Promise.all([
      api.listDocuments().catch(() => ({ total: 0, documents: [] })),
      api.listConversations().catch(() => []),
    ]).then(([docRes, convList]) => {
      if (isMounted) {
        setDocuments(docRes.documents);
        const chunkSum = docRes.documents.reduce((acc, d) => acc + (d.chunk_count || 0), 0);
        setTotalChunks(chunkSum);
        setConversations(convList);
        setLoading(false);
      }
    });

    return () => {
      isMounted = false;
    };
  }, []);

  return (
    <div className="space-y-8 animate-in fade-in duration-300">
      {/* Hero Banner */}
      <div className="relative overflow-hidden rounded-3xl border border-slate-800 bg-gradient-to-br from-slate-900 via-slate-900 to-indigo-950/40 p-8 shadow-2xl">
        <div className="relative z-10 max-w-3xl space-y-4">
          <div className="inline-flex items-center gap-2 rounded-full border border-indigo-500/20 bg-indigo-500/10 px-3 py-1 text-xs font-semibold text-indigo-400">
            <Sparkles className="h-3.5 w-3.5" />
            Enterprise Knowledge & Workflow Orchestration
          </div>
          <h1 className="text-3xl sm:text-4xl font-extrabold tracking-tight text-white">
            Reliable enterprise intelligence with verifiable citations.
          </h1>
          <p className="text-sm sm:text-base text-slate-300 leading-relaxed">
            NexusAI ingests internal documentation, searches across dense semantic embeddings and sparse BM25 indices, applies neural cross-encoder reranking, and runs stateful LangGraph workflows with mathematical citation grounding.
          </p>

          <div className="flex flex-wrap items-center gap-3 pt-2">
            <button
              onClick={() => onNavigate('chat')}
              className="flex items-center gap-2 rounded-xl bg-indigo-600 hover:bg-indigo-500 px-5 py-2.5 text-sm font-semibold text-white shadow-lg shadow-indigo-600/30 transition-all hover:gap-3"
            >
              <MessageSquare className="h-4 w-4" />
              Start Grounded Chat
              <ArrowRight className="h-4 w-4" />
            </button>
            <button
              onClick={() => onNavigate('documents')}
              className="flex items-center gap-2 rounded-xl border border-slate-700 bg-slate-800/80 hover:bg-slate-700 px-5 py-2.5 text-sm font-semibold text-slate-200 transition-colors"
            >
              <FileText className="h-4 w-4" />
              Upload Document
            </button>
            <button
              onClick={() => onNavigate('evaluation')}
              className="flex items-center gap-2 rounded-xl border border-slate-700 bg-slate-800/80 hover:bg-slate-700 px-5 py-2.5 text-sm font-semibold text-slate-200 transition-colors"
            >
              <BarChart3 className="h-4 w-4" />
              View Ablation Benchmarks
            </button>
          </div>
        </div>

        {/* Background glow decoration */}
        <div className="absolute right-0 top-0 -mr-16 -mt-16 h-80 w-80 rounded-full bg-indigo-500/10 blur-3xl pointer-events-none" />
      </div>

      {/* Metric Cards Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Card 1: Documents */}
        <div className="rounded-2xl border border-slate-800 bg-slate-900/60 p-5 shadow-sm hover:border-slate-700 transition-colors">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold uppercase tracking-wider text-slate-400">Indexed Documents</span>
            <div className="rounded-xl bg-blue-500/10 p-2 text-blue-400 border border-blue-500/20">
              <FileText className="h-5 w-5" />
            </div>
          </div>
          <div className="mt-4 flex items-baseline gap-2">
            <span className="text-3xl font-extrabold text-white">
              {loading ? '...' : documents.length}
            </span>
            <span className="text-xs text-slate-400">files registered</span>
          </div>
          <p className="mt-2 text-xs text-slate-400">PDF, DOCX & TXT parsed page-by-page</p>
        </div>

        {/* Card 2: Chunks */}
        <div className="rounded-2xl border border-slate-800 bg-slate-900/60 p-5 shadow-sm hover:border-slate-700 transition-colors">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold uppercase tracking-wider text-slate-400">Knowledge Chunks</span>
            <div className="rounded-xl bg-emerald-500/10 p-2 text-emerald-400 border border-emerald-500/20">
              <Layers className="h-5 w-5" />
            </div>
          </div>
          <div className="mt-4 flex items-baseline gap-2">
            <span className="text-3xl font-extrabold text-white">
              {loading ? '...' : totalChunks}
            </span>
            <span className="text-xs text-slate-400">indexed passages</span>
          </div>
          <p className="mt-2 text-xs text-slate-400">ChromaDB HNSW + Lucene BM25</p>
        </div>

        {/* Card 3: Conversations */}
        <div className="rounded-2xl border border-slate-800 bg-slate-900/60 p-5 shadow-sm hover:border-slate-700 transition-colors">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold uppercase tracking-wider text-slate-400">Active Sessions</span>
            <div className="rounded-xl bg-purple-500/10 p-2 text-purple-400 border border-purple-500/20">
              <MessageSquare className="h-5 w-5" />
            </div>
          </div>
          <div className="mt-4 flex items-baseline gap-2">
            <span className="text-3xl font-extrabold text-white">
              {loading ? '...' : conversations.length}
            </span>
            <span className="text-xs text-slate-400">persisted threads</span>
          </div>
          <p className="mt-2 text-xs text-slate-400">SQLite SQLAlchemy session store</p>
        </div>

        {/* Card 4: Evaluation Benchmark */}
        <div className="rounded-2xl border border-slate-800 bg-slate-900/60 p-5 shadow-sm hover:border-slate-700 transition-colors">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold uppercase tracking-wider text-slate-400">Recall@5 Ceiling</span>
            <div className="rounded-xl bg-amber-500/10 p-2 text-amber-400 border border-amber-500/20">
              <ShieldCheck className="h-5 w-5" />
            </div>
          </div>
          <div className="mt-4 flex items-baseline gap-2">
            <span className="text-3xl font-extrabold text-white">80.0%</span>
            <span className="text-xs text-emerald-400 font-semibold">100% on answerable</span>
          </div>
          <p className="mt-2 text-xs text-slate-400">1.0000 Abstention Accuracy on negatives</p>
        </div>
      </div>

      {/* Two Column Layout: Recent Documents & Pipeline Capabilities */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left 2 Cols: Ingested Documents Overview */}
        <div className="lg:col-span-2 rounded-2xl border border-slate-800 bg-slate-900/60 p-6 space-y-4">
          <div className="flex items-center justify-between border-b border-slate-800 pb-4">
            <div>
              <h2 className="text-base font-semibold text-white">Document Knowledge Base</h2>
              <p className="text-xs text-slate-400">Recent policy and runbook files indexed in the corpus</p>
            </div>
            <button
              onClick={() => onNavigate('documents')}
              className="text-xs text-indigo-400 hover:text-indigo-300 font-medium flex items-center gap-1"
            >
              View all
              <ArrowRight className="h-3.5 w-3.5" />
            </button>
          </div>

          {loading ? (
            <div className="py-12 text-center text-xs text-slate-500">Loading documents...</div>
          ) : documents.length === 0 ? (
            <div className="py-12 text-center space-y-3">
              <FileText className="h-10 w-10 text-slate-600 mx-auto" />
              <p className="text-sm text-slate-400">No documents ingested yet.</p>
              <button
                onClick={() => onNavigate('documents')}
                className="px-4 py-2 rounded-lg bg-indigo-600 text-white text-xs font-semibold hover:bg-indigo-500 transition-colors"
              >
                Upload First Document
              </button>
            </div>
          ) : (
            <div className="divide-y divide-slate-800/60">
              {documents.slice(0, 5).map((doc) => (
                <div key={doc.id} className="py-3 flex items-center justify-between text-xs">
                  <div className="flex items-center gap-3">
                    <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-slate-800 text-slate-300">
                      <FileText className="h-4 w-4" />
                    </div>
                    <div>
                      <p className="font-semibold text-slate-200">{doc.filename}</p>
                      <div className="flex items-center gap-2 mt-0.5 text-slate-400 text-[11px]">
                        <span className="uppercase font-mono text-[10px] bg-slate-800 px-1.5 py-0.2 rounded">
                          {doc.file_type}
                        </span>
                        <span>•</span>
                        <span>{doc.chunk_count} chunks</span>
                        <span>•</span>
                        <span className="flex items-center gap-1">
                          <Clock className="h-3 w-3" />
                          {new Date(doc.created_at).toLocaleDateString()}
                        </span>
                      </div>
                    </div>
                  </div>

                  <span className="inline-flex items-center gap-1 rounded-full bg-emerald-500/10 px-2 py-0.5 text-[11px] font-medium text-emerald-400 border border-emerald-500/20">
                    <span className="h-1.5 w-1.5 rounded-full bg-emerald-400" />
                    {doc.status}
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Right Col: Active Stack & Guardrails */}
        <div className="rounded-2xl border border-slate-800 bg-slate-900/60 p-6 space-y-4">
          <div className="border-b border-slate-800 pb-4">
            <h2 className="text-base font-semibold text-white flex items-center gap-2">
              <Cpu className="h-4 w-4 text-indigo-400" />
              Active System Architecture
            </h2>
            <p className="text-xs text-slate-400">10-Day MVP Stack Configuration</p>
          </div>

          <div className="space-y-3 text-xs">
            <div className="flex items-start justify-between p-2.5 rounded-xl bg-slate-950/60 border border-slate-800/80">
              <div>
                <span className="text-slate-400 block font-medium">Embedding Model</span>
                <span className="text-slate-200 font-mono text-[11px]">all-MiniLM-L6-v2</span>
              </div>
              <span className="rounded bg-indigo-500/10 px-2 py-0.5 text-[10px] text-indigo-400 font-semibold">
                384-DIM
              </span>
            </div>

            <div className="flex items-start justify-between p-2.5 rounded-xl bg-slate-950/60 border border-slate-800/80">
              <div>
                <span className="text-slate-400 block font-medium">Neural Reranker</span>
                <span className="text-slate-200 font-mono text-[11px]">ms-marco-MiniLM-L-6-v2</span>
              </div>
              <span className="rounded bg-indigo-500/10 px-2 py-0.5 text-[10px] text-indigo-400 font-semibold">
                CROSS-ENC
              </span>
            </div>

            <div className="flex items-start justify-between p-2.5 rounded-xl bg-slate-950/60 border border-slate-800/80">
              <div>
                <span className="text-slate-400 block font-medium">Rank Fusion</span>
                <span className="text-slate-200 font-mono text-[11px]">Reciprocal Rank Fusion</span>
              </div>
              <span className="rounded bg-emerald-500/10 px-2 py-0.5 text-[10px] text-emerald-400 font-semibold">
                k=60
              </span>
            </div>

            <div className="flex items-start justify-between p-2.5 rounded-xl bg-slate-950/60 border border-slate-800/80">
              <div>
                <span className="text-slate-400 block font-medium">State Machine</span>
                <span className="text-slate-200 font-mono text-[11px]">LangGraph StateGraph</span>
              </div>
              <span className="rounded bg-purple-500/10 px-2 py-0.5 text-[10px] text-purple-400 font-semibold">
                DAG
              </span>
            </div>

            <div className="flex items-start justify-between p-2.5 rounded-xl bg-slate-950/60 border border-slate-800/80">
              <div>
                <span className="text-slate-400 block font-medium">Relational Database</span>
                <span className="text-slate-200 font-mono text-[11px]">SQLite (nexusai.db)</span>
              </div>
              <span className="rounded bg-slate-800 px-2 py-0.5 text-[10px] text-slate-300 font-semibold">
                ORM 2.0
              </span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
