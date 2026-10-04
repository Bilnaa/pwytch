import { cn } from '@/lib/utils'

// No profile pictures yet: first letter of the name on the primary color
export function Avatar({ username, className }: { username: string; className?: string }) {
  return (
    <div
      className={cn(
        'flex size-12 shrink-0 items-center justify-center rounded-full bg-primary text-lg font-bold text-primary-foreground uppercase',
        className,
      )}
    >
      {username[0]}
    </div>
  )
}
