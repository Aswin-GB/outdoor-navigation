/**
 * WebSocket service for real-time navigation updates.
 */
const normalizeWebSocketBase = (baseUrl, fallback) => {
  const candidate = (baseUrl || fallback).trim().replace(/\/+$/, '')
  return candidate || fallback
}

const WS_BASE = normalizeWebSocketBase(import.meta.env.VITE_WS_BASE_URL, 'ws://localhost:8000')

export class NavigationWebSocket {
  constructor(navigationId, onMessage, onConnect, onDisconnect) {
    this.navigationId = navigationId
    this.onMessage = onMessage
    this.onConnect = onConnect
    this.onDisconnect = onDisconnect
    this.ws = null
    this.reconnectAttempts = 0
    this.maxReconnectAttempts = 5
    this.reconnectDelay = 1000
    this.closed = false
  }

  connect() {
    if (this.closed || !this.navigationId) return

    const url = `${WS_BASE.replace(/\/$/, '')}/ws/navigation/${this.navigationId}/`
    this.ws = new WebSocket(url)

    this.ws.onopen = () => {
      this.reconnectAttempts = 0
      this.onConnect?.()
    }

    this.ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data)
        this.onMessage?.(data)
      } catch (e) {
        console.error('WebSocket message parse error:', e)
      }
    }

    this.ws.onclose = () => {
      this.onDisconnect?.()
      if (!this.closed && this.reconnectAttempts < this.maxReconnectAttempts) {
        this.reconnectAttempts++
        setTimeout(() => this.connect(), this.reconnectDelay * this.reconnectAttempts)
      }
    }

    this.ws.onerror = (error) => {
      console.error('WebSocket error:', error)
    }
  }

  send(data) {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(data))
    }
  }

  close() {
    this.closed = true
    this.ws?.close()
  }
}
