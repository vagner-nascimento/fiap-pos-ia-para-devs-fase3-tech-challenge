import { useEffect, useRef } from "react";
import { getFineTuningStatus } from "../api/fineTuning";
import type { FineTuningDocument } from "../types/fineTuning";

const POLL_INTERVAL_MS = 5000;

interface UseFineTuningPollingOptions {
  docId: string | null;
  enabled: boolean;
  onUpdate: (document: FineTuningDocument) => void;
  onError: (message: string) => void;
  onComplete: () => void;
}

export function useFineTuningPolling({
  docId,
  enabled,
  onUpdate,
  onError,
  onComplete,
}: UseFineTuningPollingOptions): void {
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
        const document = await getFineTuningStatus(docId);
        if (cancelled) {
          return;
        }

        callbacksRef.current.onUpdate(document);

        if (document.status === "completed" || document.status === "error") {
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
