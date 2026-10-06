import { api } from '@/lib/api'
import type { TargetType } from '@/lib/bookmarks'

// All the stats routes are for admins only, main answers 403 to anyone else

export interface SearchCounter {
  item_type: 'streamer' | 'message'
  // a user id for a streamer, a message uuid for a message
  item_id: string
  count: number
}

export interface BookmarkDeletedCounter {
  target_type: TargetType
  target_id: number
  count: number
}

export interface ChatMessagesCounter {
  stream_id: number
  count: number
}

export interface PlayerCounters {
  stream_id: number
  play: number
  pause: number
  stop: number
}

export const TOP_SIZE = 10

export function topSearchedStreamers(): Promise<SearchCounter[]> {
  return api<SearchCounter[]>(`/stats/search/top?item_type=streamer&limit=${TOP_SIZE}`)
}

export function topBookmarkDeleted(): Promise<BookmarkDeletedCounter[]> {
  return api<BookmarkDeletedCounter[]>(`/stats/bookmarks/deleted/top?limit=${TOP_SIZE}`)
}

export function topChatMessages(): Promise<ChatMessagesCounter[]> {
  return api<ChatMessagesCounter[]>(`/stats/chat/top?limit=${TOP_SIZE}`)
}

export function getPlayerCounters(streamId: number): Promise<PlayerCounters> {
  return api<PlayerCounters>(`/stats/player/${streamId}`)
}
