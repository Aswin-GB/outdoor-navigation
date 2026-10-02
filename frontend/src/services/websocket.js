/**
 * WebSocket service for real-time navigation updates.
 */
const getWebSocketBase = () => {
  const configuredBase = import.meta.env.VITE_WS_BASE_URL
    || import.meta.env.VITE_API_BASE_URL
    || 'http://localhost:8000'
  const url = new URL(configuredBase.trim())
  const securePage = typeof window !== 'undefined' && window.location.protocol === 'https:'
  url.protocol = securePage || url.protocol === 'https:' || url.protocol === 'wss:' ? 'wss:' : 'ws:'
  return url.href.replace(/\/+$/, '')
}

const WS_BASE = getWebSocketBase()

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
    this.reconnectTimer = null
  }

  connect() {
    if (this.closed || !this.navigationId) return

    const url = `${WS_BASE.replace(/\/$/, '')}/ws/navigation/${this.navigationId}/`
    try {
      this.ws = new WebSocket(url)
    } catch (error) {
      console.error('Unable to create navigation WebSocket:', error)
      this.onDisconnect?.()
      return
    }

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
        this.reconnectTimer = setTimeout(
          () => this.connect(),
          this.reconnectDelay * this.reconnectAttempts
        )
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
    if (this.reconnectTimer !== null) {
      clearTimeout(this.reconnectTimer)
      this.reconnectTimer = null
    }
    this.ws?.close()
  }
}
