import { apiFetch } from "./client";
import type { FineTuningDocument, FineTuningRequest } from "../types/fineTuning";

export function startFineTuning(
  request: FineTuningRequest,
): Promise<FineTuningDocument> {
  return apiFetch<FineTuningDocument>("/fine-tunning/", {
    method: "POST",
    body: JSON.stringify(request),
  });
}

export function getFineTuningStatus(docId: string): Promise<FineTuningDocument> {
  return apiFetch<FineTuningDocument>(`/fine-tunning/${docId}`);
}
