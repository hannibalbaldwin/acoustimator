import { neon } from '@neondatabase/serverless'
import bcrypt from 'bcryptjs'
import { NextRequest, NextResponse } from 'next/server'

export async function POST(req: NextRequest) {
  try {
    const { email, password } = (await req.json()) as { email: string; password: string }
    if (!email || !password) {
      return NextResponse.json({ error: 'Missing credentials' }, { status: 400 })
    }

    const rawUrl = process.env.DATABASE_URL ?? ''
    // Convert SQLAlchemy-style URL (postgresql+asyncpg://) to standard postgres:// for Neon
    const dbUrl = rawUrl.replace(/^postgresql\+asyncpg:\/\//, 'postgresql://')
    if (!dbUrl) {
      return NextResponse.json({ error: 'Database not configured' }, { status: 500 })
    }

    const sql = neon(dbUrl)
    const rows = await sql`
      SELECT id::text, email, name, role, password_hash
      FROM users
      WHERE email = ${email.toLowerCase().trim()}
      LIMIT 1
    `

    if (rows.length === 0) {
      return NextResponse.json({ error: 'Invalid credentials' }, { status: 401 })
    }

    const user = rows[0]
    const valid = await bcrypt.compare(password, user.password_hash as string)
    if (!valid) {
      return NextResponse.json({ error: 'Invalid credentials' }, { status: 401 })
    }

    return NextResponse.json({
      id: user.id,
      email: user.email,
      name: user.name,
      role: user.role,
    })
  } catch (err) {
    console.error('[credentials/verify]', err)
    return NextResponse.json({ error: 'Internal server error' }, { status: 500 })
  }
}
