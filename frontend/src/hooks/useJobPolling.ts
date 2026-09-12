import { useEffect, useState } from "react";

import { ApiError, getJob } from "../api/jobs";
import { POLL_INTERVAL_MS } from "../config";
import { isFinished, type Job } from "../types/job";

interface JobPolling {
  job: Job | null;
  error: string | null;
}

interface PollState extends JobPolling {
  jobId: string;
}

const EMPTY: JobPolling = { job: null, error: null };

/** Polls GET /api/jobs/{id} until the job is completed or failed. */
export function useJobPolling(jobId: string | null): JobPolling {
  const [state, setState] = useState<PollState | null>(null);

  useEffect(() => {
    if (!jobId) return;

    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | undefined;

    const poll = async () => {
      try {
        const job = await getJob(jobId);
        if (cancelled) return;
        setState({ jobId, job, error: null });
        if (!isFinished(job.status)) timer = setTimeout(poll, POLL_INTERVAL_MS);
      } catch (caught) {
        if (cancelled) return;
        const error = caught instanceof ApiError ? caught.message : "Lost contact with the server.";
        setState((previous) => ({ jobId, job: previous?.jobId === jobId ? previous.job : null, error }));
      }
    };
    void poll();

    return () => {
      cancelled = true;
      if (timer) clearTimeout(timer);
    };
  }, [jobId]);

  // State from a previous job must not leak into a new one.
  return state && state.jobId === jobId ? state : EMPTY;
}
