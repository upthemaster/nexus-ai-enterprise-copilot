import React, { useEffect, useState, useRef } from 'react';
import {
  UploadCloud,
  FileText,
  Trash2,
  Sparkles,
  AlertTriangle,
  CheckCircle2,
  Clock,
  Loader2,
  Copy,
  Check,
  Search,
  Layers,
  ArrowRight,
  ShieldAlert,
} from 'lucide-react';
import { api } from '../api/client';
import {
  DocumentSummaryItem,
  DocumentSummarizeResponse,
  DocumentRisksResponse,
  CitationItem,
} from '../types/api';

interface DocumentsViewProps {
  onInspectCitation?: (citation: CitationItem) => void;
}

export const DocumentsView: React.FC<DocumentsViewProps> = ({ onInspectCitation }) => {
  const [documents, setDocuments] = useState<DocumentSummaryItem[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [search, setSearch] = useState<string>('');
  const [uploading, setUploading] = useState<boolean>(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [uploadSuccess, setUploadSuccess] = useState<string | null>(null);
  const [copiedId, setCopiedId] = useState<string | null>(null);

  // Workflow output modal states
  const [summaryResult, setSummaryResult] = useState<DocumentSummarizeResponse | null>(null);
  const [risksResult, setRisksResult] = useState<DocumentRisksResponse | null>(null);
  const [actionLoading, setActionLoading] = useState<string | null>(null);

  const fileInputRef = useRef<HTMLInputElement>(null);

  const loadDocs = async () => {
    try {
      setLoading(true);
      const res = await api.listDocuments();
      setDocuments(res.documents);
    } catch (err: any) {
      console.error('Failed to load documents:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadDocs();
  }, []);

  const handleFileUpload = async (file: File) => {
    setUploading(true);
    setUploadError(null);
    setUploadSuccess(null);

    try {
      const res = await api.uploadDocument(file);
      setUploadSuccess(`Ingested "${res.filename}" into ${res.chunk_count} searchable chunks!`);
      await loadDocs();
    } catch (err: any) {
      setUploadError(err.message || 'File ingestion failed.');
    } finally {
      setUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      handleFileUpload(e.dataTransfer.files[0]);
    }
  };

  const handleDelete = async (id: string, filename: string) => {
    if (!window.confirm(`Are you sure you want to delete "${filename}" and its vector index chunks?`)) {
      return;
    }
    try {
      await api.deleteDocument(id);
      await loadDocs();
    } catch (err: any) {
      alert(`Delete failed: ${err.message}`);
    }
  };

  const handleSummarize = async (id: string) => {
    setActionLoading(id);
    try {
      const res = await api.summarizeDocument(id);
      setSummaryResult(res);
    } catch (err: any) {
      alert(`Summarization failed: ${err.message}`);
    } finally {
      setActionLoading(null);
    }
  };

  const handleExtractRisks = async (id: string) => {
    setActionLoading(id);
    try {
      const res = await api.extractRisks(id);
      setRisksResult(res);
    } catch (err: any) {
      alert(`Risk extraction failed: ${err.message}`);
    } finally {
      setActionLoading(null);
    }
  };

  const handleCopyId = (id: string) => {
    navigator.clipboard.writeText(id);
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 2000);
  };

  const filteredDocs = documents.filter(
    (d) =>
      d.filename.toLowerCase().includes(search.toLowerCase()) ||
      d.id.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div className="space-y-8 animate-in fade-in duration-300">
      {/* Upload Box */}
      <div
        onDragOver={(e) => e.preventDefault()}
        onDrop={handleDrop}
        className="relative overflow-hidden rounded-3xl border-2 border-dashed border-slate-700 bg-slate-900/50 p-8 text-center hover:border-indigo-500/60 transition-colors"
      >
        <input
          ref={fileInputRef}
          type="file"
          accept=".pdf,.docx,.txt"
          onChange={(e) => e.target.files && e.target.files[0] && handleFileUpload(e.target.files[0])}
          className="hidden"
          id="file-upload"
        />

        <div className="max-w-md mx-auto space-y-3">
          <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl bg-indigo-500/10 text-indigo-400 border border-indigo-500/20 shadow-inner">
            {uploading ? (
              <Loader2 className="h-7 w-7 animate-spin" />
            ) : (
              <UploadCloud className="h-7 w-7" />
            )}
          </div>

          <div>
            <h2 className="text-base font-bold text-white">
              {uploading ? 'Processing document ingestion pipeline...' : 'Upload enterprise documents'}
            </h2>
            <p className="mt-1 text-xs text-slate-400">
              Drag and drop files here, or{' '}
              <label
                htmlFor="file-upload"
                className="cursor-pointer text-indigo-400 font-semibold hover:text-indigo-300 underline underline-offset-2"
              >
                browse local files
              </label>
            </p>
          </div>

          <div className="flex items-center justify-center gap-2 pt-1 text-[11px] text-slate-500">
            <span className="rounded bg-slate-800 px-2 py-0.5 font-mono">PDF</span>
            <span className="rounded bg-slate-800 px-2 py-0.5 font-mono">DOCX</span>
            <span className="rounded bg-slate-800 px-2 py-0.5 font-mono">TXT</span>
            <span>• Max 10 MB per file</span>
          </div>
        </div>

        {uploadSuccess && (
          <div className="mt-4 inline-flex items-center gap-2 rounded-xl border border-emerald-500/30 bg-emerald-500/10 px-4 py-2 text-xs font-medium text-emerald-400">
            <CheckCircle2 className="h-4 w-4" />
            {uploadSuccess}
          </div>
        )}

        {uploadError && (
          <div className="mt-4 inline-flex items-center gap-2 rounded-xl border border-rose-500/30 bg-rose-500/10 px-4 py-2 text-xs font-medium text-rose-400">
            <ShieldAlert className="h-4 w-4" />
            {uploadError}
          </div>
        )}
      </div>

      {/* Document Inventory Table */}
      <div className="rounded-2xl border border-slate-800 bg-slate-900/60 p-6 space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-slate-800 pb-4">
          <div>
            <h2 className="text-base font-semibold text-white">Indexed Document Catalog</h2>
            <p className="text-xs text-slate-400">
              {documents.length} documents stored across ChromaDB vector store and BM25 index
            </p>
          </div>

          <div className="relative w-full sm:w-64">
            <Search className="absolute left-3 top-2.5 h-4 w-4 text-slate-500" />
            <input
              type="text"
              placeholder="Search filename or UUID..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="w-full rounded-xl border border-slate-800 bg-slate-950 pl-9 pr-3 py-1.5 text-xs text-slate-200 placeholder-slate-500 focus:border-indigo-500 focus:outline-none"
            />
          </div>
        </div>

        {loading ? (
          <div className="py-16 text-center text-xs text-slate-500 flex flex-col items-center gap-2">
            <Loader2 className="h-6 w-6 text-indigo-400 animate-spin" />
            <span>Fetching registered documents...</span>
          </div>
        ) : filteredDocs.length === 0 ? (
          <div className="py-16 text-center text-xs text-slate-500">
            No documents match your query.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs text-slate-300">
              <thead className="border-b border-slate-800 bg-slate-950/40 text-[11px] font-semibold uppercase tracking-wider text-slate-500">
                <tr>
                  <th className="py-3 px-4">Document</th>
                  <th className="py-3 px-4">Document ID</th>
                  <th className="py-3 px-4">Format</th>
                  <th className="py-3 px-4">Chunks</th>
                  <th className="py-3 px-4">Status</th>
                  <th className="py-3 px-4">Ingested</th>
                  <th className="py-3 px-4 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60 font-sans">
                {filteredDocs.map((doc) => (
                  <tr key={doc.id} className="hover:bg-slate-800/30 transition-colors">
                    <td className="py-3.5 px-4">
                      <div className="flex items-center gap-2.5">
                        <FileText className="h-4 w-4 text-indigo-400 shrink-0" />
                        <span className="font-semibold text-slate-200 max-w-xs truncate" title={doc.filename}>
                          {doc.filename}
                        </span>
                      </div>
                    </td>

                    <td className="py-3.5 px-4 font-mono text-[11px] text-slate-400">
                      <div className="flex items-center gap-1.5">
                        <span>{doc.id.slice(0, 8)}...</span>
                        <button
                          onClick={() => handleCopyId(doc.id)}
                          className="text-slate-500 hover:text-slate-300"
                          title="Copy Full UUID"
                        >
                          {copiedId === doc.id ? (
                            <Check className="h-3 w-3 text-emerald-400" />
                          ) : (
                            <Copy className="h-3 w-3" />
                          )}
                        </button>
                      </div>
                    </td>

                    <td className="py-3.5 px-4">
                      <span className="rounded bg-slate-800 px-2 py-0.5 font-mono text-[10px] uppercase text-slate-300">
                        {doc.file_type}
                      </span>
                    </td>

                    <td className="py-3.5 px-4 font-medium text-slate-200">
                      <span className="flex items-center gap-1">
                        <Layers className="h-3.5 w-3.5 text-slate-500" />
                        {doc.chunk_count}
                      </span>
                    </td>

                    <td className="py-3.5 px-4">
                      <span className="inline-flex items-center gap-1 rounded-full bg-emerald-500/10 px-2.5 py-0.5 text-[10px] font-semibold text-emerald-400 border border-emerald-500/20">
                        <span className="h-1.5 w-1.5 rounded-full bg-emerald-400" />
                        {doc.status}
                      </span>
                    </td>

                    <td className="py-3.5 px-4 text-slate-400 text-[11px]">
                      <span className="flex items-center gap-1">
                        <Clock className="h-3 w-3 text-slate-500" />
                        {new Date(doc.created_at).toLocaleDateString()}
                      </span>
                    </td>

                    <td className="py-3.5 px-4 text-right">
                      <div className="flex items-center justify-end gap-1.5">
                        <button
                          onClick={() => handleSummarize(doc.id)}
                          disabled={actionLoading === doc.id}
                          className="rounded-lg border border-slate-700 bg-slate-800 hover:bg-slate-700 px-2.5 py-1 text-[11px] font-medium text-slate-200 flex items-center gap-1 transition-colors"
                          title="Execute Executive Summarization Workflow"
                        >
                          {actionLoading === doc.id ? (
                            <Loader2 className="h-3 w-3 animate-spin" />
                          ) : (
                            <Sparkles className="h-3 w-3 text-indigo-400" />
                          )}
                          Summarize
                        </button>

                        <button
                          onClick={() => handleExtractRisks(doc.id)}
                          disabled={actionLoading === doc.id}
                          className="rounded-lg border border-slate-700 bg-slate-800 hover:bg-slate-700 px-2.5 py-1 text-[11px] font-medium text-slate-200 flex items-center gap-1 transition-colors"
                          title="Extract Structured Risks"
                        >
                          <AlertTriangle className="h-3 w-3 text-amber-400" />
                          Risks
                        </button>

                        <button
                          onClick={() => handleDelete(doc.id, doc.filename)}
                          className="rounded-lg p-1.5 text-slate-500 hover:text-rose-400 hover:bg-rose-500/10 transition-colors"
                          title="Delete Document"
                        >
                          <Trash2 className="h-3.5 w-3.5" />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Summary Result Modal */}
      {summaryResult && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-sm">
          <div className="relative w-full max-w-2xl rounded-2xl border border-slate-800 bg-slate-900 p-6 shadow-2xl space-y-4 max-h-[85vh] overflow-y-auto">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <div className="flex items-center gap-2">
                <Sparkles className="h-5 w-5 text-indigo-400" />
                <h3 className="text-sm font-bold text-white">Executive Document Summary</h3>
              </div>
              <button
                onClick={() => setSummaryResult(null)}
                className="text-slate-400 hover:text-white text-xs font-semibold"
              >
                ✕ Close
              </button>
            </div>

            <div className="space-y-4 text-xs">
              <div>
                <span className="font-semibold text-slate-300 block mb-1 uppercase tracking-wider text-[10px]">
                  Executive Overview
                </span>
                <p className="text-slate-200 bg-slate-950 p-3 rounded-xl border border-slate-800 leading-relaxed whitespace-pre-wrap">
                  {summaryResult.summary}
                </p>
              </div>

              {summaryResult.key_findings && summaryResult.key_findings.length > 0 && (
                <div>
                  <span className="font-semibold text-slate-300 block mb-1 uppercase tracking-wider text-[10px]">
                    Key Findings
                  </span>
                  <ul className="space-y-1.5 bg-slate-950 p-3 rounded-xl border border-slate-800">
                    {summaryResult.key_findings.map((f, i) => (
                      <li key={i} className="flex items-start gap-2 text-slate-200">
                        <span className="text-indigo-400 font-bold">•</span>
                        <span>{f}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {summaryResult.action_items && summaryResult.action_items.length > 0 && (
                <div>
                  <span className="font-semibold text-slate-300 block mb-1 uppercase tracking-wider text-[10px]">
                    Action Items
                  </span>
                  <ul className="space-y-1.5 bg-slate-950 p-3 rounded-xl border border-slate-800">
                    {summaryResult.action_items.map((a, i) => (
                      <li key={i} className="flex items-start gap-2 text-slate-200">
                        <ArrowRight className="h-3.5 w-3.5 text-emerald-400 shrink-0 mt-0.5" />
                        <span>{a}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {summaryResult.citations && summaryResult.citations.length > 0 && (
                <div>
                  <span className="font-semibold text-slate-300 block mb-1 uppercase tracking-wider text-[10px]">
                    Evidence Citations
                  </span>
                  <div className="flex flex-wrap gap-1.5">
                    {summaryResult.citations.map((c, i) => (
                      <button
                        key={i}
                        onClick={() => onInspectCitation && onInspectCitation(c)}
                        className="rounded bg-slate-800 hover:bg-indigo-600/30 hover:border-indigo-500/50 px-2 py-1 font-mono text-[10px] text-indigo-300 border border-slate-700 transition-colors"
                      >
                        [{c.chunk_id}] (p.{c.page_number || 1})
                      </button>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Risks Result Modal */}
      {risksResult && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-sm">
          <div className="relative w-full max-w-3xl rounded-2xl border border-slate-800 bg-slate-900 p-6 shadow-2xl space-y-4 max-h-[85vh] overflow-y-auto">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <div className="flex items-center gap-2">
                <AlertTriangle className="h-5 w-5 text-amber-400" />
                <h3 className="text-sm font-bold text-white">Document Risk Register</h3>
                <span
                  className={`ml-2 rounded px-2 py-0.5 text-[10px] font-bold ${
                    risksResult.overall_risk_level === 'HIGH'
                      ? 'bg-rose-500/20 text-rose-400 border border-rose-500/30'
                      : risksResult.overall_risk_level === 'MEDIUM'
                      ? 'bg-amber-500/20 text-amber-400 border border-amber-500/30'
                      : 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30'
                  }`}
                >
                  OVERALL: {risksResult.overall_risk_level}
                </span>
              </div>
              <button
                onClick={() => setRisksResult(null)}
                className="text-slate-400 hover:text-white text-xs font-semibold"
              >
                ✕ Close
              </button>
            </div>

            <div className="space-y-3">
              {risksResult.risks.length === 0 ? (
                <div className="py-8 text-center text-xs text-slate-400">
                  No compliance or operational risks identified in this document.
                </div>
              ) : (
                risksResult.risks.map((r, i) => (
                  <div
                    key={i}
                    className="p-3.5 rounded-xl border border-slate-800 bg-slate-950/80 space-y-2 text-xs"
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <span
                          className={`rounded px-1.5 py-0.5 text-[10px] font-bold ${
                            r.severity === 'HIGH'
                              ? 'bg-rose-500/20 text-rose-400'
                              : r.severity === 'MEDIUM'
                              ? 'bg-amber-500/20 text-amber-400'
                              : 'bg-emerald-500/20 text-emerald-400'
                          }`}
                        >
                          {r.severity}
                        </span>
                        <span className="font-semibold text-slate-200">{r.category}</span>
                      </div>
                      <span className="font-mono text-[10px] text-slate-500">{r.risk_id}</span>
                    </div>

                    <p className="text-slate-300 leading-relaxed">{r.description}</p>

                    {r.mitigation && (
                      <div className="pt-1.5 border-t border-slate-800/60 flex items-start gap-1.5 text-slate-400 text-[11px]">
                        <span className="font-semibold text-slate-300">Mitigation:</span>
                        <span>{r.mitigation}</span>
                      </div>
                    )}
                  </div>
                ))
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

