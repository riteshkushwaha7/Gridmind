export function formatMinuteOfDay(minutes: number): string {
  if (minutes >= 24 * 60) return "24:00";
  const h = Math.floor(minutes / 60);
  const m = Math.floor(minutes % 60);
  return `${String(h).padStart(2, "0")}:${String(m).padStart(2, "0")}`;
}

export function minuteOfDayFromDate(d: Date): number {
  return d.getHours() * 60 + d.getMinutes() + d.getSeconds() / 60;
}

export type LoadTone = "green" | "amber" | "red";

export function toneForFeederUtilization(ratio: number): LoadTone {
  if (ratio < 0.8) return "green";
  if (ratio <= 0.95) return "amber";
  return "red";
}
