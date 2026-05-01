"use client";

import { Loader2, Upload } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { api } from "@/lib/api";

export function SourceInput() {
  const router = useRouter();
  const [url, setUrl] = useState("");
  const [count, setCount] = useState(6);
  const [hook, setHook] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!url.trim()) return;
    setLoading(true);
    setError(null);
    try {
      const job = await api.createJob({
        source_url: url.trim(),
        target_clip_count: count,
        enable_voice_hook: hook
      });
      router.push(`/jobs/${job.id}`);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : "Failed to create job";
      setError(message);
    } finally {
      setLoading(false);
    }
  }

  async function uploadFile(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setLoading(true);
    setError(null);
    try {
      const form = new FormData();
      form.append("file", file);
      const base = process.env.NEXT_PUBLIC_API_BASE_URL || "/api/backend";
      const upRes = await fetch(`${base}/uploads/direct`, { method: "POST", body: form });
      if (!upRes.ok) throw new Error(`Upload failed (${upRes.status})`);
      const { key } = (await upRes.json()) as { key: string };
      const job = await api.createJob({
        source_object_key: key,
        target_clip_count: count,
        enable_voice_hook: hook
      });
      router.push(`/jobs/${job.id}`);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : "Upload failed";
      setError(message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <form onSubmit={submit} className="mx-auto w-full max-w-2xl space-y-3">
      <div className="flex flex-col gap-2 sm:flex-row">
        <Input
          type="url"
          placeholder="https://www.youtube.com/watch?v=..."
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          required
        />
        <Button type="submit" size="lg" disabled={loading || !url.trim()}>
          {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : "Buat Klip"}
        </Button>
      </div>

      <div className="flex items-center gap-3 text-xs text-white/60">
        <span className="opacity-60">atau</span>
        <label className="inline-flex cursor-pointer items-center gap-2 rounded-lg border border-white/10 bg-white/5 px-3 py-1.5 hover:bg-white/10">
          <Upload className="h-3.5 w-3.5" /> Upload Video
          <input
            type="file"
            accept="video/mp4,video/quicktime,video/webm,video/x-matroska"
            className="hidden"
            onChange={uploadFile}
          />
        </label>

        <div className="ml-auto flex items-center gap-3">
          <label className="flex items-center gap-2">
            <span className="opacity-70">Jumlah klip</span>
            <select
              value={count}
              onChange={(e) => setCount(Number(e.target.value))}
              className="rounded-md border border-white/10 bg-black/40 px-2 py-1 text-white"
            >
              {[3, 5, 6, 8, 10, 12].map((n) => (
                <option key={n} value={n}>
                  {n}
                </option>
              ))}
            </select>
          </label>
          <label className="flex items-center gap-2">
            <input
              type="checkbox"
              checked={hook}
              onChange={(e) => setHook(e.target.checked)}
              className="h-3.5 w-3.5 rounded border-white/30 bg-black/30"
            />
            AI Voice Hook
          </label>
        </div>
      </div>

      {error && (
        <p className="rounded-md border border-red-400/40 bg-red-500/10 p-2 text-sm text-red-300">
          {error}
        </p>
      )}
    </form>
  );
}
