export function LoadingSkeleton() {
  return (
    <div className="min-h-screen bg-blueprint-mist p-6 dark:bg-blueprint-navy">
      <div className="mx-auto max-w-[1600px] animate-pulse">
        <div className="h-10 w-full rounded-md bg-blueprint-navy/15 dark:bg-white/10" />
        <div className="mt-8 grid grid-cols-3 gap-4">
          {Array.from({ length: 6 }).map((_, i) => (
            <div
              key={i}
              className="h-28 rounded-xl border border-white/10 bg-white/25 dark:bg-white/5"
            />
          ))}
        </div>
      </div>
    </div>
  );
}
