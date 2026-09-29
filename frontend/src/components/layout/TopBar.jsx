import React, { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Menu, Building2, ChevronDown, Languages, User as UserIcon, LogOut } from 'lucide-react'
import { useAuth } from '@hooks/useAuth'
import { usePermission } from '@hooks/usePermission'
import { useBranch } from '@hooks/useBranch'
import { useLanguage } from '@hooks/useLanguage'
import { useToast } from '@hooks/useToast'
import { userService } from '@services/userService'
import Avatar from '@components/ui/Avatar'
import SW from '@constants/sw'

export default function TopBar({ onMenuClick }) {
  const { user, logout } = useAuth()
  const { isGlobal } = usePermission()
  const { activeBranchId, selectBranch, branches, setBranches } = useBranch()
  const { language, toggleLanguage } = useLanguage()
  const toast = useToast()
  const navigate = useNavigate()
  const [dropOpen, setDropOpen] = useState(false)
  const [userMenuOpen, setUserMenuOpen] = useState(false)

  const handleLogout = async () => {
    setUserMenuOpen(false)
    await logout()
    navigate('/login')
    toast.info(SW.mafanikio.umefanikiwaKutoka)
  }

  useEffect(() => {
    if (isGlobal) {
      userService.branches().then(setBranches).catch(() => {})
    }
  }, [isGlobal, setBranches])

  const activeBranch = branches.find((b) => b.id === activeBranchId)
  const branchLabel = activeBranch?.name || (isGlobal ? SW.common.ofisiYote : user?.branch || '')

  return (
    <header className="h-14 bg-bg-card border-b border-border flex items-center px-4 gap-2 flex-shrink-0">
      <div className="flex items-center gap-3 flex-1 min-w-0">
        <button onClick={onMenuClick} className="text-text-muted hover:text-text-primary transition-colors p-1.5 rounded-lg hover:bg-bg-hover flex-shrink-0">
          <Menu size={20} />
        </button>
        <div className="hidden sm:block min-w-0">
          <p className="text-sm text-text-muted truncate">
            <span className="text-text-primary font-medium">{SW.appName}</span>
          </p>
        </div>
      </div>

      {/* Branch context selector — kept centered per the app's header
          convention; still the single source of truth for branch context
          (useBranch/BranchContext), just repositioned. */}
      <div className="flex items-center justify-center flex-shrink-0">
        {isGlobal && (
          <div className="relative">
            <button
              onClick={() => { setDropOpen((v) => !v); setUserMenuOpen(false) }}
              className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-bg-panel border border-border text-sm text-text-secondary hover:text-text-primary hover:border-border-light transition-colors"
            >
              <Building2 size={14} className="flex-shrink-0" />
              <span className="max-w-[120px] sm:max-w-[220px] truncate">{branchLabel}</span>
              <ChevronDown size={14} className="flex-shrink-0" />
            </button>
            {dropOpen && (
              <div className="absolute left-1/2 -translate-x-1/2 top-full mt-2 w-56 glass-card shadow-glass z-50 py-1">
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
            <Building2 size={14} className="flex-shrink-0" />
            <span className="max-w-[120px] sm:max-w-[220px] truncate">{user.branch}</span>
          </div>
        )}
      </div>

      <div className="flex items-center gap-3 flex-1 min-w-0 justify-end">
        <button
          onClick={toggleLanguage}
          title={language === 'sw' ? SW.common.badilishaKwendaKiingereza : SW.common.badilishaKwendaKiswahili}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-bg-panel border border-border text-sm text-text-secondary hover:text-text-primary hover:border-border-light transition-colors flex-shrink-0"
        >
          <Languages size={14} />
          <span className="font-medium">{language === 'sw' ? 'SW' : 'EN'}</span>
        </button>

        <div className="relative flex-shrink-0">
          <button
            onClick={() => { setUserMenuOpen((v) => !v); setDropOpen(false) }}
            className="flex items-center gap-2 pl-1 pr-2 py-1 rounded-lg hover:bg-bg-hover transition-colors"
          >
            <Avatar name={user?.full_name || ''} size="sm" />
            <div className="hidden sm:block text-left leading-tight">
              <p className="text-sm font-medium text-text-primary">{user?.full_name}</p>
              <p className="text-[11px] text-text-muted">{SW.majukumu[user?.role] || user?.role}</p>
            </div>
            <ChevronDown size={14} className="hidden sm:block text-text-muted" />
          </button>
          {userMenuOpen && (
            <div className="absolute right-0 top-full mt-2 w-48 glass-card shadow-glass z-50 py-1">
              <button
                onClick={() => { navigate('/wasifu'); setUserMenuOpen(false) }}
                className="w-full flex items-center gap-2.5 text-left px-4 py-2 text-sm text-text-secondary hover:text-text-primary hover:bg-bg-hover transition-colors"
              >
                <UserIcon size={15} />
                {SW.nav.wasifu}
              </button>
              <button
                onClick={handleLogout}
                className="w-full flex items-center gap-2.5 text-left px-4 py-2 text-sm text-accent-red hover:bg-accent-red-muted transition-colors"
              >
                <LogOut size={15} />
                {SW.nav.toka}
              </button>
            </div>
          )}
        </div>
      </div>
    </header>
  )
}
