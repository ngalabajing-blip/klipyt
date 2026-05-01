import { AIVideoTabs } from "@/components/ai-video-tabs";
import { SourceInput } from "@/components/source-input";

export default function HomePage() {
  return (
    <div>
      <section className="pt-12 text-center sm:pt-20">
        <div className="mx-auto mb-6 grid h-16 w-16 place-content-center rounded-full bg-gradient-to-br from-brand-300 via-brand-500 to-brand-700 shadow-[0_0_60px_rgba(245,158,11,0.45)]">
          <span className="text-3xl font-black text-black">M</span>
        </div>
        <h1 className="text-3xl font-black tracking-tight text-white sm:text-5xl">
          Satu Video, <span className="text-brand-400">Puluhan Klip Viral!</span>
        </h1>
        <p className="mx-auto mt-3 max-w-xl text-sm text-white/60 sm:text-base">
          Tempelkan link YouTube/TikTok atau upload video — kami akan deteksi momen
          paling viral, potong vertikal 9:16, tambahkan subtitle karaoke, dan opsional
          generate hook AI dengan suara kreator sendiri.
        </p>
        <div className="mt-8">
          <SourceInput />
        </div>
      </section>

      <AIVideoTabs />

      <section className="mt-12 grid gap-3 sm:grid-cols-3">
        {[
          {
            title: "AI Highlight Detection",
            body: "MiMo V2.5-Pro membaca transkrip & mendeteksi 6-10 momen paling viral dari video panjangmu."
          },
          {
            title: "Karaoke Subtitle",
            body: "Subtitle word-level dengan highlight kata-per-kata, gaya MrBeast / Hormozi siap-viral."
          },
          {
            title: "AI Voice Hook",
            body: "Clone suara kreator (V2.5-TTS-VoiceClone) — tambah hook 3 detik untuk maksimalkan retention."
          }
        ].map((f) => (
          <div
            key={f.title}
            className="rounded-2xl border border-white/10 bg-white/[0.03] p-4"
          >
            <h3 className="text-sm font-semibold text-white">{f.title}</h3>
            <p className="mt-1 text-xs text-white/60">{f.body}</p>
          </div>
        ))}
      </section>
    </div>
  );
}
