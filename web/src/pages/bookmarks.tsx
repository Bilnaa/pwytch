import { useEffect, useState, type FormEvent } from 'react'
import { Link, useSearchParams } from 'react-router'

import { Avatar } from '@/components/avatar'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { errorMessage } from '@/lib/api'
import {
  deleteBookmark,
  listBookmarks,
  notifyFollowsChanged,
  updateBookmark,
  type Bookmark,
  type BookmarkPage,
  type TargetType,
} from '@/lib/bookmarks'
import { getUsers } from '@/lib/users'

const PAGE_SIZE = 20

// a bookmarked streamer is a follow, like on twitch. Only replays have a label and a note
const TABS: { type: TargetType; name: string; empty: string }[] = [
  { type: 'streamer', name: 'Following', empty: 'You don\'t follow anyone yet. Use "Follow" on a channel.' },
  { type: 'replay', name: 'Replays', empty: 'No replays saved yet.' },
]

function EditForm({ bookmark, onSaved, onCancel }: {
  bookmark: Bookmark
  onSaved: (bookmark: Bookmark) => void
  onCancel: () => void
}) {
  const [label, setLabel] = useState(bookmark.label)
  const [note, setNote] = useState(bookmark.note ?? '')
  const [error, setError] = useState('')

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    try {
      onSaved(await updateBookmark(bookmark.id, label, note))
    } catch (err) {
      setError(errorMessage(err))
    }
  }

  return (
    <form onSubmit={handleSubmit} className="flex-1 space-y-2">
      <Input value={label} onChange={(e) => setLabel(e.target.value)} maxLength={100} required aria-label="Label" />
      <Input value={note} onChange={(e) => setNote(e.target.value)} maxLength={300} placeholder="Note" aria-label="Note" />
      {error && <p className="text-xs text-destructive">{error}</p>}
      <div className="flex gap-2">
        <Button type="submit" size="sm">Save</Button>
        <Button type="button" variant="ghost" size="sm" onClick={onCancel}>Cancel</Button>
      </div>
    </form>
  )
}

function ReplayRow({ bookmark, onChanged, onDeleted }: {
  bookmark: Bookmark
  onChanged: (bookmark: Bookmark) => void
  onDeleted: () => void
}) {
  const [editing, setEditing] = useState(false)
  // second click on delete, so one misclick doesn't lose a bookmark
  const [confirming, setConfirming] = useState(false)
  const [error, setError] = useState('')

  async function handleDelete() {
    try {
      await deleteBookmark(bookmark.id)
      onDeleted()
    } catch (err) {
      setError(errorMessage(err))
      setConfirming(false)
    }
  }

  if (editing) {
    return (
      <li className="rounded-lg border p-3">
        <EditForm
          bookmark={bookmark}
          onSaved={(saved) => {
            onChanged(saved)
            setEditing(false)
          }}
          onCancel={() => setEditing(false)}
        />
      </li>
    )
  }

  return (
    <li className="flex items-start gap-3 rounded-lg border p-3">
      <div className="min-w-0 flex-1">
        <p className="font-semibold">{bookmark.label}</p>
        {bookmark.note && <p className="text-sm text-muted-foreground">{bookmark.note}</p>}
        <p className="text-xs text-muted-foreground">Saved {new Date(bookmark.created_at).toLocaleDateString()}</p>
        {error && <p className="text-xs text-destructive">{error}</p>}
        {/* under the text and not in place of Delete, so a double click can't confirm */}
        {confirming && (
          <div className="mt-2 flex items-center gap-2">
            <span className="text-sm">Delete this bookmark?</span>
            <Button variant="destructive" size="sm" onClick={handleDelete}>Delete</Button>
            <Button variant="ghost" size="sm" onClick={() => setConfirming(false)}>Cancel</Button>
          </div>
        )}
      </div>
      <div className="flex gap-1">
        <Button variant="ghost" size="sm" onClick={() => setEditing(true)} disabled={confirming}>Edit</Button>
        <Button variant="ghost" size="sm" onClick={() => setConfirming(true)} disabled={confirming}>Delete</Button>
      </div>
    </li>
  )
}

function FollowRow({ bookmark, username, onDeleted }: {
  bookmark: Bookmark
  // undefined if the account is gone
  username?: string
  onDeleted: () => void
}) {
  const [error, setError] = useState('')
  const name = username ?? bookmark.label

  // no confirmation: following again is one click on the channel
  async function handleUnfollow() {
    try {
      await deleteBookmark(bookmark.id)
      notifyFollowsChanged()
      onDeleted()
    } catch (err) {
      setError(errorMessage(err))
    }
  }

  return (
    <li className="flex items-center gap-3 rounded-lg border p-3">
      <Avatar username={name} className="size-10 text-base" />
      <div className="min-w-0 flex-1">
        {username ? (
          <Link to={`/${username}`} className="font-semibold hover:text-primary">
            {username}
          </Link>
        ) : (
          <p className="font-semibold">{name}</p>
        )}
        <p className="text-xs text-muted-foreground">Since {new Date(bookmark.created_at).toLocaleDateString()}</p>
        {error && <p className="text-xs text-destructive">{error}</p>}
      </div>
      <Button variant="outline" size="sm" onClick={handleUnfollow}>Unfollow</Button>
    </li>
  )
}

interface Loaded {
  // which tab and page this answer is for
  key: string
  data: BookmarkPage | null
  // username of each followed streamer, by user id
  usernames: Map<number, string>
  error: string
}

// a follow only has the user id of the streamer, the channel url needs the name.
// One call for the whole page
async function loadUsernames(follows: Bookmark[]): Promise<Map<number, string>> {
  const usernames = new Map<number, string>()
  if (follows.length === 0) {
    return usernames
  }
  const ids: number[] = []
  for (const follow of follows) {
    ids.push(follow.target_id)
  }
  for (const user of await getUsers(ids)) {
    usernames.set(user.id, user.username)
  }
  return usernames
}

// /bookmarks?tab=replays&page=2, in the url so a refresh stays on the same page
export function BookmarksPage() {
  const [params, setParams] = useSearchParams()
  let type: TargetType = 'streamer'
  if (params.get('tab') === 'replays') {
    type = 'replay'
  }
  const page = Math.max(1, Number(params.get('page')) || 1)
  const key = `${type}-${page}`
  const [loaded, setLoaded] = useState<Loaded | null>(null)
  // bumped after a delete, to reload the page with the next bookmark moving up
  const [reloadCount, setReloadCount] = useState(0)

  useEffect(() => {
    let cancelled = false
    listBookmarks(page, PAGE_SIZE, type)
      .then(async (data) => {
        let usernames = new Map<number, string>()
        if (type === 'streamer') {
          usernames = await loadUsernames(data.items)
        }
        if (!cancelled) {
          setLoaded({ key, data, usernames, error: '' })
        }
      })
      .catch((err) => {
        if (!cancelled) {
          setLoaded({ key, data: null, usernames: new Map(), error: errorMessage(err) })
        }
      })
    return () => {
      cancelled = true
    }
  }, [key, page, type, reloadCount])

  function goTo(newType: TargetType, newPage: number) {
    const next: Record<string, string> = {}
    if (newType === 'replay') {
      next.tab = 'replays'
    }
    if (newPage > 1) {
      next.page = String(newPage)
    }
    setParams(next)
  }

  function replaceBookmark(saved: Bookmark) {
    setLoaded((old) => {
      if (!old?.data) {
        return old
      }
      const items = old.data.items.map((item) => (item.id === saved.id ? saved : item))
      return { ...old, data: { ...old.data, items } }
    })
  }

  function handleDeleted() {
    // last bookmark of the last page: go back one page instead of showing an empty one
    if (loaded?.data && loaded.data.items.length === 1 && page > 1) {
      goTo(type, page - 1)
    } else {
      setReloadCount((n) => n + 1)
    }
  }

  const current = loaded && loaded.key === key ? loaded : null
  const pageCount = current?.data ? Math.max(1, Math.ceil(current.data.total / PAGE_SIZE)) : 1
  const tab = TABS.find((t) => t.type === type)!

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-semibold">My bookmarks</h1>

      <div className="flex gap-2">
        {TABS.map((t) => (
          <Button key={t.type} variant={t.type === type ? 'default' : 'outline'} size="sm" onClick={() => goTo(t.type, 1)}>
            {t.name}
          </Button>
        ))}
      </div>

      {current?.error && <p className="text-sm text-destructive">Cannot load the bookmarks: {current.error}</p>}

      {current?.data && current.data.items.length === 0 && <p className="text-muted-foreground">{tab.empty}</p>}

      {current?.data && current.data.items.length > 0 && (
        <ul className="space-y-2">
          {current.data.items.map((bookmark) => {
            if (type === 'streamer') {
              return (
                <FollowRow
                  key={bookmark.id}
                  bookmark={bookmark}
                  username={current.usernames.get(bookmark.target_id)}
                  onDeleted={handleDeleted}
                />
              )
            }
            return (
              <ReplayRow key={bookmark.id} bookmark={bookmark} onChanged={replaceBookmark} onDeleted={handleDeleted} />
            )
          })}
        </ul>
      )}

      {pageCount > 1 && (
        <div className="flex items-center gap-3 text-sm">
          <Button variant="outline" size="sm" disabled={page <= 1} onClick={() => goTo(type, page - 1)}>
            Previous
          </Button>
          <span>
            Page {page} of {pageCount}
          </span>
          <Button variant="outline" size="sm" disabled={page >= pageCount} onClick={() => goTo(type, page + 1)}>
            Next
          </Button>
        </div>
      )}
    </div>
  )
}
