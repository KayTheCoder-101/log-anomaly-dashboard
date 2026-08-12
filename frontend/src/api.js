import axios from 'axios'

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

export async function fetchRecentLogs(limit = 500) {
  const response = await axios.get(`${API_URL}/logs`, {
    params: { limit },
  })
  return response.data
}
