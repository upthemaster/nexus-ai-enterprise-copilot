/**
 * TypeScript API contracts for NexusAI Enterprise Copilot.
 * 
 * Why: Strictly mirrors the backend Pydantic schemas across Ingestion,
 * Retrieval, Grounded Generation, LangGraph Workflows, and Evaluation.
 */

export interface HealthResponse {
  status: string;
  app: string;
  environment: string;
  version: string;
  timestamp: string;
}

export interface DocumentSummaryItem {
  id: string;
  filename: string;
  file_type: string;
  content_hash: string;
  status: 'indexing' | 'indexed' | 'failed' | string;
  chunk_count: number;
  created_at: string;
  updated_at: string;
}

export interface DocumentListResponse {
  total: number;
  documents: DocumentSummaryItem[];
}

export interface PageExtraction {
  page_number: number;
  text: string;
  character_count: number;
}

export interface DocumentUploadResponse {
  document_id: string;
  filename: string;
  file_type: string;
  status: string;
  extracted_pages: PageExtraction[];
  character_count: number;
  chunk_count: number;
  content_hash: string;
  warnings: string[];
}

export interface CitationItem {
  chunk_id: string;
  document_id?: string;
  filename?: string;
  page_number?: number;
  bounding_box?: string;
  is_direct_quote?: boolean;
  quote_span?: string;
  snippet?: string;
}

export interface ChatResponse {
  answer: string;
  citations: CitationItem[];
  insufficient_evidence: boolean;
  request_id?: string;
  latency_ms?: number;
  top_rerank_score?: number;
  execution_route?: string[];
  conversation_id?: string;
}

export interface CitationSourceDetails {
  chunk_id: string;
  document_id: string;
  filename: string;
  page_number: number;
  chunk_index: number;
  character_count: number;
  text: string;
}

export interface ConversationItem {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
  message_count?: number;
}

export interface ConversationMessage {
  id: string;
  conversation_id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  citations?: CitationItem[];
  insufficient_evidence?: boolean;
  created_at: string;
}

export interface ConversationThread {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
  messages: ConversationMessage[];
}

export type WorkflowType = 'auto' | 'qa' | 'summarize' | 'extract_risks';

export interface WorkflowRunResponse {
  query: string;
  workflow_type: WorkflowType;
  execution_route: string[];
  result?: string;
  answer?: string;
  citations: CitationItem[];
  insufficient_evidence: boolean;
  latency_ms?: number;
  timing_ms?: number;
  top_rerank_score?: number;
}

export interface DocumentSummarizeResponse {
  document_id: string;
  summary: string;
  key_findings: string[];
  action_items: string[];
  citations: CitationItem[];
  latency_ms: number;
}

export interface RiskItem {
  risk_id: string;
  category: string;
  severity: 'HIGH' | 'MEDIUM' | 'LOW' | string;
  description: string;
  mitigation: string;
  source_chunk_id?: string;
}

export interface DocumentRisksResponse {
  document_id: string;
  risks: RiskItem[];
  overall_risk_level: 'HIGH' | 'MEDIUM' | 'LOW' | 'UNKNOWN' | string;
  citations: CitationItem[];
  latency_ms: number;
}

export interface RetrievalMetrics {
  recall_at_1: number;
  recall_at_5: number;
  hit_at_5: number;
  mrr: number;
  map_at_5: number;
}

export interface GenerationMetrics {
  faithfulness: number;
  context_recall: number;
  citation_precision: number;
  citation_recall: number;
  verbatim_quote_ratio: number;
  abstention_accuracy: number;
}

export interface OperationalMetrics {
  latency_p50_ms: number;
  latency_p90_ms: number;
  latency_p99_ms: number;
}

export interface EvaluationRunSummary {
  run_id: string;
  dataset_version: string;
  timestamp?: string;
  retrieval_config?: string;
  total_questions?: number;
  total_queries?: number;
  duration_seconds?: number;
  overall_retrieval_metrics?: {
    recall_at_1?: number;
    recall_at_3?: number;
    recall_at_5?: number;
    hit_at_1?: number;
    hit_at_3?: number;
    hit_at_5?: number;
    mrr?: number;
    context_precision?: number;
    context_recall?: number;
  };
  overall_generation_metrics?: {
    faithfulness?: number;
    context_recall?: number;
    citation_precision?: number;
    citation_recall?: number;
    verbatim_quote_ratio?: number;
    abstention_accuracy?: number;
  } | null;
  operational_metrics?: {
    latency_p50_ms?: number;
    latency_p90_ms?: number;
    latency_p95_ms?: number;
    latency_mean_ms?: number;
    total_queries?: number;
  };
  retrieval?: any;
  generation?: any;
  operational?: any;
}

export interface AblationConfigResult {
  config_name: string;
  description?: string;
  metrics?: RetrievalMetrics;
  retrieval_metrics?: RetrievalMetrics;
  latency_mean_ms?: number;
  latency_p95_ms?: number;
  latency_p50_ms?: number;
  latency_p90_ms?: number;
}

export interface AblationComparisonResponse {
  timestamp?: string;
  dataset_version: string;
  total_queries?: number;
  total_questions?: number;
  configurations?: Record<string, AblationConfigResult>;
  results?: Record<string, AblationConfigResult>;
  best_performing_config?: string;
  key_findings?: string[];
}

