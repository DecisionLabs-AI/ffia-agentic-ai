import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "FFIA — Fuel & Food Impact Analyzer",
  description: "Agentic AI decision support for Bangkok restaurant owners",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="th" className="h-full antialiased">
      <body className="min-h-full flex flex-col">{children}</body>
    </html>
  );
}
