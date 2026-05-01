"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

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

export default function DashboardPage() {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    async function load() {
      try {
        const data = await api.listJobs();
        if (active) setJobs(data);
      } catch (err: unknown) {
        const m = err instanceof Error ? err.message : "Failed to load jobs";
        if (active) setError(m);
      } finally {
        if (active) setLoading(false);
      }
    }
    load();
    const id = setInterval(load, 5000);
    return () => {
      active = false;
      clearInterval(id);
    };
  }, []);

  return (
    <div className="pt-8">
      <h1 className="mb-1 text-2xl font-bold">Dashboard</h1>
      <p className="text-sm text-white/60">Daftar pekerjaan auto-clip dan AI video.</p>

      {error && (
        <p className="mt-4 rounded-md border border-red-400/40 bg-red-500/10 p-2 text-sm text-red-300">
          {error}
        </p>
      )}

      {loading ? (
        <p className="mt-6 text-sm text-white/40">Memuat…</p>
      ) : jobs.length === 0 ? (
        <p className="mt-6 text-sm text-white/40">
          Belum ada pekerjaan. Buat dari halaman utama.
        </p>
      ) : (
        <div className="mt-6 space-y-2">
          {jobs.map((job) => (
            <Link
              key={job.id}
              href={`/jobs/${job.id}`}
              className="flex items-center gap-4 rounded-xl border border-white/10 bg-white/[0.03] p-3 hover:bg-white/[0.06]"
            >
              <div className="flex h-14 w-24 shrink-0 items-center justify-center overflow-hidden rounded-lg bg-black">
                {job.source_thumbnail ? (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img
                    src={job.source_thumbnail}
                    alt=""
                    className="h-full w-full object-cover"
                  />
                ) : (
                  <span className="text-[10px] text-white/30">no thumb</span>
                )}
              </div>
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2">
                  <Badge tone={STATUS_TONE[job.status]}>{job.status}</Badge>
                  <span className="text-[11px] text-white/40">
                    {formatRelativeTime(job.created_at)}
                  </span>
                </div>
                <p className="mt-1 truncate text-sm text-white">
                  {job.source_title || job.source_url || job.id}
                </p>
                <p className="text-[11px] text-white/40">
                  {job.clips.length} klip • durasi sumber {formatDuration(job.source_duration)}
                </p>
              </div>
              <div className="hidden w-32 sm:block">
                <div className="h-1.5 w-full rounded-full bg-white/10">
                  <div
                    className="h-1.5 rounded-full bg-brand-400 transition-all"
                    style={{ width: `${Math.min(100, job.progress)}%` }}
                  />
                </div>
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
