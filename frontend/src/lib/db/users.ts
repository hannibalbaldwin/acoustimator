export interface DbUser {
  id: string
  email: string
  name: string | null
  role: string
}

/**
 * Verify user credentials by calling the backend /api/auth/verify endpoint.
 * The backend does the bcrypt comparison so we never handle password hashes in the frontend.
 */
export async function verifyUserCredentials(
  email: string,
  password: string
): Promise<DbUser | null> {
  const BASE = process.env.NEXT_PUBLIC_API_URL ?? ''
  const API_KEY = process.env.NEXT_PUBLIC_API_KEY ?? ''
  try {
    const res = await fetch(`${BASE}/api/auth/verify`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(API_KEY ? { 'X-API-Key': API_KEY } : {}),
      },
      body: JSON.stringify({ email, password }),
    })
    if (!res.ok) return null
    return res.json() as Promise<DbUser>
  } catch {
    return null
  }
}
