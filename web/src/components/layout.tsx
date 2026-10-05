import { useState } from 'react'
import { Link, NavLink, Outlet } from 'react-router'
import { LogOut, Moon, Sun, User } from 'lucide-react'

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
          {user.display_name}
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end">
        <DropdownMenuLabel>@{user.username}</DropdownMenuLabel>
        <DropdownMenuSeparator />
        <DropdownMenuItem onSelect={logout}>
          <LogOut />
          Log out
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  )
}

export function Layout() {
  const { user } = useAuth()

  return (
    <div className="flex min-h-svh flex-col">
      <header className="sticky top-0 z-10 border-b bg-card shadow-sm">
        <div className="flex h-12 items-center gap-6 px-4">
          <Link to="/" className="flex items-center gap-2 text-lg font-bold">
            <img src="/favicon.svg" alt="" className="size-7" />
            <span>
              Pw<span className="text-primary">y</span>tch
            </span>
          </Link>
          <nav className="flex gap-4">
            <NavLink to="/" end className={navClass}>
              Lives
            </NavLink>
            {user && (
              <>
                <NavLink to="/go-live" className={navClass}>
                  Go live
                </NavLink>
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
            <UserMenu />
          </div>
        </div>
      </header>
      <main className="mx-auto w-full max-w-6xl flex-1 px-4 py-6">
        <Outlet />
      </main>
    </div>
  )
}
