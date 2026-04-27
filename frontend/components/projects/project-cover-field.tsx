"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { ImageIcon, Upload, X } from "lucide-react";

import { cn, formatFileSize } from "@/lib/utils";
import { Button } from "@/components/ui/button";

const MAX_BYTES = 8 * 1024 * 1024;
const ACCEPT = "image/jpeg,image/png,image/webp";

function isAllowedImage(f: File): boolean {
  const t = f.type.toLowerCase();
  return t === "image/jpeg" || t === "image/png" || t === "image/webp";
}

interface ProjectCoverFieldProps {
  file: File | null;
  onFile: (file: File | null) => void;
  /** When set and `file` is null, show this image with a replace action (edit project flow). */
  existingCoverUrl?: string | null;
  disabled?: boolean;
}

export function ProjectCoverField({
  file,
  onFile,
  existingCoverUrl = null,
  disabled = false,
}: ProjectCoverFieldProps) {
  const [dragActive, setDragActive] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (!file) {
      setPreviewUrl(null);
      return;
    }
    const url = URL.createObjectURL(file);
    setPreviewUrl(url);
    return () => URL.revokeObjectURL(url);
  }, [file]);

  const handleFiles = useCallback(
    (files: FileList | null) => {
      if (!files || files.length === 0) return;
      const f = files[0];
      if (!isAllowedImage(f)) {
        setError("Use JPEG, PNG, or WebP");
        return;
      }
      if (f.size > MAX_BYTES) {
        setError("Image must be 8 MB or smaller");
        return;
      }
      setError(null);
      onFile(f);
    },
    [onFile]
  );

  return (
    <div className="flex flex-col gap-2">
      {file && previewUrl ? (
        <div className="relative overflow-hidden rounded-md border border-border bg-muted">
          {/* eslint-disable-next-line @next/next/no-img-element -- local object URL */}
          <img
            src={previewUrl}
            alt=""
            className="aspect-[4/3] w-full object-cover"
          />
          <div className="absolute inset-x-0 bottom-0 flex items-center justify-between gap-2 bg-gradient-to-t from-black/70 to-transparent px-2 pb-2 pt-8">
            <span className="truncate text-[10px] text-white/90">
              {file.name} · {formatFileSize(file.size)}
            </span>
            <Button
              type="button"
              variant="secondary"
              size="icon-sm"
              className="shrink-0 bg-background/90"
              onClick={() => onFile(null)}
              disabled={disabled}
              aria-label="Remove image"
            >
              <X className="h-4 w-4" />
            </Button>
          </div>
        </div>
      ) : existingCoverUrl ? (
        <div className="relative overflow-hidden rounded-md border border-border bg-muted">
          {/* eslint-disable-next-line @next/next/no-img-element -- signed URL from API */}
          <img
            src={existingCoverUrl}
            alt=""
            className="aspect-[4/3] w-full object-cover"
          />
          <div className="absolute inset-x-0 bottom-0 flex flex-wrap items-center justify-between gap-2 bg-gradient-to-t from-black/70 to-transparent px-2 pb-2 pt-8">
            <span className="text-[10px] text-white/90">Current cover</span>
            <Button
              type="button"
              variant="secondary"
              size="sm"
              className="shrink-0 bg-background/90 text-xs"
              onClick={() => inputRef.current?.click()}
              disabled={disabled}
            >
              <Upload className="mr-1.5 h-3.5 w-3.5" aria-hidden />
              Replace image
            </Button>
          </div>
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
            "flex aspect-[4/3] w-full flex-col items-center justify-center gap-2 rounded-md border border-dashed border-border bg-card/40 px-4 text-center text-xs text-muted-foreground transition-colors",
            dragActive && "border-primary/50 bg-primary/5",
            !disabled && "hover:border-primary/40 hover:bg-surface-overlay"
          )}
        >
          <ImageIcon className="h-8 w-8 opacity-50" aria-hidden />
          <span className="flex items-center gap-1 font-medium text-foreground/90">
            <Upload className="h-3.5 w-3.5" aria-hidden />
            Drop an image or click to browse
          </span>
          <span className="text-[10px]">JPEG, PNG, or WebP · max 8 MB</span>
        </button>
      )}
      <input
        ref={inputRef}
        type="file"
        accept={ACCEPT}
        className="sr-only"
        disabled={disabled}
        onChange={(e) => {
          handleFiles(e.target.files);
          e.target.value = "";
        }}
      />
      {error && (
        <p className="text-xs text-destructive" role="alert">
          {error}
        </p>
      )}
    </div>
  );
}
