import { api } from '@/lib/api'

export type TargetType = 'streamer' | 'replay'

export interface Bookmark {
  id: number
  user_id: number
  target_type: TargetType
  // id of the streamer (a user), or of the stream for a replay
  target_id: number
  label: string
  note: string | null
  created_at: string
  updated_at: string
}

export interface BookmarkPage {
  items: Bookmark[]
  total: number
  page: number
  size: number
}

export function listBookmarks(page: number, size: number, type: TargetType | null): Promise<BookmarkPage> {
  const params = new URLSearchParams({ page: String(page), size: String(size) })
  if (type) {
    params.set('target_type', type)
  }
  return api<BookmarkPage>(`/bookmarks?${params}`)
}

// bookmarks refuses an empty note, no note is null
function cleanNote(note: string): string | null {
  return note.trim() || null
}

export function createBookmark(type: TargetType, targetId: number, label: string): Promise<Bookmark> {
  return api<Bookmark>('/bookmarks', {
    method: 'POST',
    body: JSON.stringify({ target_type: type, target_id: targetId, label }),
  })
}

export function updateBookmark(id: number, label: string, note: string): Promise<Bookmark> {
  return api<Bookmark>(`/bookmarks/${id}`, {
    method: 'PATCH',
    body: JSON.stringify({ label, note: cleanNote(note) }),
  })
}

export function deleteBookmark(id: number): Promise<void> {
  return api<void>(`/bookmarks/${id}`, { method: 'DELETE' })
}

// The follow of this streamer, or null. bookmarks can't filter by target_id, so
// we look in the first 100 follows (max page size), plenty for us
export async function findFollow(streamerId: number): Promise<Bookmark | null> {
  const page = await listBookmarks(1, 100, 'streamer')
  for (const bookmark of page.items) {
    if (bookmark.target_id === streamerId) {
      return bookmark
    }
  }
  return null
}
