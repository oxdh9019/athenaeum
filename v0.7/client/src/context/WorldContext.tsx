/**
 * WorldContext.tsx — V0.7 世界状态管理
 * 使用 Context + useReducer 管理全局状态
 */

import React, { createContext, useContext, useReducer, ReactNode } from 'react'

// ==================== 类型定义 ====================

export interface Agent {
  id: string
  name: string
  location: string
  occupation?: string
  neighbors?: string[]
  is_active?: boolean
  personality?: {
    openness?: number
    conscientiousness?: number
    extraversion?: number
    agreeableness?: number
    neuroticism?: number
  }
  mood?: string
  intention?: string
  desires?: { safety: number; belonging: number; novelty: number }
  soul?: {
    core_desires?: Array<{ name: string; level: number }>
    inner_conflict?: { description: string }
    subconscious_rules?: Array<{ trigger: string; action: string }>
  }
  emotion_state?: { label: string; valence: number; arousal: number }
  active_goal?: string
  goal_progress?: number
  extended_personality?: Record<string, number>
}

export interface Location {
  id: string
  name: string
  tags: string[]
  agents: string[]
}

export interface DialogueEntry {
  from: string
  from_id: string
  to: string
  utterance: string
  micro_action?: string
  tick: number
}

export interface ActionEntry {
  agent_id: string
  agent_name: string
  action_type: string
  description: string
  target_location: string | null
  tick: number
}

export interface WorldState {
  tick_id: number
  time: { game_hour: number; time_of_day: string }
  weather: string
  tick_type: string
  agents: Agent[]
  locations: Location[]
  recent_dialogues: DialogueEntry[]
  recent_actions: ActionEntry[]
}

export type ViewMode = 'dashboard' | 'agents' | 'dialogue' | 'soul' | 'world' | 'diary' | 'timeline' | 'map' | 'possess'

// ==================== State & Action ====================

interface State {
  world: WorldState | null
  viewMode: ViewMode
  selectedAgentId: string | null
  possessAgent: string
  paused: boolean
  connected: boolean
  connectionState: 'connecting' | 'connected' | 'disconnected' | 'reconnecting'
}

type Action =
  | { type: 'SET_WORLD'; payload: WorldState }
  | { type: 'SET_VIEW_MODE'; payload: ViewMode }
  | { type: 'SET_SELECTED_AGENT'; payload: string | null }
  | { type: 'SET_POSSESS_AGENT'; payload: string }
  | { type: 'SET_PAUSED'; payload: boolean }
  | { type: 'SET_CONNECTED'; payload: boolean }
  | { type: 'SET_CONNECTION_STATE'; payload: 'connecting' | 'connected' | 'disconnected' | 'reconnecting' }
  | { type: 'ADD_DIALOGUE'; payload: DialogueEntry }
  | { type: 'ADD_ACTION'; payload: ActionEntry }

const initialState: State = {
  world: null,
  viewMode: 'dashboard',
  selectedAgentId: null,
  possessAgent: '',
  paused: false,
  connected: false,
  connectionState: 'connecting',
}

function reducer(state: State, action: Action): State {
  switch (action.type) {
    case 'SET_WORLD':
      return { ...state, world: action.payload }
    case 'SET_VIEW_MODE':
      return { ...state, viewMode: action.payload }
    case 'SET_SELECTED_AGENT':
      return { ...state, selectedAgentId: action.payload }
    case 'SET_POSSESS_AGENT':
      return { ...state, possessAgent: action.payload }
    case 'SET_PAUSED':
      return { ...state, paused: action.payload }
    case 'SET_CONNECTED':
      return { ...state, connected: action.payload }
    case 'SET_CONNECTION_STATE':
      return { ...state, connectionState: action.payload }
    case 'ADD_DIALOGUE':
      if (!state.world) return state
      return {
        ...state,
        world: {
          ...state.world,
          recent_dialogues: [...state.world.recent_dialogues, action.payload].slice(-50),
        },
      }
    case 'ADD_ACTION':
      if (!state.world) return state
      return {
        ...state,
        world: {
          ...state.world,
          recent_actions: [...state.world.recent_actions, action.payload].slice(-30),
        },
      }
    default:
      return state
  }
}

// ==================== Context ====================

interface WorldContextValue {
  state: State
  dispatch: React.Dispatch<Action>
}

const WorldContext = createContext<WorldContextValue | null>(null)

// ==================== Provider ====================

export function WorldProvider({ children }: { children: ReactNode }) {
  const [state, dispatch] = useReducer(reducer, initialState)

  return (
    <WorldContext.Provider value={{ state, dispatch }}>
      {children}
    </WorldContext.Provider>
  )
}

export function useWorld() {
  const ctx = useContext(WorldContext)
  if (!ctx) {
    throw new Error('useWorld must be used within WorldProvider')
  }
  return ctx
}

export function useWorldState() {
  const { state } = useWorld()
  return state
}

export function useWorldDispatch() {
  const { dispatch } = useWorld()
  return dispatch
}