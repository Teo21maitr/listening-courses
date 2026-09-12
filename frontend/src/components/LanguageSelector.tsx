import { LANGUAGES, type Language } from "../types/job";

interface LanguageSelectorProps {
  value: Language | null;
  disabled?: boolean;
  onChange: (language: Language) => void;
}

export function LanguageSelector({ value, disabled = false, onChange }: LanguageSelectorProps) {
  return (
    <fieldset className="language-selector" disabled={disabled}>
      <legend className="section-label">Document language</legend>
      <div className="segmented" role="radiogroup" aria-label="Document language">
        {LANGUAGES.map(({ code, label }) => (
          <button
            key={code}
            type="button"
            role="radio"
            aria-checked={value === code}
            className={`segment${value === code ? " segment--selected" : ""}`}
            onClick={() => onChange(code)}
          >
            {label}
          </button>
        ))}
      </div>
    </fieldset>
  );
}
