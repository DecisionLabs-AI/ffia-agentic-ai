"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import Image from "next/image";
import { login } from "@/lib/api";
import { isAuthenticated, setCurrentUser } from "@/lib/auth";

export default function LoginPage() {
  const router = useRouter();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (isAuthenticated()) router.replace("/");
  }, [router]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const res = await login(username, password);
      if (!res.ok || !res.user) {
        setError(res.error || "Invalid username or password");
        return;
      }
      setCurrentUser({
        user_id: res.user.user_id,
        username: res.user.username,
        display_name: res.user.display_name || res.user.username,
        restaurant_name: res.user.restaurant_name,
      });
      router.replace("/");
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "เข้าสู่ระบบไม่สำเร็จ");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-orange-50 px-4 py-6 sm:px-6 lg:px-8">
      <div className="grid min-h-[min(760px,calc(100vh-3rem))] w-full max-w-6xl overflow-hidden rounded-[2rem] border border-orange-100 bg-white shadow-2xl shadow-orange-200/50 lg:grid-cols-2">
        {/* Left panel — hero image */}
        <div className="relative hidden min-h-full overflow-hidden lg:block">
          <Image
            src="/home_screen.png"
            alt="FFIA restaurant dashboard preview"
            fill
            sizes="50vw"
            className="object-cover"
            priority
          />
          <div className="absolute inset-0 bg-gradient-to-t from-orange-950/75 via-orange-950/10 to-transparent" />
          <div className="absolute inset-x-0 bottom-0 p-8 xl:p-10">
            <p className="text-sm font-bold uppercase tracking-[0.18em] text-orange-300">
              FFIA
            </p>
            <h2 className="mt-3 text-4xl font-black leading-tight text-white">
              Fuel &amp; Food<br />Impact Analyzer
            </h2>
            <p className="mt-3 max-w-md text-sm leading-6 text-orange-100/90">
              ตัดสินใจด้านราคาได้ดีขึ้น ด้วยข้อมูลจริงจากร้านของคุณ
            </p>
          </div>
        </div>

        {/* Right panel — form */}
        <div className="flex min-h-[620px] items-center justify-center px-6 py-10 sm:px-10 lg:min-h-full lg:px-14 xl:px-16">
          <div className="w-full max-w-md">
            {/* Brand */}
            <div className="mb-9">
              <p className="text-sm font-bold uppercase tracking-[0.18em] text-orange-600">
                FFIA
              </p>
              <h1 className="mt-3 text-4xl font-black tracking-tight text-slate-950">Sign In</h1>
              <p className="mt-3 max-w-sm text-sm leading-6 text-slate-500">
                เข้าสู่ระบบเพื่อดูข้อมูลต้นทุนและวิเคราะห์ราคาร้านของคุณ
              </p>
            </div>

            {/* Form */}
            <form onSubmit={handleSubmit} className="space-y-5">
              <div>
                <label className="mb-2 block text-xs font-bold uppercase tracking-wide text-slate-600">
                  Username
                </label>
                <input
                  type="text"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  required
                  autoFocus
                  placeholder="your username"
                  className="w-full rounded-xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-900 placeholder-slate-400 shadow-sm focus:border-orange-400 focus:outline-none focus:ring-4 focus:ring-orange-100"
                />
              </div>

              <div>
                <label className="mb-2 block text-xs font-bold uppercase tracking-wide text-slate-600">
                  Password
                </label>
                <input
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                  className="w-full rounded-xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-900 shadow-sm focus:border-orange-400 focus:outline-none focus:ring-4 focus:ring-orange-100"
                />
              </div>

              {error && (
                <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm font-semibold text-red-700">
                  {error}
                </div>
              )}

              <button
                type="submit"
                disabled={loading}
                className="w-full rounded-xl bg-orange-600 px-4 py-3 text-sm font-bold text-white shadow-sm transition-colors hover:bg-orange-500 disabled:opacity-50"
              >
                {loading ? "กำลังเข้าสู่ระบบ…" : "Sign In"}
              </button>
            </form>
          </div>
        </div>
      </div>
    </div>
  );
}
