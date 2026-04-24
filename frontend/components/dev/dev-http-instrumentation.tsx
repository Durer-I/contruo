"use client";

import { useLayoutEffect } from "react";
import { installDevHttpInstrumentation } from "@/lib/dev-instrument-fetch";

/** Temporary: patches global fetch when NEXT_PUBLIC_DEBUG_HTTP=1. Safe no-op otherwise. */
export function DevHttpInstrumentation() {
  useLayoutEffect(() => {
    installDevHttpInstrumentation();
  }, []);
  return null;
}
