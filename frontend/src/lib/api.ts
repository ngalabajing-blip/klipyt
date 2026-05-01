// Tiny typed client around the backend API.

export type JobStatus =
  | "pending"
  | "downloading"
  | "transcribing"
  | "detecting"
  | "clipping"
  | "rendering"
  | "completed"
  | "failed";

export interface Clip {
  id: string;
  index: number;
  title: string;
  caption: string;
  hashtags_json: string[] | null;
  score: number;
  reason: string;
  start: number;
  end: number;
  duration: number;
  object_key: string | null;
  thumbnail_object_key: string | null;
  aspect_ratio: string;
  has_voice_hook: boolean;
  created_at: string;
}

export interface Job {
  id: string;
  kind: string;
  status: JobStatus;
  progress: number;
  source_url: string | null;
  source_title: string | null;
  source_thumbnail: string | null;
  source_duration: number | null;
  source_language: string | null;
  error_message: string | null;
  created_at: string;
  updated_at: string;
  clips: Clip[];
}

export type AIVideoKind =
  | "educational"
  | "history"
  | "satisfying"
  | "short_movie"
  | "character";

const BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "/api/backend";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers || {})
    },
    cache: "no-store",
    ...init
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`API ${res.status}: ${text}`);
  }
  return res.json() as Promise<T>;
}

export const api = {
  health: () => request<{ ok: boolean; version: string; mimo_models: string[] }>("/health"),

  createJob: (body: {
    source_url?: string;
    source_object_key?: string;
    target_clip_count?: number;
    enable_voice_hook?: boolean;
    enable_subtitles?: boolean;
  }) => request<Job>("/jobs", { method: "POST", body: JSON.stringify(body) }),

  listJobs: (limit = 50) => request<Job[]>(`/jobs?limit=${limit}`),

  getJob: (id: string) => request<Job>(`/jobs/${id}`),

  generateAIVideo: (body: {
    kind: AIVideoKind;
    prompt: string;
    language?: string;
    voice_description?: string;
  }) =>
    request<{
      job_id: string;
      title: string;
      video_url: string;
      beats: string[];
      voice_description: string;
    }>("/ai-videos/generate", { method: "POST", body: JSON.stringify(body) }),

  tts: (body: { text: string; voice_description?: string }) =>
    request<{ audio_b64: string; sample_rate: number }>(
      body.voice_description ? "/tts/voice-design" : "/tts/standard",
      { method: "POST", body: JSON.stringify(body) }
    ),

  voiceClone: (body: { text: string; reference_audio_b64: string }) =>
    request<{ audio_b64: string; sample_rate: number }>("/tts/voice-clone", {
      method: "POST",
      body: JSON.stringify(body)
    })
};
