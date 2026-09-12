import { API_BASE_URL } from "../config";
import type { Job, JobCreated, Language } from "../types/job";

export class ApiError extends Error {
  readonly status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

export async function createJob(file: File, language: Language): Promise<JobCreated> {
  const body = new FormData();
  body.append("file", file, file.name);
  body.append("language", language);
  return request<JobCreated>("/api/jobs", { method: "POST", body });
}

export function getJob(id: string): Promise<Job> {
  return request<Job>(`/api/jobs/${encodeURIComponent(id)}`);
}

export function audioUrl(job: Job): string | null {
  return job.audio_url ? `${API_BASE_URL}${job.audio_url}` : null;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, init);
  } catch {
    throw new ApiError("Cannot reach the server. Is the backend running?", 0);
  }
  if (!response.ok) {
    throw new ApiError(await errorMessage(response), response.status);
  }
  return (await response.json()) as T;
}

async function errorMessage(response: Response): Promise<string> {
  try {
    const payload = (await response.json()) as { detail?: unknown };
    if (typeof payload.detail === "string") return payload.detail;
  } catch {
    // non-JSON error body
  }
  return `Request failed (${response.status}).`;
}
