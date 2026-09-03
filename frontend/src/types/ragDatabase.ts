export type RagGenerationStatus = "completed" | "error";

export interface RagGenerationPreprocessSnapshot {
  _id: string;
  status: string;
  rag_percent?: number | null;
  updated_date?: string | null;
}

export interface RagGenerationDocument {
  id: string;
  batch_id: string;
  preprocess_id: string;
  preprocess_snapshot: RagGenerationPreprocessSnapshot;
  clinical_protocols_rag_path: string;
  medical_reports_path: string;
  embedding_model: string;
  splitter_name: string;
  splitter_chunk_size: number;
  splitter_chunk_overlap: number;
  status: RagGenerationStatus;
  error_message: string | null;
  created_date: string;
  updated_date: string;
  clinical_protocol_documents: number;
  medical_report_documents: number;
  total_documents: number;
}

export interface RagGenerationRequest {
  preprocess_id: string;
}

export interface RagQueryRequest {
  query: string;
  top_k?: number;
  preprocess_id?: string | null;
  similarity_threshold?: number | null;
}

export interface RagDocumentResult {
  id: string;
  preprocess_id: string;
  dataset: string;
  source_type: string;
  content: string;
  similarity_score: number;
  metadatas: Record<string, any>;
  chunk_index?: number | null;
  chunk_total?: number | null;
}

export interface RagQueryResponse {
  query: string;
  total_results: number;
  documents: RagDocumentResult[];
}

