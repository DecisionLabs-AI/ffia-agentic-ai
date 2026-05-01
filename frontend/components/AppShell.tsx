"use client";

import type { ReactNode } from "react";
import AuthGuard from "./AuthGuard";
import Sidebar from "./Sidebar";

interface Props {
  children: ReactNode;
}

export default function AppShell({ children }: Props) {
  return (
    <AuthGuard>
      {() => (
        <div className="min-h-screen bg-[#fff8f1] text-slate-950 lg:flex">
          <Sidebar />
          <main className="min-w-0 flex-1 px-4 py-5 sm:px-6 lg:px-8 lg:py-8">
            {children}
          </main>
        </div>
      )}
    </AuthGuard>
  );
}
