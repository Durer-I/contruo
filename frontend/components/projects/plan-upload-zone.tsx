"use client";

import { useCallback, useRef, useState } from "react";
import { File as FileIcon, Upload, X } from "lucide-react";

import { cn, formatFileSize } from "@/lib/utils";
import { Button } from "@/components/ui/button";

const MAX_SIZE_BYTES = 200 * 1024 * 1024; // mirror backend MAX_PLAN_FILE_SIZE

interface PlanUploadZoneProps {
  file: File | null;
  onFile: (file: File | null) => void;
  disabled?: boolean;
}

export function PlanUploadZone({ file, onFile, disabled = false }: PlanUploadZoneProps) {
  const [dragActive, setDragActive] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const handleFiles = useCallback(
    (files: FileList | null) => {
      if (!files || files.length === 0) return;
      const f = files[0];
      if (!f.name.toLowerCase().endsWith(".pdf")) {
        setError("Only PDF files are supported");
        return;
      }
      if (f.size > MAX_SIZE_BYTES) {
        setError("File exceeds 200 MB limit");
        return;
      }
      setError(null);
      onFile(f);
    },
    [onFile]
  );

  return (
    <div className="flex flex-col gap-2">
      {file ? (
        <div className="flex items-center justify-between rounded-md border border-border bg-surface-overlay p-3">
          <div className="flex items-center gap-2">
            <FileIcon className="h-4 w-4 text-muted-foreground" />
            <div className="flex flex-col">
              <span className="text-sm font-medium">{file.name}</span>
              <span className="text-xs text-muted-foreground">
                {formatFileSize(file.size)}
              </span>
            </div>
          </div>
          <Button
            variant="ghost"
            size="icon-sm"
            type="button"
            onClick={() => onFile(null)}
            disabled={disabled}
            aria-label="Remove file"
          >
            <X className="h-4 w-4" />
          </Button>
        </div>
      ) : (
        <button
          type="button"
          disabled={disabled}
          onClick={() => inputRef.current?.click()}
          onDragOver={(e) => {
            e.preventDefault();
            if (!disabled) setDragActive(true);
          }}
          onDragLeave={() => setDragActive(false)}
          onDrop={(e) => {
            e.preventDefault();
            setDragActive(false);
            if (disabled) return;
            handleFiles(e.dataTransfer.files);
          }}
          className={cn(
            "flex flex-col items-center justify-center gap-2 rounded-md border border-dashed border-border bg-surface-overlay/50 px-4 py-6 text-center text-sm text-muted-foreground transition-colors",
            "hover:border-primary/60 hover:bg-surface-overlay hover:text-foreground",
            dragActive && "border-primary bg-primary/5 text-foreground",
            disabled && "cursor-not-allowed opacity-60"
          )}
        >
          <Upload className="h-5 w-5" />
          <span>
            <span className="text-foreground">Drop a PDF</span> or click to browse
          </span>
          <span className="text-xs">Up to 200 MB, vector PDFs recommended</span>
        </button>
      )}

      <input
        ref={inputRef}
        type="file"
        accept="application/pdf,.pdf"
        className="hidden"
        onChange={(e) => handleFiles(e.target.files)}
      />

      {error && (
        <p className="text-xs text-destructive">{error}</p>
      )}
    </div>
  );
}
