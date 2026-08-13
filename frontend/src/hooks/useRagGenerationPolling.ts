import { useEffect, useRef } from "react";
import { getRagGenerationStatus } from "../api/ragDatabase";
import { isTerminalRagStatus, type RagGenerationDocument } from "../types/ragDatabase";

const POLL_INTERVAL_MS = 5000;

interface UseRagGenerationPollingOptions {
  docId: string | null;
  enabled: boolean;
  onUpdate: (document: RagGenerationDocument) => void;
  onError: (message: string) => void;
  onComplete: () => void;
}

export function useRagGenerationPolling({
  docId,
  enabled,
  onUpdate,
  onError,
  onComplete,
}: UseRagGenerationPollingOptions): void {
  const callbacksRef = useRef({ onUpdate, onError, onComplete });

  useEffect(() => {
    callbacksRef.current = { onUpdate, onError, onComplete };
  });

  useEffect(() => {
    if (!docId || !enabled) {
      return;
    }

    let cancelled = false;
    let timeoutId: ReturnType<typeof setTimeout> | undefined;

    const poll = async () => {
      if (cancelled) {
        return;
      }

      try {
        const document = await getRagGenerationStatus(docId);
        if (cancelled) {
          return;
        }

        callbacksRef.current.onUpdate(document);

        if (isTerminalRagStatus(document.status)) {
          callbacksRef.current.onComplete();
          return;
        }
      } catch (error) {
        if (cancelled) {
          return;
        }

        const message =
          error instanceof Error ? error.message : "Erro ao consultar status";
        callbacksRef.current.onError(message);
        callbacksRef.current.onComplete();
        return;
      }

      timeoutId = setTimeout(poll, POLL_INTERVAL_MS);
    };

    void poll();

    return () => {
      cancelled = true;
      if (timeoutId !== undefined) {
        clearTimeout(timeoutId);
      }
    };
  }, [docId, enabled]);
}
