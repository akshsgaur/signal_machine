"use client";

import { SignIn } from "@clerk/nextjs";

export default function SignInPage() {
  return (
    <main className="min-h-screen flex items-center justify-center bg-[#0A0A0A] text-white px-4">
      <SignIn />
    </main>
  );
}
