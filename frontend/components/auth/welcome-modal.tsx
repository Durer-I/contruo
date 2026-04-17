"use client";

import { useState } from "react";
import {
  Dialog,
  DialogContent,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Upload, Palette, Ruler, BarChart3 } from "lucide-react";

const DISMISSED_KEY = "contruo_welcome_dismissed";

const STEPS = [
  {
    icon: Upload,
    title: "Upload a plan",
    description: "Drop a PDF to start your takeoff",
  },
  {
    icon: Palette,
    title: "Create a condition",
    description: "Name it, pick a color, set the type",
  },
  {
    icon: Ruler,
    title: "Start measuring",
    description: "Use Linear, Area, or Count tools",
  },
  {
    icon: BarChart3,
    title: "Review quantities",
    description: "Your measurements appear in the panel",
  },
];

export function WelcomeModal() {
  const [state, setState] = useState({ synced: false, open: false });

  if (typeof window !== "undefined" && !state.synced) {
    const dismissed = localStorage.getItem(DISMISSED_KEY);
    setState({ synced: true, open: !dismissed });
  }

  const handleDismiss = () => {
    localStorage.setItem(DISMISSED_KEY, "true");
    setState((s) => ({ ...s, open: false }));
  };

  return (
    <Dialog open={state.open} onOpenChange={(isOpen) => !isOpen && handleDismiss()}>
      <DialogContent className="max-w-md">
        <DialogTitle className="text-xl font-semibold">
          Welcome to Contruo
        </DialogTitle>
        <DialogDescription className="text-muted-foreground">
          Get started in 4 steps:
        </DialogDescription>
        <div className="mt-4 space-y-4">
          {STEPS.map((step, i) => {
            const Icon = step.icon;
            return (
              <div key={step.title} className="flex items-start gap-3">
                <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-md bg-primary/10 text-primary">
                  <Icon className="h-4 w-4" />
                </div>
                <div>
                  <p className="text-sm font-medium">
                    {i + 1}. {step.title}
                  </p>
                  <p className="text-xs text-muted-foreground">
                    {step.description}
                  </p>
                </div>
              </div>
            );
          })}
        </div>
        <div className="mt-6 flex justify-end">
          <Button onClick={handleDismiss}>
            Got it, let&apos;s go &rarr;
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
