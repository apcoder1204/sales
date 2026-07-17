import React, { useEffect, useState } from 'react'
import { Menu, Building2, ChevronDown, Languages } from 'lucide-react'
import { useAuth } from '@hooks/useAuth'
import { usePermission } from '@hooks/usePermission'
import { useBranch } from '@hooks/useBranch'
import { useLanguage } from '@hooks/useLanguage'
import { userService } from '@services/userService'
import SW from '@constants/sw'

export default function TopBar({ onMenuClick }) {
  const { user } = useAuth()
  const { isGlobal } = usePermission()
  const { activeBranchId, selectBranch, branches, setBranches } = useBranch()
  const { language, toggleLanguage } = useLanguage()
  const [dropOpen, setDropOpen] = useState(false)

  useEffect(() => {
    if (isGlobal) {
      userService.branches().then(setBranches).catch(() => {})
    }
  }, [isGlobal, setBranches])

  const activeBranch = branches.find((b) => b.id === activeBranchId)
  const branchLabel = activeBranch?.name || (isGlobal ? SW.common.ofisiYote : user?.branch || '')

  return (
    <header className="h-14 bg-bg-card border-b border-border flex items-center justify-between px-4 flex-shrink-0">
      <div className="flex items-center gap-3">
        <button onClick={onMenuClick} className="text-text-muted hover:text-text-primary transition-colors p-1.5 rounded-lg hover:bg-bg-hover">
          <Menu size={20} />
        </button>
        <div className="hidden sm:block">
          <p className="text-sm text-text-muted">
            <span className="text-text-primary font-medium">{SW.appName}</span>
          </p>
        </div>
      </div>

      <div className="flex items-center gap-3">
        <button
          onClick={toggleLanguage}
          title={language === 'sw' ? 'Switch to English' : 'Badilisha kwenda Kiswahili'}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-bg-panel border border-border text-sm text-text-secondary hover:text-text-primary hover:border-border-light transition-colors"
        >
          <Languages size={14} />
          <span className="font-medium">{language === 'sw' ? 'SW' : 'EN'}</span>
        </button>

        {isGlobal && (
          <div className="relative">
            <button
              onClick={() => setDropOpen((v) => !v)}
              className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-bg-panel border border-border text-sm text-text-secondary hover:text-text-primary hover:border-border-light transition-colors"
            >
              <Building2 size={14} />
              <span>{branchLabel}</span>
              <ChevronDown size={14} />
            </button>
            {dropOpen && (
              <div className="absolute right-0 top-full mt-2 w-56 glass-card shadow-glass z-50 py-1">
                <button
                  onClick={() => { selectBranch(null); setDropOpen(false) }}
                  className="w-full text-left px-4 py-2 text-sm text-text-secondary hover:text-text-primary hover:bg-bg-hover transition-colors"
                >
                  {SW.common.ofisiYote}
                </button>
                {branches.map((b) => (
                  <button
                    key={b.id}
                    onClick={() => { selectBranch(b.id); setDropOpen(false) }}
                    className="w-full text-left px-4 py-2 text-sm text-text-secondary hover:text-text-primary hover:bg-bg-hover transition-colors"
                  >
                    {b.name}
                  </button>
                ))}
              </div>
            )}
          </div>
        )}

        {!isGlobal && user?.branch && (
          <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-bg-panel border border-border text-sm text-text-secondary">
            <Building2 size={14} />
            <span>{user.branch}</span>
          </div>
        )}
      </div>
    </header>
  )
}
