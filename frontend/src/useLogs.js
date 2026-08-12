import { useState, useEffect, useCallback } from 'react'
import { fetchRecentLogs } from './api'

const POLL_INTERVAL_MS = 4000

export function useLogs(limit = 500) {
  const [logs, setLogs] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const load = useCallback(async () => {
    try {
      const data = await fetchRecentLogs(limit)
      setLogs(data)
      setError(null)
    } catch (err) {
      setError(err.message || 'Failed to load logs')
    } finally {
      setLoading(false)
    }
  }, [limit])

  useEffect(() => {
    load()
    const interval = setInterval(load, POLL_INTERVAL_MS)
    return () => clearInterval(interval)
  }, [load])

  return { logs, loading, error }
}
