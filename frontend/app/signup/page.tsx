import AuthForm from "@/components/AuthForm";

export const metadata = { title: "Sign up — Nexus BI" };

export default function SignupPage() {
  return (
    <main className="mx-auto flex min-h-screen max-w-6xl items-center justify-center px-4 pb-20 pt-28">
      <AuthForm mode="signup" />
    </main>
  );
}
