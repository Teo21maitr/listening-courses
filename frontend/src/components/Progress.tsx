interface ProgressProps {
  progress: number;
  message: string;
}

export function Progress({ progress, message }: ProgressProps) {
  const value = Math.max(0, Math.min(100, Math.round(progress)));
  return (
    <div className="progress" aria-live="polite">
      <div className="progress-header">
        <span className="progress-title">Generating audiobook…</span>
        <span className="progress-percent">{value}%</span>
      </div>
      <div
        className="progress-track"
        role="progressbar"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={value}
      >
        <div className="progress-bar" style={{ width: `${value}%` }} />
      </div>
      <p className="progress-message">{message}</p>
    </div>
  );
}
