/**
 * Hook for WebSocket connection management.
 */
import { useState, useEffect, useRef, useCallback } from 'react'
import { NavigationWebSocket } from '../services/websocket'

export function useWebSocket(navigationId) {
  const [connected, setConnected] = useState(false)
  const [lastMessage, setLastMessage] = useState(null)
  const wsRef = useRef(null)

  useEffect(() => {
    if (!navigationId) {
      setConnected(false)
      setLastMessage(null)
      return
    }

    const ws = new NavigationWebSocket(
      navigationId,
      (message) => setLastMessage(message),
      () => setConnected(true),
      () => setConnected(false)
    )

    wsRef.current = ws
    ws.connect()

    return () => {
      ws.close()
    }
  }, [navigationId])

  const send = useCallback((data) => {
    wsRef.current?.send(data)
  }, [])

  return { connected, lastMessage, send }
}
