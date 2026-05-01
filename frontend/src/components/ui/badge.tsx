import * as React from "react";

import { cn } from "@/lib/utils";

interface BadgeProps extends React.HTMLAttributes<HTMLSpanElement> {
  tone?: "default" | "success" | "warning" | "danger" | "brand";
}

export function Badge({ className, tone = "default", ...props }: BadgeProps) {
  const map: Record<string, string> = {
    default: "bg-white/10 text-white/80",
    success: "bg-emerald-500/20 text-emerald-300",
    warning: "bg-amber-500/20 text-amber-300",
    danger: "bg-red-500/20 text-red-300",
    brand: "bg-brand-500/20 text-brand-300"
  };
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-md px-2 py-0.5 text-[11px] font-medium uppercase tracking-wide",
        map[tone],
        className
      )}
      {...props}
    />
  );
}
