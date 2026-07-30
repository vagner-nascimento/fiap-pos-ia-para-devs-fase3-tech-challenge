import { apiFetch } from "./client";
import type { PreprocessDocument, PreprocessRequest } from "../types/preprocess";

export function startPreprocess(
  request: PreprocessRequest = {},
): Promise<PreprocessDocument> {
  return apiFetch<PreprocessDocument>("/preprocess/", {
    method: "POST",
    body: JSON.stringify(request),
  });
}

export function getPreprocessStatus(docId: string): Promise<PreprocessDocument> {
  return apiFetch<PreprocessDocument>(`/preprocess/${docId}`);
}
