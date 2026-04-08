import { AlertTriangle, FileText, UploadCloud } from "lucide-react";
import {
  type ChangeEvent,
  type DragEvent,
  type KeyboardEvent,
  useCallback,
  useEffect,
  useRef,
  useState,
} from "react";
import { cn } from "@/lib/cn";
import { formatFileSize } from "@/lib/format";

interface FileDropZoneProps {
  accept: string;
  onFile: (file: File) => void;
  disabled?: boolean;
  currentFile: File | null;
  maxSizeBytes?: number;
}

export function FileDropZone({
  accept,
  onFile,
  disabled = false,
  currentFile,
  maxSizeBytes,
}: FileDropZoneProps) {
  const [isDragOver, setIsDragOver] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const validateFile = useCallback(
    (file: File): string | null => {
      if (!file.name.toLowerCase().endsWith(accept)) {
        return `Only ${accept} files are accepted`;
      }
      if (file.size === 0) {
        return "File is empty";
      }
      if (maxSizeBytes !== undefined && file.size > maxSizeBytes) {
        return `File is too large (${formatFileSize(file.size)}). Maximum size is ${formatFileSize(maxSizeBytes)}.`;
      }
      return null;
    },
    [accept, maxSizeBytes],
  );

  useEffect(() => {
    if (currentFile === null) setError(null);
  }, [currentFile]);
  const dragCounterRef = useRef(0);
  const inputRef = useRef<HTMLInputElement>(null);

  function handleDragEnter(e: DragEvent<HTMLLabelElement>) {
    e.preventDefault();
    e.stopPropagation();
    if (disabled) return;
    dragCounterRef.current++;
    if (dragCounterRef.current === 1) setIsDragOver(true);
  }

  function handleDragLeave(e: DragEvent<HTMLLabelElement>) {
    e.preventDefault();
    e.stopPropagation();
    dragCounterRef.current--;
    if (dragCounterRef.current === 0) setIsDragOver(false);
  }

  function handleDragOver(e: DragEvent<HTMLLabelElement>) {
    e.preventDefault();
    e.dataTransfer.dropEffect = disabled ? "none" : "copy";
  }

  function handleDrop(e: DragEvent<HTMLLabelElement>) {
    e.preventDefault();
    e.stopPropagation();
    dragCounterRef.current = 0;
    setIsDragOver(false);
    if (disabled) return;
    const file = e.dataTransfer.files[0];
    if (!file) return;
    const validationError = validateFile(file);
    if (validationError) {
      setError(validationError);
      return;
    }
    setError(null);
    onFile(file);
  }

  function handleChange(e: ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (file) {
      const validationError = validateFile(file);
      if (validationError) {
        setError(validationError);
        e.target.value = "";
        return;
      }
      setError(null);
      onFile(file);
    }
    e.target.value = "";
  }

  function handleKeyDown(e: KeyboardEvent<HTMLLabelElement>) {
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      inputRef.current?.click();
    }
  }

  const baseClasses =
    "flex min-h-32 cursor-pointer flex-col items-center justify-center gap-3 rounded-xl px-6 py-8 transition-colors";
  const disabledClasses = disabled ? "opacity-50 cursor-not-allowed" : "";

  let stateClasses: string;
  if (isDragOver && !disabled) {
    stateClasses = "border-2 border-dashed border-primary bg-accent";
  } else if (currentFile) {
    stateClasses = "border-2 border-solid border-input bg-card";
  } else {
    stateClasses =
      "border-2 border-dashed border-border bg-card hover:bg-muted/50";
  }

  return (
    <div>
      <label
        onDragEnter={handleDragEnter}
        onDragLeave={handleDragLeave}
        onDragOver={handleDragOver}
        onDrop={handleDrop}
        onKeyDown={handleKeyDown}
        tabIndex={disabled ? -1 : 0}
        aria-describedby={currentFile ? undefined : "dropzone-help"}
        className={cn(baseClasses, stateClasses, disabledClasses)}
      >
        <input
          type="file"
          accept={accept}
          onChange={handleChange}
          ref={inputRef}
          disabled={disabled}
          className="sr-only"
          tabIndex={-1}
          aria-hidden="true"
        />

        {currentFile ? (
          <>
            <FileText className="size-6 text-primary" />
            <div className="flex flex-col items-center gap-0.5">
              <span className="max-w-[20rem] truncate text-sm font-medium text-foreground">
                {currentFile.name}
              </span>
              <span className="text-xs text-muted-foreground tabular-nums">
                {formatFileSize(currentFile.size)}
              </span>
            </div>
            <span className="text-xs text-primary hover:underline">
              Change file
            </span>
          </>
        ) : (
          <>
            <UploadCloud
              className={`size-8 text-muted-foreground transition-transform duration-200 ${isDragOver && !disabled ? "scale-110" : ""}`}
            />
            <span className="text-sm text-muted-foreground">
              Drop your CSV here, or click to browse
            </span>
            <span
              id="dropzone-help"
              className="text-xs text-muted-foreground/70"
            >
              {accept} files only
            </span>
          </>
        )}
      </label>

      {error && (
        <div
          role="alert"
          className="mt-2 flex items-center gap-1.5 rounded-lg border border-destructive-border bg-destructive-muted px-3 py-2 text-sm text-destructive-muted-foreground"
        >
          <AlertTriangle className="size-4 shrink-0" />
          {error}
        </div>
      )}
    </div>
  );
}
