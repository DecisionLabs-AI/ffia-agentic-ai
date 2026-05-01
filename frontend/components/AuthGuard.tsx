"use client";

// Step 1: AuthGuard — wraps protected pages.
// Reads sandbox user context from localStorage on mount; redirects to /login if missing.
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { getCurrentUser, AuthUser } from "@/lib/auth";

interface Props {
  children: (user: AuthUser) => React.ReactNode;
}

export default function AuthGuard({ children }: Props) {
  const router = useRouter();
  const [user, setUser] = useState<AuthUser | null>(null);
  const [checking, setChecking] = useState(true);

  useEffect(() => {
    const current = getCurrentUser();
    if (!current) {
      router.replace("/login");
    } else {
      setUser(current);
    }
    setChecking(false);
  }, [router]);

  if (checking) {
    return (
      <div className="flex h-screen items-center justify-center text-sm font-semibold text-slate-500">
        Checking login…
      </div>
    );
  }

  if (!user) return null;
  return <>{children(user)}</>;
}
