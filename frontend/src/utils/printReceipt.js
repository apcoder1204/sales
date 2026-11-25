// Prints a receipt's inner HTML in a small popup window (the existing
// browser-print approach). The receipt markup uses Tailwind classes, which
// don't exist in the popup, so the few layout classes it relies on
// (.row, .text-center, .font-bold) are restated here.
const escapeHtml = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => (
  { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]
))

export function printHtml(title, innerHtml) {
  const win = window.open('', '_blank', 'width=400,height=600')
  if (!win) return
  win.document.write(`
    <html><head><title>${escapeHtml(title)}</title>
    <style>
      body { font-family: monospace; font-size: 12px; margin: 20px; }
      .text-center { text-align: center; }
      .row { display: flex; justify-content: space-between; gap: 8px; }
      .font-bold { font-weight: bold; }
      .pl-2 { padding-left: 8px; }
      .banner { text-align: center; font-weight: bold; border: 2px solid #000; padding: 4px; margin: 6px 0; }
      hr, .divider { border: 0; border-top: 1px dashed #000; margin: 8px 0; }
      p { margin: 2px 0; }
    </style></head>
    <body>${innerHtml || ''}</body></html>
  `)
  win.document.close()
  win.print()
  win.close()
}
