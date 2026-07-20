import { useEffect, useState } from "react";
import { checkHealth } from "./api.ts";

export type BackendStatus = "checking" | "online" | "offline";

/** Polls GET /health periodically so the UI can show a live online/offline badge. */
export function useBackendHealth(pollMs: number = 20000): BackendStatus {
  const [status, setStatus] = useState<BackendStatus>("checking");

  useEffect(() => {
    let cancelled = false;

    const check = async () => {
      const ok = await checkHealth();
      if (!cancelled) setStatus(ok ? "online" : "offline");
    };

    check();
    const interval = setInterval(check, pollMs);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, [pollMs]);

  return status;
}
