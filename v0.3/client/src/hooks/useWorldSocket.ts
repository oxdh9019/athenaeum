/**
 * useWorldSocket.ts — WebSocket 连接管理
 * 自动重连、心跳检测、消息队列
 */

import { useEffect, useRef, useState, useCallback } from 'react'

export type ConnectionState = 'connecting' | 'connected' | 'disconnected' | 'reconnecting'

interface UseWorldSocketOptions {
  onMessage?: (data: any) => void
  onOpen?: () => void
  onClose?: () => void
  reconnectInterval?: number
  maxReconnectAttempts?: number
  heartbeatInterval?: number
}

export interface UseWorldSocketReturn {
  ws: WebSocket | null
  connectionState: ConnectionState
  lastPong: Date | null
  send: (data: any) => void
  reconnect: () => void
}

export function useWorldSocket(options: UseWorldSocketOptions = {}): UseWorldSocketReturn {
  const {
    onMessage,
    onOpen,
    onClose,
    reconnectInterval = 3000,
    maxReconnectAttempts = 5,
    heartbeatInterval = 30000,
  } = options

  const [ws, setWs] = useState<WebSocket | null>(null)
  const [connectionState, setConnectionState] = useState<ConnectionState>('connecting')
  const [lastPong, setLastPong] = useState<Date | null>(null)

  const reconnectCount = useRef(0)
  const reconnectTimer = useRef<NodeJS.Timeout | null>(null)
  const heartbeatTimer = useRef<NodeJS.Timeout | null>(null)
  const messageQueue = useRef<any[]>([])
  const wsRef = useRef<WebSocket | null>(null)

  const send = useCallback((data: any) => {
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify(data))
    } else {
      messageQueue.current.push(data)
    }
  }, [ws])

  const flushQueue = useCallback(() => {
    while (messageQueue.current.length > 0) {
      const data = messageQueue.current.shift()
      send(data)
    }
  }, [send])

  const startHeartbeat = useCallback(() => {
    if (heartbeatTimer.current) {
      clearInterval(heartbeatTimer.current)
    }
    heartbeatTimer.current = setInterval(() => {
      if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
        wsRef.current.send(JSON.stringify({ type: 'ping' }))
      }
    }, heartbeatInterval)
  }, [heartbeatInterval])

  const connect = useCallback(() => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.close()
    }

    setConnectionState('connecting')
    const websocket = new WebSocket(`ws://${window.location.host}/ws`)
    wsRef.current = websocket

    websocket.onopen = () => {
      setConnectionState('connected')
      reconnectCount.current = 0
      flushQueue()
      startHeartbeat()
      onOpen?.()
    }

    websocket.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data)
        if (data.type === 'pong') {
          setLastPong(new Date())
          return
        }
        onMessage?.(data)
      } catch (e) {
        console.error('[WS] 解析消息失败:', e)
      }
    }

    websocket.onclose = () => {
      setConnectionState('disconnected')
      stopHeartbeat()
      onClose?.()

      if (reconnectCount.current < maxReconnectAttempts) {
        setConnectionState('reconnecting')
        reconnectCount.current += 1
        reconnectTimer.current = setTimeout(connect, reconnectInterval)
      }
    }

    websocket.onerror = (error) => {
      console.error('[WS] 连接错误:', error)
    }

    setWs(websocket)
  }, [onMessage, onOpen, onClose, flushQueue, startHeartbeat, reconnectInterval, maxReconnectAttempts])

  const stopHeartbeat = () => {
    if (heartbeatTimer.current) {
      clearInterval(heartbeatTimer.current)
      heartbeatTimer.current = null
    }
  }

  const reconnect = useCallback(() => {
    reconnectCount.current = 0
    if (reconnectTimer.current) {
      clearTimeout(reconnectTimer.current)
      reconnectTimer.current = null
    }
    connect()
  }, [connect])

  useEffect(() => {
    connect()
    return () => {
      stopHeartbeat()
      if (reconnectTimer.current) {
        clearTimeout(reconnectTimer.current)
      }
      wsRef.current?.close()
    }
  }, [])

  return { ws, connectionState, lastPong, send, reconnect }
}