import { useEffect, useRef } from "react";
import { getPreprocessStatus } from "../api/preprocess";
import { isTerminalStatus, type PreprocessDocument } from "../types/preprocess";

const POLL_INTERVAL_MS = 5000;

interface UsePreprocessPollingOptions {
  docId: string | null;
  enabled: boolean;
  onUpdate: (document: PreprocessDocument) => void;
  onError: (message: string) => void;
  onComplete: (document: PreprocessDocument | null) => void;
}

export function usePreprocessPolling({
  docId,
  enabled,
  onUpdate,
  onError,
  onComplete,
}: UsePreprocessPollingOptions): void {
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
        const document = await getPreprocessStatus(docId);
        if (cancelled) {
          return;
        }

        callbacksRef.current.onUpdate(document);

        if (isTerminalStatus(document.status)) {
          callbacksRef.current.onComplete(document);
          return;
        }
      } catch (error) {
        if (cancelled) {
          return;
        }

        const message =
          error instanceof Error ? error.message : "Erro ao consultar status";
        callbacksRef.current.onError(message);
        // Retry after a delay instead of stopping the polling so transient
        // network errors don't abort the entire flow.
        timeoutId = setTimeout(poll, POLL_INTERVAL_MS);
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
