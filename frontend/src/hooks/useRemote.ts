import { useEffect, useState } from "react";
import { ApiError } from "../api/client.ts";

export type Remote<T> =
  | { status: "loading" }
  | { status: "error"; error: ApiError }
  | { status: "success"; data: T };

export function useRemote<T>(
  key: string,
  load: (signal: AbortSignal) => Promise<T>,
  onExpired: () => void,
) {
  const [attempt, setAttempt] = useState(0);
  const [result, setResult] = useState<{
    key: string;
    attempt: number;
    state: Remote<T>;
  }>();
  useEffect(() => {
    let active = true;
    const controller = new AbortController();
    load(controller.signal)
      .then((data) => {
        if (active)
          setResult({ key, attempt, state: { status: "success", data } });
      })
      .catch((error) => {
        if (!active || controller.signal.aborted) return;
        if (error instanceof ApiError && error.status === 401) {
          onExpired();
          return;
        }
        setResult({
          key,
          attempt,
          state: {
            status: "error",
            error:
              error instanceof ApiError
                ? error
                : new ApiError(
                    0,
                    "unexpected_error",
                    "Something went wrong. Please try again.",
                  ),
          },
        });
      });
    return () => {
      active = false;
      controller.abort();
    };
  }, [key, attempt, load, onExpired]);
  // A changed key never renders the previous ticket while its next effect starts.
  const state: Remote<T> =
    result?.key === key && result.attempt === attempt
      ? result.state
      : { status: "loading" };
  return { state, reload: () => setAttempt((value) => value + 1) };
}
