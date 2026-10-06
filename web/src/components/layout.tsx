import { useState } from 'react'
import { Link, NavLink, Outlet, useMatches } from 'react-router'
import { Bookmark, ChartColumn, History, LogOut, Moon, Radio, Sun, User } from 'lucide-react'

import { FollowedSidebar } from '@/components/followed-sidebar'
import { SearchBar } from '@/components/search-bar'
import { Button } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { useAuth } from '@/lib/auth'
import { isDark, toggleTheme } from '@/lib/theme'
import { cn } from '@/lib/utils'

function navClass({ isActive }: { isActive: boolean }) {
  return cn(
    'text-sm font-semibold text-muted-foreground hover:text-primary',
    isActive && 'text-foreground',
  )
}

function ThemeButton() {
  const [dark, setDark] = useState(isDark)

  return (
    <Button variant="ghost" size="icon" onClick={() => setDark(toggleTheme())} aria-label="Toggle theme">
      {dark ? <Sun /> : <Moon />}
    </Button>
  )
}

function UserMenu() {
  const { user, loading, logout } = useAuth()

  if (loading) {
    return null
  }
  if (!user) {
    return (
      <>
        <Button asChild variant="outline" size="sm">
          <Link to="/login">Log in</Link>
        </Button>
        <Button asChild size="sm">
          <Link to="/register">Sign up</Link>
        </Button>
      </>
    )
  }
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="ghost" size="sm">
          <User />
          <span className="hidden md:inline">{user.display_name}</span>
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end">
        <DropdownMenuLabel>@{user.username}</DropdownMenuLabel>
        <DropdownMenuSeparator />
        {/* the nav of the header is hidden on a phone, its links are here instead */}
        <DropdownMenuItem asChild className="md:hidden">
          <Link to="/replays">
            <History />
            Replays
          </Link>
        </DropdownMenuItem>
        <DropdownMenuItem asChild className="md:hidden">
          <Link to="/bookmarks">
            <Bookmark />
            Bookmarks
          </Link>
        </DropdownMenuItem>
        {/* hidden for everyone else, main answers 403 to them anyway */}
        {user.role === 'admin' && (
          <DropdownMenuItem asChild>
            <Link to="/admin/stats">
              <ChartColumn />
              Stats
            </Link>
          </DropdownMenuItem>
        )}
        <DropdownMenuItem onSelect={logout}>
          <LogOut />
          Log out
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  )
}

// a route with handle: { fullWidth: true } handles its own width and padding
function useFullWidth() {
  const matches = useMatches()
  for (const match of matches) {
    const handle = match.handle as { fullWidth?: boolean } | undefined
    if (handle?.fullWidth) {
      return true
    }
  }
  return false
}

export function Layout() {
  const { user } = useAuth()
  const fullWidth = useFullWidth()

  return (
    <div className="flex min-h-svh flex-col">
      <header className="sticky top-0 z-10 border-b bg-card shadow-sm">
        <div className="flex h-12 items-center gap-3 px-4 md:gap-6">
          <Link to="/" className="flex items-center gap-2 text-lg font-bold">
            <img src="/favicon.svg" alt="" className="size-7" />
            <span className="hidden sm:inline">
              Pw<span className="text-primary">y</span>tch
            </span>
          </Link>
          <nav className="hidden gap-4 md:flex">
            <NavLink to="/" end className={navClass}>
              Lives
            </NavLink>
            <NavLink to="/replays" className={navClass}>
              Replays
            </NavLink>
            {user && (
              <>
                <NavLink to="/bookmarks" className={navClass}>
                  Bookmarks
                </NavLink>
              </>
            )}
          </nav>
          <div className="flex flex-1 justify-center">
            <SearchBar />
          </div>
          <div className="flex items-center gap-2">
            <ThemeButton />
            {/* next to the profile like on twitch, only the icon on a phone */}
            {user && (
              <Button asChild size="sm">
                <Link to="/go-live" aria-label="Go live">
                  <Radio />
                  <span className="hidden sm:inline">Go live</span>
                </Link>
              </Button>
            )}
            <UserMenu />
          </div>
        </div>
      </header>
      <div className="flex flex-1">
        <FollowedSidebar />
        <main className={cn('w-full min-w-0 flex-1', !fullWidth && 'mx-auto max-w-6xl px-4 py-6')}>
          <Outlet />
        </main>
      </div>
    </div>
  )
}
