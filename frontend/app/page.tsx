"use client";

import Link from "next/link";
import Image from "next/image";
import { SignedIn, SignedOut, UserButton } from "@clerk/nextjs";

export default function Home() {
  return (
    <main className="min-h-screen bg-[#0B0B0B] text-white">
      <div className="relative overflow-hidden">
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_top,rgba(16,185,129,0.22),transparent_55%)]" />
        <div className="absolute inset-0 bg-[linear-gradient(180deg,rgba(9,9,9,0.9),rgba(4,4,4,1))]" />
        <div className="absolute inset-0 opacity-30 bg-[radial-gradient(rgba(255,255,255,0.08)_1px,transparent_1px)] [background-size:18px_18px]" />

        <div className="relative z-10 mx-auto max-w-6xl px-6 py-8">
          <header className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="h-10 w-10 rounded-xl flex items-center justify-center overflow-hidden">
                <Image src="/image.png" alt="Signal logo" width={44} height={44} />
              </div>
              <div>
                <p className="text-sm uppercase tracking-[0.28em] text-white font-semibold">
                  Signal
                </p>
                <p className="text-xs text-zinc-400">PM Intelligence Platform</p>
              </div>
            </div>
            <nav className="hidden md:flex items-center gap-8 text-sm text-zinc-400">
              <span className="hover:text-white transition-colors">Product</span>
              <span className="hover:text-white transition-colors">Developers</span>
              <span className="hover:text-white transition-colors">Solutions</span>
              <span className="hover:text-white transition-colors">Pricing</span>
              <span className="hover:text-white transition-colors">Docs</span>
            </nav>
            <div className="flex items-center gap-3">
              <SignedIn>
                <Link
                  href="/app"
                  className="rounded-full border border-emerald-500/50 px-4 py-2 text-xs font-semibold text-emerald-200 hover:border-emerald-400 hover:text-white transition-colors"
                >
                  Dashboard
                </Link>
                <UserButton afterSignOutUrl="/" />
              </SignedIn>
              <SignedOut>
                <Link
                  href="/auth/sign-in?allow=1"
                  className="rounded-full border border-zinc-700 px-4 py-2 text-xs font-semibold text-zinc-200 hover:border-zinc-500 transition-colors"
                >
                  Sign in
                </Link>
              </SignedOut>
            </div>
          </header>

          <section className="mx-auto mt-20 max-w-3xl text-center">
            <h1 className="text-4xl md:text-6xl font-semibold tracking-tight">
              Cursor for Product Manager
            </h1>
            <p className="mt-4 text-sm md:text-base text-zinc-400">
              Build on live product signals across support, analytics, delivery, and
              customer interviews. Launch insights, decisions, and prototypes in one
              place.
            </p>

            <div className="mt-8 flex flex-col sm:flex-row items-center justify-center gap-3">
              <SignedIn>
                <Link
                  href="/app"
                  className="rounded-full bg-emerald-500 px-6 py-3 text-sm font-semibold text-black hover:bg-emerald-400 transition-colors"
                >
                  Open workspace
                </Link>
              </SignedIn>
              <SignedOut>
                <Link
                  href="/auth/sign-up?allow=1"
                  className="rounded-full bg-emerald-500 px-6 py-3 text-sm font-semibold text-black hover:bg-emerald-400 transition-colors"
                >
                  Start free
                </Link>
              </SignedOut>
              <Link
                href="/connect"
                className="rounded-full border border-zinc-700 px-6 py-3 text-sm font-semibold text-zinc-200 hover:border-zinc-500 transition-colors"
              >
                Connect data
              </Link>
            </div>
          </section>

          <section className="mt-16 grid grid-cols-1 md:grid-cols-3 gap-4">
            {[
              {
                title: "Live workspace",
                body: "Run deep analysis across your integrations and get a single narrative.",
              },
              {
                title: "Customer insights",
                body: "Upload interviews, bucket feedback, and query by folder scope.",
              },
              {
                title: "Build with Claude Code",
                body: "Open a cloud IDE with terminal access and your preferred agent.",
              },
            ].map((item) => (
              <div
                key={item.title}
                className="rounded-2xl border border-zinc-900 bg-zinc-950/70 p-5 text-left"
              >
                <h3 className="text-sm font-semibold text-white">{item.title}</h3>
                <p className="mt-2 text-xs text-zinc-400">{item.body}</p>
              </div>
            ))}
          </section>

          <section className="mt-16 rounded-3xl border border-zinc-900 bg-gradient-to-br from-zinc-950 via-zinc-950 to-emerald-500/10 p-8">
            <div className="grid grid-cols-1 md:grid-cols-[1.2fr_1fr] gap-6 items-center">
              <div>
                <p className="text-xs uppercase tracking-[0.4em] text-emerald-400">
                  Unified intelligence
                </p>
                <h2 className="mt-3 text-2xl font-semibold">
                  Make product calls with evidence, not gut feel.
                </h2>
                <p className="mt-3 text-sm text-zinc-400">
                  Signal fuses Linear, Zendesk, Amplitude, Productboard, Slack, and
                  customer interviews into decision-ready briefs.
                </p>
              </div>
              <div className="rounded-2xl border border-zinc-800 bg-zinc-950/80 p-5">
                <div className="text-xs text-zinc-400">Latest signal</div>
                <div className="mt-2 text-sm text-white">
                  ⚡ Reliability issues in tool chain are blocking new integrations.
                </div>
                <div className="mt-4 flex items-center gap-2 text-xs text-zinc-500">
                  <span className="h-2 w-2 rounded-full bg-emerald-400" />
                  Updated just now
                </div>
              </div>
            </div>
          </section>

          <section className="mt-16 pb-16">
            <SignedOut>
              <div className="mx-auto max-w-3xl rounded-3xl border border-zinc-900 bg-zinc-950/70 p-6 text-center">
                <div className="text-sm font-semibold text-white">
                  Ready to launch your workspace?
                </div>
                <p className="mt-2 text-xs text-zinc-400">
                  Sign in to connect your product signals and start analyzing.
                </p>
                <div className="mt-4">
                  <Link
                    href="/auth/sign-in?allow=1"
                    className="inline-flex items-center justify-center rounded-full bg-emerald-500 px-5 py-2 text-xs font-semibold text-black hover:bg-emerald-400 transition-colors"
                  >
                    Sign in to continue
                  </Link>
                </div>
              </div>
            </SignedOut>
          </section>
        </div>
      </div>
    </main>
  );
}
