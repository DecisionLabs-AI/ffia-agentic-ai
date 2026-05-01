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
    <div className="min-h-screen flex bg-orange-50">
      {/* Left panel — hero image */}
      <div className="hidden lg:flex lg:w-1/2 p-6 items-center justify-center">
        <div className="relative w-full h-full max-h-[calc(100vh-3rem)] rounded-3xl overflow-hidden shadow-xl">
          <Image
            src="/home_screen.png"
            alt="FFIA restaurant dashboard preview"
            fill
            className="object-cover"
            priority
          />
          {/* Gradient overlay with tagline */}
          <div className="absolute inset-0 bg-gradient-to-t from-orange-950/70 via-transparent to-transparent flex flex-col justify-end p-8">
            <p className="text-sm font-bold uppercase tracking-[0.18em] text-orange-300">
              FFIA
            </p>
            <h2 className="mt-2 text-3xl font-black text-white leading-snug">
              Fuel &amp; Food<br />Impact Analyzer
            </h2>
            <p className="mt-2 text-sm text-orange-100/80">
              ตัดสินใจด้านราคาได้ดีขึ้น ด้วยข้อมูลจริงจากร้านของคุณ
            </p>
          </div>
        </div>
      </div>

      {/* Right panel — form */}
      <div className="flex flex-1 flex-col items-center justify-center px-6 py-12">
        <div className="w-full max-w-sm">
          {/* Brand */}
          <div className="mb-8">
            <p className="text-sm font-bold uppercase tracking-[0.18em] text-orange-600">
              FFIA
            </p>
            <h1 className="mt-1 text-3xl font-black text-slate-950">Sign In</h1>
            <p className="mt-2 text-sm text-slate-500">
              เข้าสู่ระบบเพื่อดูข้อมูลต้นทุนและวิเคราะห์ราคาร้านของคุณ
            </p>
          </div>

          {/* Form */}
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-xs font-bold text-slate-600 mb-1.5 uppercase tracking-wide">
                Username
              </label>
              <input
                type="text"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                required
                autoFocus
                placeholder="your username"
                className="w-full rounded-xl border border-slate-200 bg-white px-4 py-2.5 text-sm text-slate-900 placeholder-slate-400 shadow-sm focus:border-orange-400 focus:outline-none focus:ring-2 focus:ring-orange-100"
              />
            </div>

            <div>
              <label className="block text-xs font-bold text-slate-600 mb-1.5 uppercase tracking-wide">
                Password
              </label>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                className="w-full rounded-xl border border-slate-200 bg-white px-4 py-2.5 text-sm text-slate-900 shadow-sm focus:border-orange-400 focus:outline-none focus:ring-2 focus:ring-orange-100"
              />
            </div>

            {error && (
              <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-2.5 text-sm font-semibold text-red-700">
                {error}
              </div>
            )}

            <button
              type="submit"
              disabled={loading}
              className="mt-2 w-full rounded-xl bg-orange-600 px-4 py-2.5 text-sm font-bold text-white shadow-sm transition-colors hover:bg-orange-500 disabled:opacity-50"
            >
              {loading ? "กำลังเข้าสู่ระบบ…" : "Sign In"}
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}
