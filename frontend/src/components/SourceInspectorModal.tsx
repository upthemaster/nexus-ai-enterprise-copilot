import React, { useEffect, useState } from 'react';
import { X, Copy, Check, FileText, Bookmark, Quote, Info, Loader2 } from 'lucide-react';
import { api } from '../api/client';
import { CitationItem, CitationSourceDetails } from '../types/api';

interface SourceInspectorModalProps {
  citation: CitationItem | null;
  onClose: () => void;
}

export const SourceInspectorModal: React.FC<SourceInspectorModalProps> = ({ citation, onClose }) => {
  const [details, setDetails] = useState<CitationSourceDetails | null>(null);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState<boolean>(false);

  useEffect(() => {
    if (!citation) return;

    let isMounted = true;
    setLoading(true);
    setError(null);

    api.getCitationSource(citation.chunk_id)
      .then((data) => {
        if (isMounted) {
          setDetails(data);
          setLoading(false);
        }
      })
      .catch((err) => {
        if (isMounted) {
          setError(err.message || 'Failed to load source chunk details.');
          setLoading(false);
        }
      });

    return () => {
      isMounted = false;
    };
  }, [citation]);

  if (!citation) return null;

  const handleCopy = () => {
    const textToCopy = details?.text || citation.snippet || '';
    if (textToCopy) {
      navigator.clipboard.writeText(textToCopy);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-sm animate-in fade-in duration-200">
      <div className="relative w-full max-w-2xl rounded-2xl border border-slate-800 bg-slate-900 shadow-2xl overflow-hidden flex flex-col max-h-[85vh]">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-slate-800 px-6 py-4 bg-slate-850">
          <div className="flex items-center gap-3">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-indigo-500/10 text-indigo-400 border border-indigo-500/20">
              <FileText className="h-4 w-4" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h3 className="text-sm font-semibold text-white">Source Passage Inspector</h3>
                <span className="rounded bg-slate-800 px-2 py-0.5 font-mono text-[10px] text-slate-300">
                  {citation.chunk_id}
                </span>
              </div>
              <p className="text-xs text-slate-400">Verifiable Ground-Truth Evidence Citation</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="rounded-lg p-1.5 text-slate-400 hover:bg-slate-800 hover:text-white transition-colors"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-6 space-y-4">
          {/* Metadata badges */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-xs">
            <div className="rounded-lg border border-slate-800 bg-slate-950/60 p-2.5">
              <span className="text-slate-500 block text-[10px] uppercase font-bold tracking-wider">Document</span>
              <span className="text-slate-200 font-medium truncate block" title={citation.filename || details?.filename}>
                {citation.filename || details?.filename || 'Unknown'}
              </span>
            </div>

            <div className="rounded-lg border border-slate-800 bg-slate-950/60 p-2.5">
              <span className="text-slate-500 block text-[10px] uppercase font-bold tracking-wider">Page Number</span>
              <span className="text-slate-200 font-medium">
                Page {citation.page_number ?? details?.page_number ?? 1}
              </span>
            </div>

            <div className="rounded-lg border border-slate-800 bg-slate-950/60 p-2.5">
              <span className="text-slate-500 block text-[10px] uppercase font-bold tracking-wider">Verification</span>
              {citation.is_direct_quote ? (
                <span className="inline-flex items-center gap-1 text-emerald-400 font-semibold">
                  <Quote className="h-3 w-3" /> Direct Quote
                </span>
              ) : (
                <span className="inline-flex items-center gap-1 text-sky-400 font-medium">
                  <Bookmark className="h-3 w-3" /> Paraphrase
                </span>
              )}
            </div>

            <div className="rounded-lg border border-slate-800 bg-slate-950/60 p-2.5">
              <span className="text-slate-500 block text-[10px] uppercase font-bold tracking-wider">Length</span>
              <span className="text-slate-200 font-mono">
                {details?.character_count || citation.snippet?.length || 0} chars
              </span>
            </div>
          </div>

          {/* Direct Quote Banner if matched */}
          {citation.is_direct_quote && citation.quote_span && (
            <div className="rounded-xl border border-emerald-500/20 bg-emerald-500/5 p-3 text-xs text-emerald-300 flex items-start gap-2.5">
              <Quote className="h-4 w-4 shrink-0 mt-0.5 text-emerald-400" />
              <div>
                <span className="font-semibold block text-emerald-400">Verbatim Sentence Match:</span>
                <p className="mt-1 italic font-serif text-slate-200">"{citation.quote_span}"</p>
              </div>
            </div>
          )}

          {/* Full passage view */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <label className="text-xs font-semibold text-slate-300 flex items-center gap-1.5">
                <Info className="h-3.5 w-3.5 text-indigo-400" />
                Complete Passage Text
              </label>
              <button
                onClick={handleCopy}
                className="flex items-center gap-1 text-[11px] text-slate-400 hover:text-indigo-400 transition-colors"
              >
                {copied ? (
                  <>
                    <Check className="h-3 w-3 text-emerald-400" />
                    <span className="text-emerald-400">Copied</span>
                  </>
                ) : (
                  <>
                    <Copy className="h-3 w-3" />
                    <span>Copy Text</span>
                  </>
                )}
              </button>
            </div>

            {loading ? (
              <div className="h-48 rounded-xl border border-slate-800 bg-slate-950 flex flex-col items-center justify-center gap-2">
                <Loader2 className="h-6 w-6 text-indigo-400 animate-spin" />
                <span className="text-xs text-slate-400">Fetching ground-truth chunk...</span>
              </div>
            ) : error ? (
              <div className="rounded-xl border border-rose-800/40 bg-rose-950/20 p-4 text-xs text-rose-300">
                <p className="font-semibold mb-1">Could not fetch source chunk details</p>
                <p className="text-rose-400">{error}</p>
                {citation.snippet && (
                  <div className="mt-3 pt-3 border-t border-rose-800/30">
                    <span className="font-semibold text-slate-300 block mb-1">Snippet from response:</span>
                    <p className="font-mono text-slate-400">{citation.snippet}</p>
                  </div>
                )}
              </div>
            ) : (
              <div className="rounded-xl border border-slate-800 bg-slate-950 p-4 font-mono text-xs leading-relaxed text-slate-300 whitespace-pre-wrap select-all max-h-64 overflow-y-auto">
                {details?.text || citation.snippet || 'No passage text available.'}
              </div>
            )}
          </div>
        </div>

        {/* Footer */}
        <div className="border-t border-slate-800 px-6 py-3 bg-slate-850 flex items-center justify-between text-xs text-slate-500">
          <span>Document ID: {citation.document_id || details?.document_id || 'N/A'}</span>
          <button
            onClick={onClose}
            className="px-4 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-white font-medium transition-colors"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
};

