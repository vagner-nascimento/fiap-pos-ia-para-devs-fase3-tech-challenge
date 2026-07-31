export type PreprocessStatus =
  | "created"
  | "in_progress"
  | "completed"
  | "error";

export type StepStatus = "pending" | "in_progress" | "completed" | "error";

export interface StepInfo {
  status: StepStatus;
  error_message?: string;
}

export interface ResultsData {
  train_data: number;
  rag_data: number;
}

export interface Results {
  QAs: ResultsData;
  clinical_protocols: ResultsData;
}

export interface PreprocessDocument {
  id: string;
  rag_percent: number;
  steps: Record<string, StepInfo>;
  results: Results;
  status: PreprocessStatus;
  error_message?: string;
  updated_date: string;
  completion_percentage: number;
}

export interface PreprocessRequest {
  rag_percent?: number;
}

export const TERMINAL_STATUSES: PreprocessStatus[] = ["completed", "error"];

export function isTerminalStatus(status: string): boolean {
  return TERMINAL_STATUSES.includes(status as PreprocessStatus);
}
