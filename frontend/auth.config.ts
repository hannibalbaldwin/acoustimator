import type { NextAuthConfig } from 'next-auth'

export const authConfig: NextAuthConfig = {
  pages: {
    signIn: '/login',
  },
  callbacks: {
    authorized({ auth, request: { nextUrl } }) {
      const isLoggedIn = !!auth?.user
      const isOnLogin = nextUrl.pathname === '/login'
      if (isOnLogin) {
        if (isLoggedIn) return Response.redirect(new URL('/dashboard', nextUrl))
        return true
      }
      if (!isLoggedIn) return false
      return true
    },
    jwt({ token, user }) {
      if (user) {
        token.role = (user as { role?: string }).role ?? 'user'
        token.id = user.id
      }
      return token
    },
    session({ session, token }) {
      if (session.user) {
        session.user.role = token.role as string
        session.user.id = token.id as string
      }
      return session
    },
  },
  providers: [], // filled in auth.ts
}
