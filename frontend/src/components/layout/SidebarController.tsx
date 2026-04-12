'use client'

import { useState, useCallback, useEffect } from 'react'
import { usePathname } from 'next/navigation'
import { Sidebar } from './Sidebar'
import { MobileHeader } from './MobileHeader'

// Routes that render without the sidebar shell (e.g. auth pages)
const NO_SIDEBAR_PATHS = ['/login']

interface SidebarControllerProps {
  children: React.ReactNode
}

export function SidebarController({ children }: SidebarControllerProps) {
  const pathname = usePathname()
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [collapsed, setCollapsed] = useState(false)

  // Read persisted collapsed state from localStorage on mount
  useEffect(() => {
    try {
      const stored = localStorage.getItem('sidebar-collapsed')
      if (stored !== null) setCollapsed(stored === 'true')
    } catch {
      // localStorage unavailable (SSR / private browsing) — ignore
    }
  }, [])

  // Cmd/Ctrl+B keyboard shortcut
  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent) {
      if ((e.metaKey || e.ctrlKey) && e.key === 'b') {
        e.preventDefault()
        toggleCollapsed()
      }
    }
    document.addEventListener('keydown', handleKeyDown)
    return () => document.removeEventListener('keydown', handleKeyDown)
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const handleToggle = useCallback(() => setSidebarOpen((v) => !v), [])
  const handleClose = useCallback(() => setSidebarOpen(false), [])

  function toggleCollapsed() {
    setCollapsed((c) => {
      const next = !c
      try {
        localStorage.setItem('sidebar-collapsed', String(next))
      } catch {
        // ignore
      }
      return next
    })
  }

  // Auth / standalone pages: render children directly without sidebar
  if (NO_SIDEBAR_PATHS.includes(pathname)) {
    return <>{children}</>
  }

  return (
    <div className="flex h-full">
      {/* Desktop sidebar — always rendered, mobile state handled inside */}
      <Sidebar
        isOpen={sidebarOpen}
        onClose={handleClose}
        collapsed={collapsed}
        onToggleCollapse={toggleCollapsed}
      />

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
