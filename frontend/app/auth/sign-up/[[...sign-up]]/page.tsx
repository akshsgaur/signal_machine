"use client";

import { SignUp } from "@clerk/nextjs";

export default function SignUpPage() {
  return (
    <main className="min-h-screen flex items-center justify-center bg-[#0A0A0A] text-white px-4">
      <SignUp />
    </main>
  );
}
