import SW from '@constants/sw'

// Shared by useApi.js and the handful of places that do their own
// try/catch around an API call instead of going through useApi().  A
// backend error is translated by its stable `code` (AppException) or
// `type` (a single Pydantic validation-error entry) — never by matching
// the raw message text, which is backend-supplied Swahili and won't track
// the active UI language. Falls back to that raw text only when the
// code/type has no entry in makosa.msimbo/aina yet, so nothing regresses
// to a blank message for a case this dictionary doesn't cover.
function resolveAppExceptionMessage(body) {
  const entry = SW.makosa.msimbo[body?.code]
  if (typeof entry === 'function') return entry(body?.params)
  if (typeof entry === 'string') return entry
  return typeof body?.detail === 'string' ? body.detail : null
}

function resolveValidationMessage(entry) {
  const mapped = SW.makosa.aina[entry?.type]
  if (typeof mapped === 'function') return mapped(entry?.ctx)
  if (typeof mapped === 'string') return mapped
  return (entry?.msg || '').replace(/^Value error,\s*/, '') || null
}

// Resolves any axios error (network failure, AppException response, or
// Pydantic 422 validation array) to a single message in the active UI
// language, for a component that isn't using useApi()'s own error handling.
export function resolveApiErrorMessage(err) {
  if (!err?.response) return SW.makosa.mtandao
  const raw = err.response.data?.detail
  if (Array.isArray(raw) && raw.length > 0) {
    return raw.map(resolveValidationMessage).filter(Boolean).join('; ') || SW.makosa.jumla
  }
  return resolveAppExceptionMessage(err.response.data) || SW.makosa.jumla
}

export { resolveAppExceptionMessage, resolveValidationMessage }
