/**
 * API client for NexusAI Enterprise Copilot.
 * 
 * Why: Centralizes HTTP communication, base URLs, error unwrapping,
 * and strict typing against the FastAPI backend.
 */

import {
  HealthResponse,
  DocumentListResponse,
  DocumentSummaryItem,
  DocumentUploadResponse,
  ChatResponse,
  CitationSourceDetails,
  ConversationItem,
  ConversationThread,
  WorkflowRunResponse,
  DocumentSummarizeResponse,
  DocumentRisksResponse,
  AblationComparisonResponse,
  EvaluationRunSummary,
  WorkflowType,
} from '../types/api';

const API_BASE = '/api/v1';

class ApiError extends Error {
  status: number;
  errorType?: string;

  constructor(message: string, status: number, errorType?: string) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.errorType = errorType;
  }
}

async function request<T>(endpoint: string, options?: RequestInit): Promise<T> {
  const url = `${API_BASE}${endpoint}`;
  try {
    const res = await fetch(url, {
      ...options,
      headers: {
        'Accept': 'application/json',
        ...(options?.headers || {}),
      },
    });

    if (!res.ok) {
      let errorMsg = `HTTP ${res.status}: ${res.statusText}`;
      let errorType = 'HttpError';
      try {
        const body = await res.json();
        if (body.error) errorMsg = body.error;
        if (body.detail) errorMsg = typeof body.detail === 'string' ? body.detail : JSON.stringify(body.detail);
        if (body.error_type) errorType = body.error_type;
      } catch {
        // Fallback to status text
      }
      throw new ApiError(errorMsg, res.status, errorType);
    }

    return (await res.json()) as T;
  } catch (err: any) {
    if (err instanceof ApiError) throw err;
    throw new ApiError(err?.message || 'Network error occurred', 0, 'NetworkError');
  }
}

export const api = {
  // 1. Health
  getHealth: async (): Promise<HealthResponse> => {
    return request<HealthResponse>('/health');
  },

  // 2. Documents
  listDocuments: async (): Promise<DocumentListResponse> => {
    return request<DocumentListResponse>('/documents');
  },

  getDocument: async (documentId: string): Promise<DocumentSummaryItem> => {
    return request<DocumentSummaryItem>(`/documents/${documentId}`);
  },

  deleteDocument: async (documentId: string): Promise<{ status: string; document_id: string }> => {
    return request<{ status: string; document_id: string }>(`/documents/${documentId}`, {
      method: 'DELETE',
    });
  },

  uploadDocument: async (file: File): Promise<DocumentUploadResponse> => {
    const formData = new FormData();
    formData.append('file', file);
    return request<DocumentUploadResponse>('/documents/upload', {
      method: 'POST',
      body: formData,
    });
  },

  summarizeDocument: async (documentId: string, focusAreas?: string[]): Promise<DocumentSummarizeResponse> => {
    return request<DocumentSummarizeResponse>(`/documents/${documentId}/summarize`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ focus_areas: focusAreas || [] }),
    });
  },

  extractRisks: async (documentId: string): Promise<DocumentRisksResponse> => {
    return request<DocumentRisksResponse>(`/documents/${documentId}/risks`, {
      method: 'POST',
    });
  },

  // 3. Grounded Chat
  askChat: async (payload: {
    query: string;
    top_k?: number;
    conversation_id?: string;
  }): Promise<ChatResponse> => {
    return request<ChatResponse>('/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
  },

  // 4. LangGraph Workflows
  runWorkflow: async (payload: {
    query: string;
    workflow_type?: WorkflowType;
    conversation_id?: string;
    top_k?: number;
  }): Promise<WorkflowRunResponse> => {
    return request<WorkflowRunResponse>('/workflows/run', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        query: payload.query,
        workflow_type: payload.workflow_type || 'auto',
        conversation_id: payload.conversation_id,
        top_k: payload.top_k || 5,
      }),
    });
  },

  // 5. Source Inspector
  getCitationSource: async (chunkId: string): Promise<CitationSourceDetails> => {
    return request<CitationSourceDetails>(`/citations/${chunkId}`);
  },

  // 6. Conversations
  listConversations: async (): Promise<ConversationItem[]> => {
    return request<ConversationItem[]>('/conversations');
  },

  createConversation: async (title?: string): Promise<ConversationItem> => {
    return request<ConversationItem>('/conversations', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ title: title || 'New Chat' }),
    });
  },

  getConversation: async (id: string): Promise<ConversationThread> => {
    return request<ConversationThread>(`/conversations/${id}`);
  },

  deleteConversation: async (id: string): Promise<{ status: string }> => {
    return request<{ status: string }>(`/conversations/${id}`, {
      method: 'DELETE',
    });
  },

  // 7. Evaluation & Ablation
  getAblationComparison: async (): Promise<AblationComparisonResponse> => {
    return request<AblationComparisonResponse>('/evaluation/ablation');
  },

  runEvaluation: async (payload?: {
    dataset_version?: string;
    retrieval_config?: string;
    include_generation?: boolean;
    top_k?: number;
  }): Promise<EvaluationRunSummary> => {
    return request<EvaluationRunSummary>('/evaluation/run', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        dataset_version: payload?.dataset_version || 'v1',
        retrieval_config: payload?.retrieval_config || 'hybrid_rerank',
        include_generation: payload?.include_generation ?? false,
        top_k: payload?.top_k || 5,
      }),
    });
  },

  listEvaluationRuns: async (): Promise<EvaluationRunSummary[]> => {
    return request<EvaluationRunSummary[]>('/evaluation/runs');
  },

  getEvaluationRun: async (id: string): Promise<any> => {
    return request<any>(`/evaluation/runs/${id}`);
  },
};

