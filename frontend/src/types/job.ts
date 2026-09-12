export type Language = "fr" | "en";

export const LANGUAGES: { code: Language; label: string }[] = [
  { code: "fr", label: "🇫🇷 Français" },
  { code: "en", label: "🇬🇧 English" },
];

export type JobStatus =
  | "queued"
  | "extracting"
  | "cleaning"
  | "generating_audio"
  | "assembling"
  | "completed"
  | "failed";

export interface Job {
  id: string;
  status: JobStatus;
  progress: number;
  message: string;
  filename: string;
  language: Language;
  created_at: string;
  audio_url: string | null;
  error: string | null;
}

export interface JobCreated {
  id: string;
  status: JobStatus;
}

export function isFinished(status: JobStatus): boolean {
  return status === "completed" || status === "failed";
}
