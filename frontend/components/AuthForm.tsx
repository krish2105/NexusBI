"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { motion } from "motion/react";
import { Sparkles, KeyRound, Copy, Check } from "lucide-react";
import { useAuth } from "./AuthProvider";

export default function AuthForm({ mode }: { mode: "login" | "signup" }) {
  const { login, signup } = useAuth();
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [apiKey, setApiKey] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  const isSignup = mode === "signup";

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErr(null);
    if (isSignup && password.length < 8) {
      setErr("Password must be at least 8 characters.");
      return;
    }
    setBusy(true);
    try {
      if (isSignup) {
        const { api_key } = await signup(email, password);
        if (api_key) {
          setApiKey(api_key); // show once, then let them continue
          return;
        }
      } else {
        await login(email, password);
      }
      router.push("/app");
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Something went wrong.");
    } finally {
      setBusy(false);
    }
  };

  // Post-signup: show the one-time API key before sending them to the workspace.
  if (apiKey) {
    return (
      <div className="card w-full max-w-md p-6">
        <div className="mb-3 flex items-center gap-2">
          <KeyRound className="h-5 w-5 text-cyan" />
          <h2 className="text-lg font-semibold">Your API key</h2>
        </div>
        <p className="mb-3 text-sm text-ink-dim">
          Save this now — it&apos;s shown <b>once</b> and only its hash is stored. Use it
          as the <code className="text-cyan">X-API-Key</code> header for programmatic
          access. You&apos;re already signed in for the web app.
        </p>
        <div className="flex items-center gap-2 rounded-lg border border-line bg-surface/60 p-3">
          <code className="flex-1 break-all font-mono text-xs text-ink">{apiKey}</code>
          <button
            onClick={() => {
              navigator.clipboard.writeText(apiKey).catch(() => {});
              setCopied(true);
            }}
            className="focus-ring shrink-0 rounded-lg border border-line p-2 text-ink-dim hover:text-ink"
            aria-label="Copy API key"
          >
            {copied ? <Check className="h-4 w-4 text-pos" /> : <Copy className="h-4 w-4" />}
          </button>
        </div>
        <button
          onClick={() => router.push("/app")}
          className="focus-ring mt-4 w-full rounded-lg bg-ai-gradient py-2.5 text-sm font-medium text-white"
        >
          Continue to the workspace →
        </button>
      </div>
    );
  }

  return (
    <motion.form
      onSubmit={submit}
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      className="card w-full max-w-md p-6"
    >
      <div className="mb-5 flex items-center gap-2">
        <span className="grid h-8 w-8 place-items-center rounded-lg bg-ai-gradient">
          <Sparkles className="h-4 w-4 text-white" />
        </span>
        <h1 className="text-xl font-semibold tracking-tight">
          {isSignup ? "Create your account" : "Welcome back"}
        </h1>
      </div>

      <label className="mb-1 block text-xs font-medium text-ink-dim">Email</label>
      <input
        type="email"
        autoComplete="email"
        required
        value={email}
        onChange={(e) => setEmail(e.target.value)}
        placeholder="you@company.com"
        className="focus-ring mb-4 w-full rounded-lg border border-line bg-surface/60 px-3 py-2.5 text-sm"
      />

      <label className="mb-1 block text-xs font-medium text-ink-dim">Password</label>
      <input
        type="password"
        autoComplete={isSignup ? "new-password" : "current-password"}
        required
        value={password}
        onChange={(e) => setPassword(e.target.value)}
        placeholder={isSignup ? "at least 8 characters" : "••••••••"}
        className="focus-ring mb-4 w-full rounded-lg border border-line bg-surface/60 px-3 py-2.5 text-sm"
      />

      {err && (
        <p className="mb-3 rounded-lg border border-neg/30 bg-neg/10 px-3 py-2 text-xs text-neg">
          {err}
        </p>
      )}

      <button
        type="submit"
        disabled={busy}
        className="focus-ring w-full rounded-lg bg-ai-gradient py-2.5 text-sm font-medium text-white disabled:opacity-50"
      >
        {busy ? "…" : isSignup ? "Create account" : "Sign in"}
      </button>

      {isSignup && (
        <p className="mt-3 text-center text-[11px] text-ink-faint">
          By creating an account you agree to our{" "}
          <Link href="/legal#terms" className="text-ink-dim hover:underline">Terms</Link>
          {" "}and{" "}
          <Link href="/legal#privacy" className="text-ink-dim hover:underline">Privacy Policy</Link>.
        </p>
      )}

      <p className="mt-4 text-center text-xs text-ink-dim">
        {isSignup ? (
          <>
            Already have an account?{" "}
            <Link href="/login" className="text-cyan hover:underline">
              Sign in
            </Link>
          </>
        ) : (
          <>
            New here?{" "}
            <Link href="/signup" className="text-cyan hover:underline">
              Create an account
            </Link>
          </>
        )}
      </p>
      <p className="mt-2 text-center text-[11px] text-ink-faint">
        The public demo works without an account. Sign up to save your own
        connections, history, and dashboards.
      </p>
    </motion.form>
  );
}
