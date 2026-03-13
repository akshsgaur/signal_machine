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
              <div className="h-10 w-10 flex items-center justify-center overflow-hidden">
                <Image src="/logo2.png" alt="Signal logo" width={44} height={44} />
              </div>
              <div>
                <p className="text-sm uppercase tracking-[0.28em] text-white font-normal">
                  Signal
                </p>
              </div>
            </div>
            <div className="flex items-center gap-3">
              <Link
                href="/auth/sign-in?allow=1"
                className="rounded-full border border-zinc-700 px-4 py-2 text-xs font-normal text-white hover:border-zinc-500 transition-colors"
              >
                Sign in
              </Link>
            </div>
          </header>

          <section className="mx-auto mt-24 max-w-4xl text-center">
            <h1 className="text-5xl md:text-7xl font-normal tracking-[-0.05em] leading-[0.95]">
              The Platform for Next-Gen Product Managers
            </h1>
            <p className="mx-auto mt-8 max-w-3xl text-lg font-normal tracking-[-0.03em] leading-snug text-white md:text-xl">
              Turn support, analytics, delivery, and customer interviews into
              product decisions and prototypes.
            </p>

            <div className="mt-12 flex flex-col sm:flex-row items-center justify-center gap-3">
              <Link
                href="/auth/sign-up?allow=1"
                className="rounded-full bg-emerald-500 px-6 py-3 text-sm font-normal text-black hover:bg-emerald-400 transition-colors"
              >
                Try Signal
              </Link>
            </div>
          </section>

          <section className="mt-24 grid grid-cols-1 gap-5 md:grid-cols-3">
            {[
              {
                title: "Live workspace",
                body: "Run deep analysis across your tools and get one unified narrative.",
              },
              {
                title: "Customer insights",
                body: "Upload interviews, bucket feedback, and query product signals by theme.",
              },
              {
                title: "Decision support",
                body: "Turn signals into specs, priorities, and prototype-ready outputs.",
              },
            ].map((item) => (
              <div
                key={item.title}
                className="rounded-2xl border border-zinc-900 bg-zinc-950/70 p-5 text-left"
              >
                <h3 className="text-lg font-normal tracking-[-0.03em] text-white">
                  {item.title}
                </h3>
                <p className="mt-3 text-sm font-normal tracking-[-0.02em] leading-6 text-white">
                  {item.body}
                </p>
              </div>
            ))}
          </section>
        </div>
      </div>
    </main>
  );
}
