import Link from "next/link";

export default function NotFound() {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-blueprint-mist px-6 dark:bg-blueprint-navy">
      <p className="font-mono text-5xl text-blueprint-navy/35 dark:text-blueprint-mist/30">
        404
      </p>
      <p className="mt-4 font-mono text-sm text-blueprint-navy/50 dark:text-blueprint-mist/45">
        GRIDMIND · Page not found
      </p>
      <Link
        href="/dashboard"
        className="mt-6 font-mono text-xs text-blueprint-amber underline"
      >
        ← Return to dashboard
      </Link>
    </div>
  );
}
