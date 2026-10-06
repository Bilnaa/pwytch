import { api, apiUrl } from '@/lib/api'

export type Mp4Status = 'none' | 'processing' | 'ready' | 'failed'

// A live that has ended. Its id is the stream_id of the live
export interface Replay {
  stream_id: number
  streamer_id: number
  // null when replay got the end of the live without its start
  streamer_name: string | null
  title: string | null
  game: string | null
  started_at: string | null
  ended_at: string
  duration_s: number
  mp4_status: Mp4Status
  // relative to main's API root: give it to apiUrl()
  playback_url: string
}

export interface ReplayPage {
  items: Replay[]
  total: number
  page: number
  size: number
}

export const REPLAY_PAGE_SIZE = 24

export function listReplays(page: number): Promise<ReplayPage> {
  return api<ReplayPage>(`/replays?page=${page}&size=${REPLAY_PAGE_SIZE}`)
}

export function getReplay(id: number): Promise<Replay> {
  return api<Replay>(`/replays/${id}`)
}

export function playbackUrl(replay: Replay): string {
  return apiUrl(replay.playback_url)
}

// The browser downloads it itself (Content-Disposition: attachment), never through fetch:
// a replay of several hours would be loaded in memory
export function downloadUrl(id: number): string {
  return apiUrl(`/replays/${id}/download`)
}

export type DownloadAnswer =
  | { state: 'ready' }
  | { state: 'pending'; retryAfterMs: number }
  | { state: 'failed' }

export const DEFAULT_RETRY_MS = 5000

// Asks for the mp4. replay converts it when the live ends: 202 while it's still converting.
// If the conversion never started, this call starts it (safety net)
// Only called when the mp4 isn't ready: on a 200 the body is dropped unread
export async function requestDownload(id: number): Promise<DownloadAnswer> {
  const response = await fetch(downloadUrl(id))
  if (response.status === 202) {
    const seconds = Number(response.headers.get('Retry-After'))
    return { state: 'pending', retryAfterMs: seconds > 0 ? seconds * 1000 : DEFAULT_RETRY_MS }
  }
  if (response.ok) {
    await response.body?.cancel()
    return { state: 'ready' }
  }
  // 500: the conversion failed, the next call starts it again
  return { state: 'failed' }
}
