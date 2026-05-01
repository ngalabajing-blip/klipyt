import "./globals.css";

import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = {
  title: "Mager Klip — Konten mulus, effort minus",
  description:
    "Satu video panjang, puluhan klip viral. Auto-clip, auto-subtitle, AI voice hook, dan dubbing multi-bahasa — powered by Xiaomi MiMo."
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="id" className="dark">
      <body className="min-h-screen bg-radial">
        <div className="mx-auto flex min-h-screen max-w-6xl flex-col px-4 sm:px-6">
          <header className="flex items-center justify-between py-5">
            <Link href="/" className="flex items-center gap-2">
              <span className="grid h-8 w-8 place-content-center rounded-xl bg-gradient-to-br from-brand-300 to-brand-600 text-base font-black text-black">
                M
              </span>
              <span className="text-base font-semibold tracking-tight">
                Mager Klip
              </span>
              <span className="hidden rounded-md bg-white/10 px-2 py-0.5 text-[10px] uppercase tracking-wide text-white/60 sm:inline">
                v0.1
              </span>
            </Link>
            <nav className="flex items-center gap-3 text-sm">
              <Link
                href="/dashboard"
                className="rounded-lg px-3 py-1.5 text-white/70 hover:bg-white/10 hover:text-white"
              >
                Dashboard
              </Link>
              <Link
                href="https://github.com/sikirujak"
                target="_blank"
                className="rounded-lg border border-white/15 px-3 py-1.5 text-white/80 hover:bg-white/10"
              >
                GitHub
              </Link>
            </nav>
          </header>

          <main className="flex-1 pb-20">{children}</main>

          <footer className="border-t border-white/5 py-6 text-center text-xs text-white/40">
            Powered by{" "}
            <a
              href="https://mimo.xiaomi.com"
              className="text-brand-300 hover:underline"
              target="_blank"
              rel="noreferrer"
            >
              Xiaomi MiMo
            </a>
            . Open source MIT.
          </footer>
        </div>
      </body>
    </html>
  );
}
