import NextAuth from 'next-auth'
import Credentials from 'next-auth/providers/credentials'
import { authConfig } from './auth.config'
import { verifyUserCredentials } from '@/lib/db/users'

export const { handlers, signIn, signOut, auth } = NextAuth({
  ...authConfig,
  providers: [
    Credentials({
      async authorize(credentials) {
        const { email, password } = credentials as { email: string; password: string }
        if (!email || !password) return null
        const user = await verifyUserCredentials(email, password)
        if (!user) return null
        return { id: user.id, email: user.email, name: user.name ?? user.email, role: user.role }
      },
    }),
  ],
})
