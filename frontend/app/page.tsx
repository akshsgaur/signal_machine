import Link from "next/link";
import { HypothesisForm } from "@/components/HypothesisForm";

export default function Home() {
  return (
    <main className="flex flex-col items-center justify-center min-h-screen px-4 py-16">
      <div className="w-full max-w-2xl space-y-6">
        <div className="text-center space-y-2">
          <h1 className="text-4xl font-bold text-white tracking-tight">Signal</h1>
          <p className="text-zinc-400">
            AI-powered hypothesis validation from Amplitude, Zendesk, Productboard &amp; Linear
          </p>
          <Link
            href="/connect"
            className="inline-block text-sm text-zinc-500 hover:text-zinc-300 underline underline-offset-2 transition-colors"
          >
            Manage integrations →
          </Link>
        </div>
        <HypothesisForm />
      </div>
    </main>
  );
}
