import { useState, useEffect, useMemo, useRef, useLayoutEffect } from 'react'
import { calculateAll, type CipherResult, validatePhrase, tripleNumbers, cipherDisplayNames } from '@gematria/shared'
import type { User, StoredPhrase } from './App'
import {
  DndContext,
  closestCenter,
  KeyboardSensor,
  PointerSensor,
  TouchSensor,
  useSensor,
  useSensors,
  type DragEndEvent,
} from '@dnd-kit/core'
import {
  arrayMove,
  SortableContext,
  sortableKeyboardCoordinates,
  useSortable,
  rectSortingStrategy,
  horizontalListSortingStrategy,
} from '@dnd-kit/sortable'
import { CSS } from '@dnd-kit/utilities'

const API_URL = import.meta.env.PROD ? '/gematria' : 'http://localhost:8130/gematria'
// Plexenomy: encode n using 0=2, (x)=x-th prime, juxtaposition=product, factors descending
const PLEX_DIGIT_CAP = 1_000_000_000_000
const SIEVE_MAX = 5_000_000
const _primes: number[] = []
const _primeToIndex: Map<number, number> = new Map()
let _maxPrime = 0

function ensurePrimes(limit: number): void {
  if (limit <= _maxPrime) return
  if (limit > SIEVE_MAX) return
  const size = Math.max(limit, _maxPrime * 2, 100)
  const sieve = new Uint8Array(size + 1).fill(1)
  sieve[0] = sieve[1] = 0
  for (let i = 2; i * i <= size; i++) {
    if (sieve[i]) {
      for (let j = i * i; j <= size; j += i) sieve[j] = 0
    }
  }
  _primes.length = 0
  _primeToIndex.clear()
  for (let i = 2; i <= size; i++) {
    if (sieve[i]) {
      _primeToIndex.set(i, _primes.length + 1)
      _primes.push(i)
    }
  }
  _maxPrime = size
}

function primeIndex(p: number): number | null {
  if (p > _maxPrime) ensurePrimes(Math.max(p, Math.ceil(Math.sqrt(p)) + 100) * 2)
  const idx = _primeToIndex.get(p)
  if (idx) return idx
  if (p >= SIEVE_MAX) return null
  const oldMax = _maxPrime
  ensurePrimes(p * 2)
  if (_maxPrime <= oldMax) return null
  return primeIndex(p)
}

function factorizeDesc(n: number): number[] {
  const needed = Math.min(Math.ceil(Math.sqrt(n)) + 1000, SIEVE_MAX)
  if (needed > _maxPrime) ensurePrimes(needed)
  const factors: number[] = []
  let remaining = n
  for (const p of _primes) {
    if (p * p > remaining) break
    while (remaining % p === 0) {
      factors.push(p)
      remaining /= p
    }
  }
  if (remaining > 1) factors.push(remaining)
  return factors.sort((a, b) => b - a)
}

function plexenomy(n: number): string {
  if (Math.abs(n).toString().length >= 13) return 'Too high!'
  if (n < 2) return n.toString()
  if (n === 2) return '0'
  const factors = factorizeDesc(n)
  let result = ''
  for (const p of factors) {
    if (p === 2) {
      result += '0'
    } else {
      const idx = primeIndex(p)
      if (idx === null) {
        result += '[' + p + ']'
      } else {
        result += '(' + plexenomy(idx) + ')'
      }
    }
  }
  return result
}

function nthPrime(n: number): number {
  if (n < 1) return 0
  while (_primes.length < n) {
    ensurePrimes(_maxPrime === 0 ? 100 : _maxPrime * 2)
  }
  return _primes[n - 1]
}

function decodePlexenomy(s: string): number {
  s = s.replace(/\s+/g, '')
  let pos = 0
  function parseExpr(): number {
    let result = 1
    let hasTerms = false
    while (pos < s.length && (s[pos] === '0' || s[pos] === '(')) {
      hasTerms = true
      result *= parseTerm()
      if (result >= PLEX_DIGIT_CAP) throw new Error('too high')
    }
    if (!hasTerms) throw new Error('empty')
    return result
  }
  function parseTerm(): number {
    if (s[pos] === '0') {
      pos++
      return 2
    }
    if (s[pos] === '(') {
      pos++
      const inner = parseExpr()
      if (pos >= s.length || s[pos] !== ')') throw new Error('missing )')
      pos++
      const p = nthPrime(inner)
      if (p >= PLEX_DIGIT_CAP) throw new Error('too high')
      return p
    }
    throw new Error('unexpected')
  }
  const result = parseExpr()
  if (pos !== s.length) throw new Error('trailing')
  return result
}

function hasBalancedParens(s: string): boolean {
  let depth = 0
  for (const ch of s) {
    if (ch === '(') depth++
    else if (ch === ')') depth--
    if (depth < 0) return false
  }
  return depth === 0
}


interface CalculatorProps {
  user: User | null
  setUser: React.Dispatch<React.SetStateAction<User | null>>
  storedPhrases: StoredPhrase[]
  setStoredPhrases: React.Dispatch<React.SetStateAction<StoredPhrase[]>>
  userCategories: string[]
  setUserCategories: React.Dispatch<React.SetStateAction<string[]>>
}

// Cipher groups
const alphanumericCiphers = [
  'Alphanumeric Qabbala',
  'Ordinal',
  'AQ Primes',
  'AQ Squares', 
  'AQ Trigonal',
]

const qwertyCiphers = [
  'Numeric QWERTY',
  'QWERTY',
  'NQ Primes',
  'NQ Squares',
  'NQ Trigonal',
]

const otherCiphers = [
  'Synx',
  'Unun',
  'Vaxen',
  'Based Atlanteanism',
  'Satanic',
  'Standard',
  'Reduction',
]

const allCipherList = [...alphanumericCiphers, ...qwertyCiphers, ...otherCiphers]

// Default cipher order for reset
const defaultCipherOrder = [
  'Alphanumeric Qabbala',
  'Ordinal',
  'AQ Primes',
  'AQ Squares',
  'AQ Trigonal',
  'Numeric QWERTY',
  'QWERTY',
  'NQ Primes',
  'NQ Squares',
  'NQ Trigonal',
  'Standard',
  'Reduction',
  'Synx',
  'Unun',
  'Vaxen',
  'Based Atlanteanism',
  'Satanic',
]

const cipherColors: Record<string, { name: string; value: string; bg: string; gradient: string; border: string }> = {
  'Alphanumeric Qabbala': { name: 'text-stone-300', value: 'text-stone-100', bg: 'bg-stone-900/30', gradient: 'from-[rgba(61,53,40,0.3)] to-[rgba(42,38,32,0.3)]', border: 'border-stone-400/40' },
  'AQ Squares': { name: 'text-stone-300', value: 'text-stone-100', bg: 'bg-stone-900/30', gradient: 'from-[rgba(61,53,40,0.3)] to-[rgba(42,38,32,0.3)]', border: 'border-stone-400/40' },
  'AQ Primes': { name: 'text-stone-300', value: 'text-stone-100', bg: 'bg-stone-900/30', gradient: 'from-[rgba(61,53,40,0.3)] to-[rgba(42,38,32,0.3)]', border: 'border-stone-400/40' },
  'AQ Trigonal': { name: 'text-stone-300', value: 'text-stone-100', bg: 'bg-stone-900/30', gradient: 'from-[rgba(61,53,40,0.3)] to-[rgba(42,38,32,0.3)]', border: 'border-stone-400/40' },
  'Ordinal': { name: 'text-stone-200', value: 'text-stone-100', bg: 'bg-stone-700/30', gradient: 'from-[rgba(90,80,72,0.3)] to-[rgba(64,56,48,0.3)]', border: 'border-stone-400/40' },
  'Numeric QWERTY': { name: 'text-green-400', value: 'text-green-200', bg: 'bg-green-950/30', gradient: 'from-[rgba(26,74,26,0.3)] to-[rgba(10,42,10,0.3)]', border: 'border-green-500/40' },
  'NQ Squares': { name: 'text-[#5A9B5A]', value: 'text-[#7ABD7A]', bg: 'bg-[rgba(15,37,16,0.3)]', gradient: 'from-[rgba(31,69,32,0.3)] to-[rgba(15,37,16,0.3)]', border: 'border-[#5A9B5A]/40' },
  'NQ Primes': { name: 'text-[#6ABD6A]', value: 'text-[#8BDF8B]', bg: 'bg-[rgba(26,53,26,0.3)]', gradient: 'from-[rgba(42,85,48,0.3)] to-[rgba(26,53,26,0.3)]', border: 'border-[#6ABD6A]/40' },
  'NQ Trigonal': { name: 'text-[#8BDF8B]', value: 'text-[#ABFFAB]', bg: 'bg-[rgba(42,69,42,0.3)]', gradient: 'from-[rgba(58,101,64,0.3)] to-[rgba(42,69,42,0.3)]', border: 'border-[#8BDF8B]/40' },
  'QWERTY': { name: 'text-lime-400', value: 'text-lime-200', bg: 'bg-lime-950/30', gradient: 'from-[rgba(42,74,10,0.3)] to-[rgba(26,42,0,0.3)]', border: 'border-lime-500/40' },
  'Standard': { name: 'text-[#E8A830]', value: 'text-[#F8C040]', bg: 'bg-[rgba(61,40,21,0.3)]', gradient: 'from-[rgba(90,64,32,0.3)] to-[rgba(61,40,21,0.3)]', border: 'border-[#E8A830]/40' },
  'Satanic': { name: 'text-red-500', value: 'text-red-300', bg: 'bg-red-950/30', gradient: 'from-[rgba(74,10,10,0.3)] to-[rgba(42,0,0,0.3)]', border: 'border-red-600/40' },
  'Synx': { name: 'text-cyan-400', value: 'text-cyan-200', bg: 'bg-cyan-950/30', gradient: 'from-[rgba(10,74,74,0.3)] to-[rgba(0,42,42,0.3)]', border: 'border-cyan-500/40' },
  'Vaxen': { name: 'text-violet-400', value: 'text-violet-200', bg: 'bg-violet-950/30', gradient: 'from-[rgba(74,10,74,0.3)] to-[rgba(42,0,42,0.3)]', border: 'border-violet-500/40' },
  'Unun': { name: 'text-indigo-400', value: 'text-indigo-200', bg: 'bg-indigo-950/30', gradient: 'from-[rgba(49,46,129,0.3)] to-[rgba(30,27,75,0.3)]', border: 'border-indigo-500/40' },
  'Based Atlanteanism': { name: 'text-amber-500', value: 'text-amber-300', bg: 'bg-amber-950/30', gradient: 'from-[rgba(74,53,10,0.3)] to-[rgba(42,26,0,0.3)]', border: 'border-amber-500/40' },
  'Reduction': { name: 'text-[#F0B840]', value: 'text-[#F8D060]', bg: 'bg-[rgba(74,50,32,0.3)]', gradient: 'from-[rgba(106,80,48,0.3)] to-[rgba(74,50,32,0.3)]', border: 'border-[#F0B840]/40' },
}

// Font options for each row - you can choose which font goes where:
// Row 1 (AQ) Font Options: 'Crimson Text' (current), 'Courier Prime', 'IBM Plex Mono'
// Row 2 (NQ) Font Options: 'JetBrains Mono' (current), 'Space Mono', 'Roboto Mono', 'VT323', 'IBM Plex Mono', 'Cutive Mono'
// Individual NQ cipher fonts - all set to IBM Plex Mono per user request
const nqCipherFonts: Record<string, string> = {
  'Numeric QWERTY': "'IBM Plex Mono', monospace",
  'NQ Primes': "'IBM Plex Mono', monospace",
  'NQ Squares': "'IBM Plex Mono', monospace",
  'NQ Trigonal': "'IBM Plex Mono', monospace",
  'QWERTY': "'IBM Plex Mono', monospace",
}

// Individual AQ cipher fonts - all set to Courier Prime (Ordinal's font) per user request
const aqCipherFonts: Record<string, string> = {
  'Alphanumeric Qabbala': "'Courier Prime', monospace",
  'Ordinal': "'Courier Prime', monospace",
  'AQ Primes': "'Courier Prime', monospace",
  'AQ Squares': "'Courier Prime', monospace",
  'AQ Trigonal': "'Courier Prime', monospace",
}

function SortableCipherCard({ 
  cipherName, 
  result, 
  shouldHighlight,
  fontFamily,
  onHide
}: { 
  cipherName: string
  result: CipherResult
  shouldHighlight: boolean
  fontFamily?: string
  onHide?: () => void
}) {
  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    transition,
    isDragging,
  } = useSortable({ id: cipherName })

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
  }
  
  const lastTapRef = useRef(0)

  const colors = cipherColors[cipherName]
  const { value } = result
  const isBased = cipherName === 'Based Atlanteanism'
  const baIntermediate = isBased ? value * 9 : null

  const handleContextMenu = (e: React.MouseEvent) => {
    e.preventDefault()
    e.stopPropagation()
    if (onHide) {
      onHide()
    }
  }

  const handleTap = (e: React.MouseEvent | React.TouchEvent) => {
    if (isDragging) return
    const now = Date.now()
    if (now - lastTapRef.current < 300) {
      e.preventDefault()
      e.stopPropagation()
      lastTapRef.current = 0
      if (onHide) onHide()
    } else {
      lastTapRef.current = now
    }
  }

  const numberFontMap: Record<string, string> = {
    'Alphanumeric Qabbala': "'IBM Plex Mono', monospace",
    'Ordinal': "'IBM Plex Mono', monospace",
    'AQ Squares': "'IBM Plex Mono', monospace",
    'AQ Primes': "'IBM Plex Mono', monospace",
    'AQ Trigonal': "'IBM Plex Mono', monospace",
    'Numeric QWERTY': "'IBM Plex Mono', monospace",
    'QWERTY': "'IBM Plex Mono', monospace",
    'NQ Squares': "'IBM Plex Mono', monospace",
    'NQ Primes': "'IBM Plex Mono', monospace",
    'NQ Trigonal': "'IBM Plex Mono', monospace",
    'Standard': "'IBM Plex Mono', monospace",
    'Satanic': "'IBM Plex Mono', monospace",
    'Synx': "'IBM Plex Mono', monospace",
    'Vaxen': "'IBM Plex Mono', monospace",
    'Unun': "'IBM Plex Mono', monospace",
    'Based Atlanteanism': "'IBM Plex Mono', monospace",
    'Reduction': "'IBM Plex Mono', monospace",
  }
  const numberFont = numberFontMap[cipherName] || "'JetBrains Mono', monospace"

  return (
    <div
      ref={setNodeRef}
      style={style}
      {...attributes}
      {...listeners}
      onContextMenu={handleContextMenu}
      onClick={handleTap}
      className={`
        bg-gradient-to-br ${colors.gradient}
        px-2 py-2 sm:px-3 sm:py-2 cursor-move rounded-none border border-green-500/30
        shadow-[0_4px_0_rgba(0,0,0,0.4),0_6px_6px_rgba(0,0,0,0.3)]
        hover:translate-y-[2px] hover:shadow-[0_2px_0_rgba(0,0,0,0.4),0_3px_3px_rgba(0,0,0,0.3),0_0_15px_rgba(74,222,128,0.3)]
        active:translate-y-[4px] active:shadow-[0_0px_0_rgba(0,0,0,0.4)]
        active:cursor-grabbing active:scale-95
        transition-all duration-200
        flex flex-col items-center justify-center min-w-0 sm:min-w-[80px] select-none [touch-action:manipulation]
        ${isDragging ? 'opacity-50 shadow-2xl ring-2 ring-white/20' : ''}
        ${shouldHighlight ? 'shadow-lg shadow-amber-500/50 ring-2 ring-amber-500/50 animate-pulse bg-amber-900/30' : ''}
      `}
    >
      <span 
        className={`${colors.name} text-xs sm:text-sm font-medium text-center leading-tight mb-1`}
        style={{ 
          fontFamily: fontFamily || "'JetBrains Mono', monospace",
          textShadow: '0 2px 4px rgba(0,0,0,0.5), 0 0 8px rgba(0,0,0,0.3)'
        }}
      >
        {cipherDisplayNames[cipherName] || cipherName}
      </span>
      <span 
        className={`${shouldHighlight ? 'text-amber-400' : colors.value} text-xl sm:text-lg font-bold tabular-nums leading-none`}
        style={{ 
          fontFamily: numberFont,
          textShadow: shouldHighlight ? '0 2px 4px rgba(0,0,0,0.6), 0 0 12px rgba(251, 191, 36, 0.6)' : '0 2px 4px rgba(0,0,0,0.6), 0 0 12px rgba(0,0,0,0.4)'
        }}
      >
        {isBased ? <span className="flex flex-col items-center leading-tight"><span className={`text-xs leading-none ${shouldHighlight ? 'text-amber-400/70' : 'opacity-70'}`} style={shouldHighlight ? { textShadow: '0 0 8px rgba(251, 191, 36, 0.8), 0 0 16px rgba(251, 191, 36, 0.4)' } : {}}>{baIntermediate}/9</span><span className="leading-none">{value}</span></span> : value}
      </span>
    </div>
  )
}

function SortableTableHeader({
  cipher,
  colors,
  onContextMenu,
  columnWidth
}: {
  cipher: string
  colors: { name: string; value: string; bg: string; gradient: string; border: string }
  onContextMenu: (e: React.MouseEvent) => void
  columnWidth: string
}) {
  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    transition,
    isDragging,
  } = useSortable({ id: cipher })

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
  }

  return (
    <th
      ref={setNodeRef}
      {...attributes}
      {...listeners}
      onContextMenu={onContextMenu}
      className={`
        px-2 py-2 text-center text-[10px] ${colors.name} border border-green-800/40
        cursor-move hover:bg-green-900/30 select-none
        ${isDragging ? 'opacity-50 ring-2 ring-white/20 bg-green-900/40' : ''}
      `}
      style={{ 
        ...style,
        width: columnWidth
      }}
    >
      {cipherDisplayNames[cipher] || cipher}
    </th>
  )
}

interface SaveDialogProps {
  userCategories: string[]
  setUserCategories: React.Dispatch<React.SetStateAction<string[]>>
  user: User | null
  saveCategory: string
  setSaveCategory: (cat: string) => void
  saveTags: string
  setSaveTags: (tags: string) => void
  phrase: string
  validationError: string
  existingPhraseWarning: string | null
  onCancel: () => void
  onSave: () => void
}

function SaveDialog({ 
  userCategories, 
  setUserCategories, 
  user, 
  saveCategory, 
  setSaveCategory,
  saveTags,
  setSaveTags,
  phrase,
  validationError,
  existingPhraseWarning,
  onCancel,
  onSave
}: SaveDialogProps) {
  const [localCategories, setLocalCategories] = useState<string[]>(userCategories)
  const [isLoading, setIsLoading] = useState(true)

  useEffect(() => {
    const fetchCategories = async () => {
      const session = localStorage.getItem('session')
      if (!session || !user) {
        setIsLoading(false)
        return
      }
      
      try {
        const response = await fetch(`${API_URL}/api/categories`, {
          headers: { 'Authorization': `Bearer ${session}` }
        })
        
        if (response.ok) {
          const data = await response.json()
          const allCategories = ['uncategorized', ...data.filter((c: string) => c !== 'uncategorized')]
          setLocalCategories(allCategories)
          setUserCategories(allCategories)
        } else {
          setLocalCategories(userCategories)
        }
      } catch (error) {
        console.error('Failed to fetch categories:', error)
        setLocalCategories(userCategories)
      }
      setIsLoading(false)
    }
    
    fetchCategories()
  }, [user, setUserCategories, userCategories])

  return (
    <div 
      className="fixed inset-0 bg-black/90 backdrop-blur-sm flex items-center justify-center z-50 p-4"
      onClick={(e) => {
        if (e.target === e.currentTarget) {
          onCancel()
        }
      }}
    >
      <div className="bg-black rounded-2xl p-8 w-full max-w-md border border-green-500 shadow-2xl shadow-green-500/20">
        <h2 className="text-2xl font-bold mb-6 text-green-400">Save Phrase</h2>
        
        <div className="mb-4">
          <p className="text-green-600 text-sm mb-2">Phrase:</p>
          <p className="text-green-300 font-medium">{phrase}</p>
        </div>
        
        {existingPhraseWarning && (
          <div className="mb-4 bg-amber-500/20 border border-amber-500/50 text-amber-400 px-4 py-3 rounded-lg">
            <span className="font-bold">⚠️ Warning:</span> {existingPhraseWarning}
          </div>
        )}
        
        {validationError && (
          <div className="mb-4 bg-red-500/20 border border-red-500/50 text-red-400 px-4 py-3 rounded-lg">
            {validationError}
          </div>
        )}
        
        {isLoading ? (
          <div className="text-green-500 text-center py-4">Loading folders...</div>
        ) : (
          <div className="space-y-4">
             <div>
               <label className="block text-sm text-green-500 mb-2">Tags (comma-separated)</label>
               <input
                 type="text"
                 value={saveTags}
                 onChange={(e) => {
                   // Only allow alphanumeric, commas, spaces, and hyphens
                   const sanitized = e.target.value.replace(/[^a-zA-Z0-9,\s-]/g, '')
                   setSaveTags(sanitized)
                 }}
                 placeholder="e.g., bible, prophecy, 666"
                 className="w-full px-4 py-3 bg-black border border-green-600 rounded-lg focus:border-green-400 focus:outline-none focus:ring-2 focus:ring-green-500/20 transition-all text-green-400"
               />
             </div>
            
            <div>
              <label className="block text-sm text-green-500 mb-2">Category/Folder ({localCategories.length} folders available)</label>
              <select
                value={saveCategory}
                onChange={(e) => setSaveCategory(e.target.value)}
                className="w-full px-4 py-3 bg-black border border-green-600 rounded-lg focus:border-green-400 focus:outline-none focus:ring-2 focus:ring-green-500/20 transition-all text-green-400"
              >
                {localCategories.map(cat => (
                  <option key={cat} value={cat}>{cat}</option>
                ))}
              </select>
            </div>
          </div>
        )}
        
        <div className="flex gap-3 pt-6">
          <button
            type="button"
            onClick={onCancel}
            className="flex-1 px-4 py-3 text-green-500 hover:text-green-300 transition-colors"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={onSave}
            disabled={isLoading}
            className="flex-1 px-4 py-3 bg-gradient-to-r from-green-500 to-emerald-500 hover:from-green-400 hover:to-emerald-400 text-black font-bold rounded-lg transition-all disabled:opacity-50"
          >
            Save
          </button>
        </div>
        
        {!user ? (
          <div className="mt-6 pt-6 border-t border-green-800">
            <p className="text-green-600 text-sm text-center mb-4">
              To save phrases permanently and access them from anywhere, please sign in or create an account.
            </p>
          </div>
        ) : null}
      </div>
    </div>
  )
}

export function Calculator({ user, setUser, storedPhrases, setStoredPhrases, userCategories, setUserCategories }: CalculatorProps) {
  const [phrase, setPhraseState] = useState('')
  
  // Wrap setPhrase to filter out suspicious clipboard pastes
  const setPhrase = (value: string | ((prev: string) => string)) => {
    const newValue = typeof value === 'function' ? value(phrase) : value
    
    // Filter out values that look like copied cipher results
    // These patterns indicate accidental clipboard paste
    if (newValue.includes(' = ') && (newValue.includes('(Ordinal)') || newValue.includes('(AQ') || newValue.includes('(Alphanumeric') || newValue.includes('(Numeric'))) {
      return // Don't update
    }
    
    setPhraseState(value)
  }
  const [alphanumericCipherOrder, _setAlphanumericCipherOrder] = useState<string[]>(() => {
    const saved = localStorage.getItem('alphanumericCipherOrder')
    return saved ? JSON.parse(saved) : alphanumericCiphers
  })
  const [qwertyCipherOrder, _setQwertyCipherOrder] = useState<string[]>(() => {
    const saved = localStorage.getItem('qwertyCipherOrder')
    return saved ? JSON.parse(saved) : qwertyCiphers
  })
  const [otherCipherOrder, _setOtherCipherOrder] = useState<string[]>(() => {
    const saved = localStorage.getItem('otherCipherOrder')
    return saved ? JSON.parse(saved) : otherCiphers
  })
  // Unified cipher order for single grid
  const [unifiedCipherOrder, setUnifiedCipherOrder] = useState<string[]>(() => {
    const saved = localStorage.getItem('unifiedCipherOrder')
    return saved ? JSON.parse(saved) : [...alphanumericCiphers, ...qwertyCiphers, ...otherCiphers]
  })
  const [hiddenCiphers, setHiddenCiphers] = useState<Set<string>>(() => {
    const saved = localStorage.getItem('hiddenCiphers')
    return saved ? new Set(JSON.parse(saved)) : new Set()
  })
  const [hiddenTableColumns, setHiddenTableColumns] = useState<Set<string>>(new Set())
  const [hiddenCellValues, setHiddenCellValues] = useState<Set<string>>(new Set())
  const [tableColumnOrder, setTableColumnOrder] = useState<string[]>(() => {
    const saved = localStorage.getItem('tableColumnOrder')
    return saved ? JSON.parse(saved) : allCipherList
  })
  const [contextMenu, setContextMenu] = useState<{
    visible: boolean
    x: number
    y: number
    cipherName: string | null
    type: 'cipher' | 'cell' | 'table-column' | null
  }>({
    visible: false,
    x: 0,
    y: 0,
    cipherName: null,
    type: null
  })
  const [showAuth, setShowAuth] = useState(false)
  const [authMode, setAuthMode] = useState<'login' | 'register'>('login')
  const [authForm, setAuthForm] = useState({ username: '', password: '' })
  const [authError, setAuthError] = useState('')
  const [justStored, setJustStored] = useState(false)
  const [showSaveDialog, setShowSaveDialog] = useState(false)
  const [saveTags, setSaveTags] = useState('')
  const [saveCategory, setSaveCategory] = useState('uncategorized')
  const [showLoginPrompt, setShowLoginPrompt] = useState(false)
  const [validationError, setValidationError] = useState<string>('')
  const [existingPhraseWarning, setExistingPhraseWarning] = useState<string | null>(null)
  const [highlightedValue, setHighlightedValue] = useState<number | null>(null)
  const [highlightedPhrases, setHighlightedPhrases] = useState<string[]>(() => {
    const saved = localStorage.getItem('highlightedPhrases')
    return saved ? JSON.parse(saved) : []
  })
  const [userHighlightedValues, setUserHighlightedValues] = useState<number[]>(() => {
    const saved = localStorage.getItem('userHighlightedValues')
    return saved ? JSON.parse(saved) : []
  })
  const [disabledDefaultValues, setDisabledDefaultValues] = useState<number[]>(() => {
    const saved = localStorage.getItem('disabledDefaultValues')
    return saved ? JSON.parse(saved) : []
  })
  const [hasClickedCog, setHasClickedCog] = useState(() => localStorage.getItem('cogClicked') === 'true')
  const [plexenomyCipherLine1, setPlexenomyCipherLine1] = useState<string>(() => {
    const saved = localStorage.getItem('plexenomyCipherLine1')
    return saved && allCipherList.includes(saved) ? saved : 'Alphanumeric Qabbala'
  })
  const [plexenomyCipherLine2, setPlexenomyCipherLine2] = useState<string>(() => {
    const saved = localStorage.getItem('plexenomyCipherLine2')
    return saved && allCipherList.includes(saved) ? saved : 'Synx'
  })

  // Helper function to check if a value should be highlighted
  const shouldHighlightValue = (value: number): boolean => {
    // User-added values are always highlighted
    if (userHighlightedValues.includes(value)) return true
    // Default triple numbers are highlighted only if not disabled
    if (tripleNumbers.includes(value) && !disabledDefaultValues.includes(value)) return true
    return false
  }

  const [showPhraseSettings, setShowPhraseSettings] = useState(false)
  const [newHighlightPhrase, setNewHighlightPhrase] = useState('')
  const [showValueSettings, setShowValueSettings] = useState(false)
  const [newHighlightValue, setNewHighlightValue] = useState('')
  const [showHelp, setShowHelp] = useState(false)
  const [helpTab, setHelpTab] = useState<'guide' | 'cipherkey'>('guide')
  const [selectedCipherKey, setSelectedCipherKey] = useState<string>('Alphanumeric Qabbala')
  const [showCipherDropdown, setShowCipherDropdown] = useState(false)
  const [showExtrasDropdown, setShowExtrasDropdown] = useState(false)
  const [showDiscoveryModal, setShowDiscoveryModal] = useState(false)
  const [discoveryInfo, setDiscoveryInfo] = useState<{phrase: string; discovered_by: string; is_new: boolean} | null>(null)
  const [phraseColumnWidth, setPhraseColumnWidth] = useState<number>(200)
  const [isResizing, setIsResizing] = useState<boolean>(false)
  
  // Query functionality state
  const [searchResults, setSearchResults] = useState<Array<{
    phrase: string
    discoveredBy: string
    discoveredAt: string
    ciphers: Record<string, number>
  }>>([])
  const [showResults, setShowResults] = useState(false)
  const [hoveredResult, setHoveredResult] = useState<string | null>(null)
  const [hiddenCiphersExpanded, setHiddenCiphersExpanded] = useState(false)
  const [activeLetterFilter, setActiveLetterFilter] = useState<string | null>(null)
  const [activeWordCountFilter, setActiveWordCountFilter] = useState<number | null>(null)
  const [searchPage, setSearchPage] = useState(0)
  const [hasMoreResults, setHasMoreResults] = useState(false)
  const [isLoadingMore, setIsLoadingMore] = useState(false)
  const [totalSearchResults, setTotalSearchResults] = useState(0)

  // Ref for results scroll container
  const resultsScrollRef = useRef<HTMLDivElement>(null)

  // Scroll to top when filters change - use useLayoutEffect to sync before paint
  useLayoutEffect(() => {
    if (resultsScrollRef.current) {
      resultsScrollRef.current.scrollTop = 0
    }
  }, [activeLetterFilter, activeWordCountFilter])

  // Client-side filtering of search results
  const filteredResults = useMemo(() => {
    return searchResults.filter(result => {
      // Letter filter
      if (activeLetterFilter) {
        if (activeLetterFilter === '#') {
          if (!/^\d/.test(result.phrase)) return false
        } else {
          if (!result.phrase.toLowerCase().startsWith(activeLetterFilter.toLowerCase())) return false
        }
      }
      // Word count filter
      if (activeWordCountFilter !== null) {
        const wordCount = result.phrase.trim().split(/\s+/).length
        if (activeWordCountFilter < 10) {
          if (wordCount !== activeWordCountFilter) return false
        } else {
          if (wordCount < 10) return false
        }
      }
      return true
    })
  }, [searchResults, activeLetterFilter, activeWordCountFilter])

  const sensors = useSensors(
    useSensor(PointerSensor, {
      activationConstraint: { distance: 8 },
    }),
    useSensor(TouchSensor, {
      activationConstraint: { delay: 250, tolerance: 5 },
    }),
    useSensor(KeyboardSensor, {
      coordinateGetter: sortableKeyboardCoordinates,
    })
  )

  const handleDragEnd = (event: DragEndEvent, order: string[], setOrder: React.Dispatch<React.SetStateAction<string[]>>) => {
    const { active, over } = event
    if (over && active.id !== over.id) {
      const oldIndex = order.indexOf(active.id as string)
      const newIndex = order.indexOf(over.id as string)
      setOrder(arrayMove(order, oldIndex, newIndex))
    }
  }

  // Column resize handlers
  const handleResizeStart = (e: React.MouseEvent | React.TouchEvent) => {
    e.preventDefault()
    setIsResizing(true)
    const startX = 'touches' in e ? e.touches[0]!.clientX : e.clientX
    const startWidth = phraseColumnWidth
    
    const handleMouseMove = (e: MouseEvent) => {
      const newWidth = Math.max(80, Math.min(400, startWidth + (e.clientX - startX)))
      setPhraseColumnWidth(newWidth)
    }
    
    const handleTouchMove = (e: TouchEvent) => {
      const newWidth = Math.max(80, Math.min(400, startWidth + (e.touches[0]!.clientX - startX)))
      setPhraseColumnWidth(newWidth)
    }
    
    const handleMouseUp = () => {
      setIsResizing(false)
      document.removeEventListener('mousemove', handleMouseMove)
      document.removeEventListener('mouseup', handleMouseUp)
    }

    const handleTouchEnd = () => {
      setIsResizing(false)
      document.removeEventListener('touchmove', handleTouchMove)
      document.removeEventListener('touchend', handleTouchEnd)
    }
    
    document.addEventListener('mousemove', handleMouseMove)
    document.addEventListener('mouseup', handleMouseUp)
    document.addEventListener('touchmove', handleTouchMove, { passive: false })
    document.addEventListener('touchend', handleTouchEnd)
  }

  useEffect(() => {
    localStorage.setItem('hiddenCiphers', JSON.stringify(Array.from(hiddenCiphers)))
  }, [hiddenCiphers])

  useEffect(() => {
    localStorage.setItem('alphanumericCipherOrder', JSON.stringify(alphanumericCipherOrder))
  }, [alphanumericCipherOrder])

  useEffect(() => {
    localStorage.setItem('qwertyCipherOrder', JSON.stringify(qwertyCipherOrder))
  }, [qwertyCipherOrder])

  useEffect(() => {
    localStorage.setItem('otherCipherOrder', JSON.stringify(otherCipherOrder))
  }, [otherCipherOrder])

  useEffect(() => {
    localStorage.setItem('unifiedCipherOrder', JSON.stringify(unifiedCipherOrder))
  }, [unifiedCipherOrder])

  useEffect(() => {
    localStorage.setItem('tableColumnOrder', JSON.stringify(tableColumnOrder))
  }, [tableColumnOrder])

  useEffect(() => {
    localStorage.setItem('highlightedPhrases', JSON.stringify(highlightedPhrases))
  }, [highlightedPhrases])

  useEffect(() => {
    localStorage.setItem('userHighlightedValues', JSON.stringify(userHighlightedValues))
  }, [userHighlightedValues])

  useEffect(() => {
    localStorage.setItem('disabledDefaultValues', JSON.stringify(disabledDefaultValues))
  }, [disabledDefaultValues])

  useEffect(() => {
    localStorage.setItem('plexenomyCipherLine1', plexenomyCipherLine1)
  }, [plexenomyCipherLine1])
  useEffect(() => {
    localStorage.setItem('plexenomyCipherLine2', plexenomyCipherLine2)
  }, [plexenomyCipherLine2])

  // Fetch user's phrases from database when they log in
  // NOTE: We don't auto-populate workspace anymore - only Enter key adds to workspace
  useEffect(() => {
    // Intentionally empty - workspace is only populated via Enter key
  }, [user])

  // Sync user state with localStorage changes (for logout from other tabs/pages)
  useEffect(() => {
    const checkAuthState = () => {
      const savedUser = localStorage.getItem('user')
      const session = localStorage.getItem('session')
      
      if (savedUser && session) {
        // User should be logged in
        if (!user) {
          setUser(JSON.parse(savedUser))
        }
      } else {
        // User should be logged out
        if (user) {
          setUser(null)
          setStoredPhrases([]) // Clear workspace on logout
        }
      }
    }

    // Check on mount and when window gets focus (returning from profile page)
    checkAuthState()
    window.addEventListener('focus', checkAuthState)
    
    // Also listen for storage events (logout from other tabs)
    window.addEventListener('storage', checkAuthState)

    return () => {
      window.removeEventListener('focus', checkAuthState)
      window.removeEventListener('storage', checkAuthState)
    }
  }, [user])

  useEffect(() => {
    const savedUser = localStorage.getItem('user')
    if (savedUser) {
      setUser(JSON.parse(savedUser))
    }
  }, [])

  const results = useMemo(() => {
    return calculateAll(phrase)
  }, [phrase])

  const resultsMap = useMemo(() => {
    const map = new Map<string, CipherResult>()
    results.forEach(r => {
      map.set(r.name, r)
    })
    return map
  }, [results])

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter' && phrase.trim()) {
      const validation = validatePhrase(phrase.trim())
      if (!validation.valid) {
        setValidationError(validation.error || 'Invalid phrase')
        return
      }
      setValidationError('')
      
      // Check for duplicate
      const trimmedPhrase = phrase.trim()
      const isDuplicate = storedPhrases.some(p => p.phrase === trimmedPhrase)
      if (isDuplicate) {
        setValidationError('Phrase already exists in workspace')
        return
      }
      
      // Add to workspace table only - no save dialog
      const newPhrase: StoredPhrase = {
        phrase: trimmedPhrase,
        results: results,
        timestamp: Date.now(),
        category: 'uncategorized',
        tags: []
      }
      
      setStoredPhrases(prev => [newPhrase, ...prev])
      
      // Clear input for next phrase
      setPhrase('')
    }
  }

  const handleAuth = async (e: React.FormEvent) => {
    e.preventDefault()
    setAuthError('')
    
    try {
      const endpoint = authMode === 'login' ? '/api/auth/login' : '/api/auth/register'
      const response = await fetch(`${API_URL}${endpoint}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(authForm)
      })
      
      if (response.ok) {
        const data = await response.json()
        localStorage.setItem('session', data.session)
        localStorage.setItem('csrfToken', data.csrfToken) // Store CSRF token
        localStorage.setItem('user', JSON.stringify(data.user))
        setUser(data.user)
        setShowAuth(false)
        setAuthForm({ username: '', password: '' })
        
        if (showLoginPrompt) {
          setShowLoginPrompt(false)
          setShowSaveDialog(true)
        }
      } else {
        const error = await response.json()
        setAuthError(error.error || 'Authentication failed')
      }
    } catch (error) {
      setAuthError('Network error. Please try again.')
    }
  }

  const savePhraseToBackend = async () => {
    if (!user) {
      setShowLoginPrompt(true)
      return
    }
    
    const validation = validatePhrase(phrase.trim())
    if (!validation.valid) {
      setValidationError(validation.error || 'Invalid phrase')
      return
    }
    
    const session = localStorage.getItem('session')
    if (!session) {
      setValidationError('Please sign in again')
      return
    }
    
    try {
      // Sanitize tags to only allow alphanumeric, spaces, and hyphens
      const tags = saveTags.split(',').map(t => t.trim().replace(/[^a-zA-Z0-9\s-]/g, '')).filter(t => t)
      const csrfToken = localStorage.getItem('csrfToken')
      
      const response = await fetch(`${API_URL}/api/phrases`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${session}`,
          'X-CSRF-Token': csrfToken || ''
        },
        body: JSON.stringify({
          phrase: phrase.trim(),
          category: saveCategory,
          tags
        })
      })
      
      if (response.ok) {
        const data = await response.json()
        setJustStored(true)
        setTimeout(() => setJustStored(false), 2000)
        setShowSaveDialog(false)
        setPhrase('')
        setSaveTags('')
        setSaveCategory('uncategorized')
        setValidationError('')
        
        if (data.discovery) {
          setDiscoveryInfo({
            phrase: phrase.trim(),
            discovered_by: data.discovery.discovered_by,
            is_new: data.discovery.is_new
          })
          setShowDiscoveryModal(true)
        }
      } else {
        const error = await response.json()
        if (response.status === 401) {
          // Session is invalid - clear stale session data
          localStorage.removeItem('session')
          localStorage.removeItem('user')
          setUser(null)
          setValidationError('Your session has expired. Please sign in again.')
          setShowLoginPrompt(true)
        } else {
          setValidationError(error.error || 'Failed to save phrase')
        }
      }
    } catch (error) {
      setValidationError('Network error. Please try again.')
    }
  }

  // Global phrase search query handler
  const handleQuery = async (page: number = 0) => {
    if (!phrase.trim()) return
    
    // Use unifiedCipherOrder to match the visual order in the UI
    const visibleCiphers = unifiedCipherOrder.filter(c => !hiddenCiphers.has(c))
    if (visibleCiphers.length === 0) {
      setValidationError('Enable at least one cipher to query')
      return
    }
    
    setValidationError('')
    
    try {
      // Check if query is numeric with comma-separated values and wildcards
      const trimmedQuery = phrase.trim()
      const isNumericFormat = /^[\d\s,\*]+$/.test(trimmedQuery) && 
        trimmedQuery.split(',').every(p => {
          const val = p.trim()
          return val === '' || val === '*' || /^\d+$/.test(val)
        })
      
      // Auto-detect: if it looks like numeric format with commas, use it
      const isNumeric = isNumericFormat || /^\d+$/.test(trimmedQuery)
      
      const requestBody: any = {
        mode: isNumeric ? 'numeric' : 'text',
        query: trimmedQuery,
        ciphers: visibleCiphers,
        pagination: {
          page,
          limit: 50
        }
      }
      
      // Add filters if active
      if (activeLetterFilter || activeWordCountFilter !== null) {
        requestBody.filters = {}
        if (activeLetterFilter) {
          requestBody.filters.startsWith = activeLetterFilter
        }
        if (activeWordCountFilter !== null) {
          requestBody.filters.wordCount = activeWordCountFilter
        }
      }
      
      const response = await fetch(`${API_URL}/api/phrases/search`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(requestBody)
      })
      
      if (response.ok) {
        const data = await response.json()
        const mapResult = (r: any) => ({ ...r, discoveredBy: r.discovered_by })
        if (page === 0) {
          setSearchResults((data.results || []).map(mapResult))
          setSearchPage(0)
        } else {
          setSearchResults(prev => [...prev, ...(data.results || []).map(mapResult)])
          setSearchPage(page)
        }
        setHasMoreResults(data.pagination?.hasMore || false)
        setTotalSearchResults(data.pagination?.total || 0)
        setShowResults(true)
      } else {
        const error = await response.json()
        setValidationError(error.error || 'Query failed')
      }
    } catch (err) {
      setValidationError('Network error during query')
    } finally {
      setIsLoadingMore(false)
    }
  }

  // Auto-run search when filters change (reset to page 0)
  useEffect(() => {
    if (showResults && phrase.trim()) {
      setSearchPage(0)
      handleQuery(0)
    }
  }, [activeLetterFilter, activeWordCountFilter])

  useEffect(() => {
    const handleClick = () => {
      if (contextMenu.visible) {
        setContextMenu(prev => ({ ...prev, visible: false }))
      }
    }
    document.addEventListener('click', handleClick)
    return () => document.removeEventListener('click', handleClick)
  }, [contextMenu.visible])

  // Close extras dropdown when clicking outside
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (showExtrasDropdown) {
        const target = e.target as HTMLElement
        if (!target.closest('.extras-dropdown')) {
          setShowExtrasDropdown(false)
        }
      }
    }
    document.addEventListener('click', handleClickOutside)
    return () => document.removeEventListener('click', handleClickOutside)
  }, [showExtrasDropdown])

  // Close cipher key dropdown when clicking outside
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (showCipherDropdown) {
        const target = e.target as HTMLElement
        if (!target.closest('.cipher-dropdown')) {
          setShowCipherDropdown(false)
        }
      }
    }
    document.addEventListener('click', handleClickOutside)
    return () => document.removeEventListener('click', handleClickOutside)
  }, [showCipherDropdown])

  return (
    <div className="min-h-screen bg-black text-white overflow-x-hidden" style={{ fontFamily: "'Special Elite', cursive" }}>
      <header className="border-b border-green-900 bg-black/50 backdrop-blur-sm">
        <div className="max-w-7xl mx-auto px-2 sm:px-4 py-2">
          <div className="flex items-center justify-between gap-1 sm:gap-2">
            <div className="flex items-center gap-1 sm:gap-2">
              {/* Extras Dropdown */}
              <div className="relative extras-dropdown">
                <button
                  onClick={() => setShowExtrasDropdown(!showExtrasDropdown)}
                  className="text-sm md:text-base font-bold text-green-400 hover:text-green-300 transition-colors"
                >
                  Extras
                </button>
                {showExtrasDropdown && (
                  <div className="absolute top-full left-0 mt-1 bg-black border border-green-800 rounded-lg shadow-xl z-50 min-w-[200px]">
                    <a
                      href="https://qliphoth.systems/"
                      target="_blank"
                      rel="noopener noreferrer"
                      className="block px-4 py-2 text-green-400 hover:text-green-300 hover:bg-green-900/30 transition-colors text-sm"
                    >
                      qliphoth.systems
                    </a>
                    <a
                      href="https://www.playdecadence.online/"
                      target="_blank"
                      rel="noopener noreferrer"
                      className="block px-4 py-2 text-green-400 hover:text-green-300 hover:bg-green-900/30 transition-colors text-sm"
                    >
                      playdecadence.online
                    </a>
                    <a
                      href="https://ciphers.news/"
                      target="_blank"
                      rel="noopener noreferrer"
                      className="block px-4 py-2 text-green-400 hover:text-green-300 hover:bg-green-900/30 transition-colors text-sm"
                    >
                      ciphers.news
                    </a>
                    <a
                      href="https://basedatlantis.neocities.org/"
                      target="_blank"
                      rel="noopener noreferrer"
                      className="block px-4 py-2 text-green-400 hover:text-green-300 hover:bg-green-900/30 transition-colors text-sm"
                    >
                      basedatlantis.neocities.org
                    </a>
                  </div>
                )}
              </div>
              {justStored && (
                <span className="text-green-500 text-xs animate-pulse">
                  Saved!
                </span>
              )}
            </div>
            <div className="flex items-center gap-2">
              <div className="flex items-center gap-2">
                <button
                  onClick={() => {
                    setShowValueSettings(true)
                    localStorage.setItem('cogClicked', 'true')
                    setHasClickedCog(true)
                  }}
                  className="text-green-500 hover:text-green-400 text-lg cursor-pointer min-w-[44px] md:min-w-0 min-h-[44px] md:min-h-0 flex items-center justify-center"
                  title="Highlight values"
                  style={!hasClickedCog ? { textShadow: '0 0 8px rgba(251,191,36,0.8), 0 0 16px rgba(251,191,36,0.4)' } : undefined}
                >
                  ⚙️
                </button>
                <button
                  onClick={() => setShowHelp(true)}
                  className="text-green-500 hover:text-green-400 text-lg cursor-pointer min-w-[44px] md:min-w-0 min-h-[44px] md:min-h-0 flex items-center justify-center"
                  title="Help & Guide"
                >
                  ⓘ
                </button>
              </div>
            </div>
          </div>
        </div>
      </header>


      <main className="max-w-7xl mx-auto px-4 py-4 sm:py-6 pb-20 md:pb-6">
        <div className="mb-6">
          <div className="flex flex-col sm:flex-row gap-2 mb-2">
            <input
              type="text"
              value={phrase}
              onChange={(e) => {
                setPhrase(e.target.value)
                setValidationError('')
                // Close query results when phrase field is cleared
                if (!e.target.value.trim() && showResults) {
                  setShowResults(false)
                }
              }}
              onKeyDown={handleKeyDown}
              placeholder="Enter phrase to calculate..."
              className="w-full sm:flex-1 px-4 py-3 bg-black border-2 border-green-600 rounded-lg focus:border-green-400 focus:outline-none focus:ring-4 focus:ring-green-500/20 transition-all text-green-400 text-lg text-center"
              style={{ fontFamily: "'Special Elite', cursive" }}
            />
            <div className="flex gap-2">
              <button
                onClick={() => {
                  const validation = validatePhrase(phrase.trim())
                  if (!validation.valid) {
                    setValidationError(validation.error || 'Invalid phrase')
                    return
                  }
                  setValidationError('')
                  
                  // Check if phrase already exists in user's storage
                  const existingPhrase = storedPhrases.find(p => p.phrase.toLowerCase() === phrase.trim().toLowerCase())
                  if (existingPhrase) {
                    setExistingPhraseWarning(`You already have "${phrase.trim()}" saved in your profile. Saving again will update its settings.`)
                  } else {
                    setExistingPhraseWarning(null)
                  }
                  
                  // Show save dialog
                  setShowSaveDialog(true)
                }}
                disabled={!phrase.trim() || !user}
                className="flex-1 sm:flex-none px-4 sm:px-6 py-2 sm:py-3 bg-gradient-to-r from-green-500 to-emerald-500 hover:from-green-400 hover:to-emerald-400 disabled:from-green-900 disabled:to-emerald-900 disabled:text-green-700 text-black font-bold rounded-lg transition-all text-sm sm:text-base min-h-[44px] md:min-h-0"
              >
                {user ? 'Save' : 'Sign in to Save'}
              </button>
              <button
                onClick={() => handleQuery(0)}
                disabled={!phrase.trim() || hiddenCiphers.size === allCipherList.length}
                className="flex-1 sm:flex-none px-4 sm:px-6 py-2 sm:py-3 border-2 border-green-500 text-green-400 hover:bg-green-500/20 disabled:border-green-900 disabled:text-green-700 font-bold rounded-lg transition-all text-sm sm:text-base min-h-[44px] md:min-h-0"
              >
                Query
              </button>
              <button
                onClick={() => {
                  setUnifiedCipherOrder([...defaultCipherOrder])
                  setHiddenCiphers(new Set())
                  setTableColumnOrder([...defaultCipherOrder])
                  setHiddenTableColumns(new Set())
                }}
                className="flex-1 sm:flex-none px-3 sm:px-4 py-2 sm:py-3 border-2 border-amber-600 text-amber-500 hover:bg-amber-600/20 font-bold rounded-lg transition-all text-xs sm:text-sm min-h-[44px] md:min-h-0"
                title="Reset ciphers to default order"
              >
                Reset
              </button>
            </div>
          </div>
          
          {validationError && (
            <div className="text-red-400 text-sm">
              {validationError}
            </div>
          )}
          
          {/* Real-time stats */}
          {phrase.trim() && (() => {
            const aqValue = resultsMap.get('Alphanumeric Qabbala')?.value || 0
            const nqValue = resultsMap.get('Numeric QWERTY')?.value || 0
            const rawPhrase = phrase.trim()
            const isPlexenomyExpr = /^[\s0()]+$/.test(rawPhrase) && hasBalancedParens(rawPhrase)
            let plexDecoded: number | null = null
            if (isPlexenomyExpr) {
              try { plexDecoded = decodePlexenomy(rawPhrase) } catch {}
            }
            const isRawNumber = plexDecoded === null && /^\d+$/.test(rawPhrase)
            const plexValueLine1 = plexDecoded ?? (isRawNumber ? parseInt(rawPhrase, 10) : resultsMap.get(plexenomyCipherLine1)?.value || 0)
            const plexValueLine2 = plexDecoded ?? (isRawNumber ? parseInt(rawPhrase, 10) : resultsMap.get(plexenomyCipherLine2)?.value || 0)
            const shouldGlowAQ = shouldHighlightValue(aqValue)
            const shouldGlowNQ = shouldHighlightValue(nqValue)
            const plexColorLine1 = plexDecoded !== null ? 'text-white' : (isRawNumber ? 'text-green-400' : (cipherColors[plexenomyCipherLine1]?.value || 'text-stone-100'))
            const plexColorLine2 = plexDecoded !== null ? 'text-white' : (isRawNumber ? 'text-green-400' : (cipherColors[plexenomyCipherLine2]?.value || 'text-cyan-400'))
            return (
              <>
                <div className="flex items-center justify-center gap-4 text-xs text-green-400 mt-2">
                  <span>Words: {phrase.trim().split(/\s+/).length}</span>
                  <span>Characters: {phrase.replace(/[^a-zA-Z0-9]/g, '').length}</span>
                  <span className={shouldGlowAQ ? 'text-amber-400' : 'text-green-400'} style={shouldGlowAQ ? { textShadow: '0 0 8px rgba(251, 191, 36, 0.8), 0 0 16px rgba(251, 191, 36, 0.4)' } : undefined}>AQ = {aqValue}</span>
                  <span className={shouldGlowNQ ? 'text-amber-400' : 'text-green-400'} style={shouldGlowNQ ? { textShadow: '0 0 8px rgba(251, 191, 36, 0.8), 0 0 16px rgba(251, 191, 36, 0.4)' } : undefined}>NQ = {nqValue}</span>
                </div>
                <div className="flex items-center justify-center gap-4 text-xs text-green-400 mt-1">
                  <span className={plexColorLine1}>Plexenomy = {plexDecoded !== null ? plexDecoded : plexenomy(plexValueLine1)}</span>
                </div>
                <div className="flex items-center justify-center gap-4 text-xs text-green-400 mt-1">
                  <span className={plexColorLine2}>Plexenomy = {plexDecoded !== null ? plexDecoded : plexenomy(plexValueLine2)}</span>
                </div>
              </>
            )
          })()}
        </div>

        {/* Unified Cipher Grid - All ciphers in one flow */}
        <DndContext
          sensors={sensors}
          collisionDetection={closestCenter}
          onDragEnd={(e) => handleDragEnd(e, unifiedCipherOrder, setUnifiedCipherOrder)}
        >
          <SortableContext items={unifiedCipherOrder.filter(c => !hiddenCiphers.has(c))} strategy={rectSortingStrategy}>
            <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-2 sm:gap-3 mb-3">
              {unifiedCipherOrder
                .filter(cipher => !hiddenCiphers.has(cipher))
                .map((cipher) => {
                  const result = resultsMap.get(cipher)
                  if (!result) return null
                  const highlight = cipher === 'Based Atlanteanism'
                    ? shouldHighlightValue(result.value) || shouldHighlightValue(result.value * 9)
                    : shouldHighlightValue(result.value)
                  
                  // Determine font based on cipher group
                  let fontFamily = "'IBM Plex Mono', monospace"
                  if (alphanumericCiphers.includes(cipher)) {
                    fontFamily = aqCipherFonts[cipher] || "'Courier Prime', monospace"
                  } else if (qwertyCiphers.includes(cipher)) {
                    fontFamily = nqCipherFonts[cipher] || "'IBM Plex Mono', monospace"
                  }
                  
                  return (
                    <SortableCipherCard
                      key={cipher}
                      cipherName={cipher}
                      result={result}
                      shouldHighlight={highlight}
                      fontFamily={fontFamily}
                      onHide={() => {
                        setHiddenCiphers(prev => new Set(prev).add(cipher))
                      }}
                    />
                  )
                })}
            </div>
          </SortableContext>
        </DndContext>

        {/* Hidden Ciphers Section */}
        {hiddenCiphers.size > 0 && (
          <div className="mb-4 border border-green-800/50 rounded-lg bg-black/30 overflow-hidden">
            <div className="flex items-center justify-between px-4 py-2 bg-green-900/20">
              <span className="text-sm text-green-400">
                {hiddenCiphers.size} Hidden Cipher{hiddenCiphers.size === 1 ? '' : 's'}
              </span>
              <div className="flex items-center gap-2">
                <button
                  onClick={() => setHiddenCiphersExpanded(!hiddenCiphersExpanded)}
                  className="w-[44px] md:w-6 h-[44px] md:h-6 flex items-center justify-center text-green-500 hover:text-green-400 hover:bg-green-900/40 rounded transition-all"
                  title={hiddenCiphersExpanded ? 'Collapse' : 'Expand'}
                >
                  <span className="transform transition-transform duration-200">▼</span>
                </button>
                <button
                  onClick={() => setHiddenCiphers(new Set())}
                  className="text-xs text-green-400 hover:text-green-300 underline min-h-[44px] md:min-h-0 flex items-center"
                >
                  Show All
                </button>
              </div>
            </div>
            {hiddenCiphersExpanded && (
              <div className="px-4 py-3 space-y-3">
              {/* Alphanumeric Ciphers */}
              {Array.from(hiddenCiphers).some(c => alphanumericCiphers.includes(c)) && (
                <div>
                  <span className="text-xs text-green-400 mb-2 block">Alphanumerics</span>
                  <div className="flex flex-wrap gap-2">
                    {Array.from(hiddenCiphers)
                      .filter(cipher => alphanumericCiphers.includes(cipher))
                      .map(cipher => {
                        const colors = cipherColors[cipher]
                        return (
                          <button
                            key={cipher}
                            onClick={() => {
                              const newHidden = new Set(hiddenCiphers)
                              newHidden.delete(cipher)
                              setHiddenCiphers(newHidden)
                            }}
                            className={`
                              bg-gradient-to-br ${colors.gradient}
                              px-3 py-2 rounded-none border border-green-500/30
                              shadow-[0_4px_0_rgba(0,0,0,0.4),0_6px_6px_rgba(0,0,0,0.3)]
                              hover:translate-y-[2px] hover:shadow-[0_2px_0_rgba(0,0,0,0.4),0_3px_3px_rgba(0,0,0,0.3),0_0_15px_rgba(74,222,128,0.3)]
                              active:translate-y-[4px] active:shadow-[0_0px_0_rgba(0,0,0,0.4)]
                              transition-all duration-200
                              flex flex-col items-center justify-center min-w-[80px]
                              opacity-60 hover:opacity-100
                            `}
                          >
                            <span className={`${colors.name} text-xs font-medium text-center leading-tight mb-1`}>
                              {cipherDisplayNames[cipher] || cipher}
                            </span>
                            <span className="text-green-500 text-[10px]">Click to show</span>
                          </button>
                        )
                      })}
                  </div>
                </div>
              )}
              
              {/* QWERTY Ciphers */}
              {Array.from(hiddenCiphers).some(c => qwertyCiphers.includes(c)) && (
                <div>
                  <span className="text-xs text-green-400 mb-2 block">QWERTY</span>
                  <div className="flex flex-wrap gap-2">
                    {Array.from(hiddenCiphers)
                      .filter(cipher => qwertyCiphers.includes(cipher))
                      .map(cipher => {
                        const colors = cipherColors[cipher]
                        return (
                          <button
                            key={cipher}
                            onClick={() => {
                              const newHidden = new Set(hiddenCiphers)
                              newHidden.delete(cipher)
                              setHiddenCiphers(newHidden)
                            }}
                            className={`
                              bg-gradient-to-br ${colors.gradient}
                              px-3 py-2 rounded-none border border-green-500/30
                              shadow-[0_4px_0_rgba(0,0,0,0.4),0_6px_6px_rgba(0,0,0,0.3)]
                              hover:translate-y-[2px] hover:shadow-[0_2px_0_rgba(0,0,0,0.4),0_3px_3px_rgba(0,0,0,0.3),0_0_15px_rgba(74,222,128,0.3)]
                              active:translate-y-[4px] active:shadow-[0_0px_0_rgba(0,0,0,0.4)]
                              transition-all duration-200
                              flex flex-col items-center justify-center min-w-[80px]
                              opacity-60 hover:opacity-100
                            `}
                          >
                            <span className={`${colors.name} text-xs font-medium text-center leading-tight mb-1`}>
                              {cipherDisplayNames[cipher] || cipher}
                            </span>
                            <span className="text-green-500 text-[10px]">Click to show</span>
                          </button>
                        )
                      })}
                  </div>
                </div>
              )}
              
              {/* Other Ciphers */}
              {Array.from(hiddenCiphers).some(c => otherCiphers.includes(c)) && (
                <div>
                  <span className="text-xs text-green-400 mb-2 block">Other</span>
                  <div className="flex flex-wrap gap-2">
                    {Array.from(hiddenCiphers)
                      .filter(cipher => otherCiphers.includes(cipher))
                      .map(cipher => {
                        const colors = cipherColors[cipher]
                        return (
                          <button
                            key={cipher}
                            onClick={() => {
                              const newHidden = new Set(hiddenCiphers)
                              newHidden.delete(cipher)
                              setHiddenCiphers(newHidden)
                            }}
                            className={`
                              bg-gradient-to-br ${colors.gradient}
                              px-3 py-2 rounded-none border border-green-500/30
                              shadow-[0_4px_0_rgba(0,0,0,0.4),0_6px_6px_rgba(0,0,0,0.3)]
                              hover:translate-y-[2px] hover:shadow-[0_2px_0_rgba(0,0,0,0.4),0_3px_3px_rgba(0,0,0,0.3),0_0_15px_rgba(74,222,128,0.3)]
                              active:translate-y-[4px] active:shadow-[0_0px_0_rgba(0,0,0,0.4)]
                              transition-all duration-200
                              flex flex-col items-center justify-center min-w-[80px]
                              opacity-60 hover:opacity-100
                            `}
                          >
                            <span className={`${colors.name} text-xs font-medium text-center leading-tight mb-1`}>
                              {cipherDisplayNames[cipher] || cipher}
                            </span>
                            <span className="text-green-500 text-[10px]">Click to show</span>
                          </button>
                        )
                      })}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      )}

        {/* Search Results */}
        {showResults && (
          <div className="mb-8 border-2 border-amber-500/50 rounded-lg bg-black/50 overflow-hidden">
            <div className="flex items-center justify-between px-4 py-3 bg-amber-900/20 border-b border-amber-500/30">
              <h3 className="text-lg font-bold text-amber-400">
                Query Results ({filteredResults.length} of {totalSearchResults} found)
              </h3>
              <button
                onClick={() => setShowResults(false)}
                className="text-amber-400 hover:text-amber-300 text-sm"
              >
                ✕ Close
              </button>
            </div>
            
            {/* Filter Controls */}
            <div className="px-4 py-3 border-b border-amber-500/20 bg-black/30 space-y-3">
              {/* Letter Filter */}
              <div className="flex items-center gap-2 flex-wrap">
                <span className="text-xs text-amber-500 mr-1">Letter:</span>
                {'ABCDEFGHIJKLMNOPQRSTUVWXYZ'.split('').map(letter => (
                  <button
                    key={letter}
                    onClick={() => {
                      const newFilter = activeLetterFilter === letter ? null : letter
                      setActiveLetterFilter(newFilter)
                    }}
                    className={`w-6 h-6 text-[10px] rounded ${
                      activeLetterFilter === letter 
                        ? 'bg-amber-500 text-black font-bold' 
                        : 'bg-amber-900/30 text-amber-400 hover:bg-amber-800/50'
                    }`}
                  >
                    {letter}
                  </button>
                ))}
                <button
                  onClick={() => {
                    const newFilter = activeLetterFilter === '#' ? null : '#'
                    setActiveLetterFilter(newFilter)
                  }}
                  className={`w-6 h-6 text-[10px] rounded ${
                    activeLetterFilter === '#' 
                      ? 'bg-amber-500 text-black font-bold' 
                      : 'bg-amber-900/30 text-amber-400 hover:bg-amber-800/50'
                  }`}
                >
                  #
                </button>
                {activeLetterFilter && (
                  <button
                    onClick={() => setActiveLetterFilter(null)}
                    className="text-xs text-amber-400 hover:text-amber-300 underline ml-2"
                  >
                    Clear
                  </button>
                )}
              </div>
              
              {/* Word Count Filter */}
              <div className="flex items-center gap-2 flex-wrap">
                <span className="text-xs text-amber-500 mr-1">Words:</span>
                {[1, 2, 3, 4, 5, 6, 7, 8, 9].map(count => (
                  <button
                    key={count}
                    onClick={() => {
                      const newFilter = activeWordCountFilter === count ? null : count
                      setActiveWordCountFilter(newFilter)
                    }}
                    className={`px-2 py-1 text-[10px] rounded ${
                      activeWordCountFilter === count 
                        ? 'bg-amber-500 text-black font-bold' 
                        : 'bg-amber-900/30 text-amber-400 hover:bg-amber-800/50'
                    }`}
                  >
                    {count}
                  </button>
                ))}
                <button
                  onClick={() => {
                    const newFilter = activeWordCountFilter === 10 ? null : 10
                    setActiveWordCountFilter(newFilter)
                  }}
                  className={`px-2 py-1 text-[10px] rounded ${
                    activeWordCountFilter === 10 
                      ? 'bg-amber-500 text-black font-bold' 
                      : 'bg-amber-900/30 text-amber-400 hover:bg-amber-800/50'
                  }`}
                >
                  10+
                </button>
                {activeWordCountFilter !== null && (
                  <button
                    onClick={() => setActiveWordCountFilter(null)}
                    className="text-xs text-amber-400 hover:text-amber-300 underline ml-2"
                  >
                    Clear
                  </button>
                )}
              </div>
            </div>
            
            {filteredResults.length === 0 ? (
              <div className="px-4 py-8 text-center text-green-600">
                No phrases found matching your filters
              </div>
            ) : (
              <div ref={resultsScrollRef} key={`${activeLetterFilter}-${activeWordCountFilter}`} className="max-h-[400px] overflow-y-auto">
                {filteredResults.map((result, index) => {
                  const visibleCiphers = allCipherList.filter(c => !hiddenCiphers.has(c))
                  
                  return (
                    <div
                      key={`${result.phrase}-${index}`}
                      className="px-4 py-3 border-b border-green-800/30 hover:bg-green-900/20 transition-colors"
                    >
                      <div className="flex items-start justify-between gap-4">
                        <div className="flex-1">
                          <p className="text-green-300 font-medium text-lg mb-2">{result.phrase}</p>
                          
                          {/* Show matching cipher values */}
                          <div className="flex flex-wrap gap-3 text-xs">
                            {visibleCiphers.map(cipherName => {
                              const value = result.ciphers[cipherName]
                              if (value === undefined) return null
                              
                              const colors = cipherColors[cipherName]
                              const isHighlighted = shouldHighlightValue(value)
                              
                              return (
                                <span key={cipherName} className="bg-green-900/30 px-2 py-1 rounded">
                                  <span className={colors.name}>{cipherDisplayNames[cipherName] || cipherName}:</span>{' '}
                                  <span className={`font-mono font-bold ${isHighlighted ? 'text-amber-400' : colors.value}`}>
                                    {value}
                                  </span>
                                </span>
                              )
                            })}
                          </div>
                        </div>
                        
                        {/* Discoverer tooltip */}
                  <div className="relative cipher-dropdown">
                          <span 
                            className="text-xs text-green-600 cursor-help"
                            onMouseEnter={() => setHoveredResult(result.phrase)}
                            onMouseLeave={() => setHoveredResult(null)}
                          >
                            ✨
                            {hoveredResult === result.phrase && (
                              <div className="absolute right-0 top-full mt-1 z-10 bg-black/95 border border-amber-500/50 rounded-lg px-3 py-2 shadow-xl whitespace-nowrap">
                                <span className="text-xs text-amber-400">
                                  Discovered by: @{result.discoveredBy}
                                </span>
                              </div>
                            )}
                          </span>
                        </div>
                      </div>
                    </div>
                  )
                })}
                
                {/* Load More Button */}
                {hasMoreResults && (
                  <div className="px-4 py-3 text-center border-t border-green-800/30">
                    <button
                      onClick={() => {
                        setIsLoadingMore(true)
                        handleQuery(searchPage + 1)
                      }}
                      disabled={isLoadingMore}
                      className="px-6 py-2 bg-green-900/50 hover:bg-green-800/50 disabled:opacity-50 text-green-400 rounded-lg transition-colors text-sm min-h-[44px] md:min-h-0"
                    >
                      {isLoadingMore ? 'Loading...' : `Load More (${filteredResults.length} of ${totalSearchResults} found)`}
                    </button>
                  </div>
                )}
              </div>
            )}
          </div>
        )}

        {/* Workspace Table - Minimalist with Cipher Colors */}
        {storedPhrases.length > 0 && (
          <div className={`mt-8 border border-green-800/50 rounded-lg overflow-hidden bg-black/30 ${isResizing ? 'cursor-col-resize' : ''}`}>
            {/* Hidden Table Columns Indicator */}
            {hiddenTableColumns.size > 0 && (
              <div className="flex items-center gap-2 px-4 py-2 bg-green-900/20 border-b border-green-800/50">
                <span className="text-xs text-green-500">
                  {hiddenTableColumns.size} column{hiddenTableColumns.size === 1 ? '' : 's'} hidden
                </span>
                <button
                  onClick={() => setHiddenTableColumns(new Set())}
                  className="text-xs text-green-400 hover:text-green-300 underline"
                >
                  Show All
                </button>
              </div>
            )}
            <div className="w-full overflow-x-auto">
              {(() => {
                const visibleCiphers = tableColumnOrder.filter(c => !hiddenTableColumns.has(c))
                const visibleCipherCount = visibleCiphers.length
                // Make cipher columns 30% bigger by using larger percentage
                const cipherColumnWidth = visibleCipherCount > 0 ? `${Math.floor((100 - 15) / visibleCipherCount * 1.3)}%` : '0%'
                
                return (
              <table className="w-full" style={{ tableLayout: 'fixed', borderCollapse: 'separate', borderSpacing: 0 }}>
                <thead>
                  <tr className="border-b border-green-800/50">
                    <th 
                      className="px-3 py-2 text-left text-xs text-green-600 font-medium sticky left-0 bg-black/60 z-10 border border-green-800/40 relative group"
                      style={{ width: `${phraseColumnWidth}px`, minWidth: `${phraseColumnWidth}px` }}
                    >
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2">
                          <button
                            onClick={() => {
                              setStoredPhrases([])
                            }}
                            className="text-red-500 hover:text-red-400 text-[10px]"
                            title="Clear all phrases"
                          >
                            ✕
                          </button>
                          <span>Phrase</span>
                        </div>
                        <div 
                          className="absolute right-0 top-0 bottom-0 w-3 cursor-col-resize bg-green-600/0 hover:bg-green-600/50 transition-colors z-20"
                          onMouseDown={handleResizeStart}
                          onTouchStart={handleResizeStart}
                          title="Drag to resize"
                        >
                          <div className="absolute right-0.5 top-1/2 -translate-y-1/2 w-0.5 h-4 bg-green-400/50"></div>
                        </div>
                      </div>
                    </th>
                    <DndContext
                      sensors={sensors}
                      collisionDetection={closestCenter}
                      onDragEnd={(e) => {
                        const { active, over } = e
                        if (over && active.id !== over.id) {
                          setTableColumnOrder(items => {
                            const visibleColumns = items.filter(c => !hiddenTableColumns.has(c))
                            const oi = visibleColumns.indexOf(active.id as string)
                            const ni = visibleColumns.indexOf(over.id as string)
                            if (oi === -1 || ni === -1) return items
                            const newVisibleColumns = arrayMove(visibleColumns, oi, ni)
                            // Rebuild full order with hidden columns in place
                            const newOrder: string[] = []
                            let visibleIdx = 0
                            for (const cipher of items) {
                              if (hiddenTableColumns.has(cipher)) {
                                newOrder.push(cipher)
                              } else {
                                newOrder.push(newVisibleColumns[visibleIdx++])
                              }
                            }
                            return newOrder
                          })
                        }
                      }}
                    >
                      <SortableContext items={visibleCiphers} strategy={horizontalListSortingStrategy}>
                        {visibleCiphers.map(cipher => {
                          const colors = cipherColors[cipher]
                          return (
                            <SortableTableHeader
                              key={cipher}
                              cipher={cipher}
                              colors={colors}
                              columnWidth={cipherColumnWidth}
                              onContextMenu={(e) => {
                                e.preventDefault()
                                e.stopPropagation()
                                setContextMenu({
                                  visible: true,
                                  x: e.clientX,
                                  y: e.clientY,
                                  cipherName: cipher,
                                  type: 'table-column'
                                })
                              }}
                            />
                          )
                        })}
                      </SortableContext>
                    </DndContext>
                  </tr>
                </thead>
                <tbody>
                  {storedPhrases.map((storedPhrase, index) => {
                    const isPhraseHighlighted = highlightedPhrases.some(
                      hp => hp.toLowerCase() === storedPhrase.phrase.toLowerCase()
                    )
                    return (
                    <tr key={index} className={`border-b border-green-900/20 hover:bg-green-900/5 ${isPhraseHighlighted ? 'bg-green-900/20' : ''}`}>
                      <td 
                        className={`px-3 py-2 text-sm sticky left-0 z-10 border border-green-800/40 overflow-hidden ${isPhraseHighlighted ? 'text-amber-400 bg-green-900/40' : 'text-green-400 bg-black/40'}`}
                        style={{ width: `${phraseColumnWidth}px`, minWidth: `${phraseColumnWidth}px`, maxWidth: `${phraseColumnWidth}px` }}
                      >
                        <div className="flex items-start gap-1 overflow-hidden">
                          <button
                            onClick={() => {
                              setStoredPhrases(prev => prev.filter((_, i) => i !== index))
                            }}
                            className="flex-shrink-0 w-4 h-4 flex items-center justify-center text-red-500 hover:text-red-400 text-[8px] leading-none transition-colors mt-0.5"
                          >
                            ×
                          </button>
                          <span className={`truncate flex-1 min-w-0 ${isPhraseHighlighted ? 'font-bold' : ''}`}>{storedPhrase.phrase}</span>
                        </div>
                       </td>
                        {visibleCiphers.map(cipher => {
                          const result = calculateAll(storedPhrase.phrase).find(r => r.name === cipher)
                          const colors = cipherColors[cipher]
                          const isHighlightedValue = result && shouldHighlightValue(result.value)
                          const isClickHighlighted = result && highlightedValue === result.value
                          const shouldGlow = isHighlightedValue
                          const cellKey = `${index}-${cipher}`
                          const isHidden = hiddenCellValues.has(cellKey)
                          return (
                            <td 
                              key={cipher} 
                              onClick={() => {
                                if (result && !isHidden) {
                                  // Toggle: if already highlighted, stop. If not, highlight this value.
                                  setHighlightedValue(current => current === result.value ? null : result.value)
                                }
                              }}
                              onContextMenu={(e) => {
                                e.preventDefault()
                                e.stopPropagation()
                                const key = `${index}-${cipher}`
                                setHiddenCellValues(prev => {
                                  const newSet = new Set(prev)
                                  if (newSet.has(key)) {
                                    newSet.delete(key)
                                  } else {
                                    newSet.add(key)
                                  }
                                  return newSet
                                })
                              }}
                              className={`px-2 py-2 text-center ${shouldGlow ? 'text-amber-400' : colors.value} text-sm tabular-nums border border-green-800/40 cursor-pointer transition-all ${isClickHighlighted ? 'bg-white/20 animate-pulse ring-1 ring-white/50' : ''}`}
                              style={{ 
                                textShadow: shouldGlow ? '0 0 8px rgba(251, 191, 36, 0.8), 0 0 16px rgba(251, 191, 36, 0.4)' : undefined,
                                width: cipherColumnWidth
                              }}
                            >
                              {isHidden ? '•' : (result?.value || '-')}
                            </td>
                          )
                        })}
                      </tr>
                    )
                  })}
                </tbody>
              </table>
              )})()}
            </div>
          </div>
        )}
      </main>

      {contextMenu.visible && (
        <div
          className="fixed bg-black border border-green-800 rounded-lg shadow-xl z-50 py-1"
          style={{ left: contextMenu.x, top: contextMenu.y }}
        >
          {contextMenu.type === 'cipher' && (
            <>
              <button
                onClick={() => {
                  if (contextMenu.cipherName) {
                    setHiddenCiphers(prev => new Set(prev).add(contextMenu.cipherName!))
                  }
                  setContextMenu(prev => ({ ...prev, visible: false }))
                }}
                className="block w-full text-left px-4 py-2 text-green-400 hover:bg-green-900/30 text-sm"
              >
                Hide This Cipher
              </button>
              <div className="border-t border-green-800/50 my-1"></div>
              <button
                onClick={() => {
                  setHiddenCiphers(prev => new Set([...prev, ...alphanumericCiphers]))
                  setContextMenu(prev => ({ ...prev, visible: false }))
                }}
                className="block w-full text-left px-4 py-2 text-green-400 hover:bg-green-900/30 text-sm"
              >
                Hide All AQ (Alphanumerics)
              </button>
              <button
                onClick={() => {
                  setHiddenCiphers(prev => new Set([...prev, ...qwertyCiphers]))
                  setContextMenu(prev => ({ ...prev, visible: false }))
                }}
                className="block w-full text-left px-4 py-2 text-green-400 hover:bg-green-900/30 text-sm"
              >
                Hide All NQ (QWERTYs)
              </button>
              <button
                onClick={() => {
                  setHiddenCiphers(prev => new Set([...prev, ...otherCiphers]))
                  setContextMenu(prev => ({ ...prev, visible: false }))
                }}
                className="block w-full text-left px-4 py-2 text-green-400 hover:bg-green-900/30 text-sm"
              >
                Hide All Others
              </button>
              <div className="border-t border-green-800/50 my-1"></div>
              <button
                onClick={() => {
                  setHiddenCiphers(new Set())
                  setContextMenu(prev => ({ ...prev, visible: false }))
                }}
                className="block w-full text-left px-4 py-2 text-green-400 hover:bg-green-900/30 text-sm"
              >
                Show All Ciphers
              </button>
            </>
          )}
          {contextMenu.type === 'table-column' && (
            <>
              <button
                onClick={() => {
                  if (contextMenu.cipherName) {
                    setHiddenTableColumns(prev => new Set(prev).add(contextMenu.cipherName!))
                  }
                  setContextMenu(prev => ({ ...prev, visible: false }))
                }}
                className="block w-full text-left px-4 py-2 text-green-400 hover:bg-green-900/30 text-sm"
              >
                Hide This Column
              </button>
              <div className="border-t border-green-800/50 my-1"></div>
              <button
                onClick={() => {
                  setHiddenTableColumns(prev => new Set([...prev, ...alphanumericCiphers]))
                  setContextMenu(prev => ({ ...prev, visible: false }))
                }}
                className="block w-full text-left px-4 py-2 text-green-400 hover:bg-green-900/30 text-sm"
              >
                Hide All AQ Columns
              </button>
              <button
                onClick={() => {
                  setHiddenTableColumns(prev => new Set([...prev, ...qwertyCiphers]))
                  setContextMenu(prev => ({ ...prev, visible: false }))
                }}
                className="block w-full text-left px-4 py-2 text-green-400 hover:bg-green-900/30 text-sm"
              >
                Hide All NQ Columns
              </button>
              <button
                onClick={() => {
                  setHiddenTableColumns(prev => new Set([...prev, ...otherCiphers]))
                  setContextMenu(prev => ({ ...prev, visible: false }))
                }}
                className="block w-full text-left px-4 py-2 text-green-400 hover:bg-green-900/30 text-sm"
              >
                Hide All Other Columns
              </button>
              <div className="border-t border-green-800/50 my-1"></div>
              <button
                onClick={() => {
                  setHiddenTableColumns(new Set())
                  setContextMenu(prev => ({ ...prev, visible: false }))
                }}
                className="block w-full text-left px-4 py-2 text-green-400 hover:bg-green-900/30 text-sm"
              >
                Show All Table Columns
              </button>
            </>
          )}
        </div>
      )}

      {showAuth && (
        <div 
          className="fixed inset-0 bg-black/90 backdrop-blur-sm flex items-center justify-center z-50 p-4"
          onClick={(e) => {
            if (e.target === e.currentTarget) {
              setShowAuth(false)
            }
          }}
        >
          <div className="bg-black rounded-2xl p-6 sm:p-8 w-full max-w-md border border-green-500 shadow-2xl shadow-green-500/20">
            <h2 className="text-2xl font-bold mb-6 text-green-400">
              {authMode === 'login' ? 'Sign In' : 'Create Account'}
            </h2>
            
            {authError && (
              <div className="mb-4 bg-red-500/20 border border-red-500/50 text-red-400 px-4 py-3 rounded-lg">
                {authError}
              </div>
            )}
            
            <form onSubmit={handleAuth} className="space-y-4">
              <div>
                <label className="block text-sm text-green-500 mb-2">Username</label>
                <input
                  type="text"
                  value={authForm.username}
                  onChange={(e) => setAuthForm({ ...authForm, username: e.target.value })}
                  className="w-full px-4 py-3 bg-black border border-green-600 rounded-lg focus:border-green-400 focus:outline-none focus:ring-2 focus:ring-green-500/20 transition-all text-green-400"
                  required
                />
              </div>
              
              <div>
                <label className="block text-sm text-green-500 mb-2">Password</label>
                <input
                  type="password"
                  value={authForm.password}
                  onChange={(e) => setAuthForm({ ...authForm, password: e.target.value })}
                  className="w-full px-4 py-3 bg-black border border-green-600 rounded-lg focus:border-green-400 focus:outline-none focus:ring-2 focus:ring-green-500/20 transition-all text-green-400"
                  required
                />
              </div>
              
              <div className="flex gap-3 pt-4">
                <button
                  type="button"
                  onClick={() => setShowAuth(false)}
                  className="flex-1 px-4 py-3 text-green-500 hover:text-green-300 transition-colors"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="flex-1 px-4 py-3 bg-gradient-to-r from-green-500 to-emerald-500 hover:from-green-400 hover:to-emerald-400 text-black font-bold rounded-lg transition-all"
                >
                  {authMode === 'login' ? 'Sign In' : 'Create Account'}
                </button>
              </div>
            </form>
            
            <div className="mt-6 text-center">
              <button
                onClick={() => setAuthMode(authMode === 'login' ? 'register' : 'login')}
                className="text-sm text-green-500 hover:text-green-400 transition-colors"
              >
                {authMode === 'login' ? "Don't have an account? Register" : 'Already have an account? Sign in'}
              </button>
            </div>
          </div>
        </div>
      )}

      {showSaveDialog && (
        <SaveDialog 
          userCategories={userCategories}
          setUserCategories={setUserCategories}
          user={user}
          saveCategory={saveCategory}
          setSaveCategory={setSaveCategory}
          saveTags={saveTags}
          setSaveTags={setSaveTags}
          phrase={phrase}
          validationError={validationError}
          existingPhraseWarning={existingPhraseWarning}
          onCancel={() => setShowSaveDialog(false)}
          onSave={savePhraseToBackend}
        />
      )}

      {showDiscoveryModal && discoveryInfo && (
        <div className="fixed inset-0 bg-black/90 backdrop-blur-sm flex items-center justify-center z-50 p-4">
          <div className="bg-black rounded-2xl p-8 w-full max-w-md border border-amber-500 shadow-2xl shadow-amber-500/20">
            <h2 className="text-2xl font-bold mb-4 text-amber-400">{discoveryInfo.is_new ? '🎉 Discovery!' : '✨ Discovered'}</h2>
            <p className="text-green-300 mb-4">
              "{discoveryInfo.phrase}"
            </p>
            <p className="text-amber-400 mb-6">
              {discoveryInfo.is_new 
                ? 'You are the first to discover this phrase on the platform!'
                : `This phrase was first discovered by ${discoveryInfo.discovered_by}`
              }
            </p>
            <button
              onClick={() => setShowDiscoveryModal(false)}
              className="w-full px-4 py-3 bg-gradient-to-r from-amber-500 to-yellow-500 hover:from-amber-400 hover:to-yellow-400 text-black font-bold rounded-lg transition-all"
            >
              Awesome!
            </button>
          </div>
        </div>
      )}

      {showPhraseSettings && (
        <div className="fixed inset-0 bg-black/90 backdrop-blur-sm flex items-center justify-center z-50 p-4">
          <div className="bg-black rounded-2xl p-8 w-full max-w-md border border-green-500 shadow-2xl shadow-green-500/20">
            <div className="flex items-center justify-between mb-6">
              <h2 className="text-2xl font-bold text-green-400">⚙️ Highlight Phrases</h2>
              <button
                onClick={() => setShowPhraseSettings(false)}
                className="text-green-500 hover:text-green-400 text-xl"
              >
                ✕
              </button>
            </div>
            
            <p className="text-green-300 text-sm mb-4">
              Enter phrases to highlight in the workspace table:
            </p>
            
            <div className="flex gap-2 mb-4">
              <input
                type="text"
                value={newHighlightPhrase}
                onChange={(e) => setNewHighlightPhrase(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && newHighlightPhrase.trim()) {
                    setHighlightedPhrases(prev => [...prev, newHighlightPhrase.trim()])
                    setNewHighlightPhrase('')
                  }
                }}
                placeholder="Enter phrase..."
                className="flex-1 px-4 py-2 bg-black border border-green-600 rounded-lg focus:border-green-400 focus:outline-none focus:ring-2 focus:ring-green-500/20 transition-all text-green-400 text-sm"
              />
              <button
                onClick={() => {
                  if (newHighlightPhrase.trim()) {
                    setHighlightedPhrases(prev => [...prev, newHighlightPhrase.trim()])
                    setNewHighlightPhrase('')
                  }
                }}
                className="px-4 py-2 bg-gradient-to-r from-green-500 to-emerald-500 hover:from-green-400 hover:to-emerald-400 text-black font-bold rounded-lg transition-all text-sm"
              >
                Add
              </button>
            </div>
            
            {highlightedPhrases.length > 0 && (
              <div className="mb-4">
                <p className="text-green-500 text-xs mb-2">Highlighted phrases:</p>
                <div className="flex flex-wrap gap-2">
                  {highlightedPhrases.map((phrase, index) => (
                    <span
                      key={index}
                      className="inline-flex items-center gap-1 px-3 py-1 bg-green-900/30 border border-green-500/30 rounded-full text-green-400 text-sm"
                    >
                      {phrase}
                      <button
                        onClick={() => setHighlightedPhrases(prev => prev.filter((_, i) => i !== index))}
                        className="text-green-500 hover:text-red-400"
                      >
                        ×
                      </button>
                    </span>
                  ))}
                </div>
              </div>
            )}
            
            <button
              onClick={() => setShowPhraseSettings(false)}
              className="w-full px-4 py-3 bg-gradient-to-r from-green-500 to-emerald-500 hover:from-green-400 hover:to-emerald-400 text-black font-bold rounded-lg transition-all"
            >
              Done
            </button>
          </div>
        </div>
      )}

      {showValueSettings && (
        <div className="fixed inset-0 bg-black/90 backdrop-blur-sm flex items-center justify-center z-50 p-4">
          <div className="bg-black rounded-2xl p-8 w-full max-w-md border border-amber-500 shadow-2xl shadow-amber-500/20">
            <div className="flex items-center justify-between mb-6">
              <h2 className="text-2xl font-bold text-amber-400">⚙️ Highlight Values</h2>
              <button
                onClick={() => setShowValueSettings(false)}
                className="text-amber-500 hover:text-amber-400 text-xl"
              >
                ✕
              </button>
            </div>
            
            <p className="text-green-300 text-sm mb-4">
              Enter cipher values to highlight globally (like 111, 222, 333):
            </p>
            
            <div className="flex gap-2 mb-4">
              <input
                type="number"
                value={newHighlightValue}
                onChange={(e) => setNewHighlightValue(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && newHighlightValue.trim()) {
                    const val = parseInt(newHighlightValue.trim(), 10)
                    if (!isNaN(val) && !userHighlightedValues.includes(val)) {
                      setUserHighlightedValues(prev => [...prev, val])
                      setNewHighlightValue('')
                    }
                  }
                }}
                placeholder="Enter value (e.g., 111)..."
                className="flex-1 px-4 py-2 bg-black border border-amber-600 rounded-lg focus:border-amber-400 focus:outline-none focus:ring-2 focus:ring-amber-500/20 transition-all text-amber-400 text-sm"
              />
              <button
                onClick={() => {
                  if (newHighlightValue.trim()) {
                    const val = parseInt(newHighlightValue.trim(), 10)
                    if (!isNaN(val) && !userHighlightedValues.includes(val)) {
                      setUserHighlightedValues(prev => [...prev, val])
                      setNewHighlightValue('')
                    }
                  }
                }}
                className="px-4 py-2 bg-gradient-to-r from-amber-500 to-yellow-500 hover:from-amber-400 hover:to-yellow-400 text-black font-bold rounded-lg transition-all text-sm"
              >
                Add
              </button>
            </div>
            
            {/* Combined list of active default values and user values */}
            <div className="mb-4">
              <p className="text-amber-500 text-xs mb-2">Highlighted values:</p>
              <div className="flex flex-wrap gap-2">
                {/* Active default (triple) values */}
                {tripleNumbers.filter(n => !disabledDefaultValues.includes(n)).map((val) => (
                  <span
                    key={`default-${val}`}
                    className="inline-flex items-center gap-1 px-3 py-1 bg-amber-900/30 border border-amber-500/30 rounded-full text-amber-400 text-sm"
                  >
                    {val}
                    <button
                      onClick={() => setDisabledDefaultValues(prev => [...prev, val])}
                      className="text-amber-500 hover:text-red-400"
                    >
                      ×
                    </button>
                  </span>
                ))}
                {/* User-added values */}
                {userHighlightedValues.map((val, index) => (
                  <span
                    key={`user-${val}-${index}`}
                    className="inline-flex items-center gap-1 px-3 py-1 bg-amber-900/30 border border-amber-500/30 rounded-full text-amber-400 text-sm"
                  >
                    {val}
                    <button
                      onClick={() => setUserHighlightedValues(prev => prev.filter((_, i) => i !== index))}
                      className="text-amber-500 hover:text-red-400"
                    >
                      ×
                    </button>
                  </span>
                ))}
              </div>
            </div>
            
            {/* Disabled default values - can be re-enabled */}
            {disabledDefaultValues.length > 0 && (
              <div className="mb-4">
                <p className="text-gray-500 text-xs mb-2">Disabled defaults (click to re-enable):</p>
                <div className="flex flex-wrap gap-2">
                  {disabledDefaultValues.map((val) => (
                    <button
                      key={`disabled-${val}`}
                      onClick={() => setDisabledDefaultValues(prev => prev.filter(v => v !== val))}
                      className="inline-flex items-center gap-1 px-3 py-1 bg-gray-900/30 border border-gray-500/30 rounded-full text-gray-400 text-sm hover:bg-amber-900/20 hover:border-amber-500/30 hover:text-amber-400 transition-all"
                    >
                      + {val}
                    </button>
                  ))}
                </div>
              </div>
            )}
            
            <div className="flex gap-2 items-start">
              <div className="flex-1">
                <p className="text-amber-500 text-xs mb-1">Plex 1 cipher:</p>
                <div className="relative">
                  <select
                    value={plexenomyCipherLine1}
                    onChange={(e) => setPlexenomyCipherLine1(e.target.value)}
                    className="w-full px-3 py-1.5 bg-black border border-amber-600 rounded-lg focus:border-amber-400 focus:outline-none focus:ring-2 focus:ring-amber-500/20 transition-all text-amber-400 text-xs appearance-none cursor-pointer"
                  >
                    {allCipherList.map((cipher) => (
                      <option key={cipher} value={cipher}>{cipherDisplayNames[cipher] || cipher}</option>
                    ))}
                  </select>
                  <span className="absolute right-2 top-1/2 -translate-y-1/2 text-amber-500 text-xs pointer-events-none">▼</span>
                </div>
              </div>
              <div className="flex-1">
                <p className="text-amber-500 text-xs mb-1">Plex 2 cipher:</p>
                <div className="relative">
                  <select
                    value={plexenomyCipherLine2}
                    onChange={(e) => setPlexenomyCipherLine2(e.target.value)}
                    className="w-full px-3 py-1.5 bg-black border border-amber-600 rounded-lg focus:border-amber-400 focus:outline-none focus:ring-2 focus:ring-amber-500/20 transition-all text-amber-400 text-xs appearance-none cursor-pointer"
                  >
                    {allCipherList.map((cipher) => (
                      <option key={cipher} value={cipher}>{cipherDisplayNames[cipher] || cipher}</option>
                    ))}
                  </select>
                  <span className="absolute right-2 top-1/2 -translate-y-1/2 text-amber-500 text-xs pointer-events-none">▼</span>
                </div>
              </div>
            </div>

            <button
              onClick={() => setShowValueSettings(false)}
              className="w-full px-4 py-3 bg-gradient-to-r from-amber-500 to-yellow-500 hover:from-amber-400 hover:to-yellow-400 text-black font-bold rounded-lg transition-all"
            >
              Done
            </button>
          </div>
        </div>
      )}

      {/* Help Modal */}
      {showHelp && (
        <div className="fixed inset-0 bg-black/90 backdrop-blur-sm flex items-center justify-center z-50 p-4">
          <div className="bg-black rounded-2xl p-8 w-full max-w-2xl border border-green-500 shadow-2xl shadow-green-500/20 max-h-[85vh] flex flex-col">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-2xl font-bold text-green-400">ⓘ Help & Guide</h2>
              <button
                onClick={() => setShowHelp(false)}
                className="text-green-500 hover:text-green-400 text-xl"
              >
                ✕
              </button>
            </div>
            
            <div className="flex gap-0 mb-4 border-b border-green-800/50">
              <button
                onClick={() => setHelpTab('guide')}
                className={`px-4 py-2 text-sm font-medium transition-colors ${
                  helpTab === 'guide'
                    ? 'text-green-400 border-b-2 border-green-400'
                    : 'text-green-600 hover:text-green-400'
                }`}
              >
                Guide
              </button>
              <button
                onClick={() => setHelpTab('cipherkey')}
                className={`px-4 py-2 text-sm font-medium transition-colors ${
                  helpTab === 'cipherkey'
                    ? 'text-green-400 border-b-2 border-green-400'
                    : 'text-green-600 hover:text-green-400'
                }`}
              >
                Cipher Key
              </button>
            </div>
            
            <div className="overflow-y-auto space-y-5 pr-2 scrollbar-thin scrollbar-thumb-green-800 scrollbar-track-transparent">
              {helpTab === 'guide' ? (
                <>
              <div className="border border-green-900/30 rounded-xl p-4 bg-green-950/20">
                <h3 className="text-base font-bold text-green-400 mb-2">Getting Started</h3>
                <p className="text-green-300 text-sm leading-relaxed">
                  Enter any word or phrase to instantly see its value across all 14 ciphers.
                  Press <kbd className="px-1.5 py-0.5 bg-green-900/50 border border-green-700 rounded text-xs text-green-300">Enter</kbd> to add it to your workspace table below the cipher grid.
                </p>
              </div>

              <div className="border border-green-900/30 rounded-xl p-4 bg-green-950/20">
                <h3 className="text-base font-bold text-green-400 mb-2">Ciphers</h3>
                <p className="text-green-300 text-sm leading-relaxed mb-2">
                  Three groups of ciphers — <span className="text-stone-300">Alphanumerics (AQ)</span>,{' '}
                  <span className="text-green-400">QWERTY (NQ)</span>, and{' '}
                  <span className="text-cyan-400">Other</span> —                   17 total.
                </p>
                <ul className="text-green-300 text-sm leading-relaxed space-y-1.5 list-disc list-inside">
                  <li>Drag to reorder cipher cards, right-click to hide/show individual or by group</li>
                  <li>Values matching triple numbers (111, 222 ... 9999) glow amber</li>
                  <li>Press the <span className="text-amber-400">⚙️</span> cog to highlight custom phrases and cipher values — add your own numbers and see them glow across the calculator, vault, feed, and public profiles</li>
                  <li>Hidden ciphers appear in a collapsible bar at the top for easy restoration</li>
                </ul>
              </div>

              <div className="border border-green-900/30 rounded-xl p-4 bg-green-950/20">
                <h3 className="text-base font-bold text-green-400 mb-2">Query</h3>
                <ul className="text-green-300 text-sm leading-relaxed space-y-1.5 list-disc list-inside">
                  <li><span className="font-bold">Text mode:</span> prefix search across ~666K+ phrases</li>
                  <li><span className="font-bold">Numeric mode:</span> enter comma-separated values matching your visible ciphers' order to find phrases matching <span className="italic">multiple</span> ciphers at once (e.g. <code className="px-1 py-0.5 bg-green-900/50 border border-green-700 rounded text-xs">666, 777, 888</code>)</li>
                  <li>Use <code className="px-1 py-0.5 bg-green-900/50 border border-green-700 rounded text-xs">*</code> as a wildcard to skip a cipher position (e.g. <code className="px-1 py-0.5 bg-green-900/50 border border-green-700 rounded text-xs">666, *, 333</code> finds phrases where cipher 1=666 and cipher 3=333, ignoring cipher 2)</li>
                  <li>Filter results by starting letter (A–Z) or word count</li>
                  <li>Hover the <span className="text-green-600">✨</span> sparkle to see who discovered a phrase first</li>
                </ul>
              </div>

              <div className="border border-green-900/30 rounded-xl p-4 bg-green-950/20">
                <h3 className="text-base font-bold text-green-400 mb-2">Vault</h3>
                <ul className="text-green-300 text-sm leading-relaxed space-y-1.5 list-disc list-inside">
                  <li>Create an account to save phrases with tags &amp; folder organization</li>
                  <li>Import/export all phrases with full metadata (tags, folders) via JSON or CSV</li>
                  <li>Filter by cipher — save/load your visible cipher presets</li>
                  <li>Lookup supports comma-separated text or numeric values</li>
                  <li>Bulk select with click-drag, drag phrases onto folders to categorize</li>
                </ul>
              </div>

              <div className="border border-green-900/30 rounded-xl p-4 bg-green-950/20">
                <h3 className="text-base font-bold text-green-400 mb-2">Public Profile</h3>
                <ul className="text-green-300 text-sm leading-relaxed space-y-1.5 list-disc list-inside">
                  <li>Set a custom bio and a pinned vanity phrase from the Settings page</li>
                  <li>Your pinned phrase displays with all 14 cipher values</li>
                  <li>Link to your public profile page at the bottom of Settings</li>
                  <li>Others can explore your phrases and save them directly into their vault</li>
                </ul>
              </div>

              <div className="border border-green-900/30 rounded-xl p-4 bg-green-950/20">
                <h3 className="text-base font-bold text-green-400 mb-2">Feed</h3>
                <ul className="text-green-300 text-sm leading-relaxed space-y-1.5 list-disc list-inside">
                  <li>Live shoutbox — post messages and see them appear in real time</li>
                  <li>Recent discoveries feed showing the latest phrases found by all users</li>
                  <li>Leaderboard ranked by discovery count with pagination</li>
                </ul>
              </div>

              <div className="border border-green-900/30 rounded-xl p-4 bg-green-950/20">
                <h3 className="text-base font-bold text-green-400 mb-2">Plexenomy</h3>
                <p className="text-green-300 text-sm leading-relaxed mb-2">
                  A compact prime-factor notation:{' '}
                  <code className="px-1 py-0.5 bg-green-900/50 border border-green-700 rounded text-xs">0</code> = 2,{' '}
                  <code className="px-1 py-0.5 bg-green-900/50 border border-green-700 rounded text-xs">(x)</code> = x-th prime,
                  juxtaposition = product.
                </p>
                <ul className="text-green-300 text-sm leading-relaxed space-y-1.5 list-disc list-inside">
                  <li>By default encodes the <span className="text-cyan-400">Synx</span> value — change the source cipher with the <span className="text-amber-400">⚙️</span> cog, then pick "Plexenomy cipher source"</li>
                  <li>Type digits only (e.g. <code className="px-1 py-0.5 bg-green-900/50 border border-green-700 rounded text-xs">210</code>) to encode that number directly instead (green text)</li>
                  <li>Numbers with 9+ digits show "Too high!" instead of crashing</li>
                  <li>Type a Plexenomy expression (e.g. <code className="px-1 py-0.5 bg-green-900/50 border border-green-700 rounded text-xs">(0)0</code>) to decode it — the result appears after "Plexenomy =" (white text)</li>
                </ul>
                <p className="text-green-300 text-sm leading-relaxed mt-2">
                  Examples: <code className="px-1 py-0.5 bg-green-900/50 border border-green-700 rounded text-xs">0</code> = 2,{' '}
                  <code className="px-1 py-0.5 bg-green-900/50 border border-green-700 rounded text-xs">00</code> = 4,{' '}
                  <code className="px-1 py-0.5 bg-green-900/50 border border-green-700 rounded text-xs">(0)</code> = 3,{' '}
                  <code className="px-1 py-0.5 bg-green-900/50 border border-green-700 rounded text-xs">(0)0</code> = 6,{' '}
                  <code className="px-1 py-0.5 bg-green-900/50 border border-green-700 rounded text-xs">((0))</code> = 5
                </p>
              </div>
                </>
              ) : (
                <div className="space-y-4">
                  <div className="cipher-dropdown">
                    <button
                      onClick={() => setShowCipherDropdown(!showCipherDropdown)}
                      className="w-full px-4 py-3 bg-black border border-green-600 rounded-lg focus:border-green-400 focus:outline-none text-green-400 text-sm text-left flex items-center justify-between"
                    >
                      <span>{selectedCipherKey}</span>
                      <span className={`text-green-600 transition-transform duration-200 ${showCipherDropdown ? 'rotate-180' : ''}`}>▼</span>
                    </button>
                    {showCipherDropdown && (
                      <div className="mt-1 bg-black border border-green-600 rounded-lg shadow-2xl max-h-[40vh] overflow-y-auto scrollbar-thin scrollbar-thumb-green-800 scrollbar-track-transparent">
                        <div className="py-1">
                          <div className="px-3 py-1.5 text-xs text-stone-500 font-medium uppercase tracking-wider">AQ Group</div>
                          {alphanumericCiphers.map(c => (
                            <button
                              key={c}
                              onClick={() => { setSelectedCipherKey(c); setShowCipherDropdown(false) }}
                              className={`w-full text-left px-3 py-2 text-sm transition-colors ${
                                selectedCipherKey === c
                                  ? 'text-green-400 bg-green-900/30'
                                  : 'text-green-500 hover:text-green-400 hover:bg-green-900/20'
                              }`}
                            >
                              {c}
                            </button>
                          ))}
                          <div className="border-t border-green-800/30 my-1"></div>
                          <div className="px-3 py-1.5 text-xs text-green-600 font-medium uppercase tracking-wider">NQ Group</div>
                          {qwertyCiphers.map(c => (
                            <button
                              key={c}
                              onClick={() => { setSelectedCipherKey(c); setShowCipherDropdown(false) }}
                              className={`w-full text-left px-3 py-2 text-sm transition-colors ${
                                selectedCipherKey === c
                                  ? 'text-green-400 bg-green-900/30'
                                  : 'text-green-500 hover:text-green-400 hover:bg-green-900/20'
                              }`}
                            >
                              {c}
                            </button>
                          ))}
                          <div className="border-t border-green-800/30 my-1"></div>
                          <div className="px-3 py-1.5 text-xs text-cyan-500 font-medium uppercase tracking-wider">Other</div>
                          {otherCiphers.map(c => (
                            <button
                              key={c}
                              onClick={() => { setSelectedCipherKey(c); setShowCipherDropdown(false) }}
                              className={`w-full text-left px-3 py-2 text-sm transition-colors ${
                                selectedCipherKey === c
                                  ? 'text-green-400 bg-green-900/30'
                                  : 'text-green-500 hover:text-green-400 hover:bg-green-900/20'
                              }`}
                            >
                              {c}
                            </button>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>

                  <div className="border border-green-800/30 rounded-lg p-4 bg-green-950/10">
                    {(() => {
                      const chars = qwertyCiphers.includes(selectedCipherKey)
                        ? [...'1234567890qwertyuiopasdfghjklzxcvbnm']
                        : [...'abcdefghijklmnopqrstuvwxyz0123456789']
                      const letterChars = chars.filter(c => c >= 'a' && c <= 'z')
                      const digitChars = chars.filter(c => c >= '0' && c <= '9')
                      return (
                        <div className="space-y-4">
                          {letterChars.length > 0 && (
                            <div>
                              <div className="grid grid-cols-[repeat(auto-fill,minmax(44px,1fr))] gap-x-1 gap-y-2">
                                {letterChars.map(char => {
                                  const value = calculateAll(char).find(r => r.name === selectedCipherKey)?.value ?? 0
                                  return (
                                    <div key={char} className="flex flex-col items-center">
                                      <span className="text-sm font-mono text-amber-400 leading-tight">{char}</span>
                                      <span className="text-[11px] font-mono tabular-nums text-green-200/80 leading-tight">{value}</span>
                                    </div>
                                  )
                                })}
                              </div>
                            </div>
                          )}
                          {digitChars.length > 0 && (
                            <>
                              <div className="border-t border-green-800/30"></div>
                              <div className="grid grid-cols-[repeat(auto-fill,minmax(44px,1fr))] gap-x-1 gap-y-2">
                                {digitChars.map(char => {
                                  const value = calculateAll(char).find(r => r.name === selectedCipherKey)?.value ?? 0
                                  return (
                                    <div key={char} className="flex flex-col items-center">
                                      <span className="text-sm font-mono text-green-400 leading-tight">{char}</span>
                                      <span className="text-[11px] font-mono tabular-nums text-green-200/80 leading-tight">{value}</span>
                                    </div>
                                  )
                                })}
                              </div>
                            </>
                          )}
                        </div>
                      )
                    })()}
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      )}

    </div>
  )
}