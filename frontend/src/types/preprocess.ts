export type PreprocessStatus =
  | "created"
  | "in_progress"
  | "completed"
  | "error"
  | "failed";

export type StepStatus = "pending" | "in_progress" | "completed" | "error";

export interface StepInfo {
  status: StepStatus;
  error_message?: string;
  completion_percentage?: number;
}

export interface Results {
  qas_train_path?: string;
  qas_train_pt_br_path?: string;
  clinical_protocols_rag_path?: string;
  medical_reports_path?: string;
  medical_reports_count: number;
  qas_count: number;
  clinical_protocols_count: number;
}

export interface PreprocessDocument {
  id: string;
  steps: Record<string, StepInfo>;
  results: Results;
  status: PreprocessStatus;
  error_message?: string;
  updated_date: string;
  completion_percentage: number;
}

export interface PreprocessRequest {
  skip_translation?: boolean;
}

export const TERMINAL_STATUSES: PreprocessStatus[] = ["completed", "error", "failed"];

export function isTerminalStatus(status: string): boolean {
  return TERMINAL_STATUSES.includes(status as PreprocessStatus);
}
