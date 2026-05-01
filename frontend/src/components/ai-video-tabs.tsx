"use client";

import { Loader2 } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { api, type AIVideoKind } from "@/lib/api";

const KINDS: { id: AIVideoKind; label: string; emoji: string; hint: string }[] = [
  {
    id: "educational",
    label: "Video Edukasi",
    emoji: "🎓",
    hint: "Topik penjelasan yang ingin dijelaskan singkat"
  },
  {
    id: "history",
    label: "Video Sejarah AI",
    emoji: "🏛",
    hint: "Peristiwa / tokoh sejarah yang ingin diceritakan"
  },
  {
    id: "satisfying",
    label: "Video Satisfying AI",
    emoji: "🍽",
    hint: "Aktivitas oddly-satisfying yang ingin dideskripsikan"
  },
  {
    id: "short_movie",
    label: "Short Movie AI",
    emoji: "🎬",
    hint: "Premis cerita singkat (genre, karakter, twist)"
  },
  {
    id: "character",
    label: "Character AI",
    emoji: "👻",
    hint: "Karakter yang ingin diberi monolog"
  }
];

export function AIVideoTabs() {
  const [active, setActive] = useState<AIVideoKind>("educational");
  const [prompt, setPrompt] = useState("");
  const [voice, setVoice] = useState("");
  const [language, setLanguage] = useState("id");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<{ url: string; title: string } | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function generate(e: React.FormEvent) {
    e.preventDefault();
    if (!prompt.trim()) return;
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const r = await api.generateAIVideo({
        kind: active,
        prompt,
        language,
        voice_description: voice || undefined
      });
      setResult({ url: r.video_url, title: r.title });
    } catch (err: unknown) {
      const m = err instanceof Error ? err.message : "Generation failed";
      setError(m);
    } finally {
      setLoading(false);
    }
  }

  const current = KINDS.find((k) => k.id === active)!;

  return (
    <section className="mt-12">
      <div className="mb-4 flex items-center gap-2">
        <h2 className="text-lg font-semibold text-white/90">Generate AI Lainnya</h2>
        <span className="rounded-md bg-white/10 px-2 py-0.5 text-[10px] uppercase tracking-wide text-white/60">
          beta
        </span>
      </div>
      <div className="mb-4 flex flex-wrap gap-2">
        {KINDS.map((k) => (
          <button
            key={k.id}
            onClick={() => setActive(k.id)}
            className={`rounded-xl border px-4 py-3 text-left transition ${
              active === k.id
                ? "border-brand-400/60 bg-brand-500/10 text-white"
                : "border-white/10 bg-white/5 text-white/70 hover:bg-white/10"
            }`}
          >
            <div className="text-xl">{k.emoji}</div>
            <div className="mt-1 text-sm font-medium">{k.label}</div>
          </button>
        ))}
      </div>

      <form onSubmit={generate} className="space-y-3">
        <Input
          placeholder={current.hint}
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          required
        />
        <div className="grid gap-3 sm:grid-cols-2">
          <Input
            placeholder="Voice persona (opsional, contoh: 'wanita muda, ceria, tempo cepat')"
            value={voice}
            onChange={(e) => setVoice(e.target.value)}
          />
          <select
            value={language}
            onChange={(e) => setLanguage(e.target.value)}
            className="h-12 w-full rounded-xl border border-white/10 bg-white/5 px-4 text-sm text-white"
          >
            <option value="id">Bahasa Indonesia</option>
            <option value="en">English</option>
            <option value="ms">Bahasa Melayu</option>
            <option value="es">Español</option>
            <option value="ja">日本語</option>
          </select>
        </div>
        <Button type="submit" size="lg" disabled={loading} className="w-full sm:w-auto">
          {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : `Generate ${current.label}`}
        </Button>
      </form>

      {error && (
        <p className="mt-3 rounded-md border border-red-400/40 bg-red-500/10 p-2 text-sm text-red-300">
          {error}
        </p>
      )}

      {result && (
        <div className="mt-6 rounded-2xl border border-white/10 bg-white/5 p-4">
          <h3 className="text-base font-semibold">{result.title}</h3>
          <video
            controls
            src={result.url}
            className="mt-3 aspect-[9/16] w-full max-w-xs rounded-xl bg-black"
          />
        </div>
      )}
    </section>
  );
}
