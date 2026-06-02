/**
 * useWorldSocket.ts — V0.7 WebSocket 连接管理
 * 自动重连、心跳检测、消息队列
 */

import { useEffect, useRef, useState, useCallback } from 'react'
import type { ConnectionState } from './types'

export type WSMessage =
  | { type: 'pong' }
  | { type: 'state'; data: unknown }
  | { type: 'possess_reply'; agent_id: string; text: string }
  | { type: string; [k: string]: unknown }

export interface UseWorldSocketOptions {
  onMessage?: (data: WSMessage) => void
  onPossessReply?: (reply: { agent_id: string; text: string }) => void
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
    onPossessReply,
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
  const reconnectTimer = useRef<ReturnType<typeof setTimeout> | null>(null)
  const heartbeatTimer = useRef<ReturnType<typeof setInterval> | null>(null)
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

  const stopHeartbeat = () => {
    if (heartbeatTimer.current) {
      clearInterval(heartbeatTimer.current)
      heartbeatTimer.current = null
    }
  }

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
        const data = JSON.parse(event.data) as WSMessage
        if (data.type === 'pong') {
          setLastPong(new Date())
          return
        }
        if (data.type === 'possess_reply' && onPossessReply) {
          onPossessReply({
            agent_id: String((data as { agent_id?: string }).agent_id ?? ''),
            text: String((data as { text?: string }).text ?? ''),
          })
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
  }, [onMessage, onPossessReply, onOpen, onClose, flushQueue, startHeartbeat, reconnectInterval, maxReconnectAttempts])

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