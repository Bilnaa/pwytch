import { useEffect, useState } from 'react'
import { Link, useSearchParams } from 'react-router'

import { ReplayCard } from '@/components/replay-card'
import { Button } from '@/components/ui/button'
import { errorMessage } from '@/lib/api'
import { listReplays, REPLAY_PAGE_SIZE, type ReplayPage } from '@/lib/replays'

// ?page=2 in the url, so a page can be reloaded or shared. Anything else is page 1
function readPage(value: string | null): number {
  const page = Number(value)
  return Number.isInteger(page) && page >= 1 ? page : 1
}

export function ReplaysPage() {
  const [searchParams] = useSearchParams()
  const page = readPage(searchParams.get('page'))
  const [result, setResult] = useState<ReplayPage | null>(null)
  const [error, setError] = useState('')

  useEffect(() => {
    let cancelled = false
    listReplays(page)
      .then((replays) => {
        if (!cancelled) {
          setResult(replays)
          setError('')
        }
      })
      .catch((err) => {
        if (!cancelled) {
          setError(errorMessage(err))
        }
      })
    return () => {
      cancelled = true
    }
  }, [page])

  const pageCount = result ? Math.max(1, Math.ceil(result.total / REPLAY_PAGE_SIZE)) : 1

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-semibold">Replays</h1>

      {error && <p className="text-sm text-destructive">Cannot load the replays: {error}</p>}

      {result && result.total === 0 && (
        <p className="text-muted-foreground">No replay yet. Lives show up here once they end.</p>
      )}

      {/* ?page=99 typed by hand: past the last page */}
      {result && result.total > 0 && result.items.length === 0 && (
        <p className="text-muted-foreground">
          No replay on this page.{' '}
          <Link to="/replays" className="underline">
            Back to the first page
          </Link>
        </p>
      )}

      {result && result.items.length > 0 && (
        <div className="grid gap-x-4 gap-y-6 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
          {result.items.map((replay) => (
            <ReplayCard key={replay.stream_id} replay={replay} />
          ))}
        </div>
      )}

      {result && result.items.length > 0 && pageCount > 1 && (
        <nav className="flex items-center justify-center gap-3">
          <Button asChild={page > 1} variant="outline" size="sm" disabled={page <= 1}>
            {page > 1 ? <Link to={`/replays?page=${page - 1}`}>Previous</Link> : 'Previous'}
          </Button>
          <span className="text-sm text-muted-foreground">
            Page {page} of {pageCount}
          </span>
          <Button asChild={page < pageCount} variant="outline" size="sm" disabled={page >= pageCount}>
            {page < pageCount ? <Link to={`/replays?page=${page + 1}`}>Next</Link> : 'Next'}
          </Button>
        </nav>
      )}
    </div>
  )
}
