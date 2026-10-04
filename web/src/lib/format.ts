// How long a live has been running: "12 min", "2h 05"
export function formatUptime(startedAt: string, now: number): string {
  const minutes = Math.max(0, Math.floor((now - new Date(startedAt).getTime()) / 60000))
  if (minutes < 60) {
    return `${minutes} min`
  }
  const hours = Math.floor(minutes / 60)
  return `${hours}h ${String(minutes % 60).padStart(2, '0')}`
}
