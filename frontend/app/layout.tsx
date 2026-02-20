import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
  title: "Signal — PM Intelligence Platform",
  description: "Validate PM hypotheses with multi-source AI analysis",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className={`${inter.className} bg-[#0A0A0A] min-h-screen text-white antialiased`}>
        {children}
      </body>
    </html>
  );
}
