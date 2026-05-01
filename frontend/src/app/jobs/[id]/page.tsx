"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { ClipCard } from "@/components/clip-card";
import { Badge } from "@/components/ui/badge";
import { api, type Job, type JobStatus } from "@/lib/api";
import { formatDuration, formatRelativeTime } from "@/lib/utils";

const STATUS_TONE: Record<JobStatus, "default" | "success" | "warning" | "danger" | "brand"> = {
  pending: "default",
  downloading: "warning",
  transcribing: "warning",
  detecting: "warning",
  clipping: "warning",
  rendering: "warning",
  completed: "success",
  failed: "danger"
};

export default function JobDetailPage({ params }: { params: { id: string } }) {
  const [job, setJob] = useState<Job | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    async function load() {
      try {
        const data = await api.getJob(params.id);
        if (active) setJob(data);
      } catch (err: unknown) {
        const m = err instanceof Error ? err.message : "Failed to load job";
        if (active) setError(m);
      }
    }
    load();
    const interval = setInterval(load, 4000);
    return () => {
      active = false;
      clearInterval(interval);
    };
  }, [params.id]);

  if (error) {
    return (
      <div className="pt-12 text-center">
        <p className="text-red-300">{error}</p>
        <Link href="/dashboard" className="mt-4 text-sm text-brand-300 hover:underline">
          ← Back to dashboard
        </Link>
      </div>
    );
  }

  if (!job) {
    return <p className="pt-12 text-center text-white/50">Memuat…</p>;
  }

  const inProgress = !["completed", "failed"].includes(job.status);
  return (
    <div className="pt-8">
      <Link
        href="/dashboard"
        className="text-xs text-white/50 hover:text-white"
      >
        ← Dashboard
      </Link>
      <div className="mt-3 flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold">
            {job.source_title || "Auto-clip job"}
          </h1>
          <div className="mt-1 flex items-center gap-2 text-xs text-white/50">
            <Badge tone={STATUS_TONE[job.status]}>{job.status}</Badge>
            <span>{formatRelativeTime(job.created_at)}</span>
            <span>•</span>
            <span>{formatDuration(job.source_duration)} sumber</span>
            {job.source_language && (
              <>
                <span>•</span>
                <span>{job.source_language}</span>
              </>
            )}
          </div>
        </div>
        {job.source_url && (
          <a
            href={job.source_url}
            target="_blank"
            rel="noreferrer"
            className="text-xs text-white/40 hover:text-white"
          >
            Sumber asli ↗
          </a>
        )}
      </div>

      {inProgress && (
        <div className="mt-6 rounded-2xl border border-white/10 bg-white/[0.04] p-5">
          <p className="text-sm text-white/80">
            Memproses video — {job.status} ({job.progress}%)
          </p>
          <div className="mt-3 h-2 w-full overflow-hidden rounded-full bg-white/10">
            <div
              className="h-2 rounded-full bg-brand-400 transition-all"
              style={{ width: `${Math.min(100, job.progress)}%` }}
            />
          </div>
          <p className="mt-2 text-xs text-white/40">
            Halaman ini akan otomatis update setiap beberapa detik.
          </p>
        </div>
      )}

      {job.error_message && (
        <div className="mt-4 rounded-md border border-red-400/40 bg-red-500/10 p-3 text-sm text-red-300">
          {job.error_message}
        </div>
      )}

      {job.clips.length > 0 && (
        <section className="mt-8">
          <h2 className="mb-3 text-lg font-semibold">
            Klip ({job.clips.length})
          </h2>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {job.clips.map((clip) => (
              <ClipCard key={clip.id} clip={clip} />
            ))}
          </div>
        </section>
      )}
    </div>
  );
}
