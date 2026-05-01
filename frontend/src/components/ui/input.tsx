"use client";

import * as React from "react";

import { cn } from "@/lib/utils";

export const Input = React.forwardRef<
  HTMLInputElement,
  React.InputHTMLAttributes<HTMLInputElement>
>(({ className, ...props }, ref) => (
  <input
    ref={ref}
    className={cn(
      "h-12 w-full rounded-xl border border-white/10 bg-white/5 px-4 text-sm text-white placeholder:text-white/40 focus:border-brand-400/60 focus:outline-none focus:ring-2 focus:ring-brand-400/40",
      className
    )}
    {...props}
  />
));
Input.displayName = "Input";
