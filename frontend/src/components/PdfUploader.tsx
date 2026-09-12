import { useId, useRef, useState, type ChangeEvent, type DragEvent } from "react";

import { MAX_PDF_SIZE_BYTES, MAX_PDF_SIZE_MB } from "../config";
import { formatBytes } from "../utils/format";

interface PdfUploaderProps {
  file: File | null;
  disabled?: boolean;
  onSelect: (file: File | null) => void;
  onError: (message: string) => void;
}

export function PdfUploader({ file, disabled = false, onSelect, onError }: PdfUploaderProps) {
  const inputId = useId();
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);

  const accept = (candidate: File | undefined) => {
    if (!candidate) return;
    const problem = validate(candidate);
    if (problem) {
      onError(problem);
      return;
    }
    onSelect(candidate);
  };

  const handleChange = (event: ChangeEvent<HTMLInputElement>) => {
    accept(event.target.files?.[0]);
    event.target.value = ""; // allow re-selecting the same file
  };

  const handleDrop = (event: DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    setDragging(false);
    if (disabled) return;
    accept(event.dataTransfer.files[0]);
  };

  const handleDragOver = (event: DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    if (!disabled) setDragging(true);
  };

  if (file) {
    return (
      <div className="file-card">
        <span className="file-icon" aria-hidden="true">
          📄
        </span>
        <div className="file-details">
          <span className="file-name">{file.name}</span>
          <span className="file-size">{formatBytes(file.size)}</span>
        </div>
        {!disabled && (
          <button type="button" className="icon-button" onClick={() => onSelect(null)} aria-label="Remove file">
            ✕
          </button>
        )}
      </div>
    );
  }

  return (
    <div
      className={`dropzone${dragging ? " dropzone--active" : ""}${disabled ? " dropzone--disabled" : ""}`}
      onDrop={handleDrop}
      onDragOver={handleDragOver}
      onDragLeave={() => setDragging(false)}
      onClick={() => inputRef.current?.click()}
      role="button"
      tabIndex={0}
      onKeyDown={(event) => {
        if (event.key === "Enter" || event.key === " ") inputRef.current?.click();
      }}
    >
      <p className="dropzone-title">Drop your PDF here</p>
      <p className="dropzone-hint">
        or <label htmlFor={inputId}>select a file</label>
      </p>
      <p className="dropzone-limit">PDF only · up to {MAX_PDF_SIZE_MB} MB</p>
      <input
        ref={inputRef}
        id={inputId}
        type="file"
        accept=".pdf,application/pdf"
        onChange={handleChange}
        disabled={disabled}
        hidden
      />
    </div>
  );
}

function validate(file: File): string | null {
  if (!file.name.toLowerCase().endsWith(".pdf")) return "Only .pdf files are accepted.";
  if (file.size === 0) return "This file is empty.";
  if (file.size > MAX_PDF_SIZE_BYTES) return `The file exceeds the ${MAX_PDF_SIZE_MB} MB limit.`;
  return null;
}
