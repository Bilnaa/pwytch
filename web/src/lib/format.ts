// How long a live has been running: "12 min", "2h 05"
export function formatUptime(startedAt: string, now: number): string {
  const minutes = Math.max(0, Math.floor((now - new Date(startedAt).getTime()) / 60000))
  if (minutes < 60) {
    return `${minutes} min`
  }
  const hours = Math.floor(minutes / 60)
  return `${hours}h ${String(minutes % 60).padStart(2, '0')}`
}

// Length of a replay: "45 min", "1h 02", "40 s" under a minute
export function formatDuration(seconds: number): string {
  // rounded before the test: 59.6 s is shown "1 min", never "60 s"
  const roundedSeconds = Math.max(0, Math.round(seconds))
  if (roundedSeconds < 60) {
    return `${roundedSeconds} s`
  }
  const minutes = Math.floor(roundedSeconds / 60)
  if (minutes < 60) {
    return `${minutes} min`
  }
  return `${Math.floor(minutes / 60)}h ${String(minutes % 60).padStart(2, '0')}`
}

// Day of a replay in the viewer's language: "Oct 4, 2026"
export function formatDate(isoDate: string): string {
  return new Date(isoDate).toLocaleDateString(undefined, {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
  })
}
