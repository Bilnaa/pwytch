import { useEffect, useState, type ReactNode } from 'react'
import { Link } from 'react-router'

import { ApiError, errorMessage } from '@/lib/api'
import { useAuth } from '@/lib/auth'
import { listReplays } from '@/lib/replays'
import {
  getPlayerCounters,
  topBookmarkDeleted,
  topChatMessages,
  topSearchedStreamers,
  type PlayerCounters,
} from '@/lib/stats'
import { getStream, listLives, type Stream } from '@/lib/streams'
import { getUsers, type PublicUser } from '@/lib/users'

// how many ended lives get their player counters, on top of the current lives
const RECENT_REPLAYS = 10

interface RankingRow {
  key: string
  label: ReactNode
  count: number
}

interface PlayerRow {
  streamId: number
  title: string
  streamer: string
  live: boolean
  counters: PlayerCounters
}

interface PlayerData {
  rows: PlayerRow[]
  // what couldn't be loaded, the rest is still shown
  missing: string[]
}

// the stats only have ids, the names come from main. If that fails we keep the ids
async function loadUsers(ids: number[]): Promise<Map<number, PublicUser>> {
  const users = new Map<number, PublicUser>()
  if (ids.length === 0) {
    return users
  }
  const found = await getUsers(ids).catch(() => [])
  for (const user of found) {
    users.set(user.id, user)
  }
  return users
}

async function loadStreams(ids: number[]): Promise<Map<number, Stream>> {
  const streams = new Map<number, Stream>()
  const found = await Promise.all(ids.map((id) => getStream(id).catch(() => null)))
  for (const stream of found) {
    if (stream) {
      streams.set(stream.id, stream)
    }
  }
  return streams
}

function userLink(id: number, users: Map<number, PublicUser>): ReactNode {
  const user = users.get(id)
  if (!user) {
    return `User #${id}`
  }
  return <Link to={`/${user.username}`} className="hover:underline">{user.display_name}</Link>
}

function streamLink(id: number, streams: Map<number, Stream>): ReactNode {
  const stream = streams.get(id)
  // the id tells apart two lives of a channel with the same title
  let title = `Stream #${id}`
  if (stream) {
    title = `${stream.title} (${stream.streamer.username}) #${id}`
  }
  return <Link to={`/videos/${id}`} className="hover:underline">{title}</Link>
}

// Each section loads on its own: one service down only empties its own section

async function loadSearched(): Promise<RankingRow[]> {
  const counters = await topSearchedStreamers()
  const users = await loadUsers(counters.map((counter) => Number(counter.item_id)))
  return counters.map((counter) => ({
    key: counter.item_id,
    label: userLink(Number(counter.item_id), users),
    count: counter.count,
  }))
}

async function loadDeleted(): Promise<RankingRow[]> {
  const counters = await topBookmarkDeleted()
  const userIds: number[] = []
  const streamIds: number[] = []
  for (const counter of counters) {
    if (counter.target_type === 'streamer') {
      userIds.push(counter.target_id)
    } else {
      // a replay's id is the id of its stream
      streamIds.push(counter.target_id)
    }
  }
  const [users, streams] = await Promise.all([loadUsers(userIds), loadStreams(streamIds)])

  return counters.map((counter) => {
    let label = <>Replay: {streamLink(counter.target_id, streams)}</>
    if (counter.target_type === 'streamer') {
      label = <>Channel: {userLink(counter.target_id, users)}</>
    }
    return { key: `${counter.target_type}:${counter.target_id}`, label, count: counter.count }
  })
}

async function loadChat(): Promise<RankingRow[]> {
  const counters = await topChatMessages()
  const streams = await loadStreams(counters.map((counter) => counter.stream_id))
  return counters.map((counter) => ({
    key: String(counter.stream_id),
    label: streamLink(counter.stream_id, streams),
    count: counter.count,
  }))
}

async function loadPlayer(): Promise<PlayerData> {
  // lives come from stream, replays from replay: one can be down without the other
  const [lives, replays] = await Promise.all([
    listLives().catch(() => null),
    listReplays(1).catch(() => null),
  ])
  if (!lives && !replays) {
    throw new Error('Lives and replays are unavailable')
  }

  const missing: string[] = []
  const watched: Omit<PlayerRow, 'counters'>[] = []
  if (lives) {
    for (const live of lives) {
      watched.push({ streamId: live.id, title: live.title, streamer: live.streamer.username, live: true })
    }
  } else {
    missing.push('current lives')
  }
  if (replays) {
    for (const replay of replays.items.slice(0, RECENT_REPLAYS)) {
      watched.push({
        streamId: replay.stream_id,
        title: replay.title ?? 'Untitled',
        streamer: replay.streamer_name ?? `User #${replay.streamer_id}`,
        live: false,
      })
    }
  } else {
    missing.push('replays')
  }

  const counters = await Promise.all(watched.map((row) => getPlayerCounters(row.streamId)))
  const rows: PlayerRow[] = []
  for (let i = 0; i < watched.length; i++) {
    rows.push({ ...watched[i], counters: counters[i] })
  }
  return { rows, missing }
}

function useSection<T>(load: () => Promise<T>) {
  const [data, setData] = useState<T | null>(null)
  const [error, setError] = useState('')

  useEffect(() => {
    let cancelled = false
    load()
      .then((result) => {
        if (!cancelled) {
          setData(result)
        }
      })
      .catch((err) => {
        if (cancelled) {
          return
        }
        // a 403 (role removed while the page is open) shows "Admin role required"
        if (err instanceof ApiError) {
          setError(errorMessage(err))
        } else {
          setError(err.message)
        }
      })
    return () => {
      cancelled = true
    }
  }, [load])

  return { data, error }
}

function SectionState({ loading, error }: { loading: boolean; error: string }) {
  if (error) {
    return <p className="text-sm text-destructive">{error}</p>
  }
  if (loading) {
    return <p className="text-sm text-muted-foreground">Loading…</p>
  }
  return null
}

function Ranking({ title, unit, load }: {
  title: string
  // singular, an s is added after 1
  unit: string
  load: () => Promise<RankingRow[]>
}) {
  const { data, error } = useSection(load)

  return (
    <section className="rounded-lg border bg-card p-4">
      <h2 className="mb-3 font-semibold">{title}</h2>
      <SectionState loading={!data} error={error} />
      {data && data.length === 0 && <p className="text-sm text-muted-foreground">Nothing counted yet.</p>}
      {data && (
        <ol className="space-y-1 text-sm">
          {data.map((row, index) => (
            <li key={row.key} className="flex gap-2">
              <span className="w-5 text-muted-foreground">{index + 1}.</span>
              <span className="min-w-0 flex-1 truncate">{row.label}</span>
              <span className="tabular-nums text-muted-foreground">
                {row.count} {unit}
                {row.count > 1 && 's'}
              </span>
            </li>
          ))}
        </ol>
      )}
    </section>
  )
}

function PlayerTable() {
  const { data, error } = useSection(loadPlayer)

  if (!data) {
    return <SectionState loading error={error} />
  }
  return (
    <>
      {data.missing.length > 0 && (
        <p className="text-sm text-destructive">Couldn't load the {data.missing.join(' and ')}.</p>
      )}
      {data.rows.length === 0 && data.missing.length === 0 && (
        <p className="text-sm text-muted-foreground">No lives or replays yet.</p>
      )}
      {data.rows.length > 0 && (
        <div className="overflow-x-auto rounded-lg border bg-card">
          <table className="w-full text-sm">
            <thead className="text-left text-muted-foreground">
              <tr className="border-b">
                <th className="p-3 font-medium">Stream</th>
                <th className="p-3 text-right font-medium">Play</th>
                <th className="p-3 text-right font-medium">Pause</th>
                <th className="p-3 text-right font-medium">Stop</th>
              </tr>
            </thead>
            <tbody>
              {data.rows.map((row) => (
                <tr key={row.streamId} className="border-b last:border-0">
                  <td className="p-3">
                    <Link to={`/videos/${row.streamId}`} className="hover:underline">
                      {row.title}
                    </Link>
                    <span className="text-muted-foreground"> · {row.streamer}</span>
                    {row.live && <span className="ml-2 text-xs font-semibold text-primary">LIVE</span>}
                  </td>
                  <td className="p-3 text-right tabular-nums">{row.counters.play}</td>
                  <td className="p-3 text-right tabular-nums">{row.counters.pause}</td>
                  <td className="p-3 text-right tabular-nums">{row.counters.stop}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  )
}

export function AdminStatsPage() {
  const { user } = useAuth()

  if (user?.role !== 'admin') {
    return (
      <div className="space-y-2">
        <h1 className="text-2xl font-semibold">Admins only</h1>
        <p className="text-sm text-muted-foreground">You need the admin role to see the stats.</p>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold">Stats</h1>
      <div className="grid gap-4 md:grid-cols-3">
        <Ranking title="Most found in search" unit="hit" load={loadSearched} />
        <Ranking title="Most removed from bookmarks" unit="removal" load={loadDeleted} />
        <Ranking title="Most chat messages" unit="message" load={loadChat} />
      </div>
      <section className="space-y-3">
        <h2 className="font-semibold">Player events</h2>
        <PlayerTable />
      </section>
    </div>
  )
}
