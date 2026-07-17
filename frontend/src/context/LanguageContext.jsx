import React, { createContext, useState, useCallback } from 'react'
import { getLanguage, setLanguage as persistLanguage } from '@constants/sw'

export const LanguageContext = createContext(null)

export function LanguageProvider({ children }) {
  const [language, setLanguageState] = useState(getLanguage())

  const changeLanguage = useCallback((lang) => {
    persistLanguage(lang)
    setLanguageState(lang)
  }, [])

  const toggleLanguage = useCallback(() => {
    changeLanguage(language === 'sw' ? 'en' : 'sw')
  }, [language, changeLanguage])

  return (
    <LanguageContext.Provider value={{ language, changeLanguage, toggleLanguage }}>
      {children}
    </LanguageContext.Provider>
  )
}
