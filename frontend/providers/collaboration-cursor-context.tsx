"use client";

import { createContext, useContext } from "react";
import type { PdfPoint } from "@/components/plan-viewer/plan-pdf-canvas";

export const SetCollaborationPdfCursorContext = createContext<
  ((pt: PdfPoint | null) => void) | null
>(null);

export function useSetCollaborationPdfCursor(): ((pt: PdfPoint | null) => void) | null {
  return useContext(SetCollaborationPdfCursorContext);
}
