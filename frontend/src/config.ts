/** Mirrors MAX_PDF_SIZE_MB on the backend (the server enforces the real limit). */
export const MAX_PDF_SIZE_MB = 100;
export const MAX_PDF_SIZE_BYTES = MAX_PDF_SIZE_MB * 1024 * 1024;

/** How often the job status is polled while a job is running. */
export const POLL_INTERVAL_MS = 1500;

/** Empty in production: the API is served from the same origin as the frontend. */
export const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL ?? "").replace(/\/$/, "");
