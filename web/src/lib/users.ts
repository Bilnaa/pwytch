import { ApiError, api } from '@/lib/api'

export interface PublicUser {
  id: number
  username: string
  display_name: string
}

// null when the account doesn't exist
export async function getUser(username: string): Promise<PublicUser | null> {
  try {
    return await api<PublicUser>(`/users/${encodeURIComponent(username)}`)
  } catch (err) {
    if (err instanceof ApiError && err.status === 404) {
      return null
    }
    throw err
  }
}

// unknown ids are left out of the answer
export function getUsers(ids: number[]): Promise<PublicUser[]> {
  const params = new URLSearchParams()
  for (const id of ids) {
    params.append('id', String(id))
  }
  return api<PublicUser[]>(`/users?${params}`)
}
