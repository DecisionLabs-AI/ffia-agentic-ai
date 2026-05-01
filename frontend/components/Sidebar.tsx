"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { AuthUser, getCurrentUser, logout } from "@/lib/auth";

const NAV_ITEMS = [
  { href: "/", icon: "OV", label: "Overview" },
  { href: "/setup", icon: "BS", label: "Business Setup" },
  { href: "/cost-data", icon: "CD", label: "Cost Data" },
  { href: "/dashboard", icon: "DB", label: "Dashboard" },
  { href: "/chat", icon: "AI", label: "AI Assistant" },
];

export default function Sidebar() {
  const pathname = usePathname();
  const [user, setUser] = useState<AuthUser | null>(null);
  const profileName = user?.restaurant_name || user?.display_name || user?.username || "";
  const avatarInitial = (profileName || user?.username || "U").trim().charAt(0).toUpperCase();

  useEffect(() => {
    setUser(getCurrentUser());
  }, [pathname]);

  function handleLogout() {
    logout();
    window.location.href = "/login";
  }

  return (
    <aside className="sticky top-0 z-20 flex flex-col border-b border-orange-100 bg-white/90 px-4 py-3 backdrop-blur lg:h-screen lg:w-72 lg:border-b-0 lg:border-r lg:px-5 lg:py-6">
      <div className="flex items-center justify-between gap-4 lg:block">
        <Link href="/" className="block">
          <p className="text-2xl font-black tracking-tight text-orange-600">FFIA</p>
          <p className="text-xs font-medium text-slate-500">Fuel & Food Impact Analyzer</p>
        </Link>
        <div className="rounded-full border border-orange-200 bg-orange-50 px-3 py-1 text-xs font-semibold text-orange-700 lg:mt-5 lg:inline-block">
          Pilot Mode
        </div>
      </div>

      <nav className="mt-4 flex gap-2 overflow-x-auto pb-1 lg:mt-8 lg:block lg:space-y-2 lg:overflow-visible">
        {NAV_ITEMS.map(({ href, icon, label }) => {
          const active = href === "/" ? pathname === "/" : pathname.startsWith(href);
          return (
            <Link
              key={href}
              href={href}
              className={`flex shrink-0 items-center gap-3 rounded-xl px-3 py-2 text-sm font-semibold transition-colors lg:w-full ${
                active
                  ? "bg-orange-600 text-white shadow-sm"
                  : "text-slate-600 hover:bg-orange-50 hover:text-orange-700"
              }`}
            >
              <span className={`grid h-8 w-8 place-items-center rounded-lg text-[11px] font-black ${
                active ? "bg-white/20 text-white" : "bg-slate-100 text-slate-500"
              }`}>
                {icon}
              </span>
              <span>{label}</span>
            </Link>
          );
        })}
      </nav>

      <div className="mt-6 hidden rounded-2xl border border-orange-100 bg-orange-50 p-4 lg:block">
        <p className="text-sm font-bold text-slate-900">จุดวิเคราะห์หลัก</p>
        <p className="mt-2 text-sm leading-6 text-slate-600">
          ดูต้นทุนจริง ผลกระทบน้ำมัน GP แพลตฟอร์ม และคำแนะนำที่ทำได้ทันที
        </p>
      </div>

      <div className="hidden flex-1 lg:block" />

      {user ? (
        <div className="mt-4 rounded-2xl border border-orange-100 bg-white px-3 py-2.5 shadow-sm lg:mt-auto">
          <div className="flex items-center justify-between gap-3">
            <div className="flex min-w-0 items-center gap-3">
              <div className="grid h-9 w-9 shrink-0 place-items-center rounded-full bg-orange-100 text-sm font-black text-orange-700">
                {avatarInitial}
              </div>
              <div className="min-w-0">
                <p className="truncate text-sm font-black text-slate-900">{profileName}</p>
              </div>
            </div>
            <button
              type="button"
              onClick={handleLogout}
              className="shrink-0 rounded-lg border border-orange-200 px-2.5 py-1 text-xs font-bold text-orange-700 transition hover:bg-orange-50"
            >
              Sign out
            </button>
          </div>
        </div>
      ) : null}
    </aside>
  );
}
