import React, { useState } from 'react';
import {
  Settings as SettingsIcon,
  Cpu,
  Database,
  Shield,
  Layers,
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  Terminal,
} from 'lucide-react';

export const SettingsView: React.FC = () => {
  const [showAdvanced, setShowAdvanced] = useState<boolean>(false);

  return (
    <div className="space-y-8 animate-in fade-in duration-300">
      {/* Header */}
      <div className="border-b border-slate-800 pb-4 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <SettingsIcon className="h-6 w-6 text-indigo-400" />
            <h1 className="text-xl font-bold text-white">System Governance & Architecture Status</h1>
          </div>
          <p className="mt-1 text-xs text-slate-400">
            Active runtime configurations, grounding policies, security controls, and storage verification
          </p>
        </div>

        <div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 text-xs font-medium w-fit">
          <CheckCircle2 className="h-3.5 w-3.5" />
          <span>Enterprise Guardrails Active</span>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* LLM Provider Configuration */}
        <div className="rounded-2xl border border-slate-800 bg-slate-900/60 p-6 space-y-4">
          <div className="flex items-center justify-between border-b border-slate-800 pb-3">
            <div className="flex items-center gap-2.5">
              <Cpu className="h-5 w-5 text-indigo-400" />
              <h2 className="text-sm font-bold text-white">LLM Orchestration & Grounding</h2>
            </div>
            <span className="text-[11px] font-semibold text-indigo-400 bg-indigo-500/10 border border-indigo-500/20 px-2 py-0.5 rounded-full">
              Production Tier
            </span>
          </div>

          <div className="space-y-3 text-xs">
            <div className="flex items-center justify-between p-2.5 rounded-xl bg-slate-950 border border-slate-800">
              <span className="text-slate-400">Active Foundation Provider</span>
              <span className="font-semibold text-indigo-400">Google Gemini API</span>
            </div>

            <div className="flex items-center justify-between p-2.5 rounded-xl bg-slate-950 border border-slate-800">
              <span className="text-slate-400">Connected Model</span>
              <span className="font-semibold text-white">Gemini 2.5 Flash</span>
            </div>

            <div className="flex items-center justify-between p-2.5 rounded-xl bg-slate-950 border border-slate-800">
              <span className="text-slate-400">Inference Mode</span>
              <span className="text-emerald-400 font-medium">Strict Factuality (Deterministic Grounding)</span>
            </div>

            <div className="flex items-center justify-between p-2.5 rounded-xl bg-slate-950 border border-slate-800">
              <span className="text-slate-400">High-Availability Failover</span>
              <span className="text-slate-300">Deterministic Offline Provider Enabled</span>
            </div>

            <div className="flex items-center justify-between p-2.5 rounded-xl bg-slate-950 border border-slate-800">
              <span className="text-slate-400">Prompt Containment Boundary</span>
              <span className="text-indigo-300 font-medium">Structural XML Evidence Isolation</span>
            </div>
          </div>
        </div>

        {/* Embedding & Vector Store */}
        <div className="rounded-2xl border border-slate-800 bg-slate-900/60 p-6 space-y-4">
          <div className="flex items-center justify-between border-b border-slate-800 pb-3">
            <div className="flex items-center gap-2.5">
              <Database className="h-5 w-5 text-emerald-400" />
              <h2 className="text-sm font-bold text-white">Embeddings & Vector Knowledge Base</h2>
            </div>
            <span className="text-[11px] font-semibold text-emerald-400 bg-emerald-500/10 border border-emerald-500/20 px-2 py-0.5 rounded-full">
              Persistent Storage
            </span>
          </div>

          <div className="space-y-3 text-xs">
            <div className="flex items-center justify-between p-2.5 rounded-xl bg-slate-950 border border-slate-800">
              <span className="text-slate-400">Dense Semantic Embeddings</span>
              <span className="font-semibold text-emerald-400">all-MiniLM-L6-v2 (384-dimensional)</span>
            </div>

            <div className="flex items-center justify-between p-2.5 rounded-xl bg-slate-950 border border-slate-800">
              <span className="text-slate-400">Vector Store Architecture</span>
              <span className="font-semibold text-white">ChromaDB Vector Index (HNSW)</span>
            </div>

            <div className="flex items-center justify-between p-2.5 rounded-xl bg-slate-950 border border-slate-800">
              <span className="text-slate-400">Distance Metric</span>
              <span className="text-white">Cosine Similarity</span>
            </div>

            <div className="flex items-center justify-between p-2.5 rounded-xl bg-slate-950 border border-slate-800">
              <span className="text-slate-400">Data Persistence Strategy</span>
              <span className="text-slate-300">Dedicated Docker Data Volume Mount</span>
            </div>

            <div className="flex items-center justify-between p-2.5 rounded-xl bg-slate-950 border border-slate-800">
              <span className="text-slate-400">Relational Metadata Store</span>
              <span className="text-slate-300">SQLite SQLAlchemy Session Store</span>
            </div>
          </div>
        </div>

        {/* Keyword Search & Reranking */}
        <div className="rounded-2xl border border-slate-800 bg-slate-900/60 p-6 space-y-4">
          <div className="flex items-center justify-between border-b border-slate-800 pb-3">
            <div className="flex items-center gap-2.5">
              <Layers className="h-5 w-5 text-purple-400" />
              <h2 className="text-sm font-bold text-white">Hybrid Retrieval & Neural Reranker</h2>
            </div>
            <span className="text-[11px] font-semibold text-purple-400 bg-purple-500/10 border border-purple-500/20 px-2 py-0.5 rounded-full">
              Dual-Stage
            </span>
          </div>

          <div className="space-y-3 text-xs">
            <div className="flex items-center justify-between p-2.5 rounded-xl bg-slate-950 border border-slate-800">
              <span className="text-slate-400">Lexical Keyword Search</span>
              <span className="font-semibold text-purple-400">Lucene BM25 (Exact Code & Identifiers)</span>
            </div>

            <div className="flex items-center justify-between p-2.5 rounded-xl bg-slate-950 border border-slate-800">
              <span className="text-slate-400">Fusion Algorithm</span>
              <span className="font-semibold text-white">Reciprocal Rank Fusion (k=60)</span>
            </div>

            <div className="flex items-center justify-between p-2.5 rounded-xl bg-slate-950 border border-slate-800">
              <span className="text-slate-400">Second-Stage Reranker</span>
              <span className="font-semibold text-white">Cross-Encoder (Joint Self-Attention)</span>
            </div>

            <div className="flex items-center justify-between p-2.5 rounded-xl bg-slate-950 border border-slate-800">
              <span className="text-slate-400">Workflow Routing Engine</span>
              <span className="text-slate-300">LangGraph Stateful Execution DAG</span>
            </div>

            <div className="flex items-center justify-between p-2.5 rounded-xl bg-slate-950 border border-slate-800">
              <span className="text-slate-400">Ablation Recall Ceiling</span>
              <span className="text-emerald-400 font-bold">80.0% Recall@5 (100% on Answerable)</span>
            </div>
          </div>
        </div>

        {/* Guardrails & Ingestion Safety */}
        <div className="rounded-2xl border border-slate-800 bg-slate-900/60 p-6 space-y-4">
          <div className="flex items-center justify-between border-b border-slate-800 pb-3">
            <div className="flex items-center gap-2.5">
              <Shield className="h-5 w-5 text-amber-400" />
              <h2 className="text-sm font-bold text-white">Enterprise Safety & Guardrails</h2>
            </div>
            <span className="text-[11px] font-semibold text-amber-400 bg-amber-500/10 border border-amber-500/20 px-2 py-0.5 rounded-full">
              Zero Hallucination
            </span>
          </div>

          <div className="space-y-3 text-xs">
            <div className="flex items-center justify-between p-2.5 rounded-xl bg-slate-950 border border-slate-800">
              <span className="text-slate-400">Evidence Sufficiency Gate</span>
              <span className="text-amber-400 font-semibold">Explicit Abstention on Out-of-Domain</span>
            </div>

            <div className="flex items-center justify-between p-2.5 rounded-xl bg-slate-950 border border-slate-800">
              <span className="text-slate-400">Direct Quote Verification</span>
              <span className="text-white font-medium">Rolling N-Gram Matcher (Click-to-Verify)</span>
            </div>

            <div className="flex items-center justify-between p-2.5 rounded-xl bg-slate-950 border border-slate-800">
              <span className="text-slate-400">Prompt Injection Defense</span>
              <span className="text-emerald-400 font-medium">Passive Text Tag Neutralization</span>
            </div>

            <div className="flex items-center justify-between p-2.5 rounded-xl bg-slate-950 border border-slate-800">
              <span className="text-slate-400">Document Ingestion Firewall</span>
              <span className="text-slate-300">Magic Byte Inspection + Strict Whitelist</span>
            </div>

            <div className="flex items-center justify-between p-2.5 rounded-xl bg-slate-950 border border-slate-800">
              <span className="text-slate-400">Tool Execution Boundary</span>
              <span className="text-slate-300">Controlled Read-Only Execution Envelope</span>
            </div>
          </div>
        </div>
      </div>

      {/* Collapsible Advanced Engineering Diagnostics */}
      <div className="border border-slate-800/80 rounded-2xl bg-slate-950/40 overflow-hidden">
        <button
          onClick={() => setShowAdvanced(!showAdvanced)}
          className="w-full flex items-center justify-between p-4 text-xs font-semibold text-slate-400 hover:text-slate-200 hover:bg-slate-900/40 transition-colors"
        >
          <div className="flex items-center gap-2">
            <Terminal className="h-4 w-4 text-slate-500" />
            <span>Developer Diagnostics & Calibration Specs</span>
            <span className="text-[10px] text-slate-500 font-normal">(Internal tuning parameters)</span>
          </div>
          {showAdvanced ? (
            <ChevronUp className="h-4 w-4 text-slate-400" />
          ) : (
            <ChevronDown className="h-4 w-4 text-slate-400" />
          )}
        </button>

        {showAdvanced && (
          <div className="p-4 border-t border-slate-800/80 bg-slate-950 text-xs text-slate-400 space-y-2 font-mono">
            <div className="flex justify-between py-1 border-b border-slate-900">
              <span>Reranker Logit Threshold:</span>
              <span className="text-amber-400">&gt;= -6.0</span>
            </div>
            <div className="flex justify-between py-1 border-b border-slate-900">
              <span>Text Chunk Parameters:</span>
              <span className="text-white">Target 500 chars, 50 chars overlap</span>
            </div>
            <div className="flex justify-between py-1 border-b border-slate-900">
              <span>Direct Quote Minimum Length:</span>
              <span className="text-white">20 characters / 4-word window</span>
            </div>
            <div className="flex justify-between py-1 border-b border-slate-900">
              <span>Max Upload File Size:</span>
              <span className="text-white">10 MB (streaming 64 KB memory chunks)</span>
            </div>
            <div className="flex justify-between py-1">
              <span>Model Checkpoint:</span>
              <span className="text-indigo-400">ms-marco-MiniLM-L-6-v2 (CPU INT8)</span>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
