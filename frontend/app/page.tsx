import { auth } from "@clerk/nextjs/server";
import Link from "next/link";
import Image from "next/image";
import { redirect } from "next/navigation";

export default async function Home() {
  const { userId } = await auth();
  if (userId) redirect("/app");

  return (
    <main className="min-h-screen bg-black text-white">
      <div className="relative min-h-screen overflow-hidden bg-black">
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
            <div className="flex items-center gap-3">
              <Link
                href="/app"
                className="rounded-full border border-emerald-500/50 px-4 py-2 text-xs font-semibold text-emerald-200 hover:border-emerald-400 hover:text-white transition-colors"
              >
                Dashboard
              </Link>
              <Link
                href="/auth/sign-in?allow=1"
                className="rounded-full border border-zinc-700 px-4 py-2 text-xs font-semibold text-zinc-200 hover:border-zinc-500 transition-colors"
              >
                Sign in
              </Link>
            </div>
          </header>

          <section className="mx-auto mt-20 max-w-3xl text-center">
            <h1 className="text-4xl md:text-6xl font-semibold tracking-tight">
              Cursor for Product Management
            </h1>
            <p className="mt-4 text-sm md:text-base text-zinc-400">
              Build on live product signals across support, analytics, delivery, and
              customer interviews. Launch insights, decisions, and prototypes in one
              place.
            </p>

            <div className="mt-8 flex flex-col sm:flex-row items-center justify-center gap-3">
              <Link
                href="/app"
                className="rounded-full bg-emerald-500 px-6 py-3 text-sm font-semibold text-black hover:bg-emerald-400 transition-colors"
              >
                Open workspace
              </Link>
              <Link
                href="/auth/sign-up?allow=1"
                className="rounded-full bg-emerald-500 px-6 py-3 text-sm font-semibold text-black hover:bg-emerald-400 transition-colors"
              >
                Start free
              </Link>
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
        </div>
      </div>
    </main>
  );
}
