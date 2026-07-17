// Live, mutable UI-strings object. All feature files import the default
// export from this exact path (`@constants/sw`) as a plain object — kept that
// way on purpose so switching language doesn't require touching every file
// that does `import SW from '@constants/sw'`. Instead, this module owns a
// single shared object and rewrites its contents in place when the language
// changes; LanguageContext forces a full remount (see AppRouter.jsx) so every
// component re-reads the now-updated strings.
import swStrings from './translations/sw'
import enStrings from './translations/en'

export const LANGUAGES = { sw: swStrings, en: enStrings }
export const STORAGE_KEY = 'dukani_lang'

const SW = {}

function applyLanguage(lang) {
  const data = LANGUAGES[lang] || swStrings
  Object.keys(SW).forEach((k) => delete SW[k])
  Object.assign(SW, data)
}

export function getLanguage() {
  return localStorage.getItem(STORAGE_KEY) === 'en' ? 'en' : 'sw'
}

export function setLanguage(lang) {
  localStorage.setItem(STORAGE_KEY, lang)
  applyLanguage(lang)
}

applyLanguage(getLanguage())

export default SW
