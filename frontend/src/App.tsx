import { useEffect, useState } from 'react'

type BackendStatus = { status: string; service?: string; version?: string }

function App() {
  const [backend, setBackend] = useState<BackendStatus | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    fetch('http://localhost:8000/')
      .then((r) => r.json())
      .then(setBackend)
      .catch((e) => setError(String(e)))
  }, [])

  return (
    <main style={{ fontFamily: 'system-ui, sans-serif', padding: '2rem', maxWidth: 640 }}>
      <h1>Course Agent</h1>
      <p style={{ color: '#666' }}>Week 1 scaffold. No features yet.</p>
      <section style={{ marginTop: '2rem' }}>
        <h2 style={{ fontSize: '1rem' }}>Backend status</h2>
        {error && <pre style={{ color: 'crimson' }}>Error: {error}</pre>}
        {backend && <pre>{JSON.stringify(backend, null, 2)}</pre>}
        {!backend && !error && <p>Connecting…</p>}
      </section>
    </main>
  )
}

export default App
