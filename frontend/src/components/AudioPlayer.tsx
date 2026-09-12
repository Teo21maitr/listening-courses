interface AudioPlayerProps {
  src: string;
  downloadName: string;
}

export function AudioPlayer({ src, downloadName }: AudioPlayerProps) {
  return (
    <div className="audio-player">
      <p className="audio-title">Audio ready</p>
      <audio controls preload="metadata" src={src} className="audio-element">
        Your browser does not support the audio element.
      </audio>
      <a className="button button--secondary" href={src} download={downloadName}>
        Download MP3
      </a>
    </div>
  );
}
