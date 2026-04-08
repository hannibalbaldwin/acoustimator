'use client'

import { useState, useCallback } from 'react'
import { Sidebar } from './Sidebar'
import { MobileHeader } from './MobileHeader'

interface SidebarControllerProps {
  children: React.ReactNode
}

export function SidebarController({ children }: SidebarControllerProps) {
  const [sidebarOpen, setSidebarOpen] = useState(false)

  const handleToggle = useCallback(() => setSidebarOpen((v) => !v), [])
  const handleClose = useCallback(() => setSidebarOpen(false), [])

  return (
    <div className="flex h-full">
      {/* Desktop sidebar — always rendered, mobile state handled inside */}
      <Sidebar isOpen={sidebarOpen} onClose={handleClose} />

      {/* Right side: mobile top bar + main content */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Mobile top bar */}
        <MobileHeader onToggle={handleToggle} />

        {/* Page content — add top padding on mobile to clear the header */}
        <main className="flex-1 overflow-y-auto min-h-screen pt-12 md:pt-0">
          {children}
        </main>
      </div>
    </div>
  )
}
