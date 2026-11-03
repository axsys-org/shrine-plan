import { useState, useRef } from 'react'

interface StoredPhrase {
  phrase: string
  results: Array<{ name: string; value: number }>
  timestamp: number | string
  category?: string
  tags?: string[] | string
}

interface ExportButtonProps {
  phrases: StoredPhrase[]
  onImport?: (phrases: StoredPhrase[]) => void
}

export function ExportButton({ phrases, onImport }: ExportButtonProps) {
  const [showMenu, setShowMenu] = useState(false)

  const exportJSON = () => {
    const data = phrases.map(p => ({
      phrase: p.phrase,
      category: p.category || 'uncategorized',
      tags: typeof p.tags === 'string' ? p.tags.split(',').map(t => t.trim()).filter(Boolean) : p.tags || [],
      timestamp: p.timestamp,
      gematria: Object.fromEntries(p.results.map(r => [r.name, r.value]))
    }))
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `gematria-phrases-${new Date().toISOString().split('T')[0]}.json`
    a.click()
    URL.revokeObjectURL(url)
    setShowMenu(false)
  }

  const exportCSV = () => {
    // Sanitize CSV value to prevent formula injection
    const sanitizeCSV = (value: string | number): string => {
      const str = String(value)
      // Prefix dangerous characters to prevent formula execution in Excel
      if (/^[=+\-@\t\r]/.test(str)) {
        return "'" + str
      }
      // Escape quotes and wrap in quotes if contains special chars
      if (/[",\n\r]/.test(str)) {
        return `"${str.replace(/"/g, '""')}"`
      }
      return str
    }

    const headers = ['Phrase', 'Category', 'Tags', 'Timestamp']
    const cipherNames = phrases.length > 0 ? Object.keys(phrases[0].results.reduce((acc, r) => ({ ...acc, [r.name]: r.value }), {})) : []
    const allHeaders = [...headers, ...cipherNames]
    
    const rows = phrases.map(p => {
      const values: Record<string, string | number> = {
        Phrase: sanitizeCSV(p.phrase),
        Category: sanitizeCSV(p.category || 'uncategorized'),
        Tags: sanitizeCSV(typeof p.tags === 'string' ? p.tags : (p.tags || []).join(', ')),
        Timestamp: sanitizeCSV(String(p.timestamp))
      }
      p.results.forEach(r => {
        values[r.name] = sanitizeCSV(r.value)
      })
      return allHeaders.map(h => values[h] ?? '')
    })
    
    const csv = [allHeaders.join(','), ...rows.map(r => r.join(','))].join('\n')
    const blob = new Blob([csv], { type: 'text/csv' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `gematria-phrases-${new Date().toISOString().split('T')[0]}.csv`
    a.click()
    URL.revokeObjectURL(url)
    setShowMenu(false)
  }

  if (phrases.length === 0 && !onImport) return null

  return (
    <div className="relative">
      <button
        onClick={() => setShowMenu(!showMenu)}
        className="text-xs text-green-500 hover:text-green-300 transition-colors px-3 py-1 border border-green-700 rounded hover:border-green-500"
      >
        Export ({phrases.length})
      </button>
      {showMenu && (
        <div className="absolute right-0 mt-1 bg-black border border-green-800 rounded-lg shadow-lg z-50 min-w-[140px]">
          <button
            onClick={exportJSON}
            className="w-full text-left px-4 py-2 text-sm text-green-400 hover:bg-green-900/30 first:rounded-t-lg"
          >
            Export as JSON
          </button>
          <button
            onClick={exportCSV}
            className="w-full text-left px-4 py-2 text-sm text-green-400 hover:bg-green-900/30 last:rounded-b-lg"
          >
            Export as CSV
          </button>
        </div>
      )}
    </div>
  )
}

export function ImportButton({ onImport }: { onImport?: (phrases: StoredPhrase[]) => void }) {
  const [isImporting, setIsImporting] = useState(false)
  const [importProgress, setImportProgress] = useState({ current: 0, total: 0 })
  const fileInputRef = useRef<HTMLInputElement>(null)

  const API_URL = import.meta.env.PROD ? '/gematria' : 'http://localhost:8130/gematria'

  const handleImport = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0]
    if (!file) return

    // File size limit: 5MB
    if (file.size > 5 * 1024 * 1024) {
      alert('File too large. Maximum size is 5MB.')
      return
    }

    const session = localStorage.getItem('session')
    if (!session) {
      alert('Please sign in to import phrases')
      return
    }

    try {
      const text = await file.text()
      let data: unknown
      
      try {
        data = JSON.parse(text)
      } catch (e) {
        alert('Invalid JSON file. Please check the file format.')
        return
      }
      
      if (!Array.isArray(data)) {
        alert('Invalid file format. Expected a JSON array of phrases.')
        return
      }
      
      // Validate and sanitize each item to prevent prototype pollution
      const sanitizedData: StoredPhrase[] = []
      for (const item of data) {
        if (typeof item !== 'object' || item === null) continue
        
        // Check for dangerous keys that could cause prototype pollution
        const dangerousKeys = ['__proto__', 'constructor', 'prototype']
        const itemKeys = Object.keys(item as object)
        if (dangerousKeys.some(k => itemKeys.includes(k))) {
          console.warn('Skipping item with dangerous keys:', item)
          continue
        }
        
        // Basic validation
        const phrase = (item as any).phrase
        if (typeof phrase !== 'string' || phrase.length === 0 || phrase.length > 500) {
          continue
        }
        
        sanitizedData.push(item as StoredPhrase)
      }
      
      if (sanitizedData.length === 0) {
        alert('No valid phrases found in file.')
        return
      }

      setIsImporting(true)
      setImportProgress({ current: 0, total: sanitizedData.length })

      let imported = 0
      let skipped = 0
      const csrfToken = localStorage.getItem('csrfToken')

      for (const item of sanitizedData) {
        try {
          const response = await fetch(`${API_URL}/api/phrases`, {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
              'Authorization': `Bearer ${session}`,
              'X-CSRF-Token': csrfToken || ''
            },
            body: JSON.stringify({
              phrase: item.phrase,
              category: item.category || 'uncategorized',
              tags: item.tags || []
            })
          })

          if (response.ok || response.status === 200) {
            imported++
          } else {
            skipped++
          }
        } catch (err) {
          skipped++
        }

        setImportProgress(prev => ({ ...prev, current: prev.current + 1 }))
      }

      setIsImporting(false)
      setImportProgress({ current: 0, total: 0 })
      
      if (onImport) {
        onImport(sanitizedData)
      }
      
      alert(`Import complete!\n✓ Imported: ${imported}\n⊘ Skipped (already exists): ${skipped}`)
    } catch (err) {
      setIsImporting(false)
      setImportProgress({ current: 0, total: 0 })
      alert('Failed to parse file. Please ensure it is a valid JSON export.')
    }

    if (fileInputRef.current) {
      fileInputRef.current.value = ''
    }
  }

  return (
    <>
      <input
        type="file"
        ref={fileInputRef}
        accept=".json"
        onChange={handleImport}
        className="hidden"
      />
      <button
        onClick={() => fileInputRef.current?.click()}
        disabled={isImporting}
        className="text-xs text-amber-500 hover:text-amber-300 transition-colors px-3 py-1 border border-amber-700 rounded hover:border-amber-500 disabled:opacity-50"
      >
        {isImporting ? `Importing ${importProgress.current}/${importProgress.total}...` : 'Import'}
      </button>
    </>
  )
}
