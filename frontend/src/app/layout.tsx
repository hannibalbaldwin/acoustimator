import type { Metadata } from 'next'
import { Space_Grotesk, JetBrains_Mono } from 'next/font/google'
import './globals.css'
import { Sidebar } from '@/components/layout/Sidebar'
import { TooltipProvider } from '@/components/ui/tooltip'

// Space Grotesk — geometric, modern tech feel
const spaceGrotesk = Space_Grotesk({
  variable: '--font-space-grotesk',
  subsets: ['latin'],
  weight: ['300', '400', '500', '600', '700'],
  display: 'swap',
})

// JetBrains Mono — for all monetary values and numbers
const jetbrainsMono = JetBrains_Mono({
  variable: '--font-jetbrains-mono',
  subsets: ['latin'],
  weight: ['400', '500', '600', '700'],
  display: 'swap',
})

export const metadata: Metadata = {
  title: 'Acoustimator — Commercial Acoustics',
  description: 'AI-powered cost estimation for commercial acoustics projects',
}

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode
}>) {
  return (
    <html
      lang="en"
      className={`${spaceGrotesk.variable} ${jetbrainsMono.variable} h-full`}
    >
      <body className="h-full flex antialiased bg-[#080b10] text-[#d8e4f5]">
        <TooltipProvider>
          <Sidebar />
          <main className="flex-1 overflow-y-auto min-h-screen">{children}</main>
        </TooltipProvider>
      </body>
    </html>
  )
}
