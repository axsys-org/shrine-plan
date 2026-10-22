import { useState, useEffect } from 'react'
import { Routes, Route } from 'react-router-dom'
import { Calculator } from './Calculator'
import { ErrorBoundary } from './ErrorBoundary'
import type { CipherResult } from '@gematria/shared'

export interface User {
  id: string
  username: string
}

export interface StoredPhrase {
  phrase: string
  results: CipherResult[]
  timestamp: number | string
  category?: string
  tags?: string[] | string  // Can be array or comma-separated string from backend
}

// Shrine serves this app from one node, owned by whoever runs it, so there
// is nothing to sign in to: the session is the node.
const LOCAL_USER: User = { id: 'shrine', username: 'shrine' }

function App() {
  const [user, setUser] = useState<User | null>(LOCAL_USER)
  const [storedPhrases, setStoredPhrases] = useState<StoredPhrase[]>([])
  const [userCategories, setUserCategories] = useState<string[]>(() => {
    const saved = localStorage.getItem('userCategories')
    if (saved) {
      try {
        return JSON.parse(saved)
      } catch {
        return ['uncategorized']
      }
    }
    return ['uncategorized']
  })

  useEffect(() => {
    localStorage.setItem('userCategories', JSON.stringify(userCategories))
  }, [userCategories])

  useEffect(() => {
    localStorage.setItem('session', 'shrine')
    localStorage.setItem('user', JSON.stringify(LOCAL_USER))
    if (!user) setUser(LOCAL_USER)
  }, [user])

  return (
    <Routes>
      <Route
        path="*"
        element={
          <ErrorBoundary>
            <Calculator
              user={user}
              setUser={setUser}
              storedPhrases={storedPhrases}
              setStoredPhrases={setStoredPhrases}
              userCategories={userCategories}
              setUserCategories={setUserCategories}
            />
          </ErrorBoundary>
        }
      />
    </Routes>
  )
}

export default App
