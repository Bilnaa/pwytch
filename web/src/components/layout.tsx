import { Link, NavLink, Outlet } from 'react-router'

import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'

function navClass({ isActive }: { isActive: boolean }) {
  return cn('text-sm text-muted-foreground hover:text-foreground', isActive && 'text-foreground')
}

export function Layout() {
  return (
    <div className="flex min-h-svh flex-col">
      <header className="border-b">
        <div className="mx-auto flex h-14 max-w-6xl items-center gap-6 px-4">
          <Link to="/" className="font-semibold">
            Pwytch
          </Link>
          <nav className="flex gap-4">
            <NavLink to="/" end className={navClass}>
              Lives
            </NavLink>
          </nav>
          <Button asChild variant="outline" size="sm" className="ml-auto">
            <Link to="/login">Log in</Link>
          </Button>
        </div>
      </header>
      <main className="mx-auto w-full max-w-6xl flex-1 px-4 py-6">
        <Outlet />
      </main>
    </div>
  )
}
