import { useState } from "react";

import { ApiError, audioUrl, createJob } from "./api/jobs";
import { AudioPlayer } from "./components/AudioPlayer";
import { LanguageSelector } from "./components/LanguageSelector";
import { PdfUploader } from "./components/PdfUploader";
import { Progress } from "./components/Progress";
import { useJobPolling } from "./hooks/useJobPolling";
import type { Job, Language } from "./types/job";

type Phase =
  | { kind: "idle" }
  | { kind: "uploading" }
  | { kind: "processing"; jobId: string }
  | { kind: "failed"; message: string };

type View = Phase | { kind: "completed"; job: Job };

export default function App() {
  const [file, setFile] = useState<File | null>(null);
  const [language, setLanguage] = useState<Language | null>(null);
  const [phase, setPhase] = useState<Phase>({ kind: "idle" });
  const [notice, setNotice] = useState<string | null>(null);

  const jobId = phase.kind === "processing" ? phase.jobId : null;
  const { job, error: pollingError } = useJobPolling(jobId);
  const view = deriveView(phase, job, pollingError);

  // Inputs are locked as soon as a job starts; "Convert another PDF" unlocks them.
  const locked = view.kind !== "idle";
  const canGenerate = file !== null && language !== null && !locked;

  const generate = async () => {
    if (!file || !language) return;
    setNotice(null);
    setPhase({ kind: "uploading" });
    try {
      const created = await createJob(file, language);
      setPhase({ kind: "processing", jobId: created.id });
    } catch (caught) {
      const message = caught instanceof ApiError ? caught.message : "Upload failed.";
      setPhase({ kind: "failed", message });
    }
  };

  const reset = () => {
    setPhase({ kind: "idle" });
    setNotice(null);
    setFile(null);
    setLanguage(null);
  };

  return (
    <main className="app">
      <header className="app-header">
        <h1>PDF to Audio</h1>
        <p className="tagline">Turn a PDF into an audiobook locally.</p>
      </header>

      <section className="card">
        <PdfUploader
          file={file}
          disabled={locked}
          onSelect={(selected) => {
            setNotice(null);
            setFile(selected);
          }}
          onError={setNotice}
        />

        <LanguageSelector value={language} disabled={locked} onChange={setLanguage} />

        {notice && (
          <p className="notice" role="alert">
            {notice}
          </p>
        )}

        {view.kind === "idle" && (
          <button type="button" className="button button--primary" disabled={!canGenerate} onClick={generate}>
            Generate audiobook
          </button>
        )}

        {view.kind === "uploading" && <Progress progress={0} message="Uploading PDF…" />}

        {view.kind === "processing" && (
          <Progress progress={job?.progress ?? 0} message={job?.message ?? "Queued…"} />
        )}

        {view.kind === "completed" && (
          <>
            <AudioPlayer src={audioUrl(view.job) ?? ""} downloadName={downloadName(view.job)} />
            <button type="button" className="button button--ghost" onClick={reset}>
              Convert another PDF
            </button>
          </>
        )}

        {view.kind === "failed" && (
          <>
            <div className="error" role="alert">
              <p className="error-title">Something went wrong</p>
              <p className="error-message">{view.message}</p>
            </div>
            <button type="button" className="button button--primary" onClick={() => setPhase({ kind: "idle" })}>
              Try again
            </button>
          </>
        )}
      </section>

      <footer className="app-footer">
        Text extraction with PyMuPDF · Voices by Piper TTS · No cloud API involved.
      </footer>
    </main>
  );
}

/** The job outcome is derived from polling instead of being copied into state. */
function deriveView(phase: Phase, job: Job | null, pollingError: string | null): View {
  if (phase.kind !== "processing") return phase;
  if (pollingError) return { kind: "failed", message: pollingError };
  if (job?.status === "completed") return { kind: "completed", job };
  if (job?.status === "failed") return { kind: "failed", message: job.error ?? "The generation failed." };
  return phase;
}

function downloadName(job: Job): string {
  const stem = job.filename.replace(/\.pdf$/i, "").replace(/[^A-Za-z0-9._-]+/g, "_");
  return `${stem || "document"}_audio_${job.language}.mp3`;
}
