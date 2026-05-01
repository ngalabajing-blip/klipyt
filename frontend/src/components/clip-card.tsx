"use client";

import { Download, Play } from "lucide-react";
import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import type { Clip } from "@/lib/api";
import { formatDuration } from "@/lib/utils";

export function ClipCard({ clip }: { clip: Clip }) {
  const [playing, setPlaying] = useState(false);
  return (
    <div className="group flex flex-col gap-3 rounded-2xl border border-white/10 bg-white/[0.04] p-3 transition hover:border-brand-400/40 hover:bg-white/[0.06]">
      <div className="relative aspect-[9/16] w-full overflow-hidden rounded-xl bg-black">
        {playing && clip.object_key ? (
          <video
            autoPlay
            controls
            src={clip.object_key}
            poster={clip.thumbnail_object_key ?? undefined}
            className="h-full w-full"
          />
        ) : (
          <>
            {clip.thumbnail_object_key ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img
                src={clip.thumbnail_object_key}
                alt={clip.title}
                className="h-full w-full object-cover"
              />
            ) : (
              <div className="flex h-full w-full items-center justify-center text-sm text-white/30">
                no preview
              </div>
            )}
            <button
              onClick={() => setPlaying(true)}
              className="absolute inset-0 flex items-center justify-center bg-black/30 opacity-0 transition group-hover:opacity-100"
            >
              <span className="flex h-12 w-12 items-center justify-center rounded-full bg-white/20 backdrop-blur">
                <Play className="ml-0.5 h-5 w-5 text-white" />
              </span>
            </button>
            <div className="absolute right-2 top-2 flex flex-col items-end gap-1">
              <Badge tone="brand">★ {clip.score.toFixed(1)}</Badge>
              {clip.has_voice_hook && <Badge tone="warning">Voice Hook</Badge>}
            </div>
            <div className="absolute bottom-2 left-2">
              <Badge>{formatDuration(clip.duration)}</Badge>
            </div>
          </>
        )}
      </div>
      <div>
        <h4 className="line-clamp-2 text-sm font-semibold text-white">{clip.title}</h4>
        {clip.caption && (
          <p className="mt-1 line-clamp-2 text-xs text-white/60">{clip.caption}</p>
        )}
        {clip.hashtags_json && clip.hashtags_json.length > 0 && (
          <div className="mt-2 flex flex-wrap gap-1">
            {clip.hashtags_json.slice(0, 5).map((h) => (
              <span
                key={h}
                className="rounded bg-white/10 px-1.5 py-0.5 text-[10px] text-white/70"
              >
                #{h}
              </span>
            ))}
          </div>
        )}
        <div className="mt-3 flex items-center gap-2">
          {clip.object_key && (
            <a
              href={clip.object_key}
              download
              className="inline-flex items-center gap-1.5 rounded-xl border border-white/15 bg-transparent px-3 py-1.5 text-xs text-white hover:bg-white/10"
            >
              <Download className="h-3.5 w-3.5" /> Unduh
            </a>
          )}
        </div>
      </div>
    </div>
  );
}
