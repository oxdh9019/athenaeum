/**
 * ErrorBoundary.tsx — React 错误边界
 *
 * 捕获子组件渲染时的未捕获 JS 错误，显示降级 UI 而不是空白屏。
 * 注意：React ErrorBoundary **不能**捕获：
 *   - 异步错误（Promise rejection、setTimeout、event handler）
 *   - 服务端渲染错误
 *   - 自身抛出的错误
 * 这两类需要用 try/catch + 全局 unhandledrejection 监听。
 */

import { Component, type ErrorInfo, type ReactNode } from 'react'

interface Props {
  children: ReactNode
  fallback?: ReactNode
  onError?: (error: Error, errorInfo: ErrorInfo) => void
}

interface State {
  hasError: boolean
  error: Error | null
}

export class ErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false, error: null }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error }
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error('[ErrorBoundary] 捕获到子组件错误:', error, errorInfo)
    this.props.onError?.(error, errorInfo)
  }

  reset = () => {
    this.setState({ hasError: false, error: null })
  }

  render() {
    if (!this.state.hasError) return this.props.children

    if (this.props.fallback) return this.props.fallback

    return (
      <div
        role="alert"
        style={{
          padding: '24px',
          margin: '24px',
          background: 'var(--bg-secondary, #f5f5f5)',
          border: '1px solid var(--accent-red, #c33)',
          borderRadius: '8px',
        }}
      >
        <h2 style={{ color: 'var(--accent-red, #c33)', marginBottom: '12px' }}>
          ⚠️ 组件渲染失败
        </h2>
        <p style={{ marginBottom: '12px' }}>子组件抛出了未捕获的错误，界面已降级显示。</p>
        <details style={{ marginBottom: '12px' }}>
          <summary style={{ cursor: 'pointer' }}>查看错误详情</summary>
          <pre
            style={{
              marginTop: '8px',
              padding: '12px',
              background: 'rgba(0,0,0,0.05)',
              borderRadius: '4px',
              overflow: 'auto',
              fontSize: '12px',
            }}
          >
            {this.state.error?.stack || this.state.error?.message || '未知错误'}
          </pre>
        </details>
        <button
          onClick={this.reset}
          style={{
            padding: '6px 14px',
            background: 'var(--accent-cyan, #0aa)',
            color: 'white',
            border: 'none',
            borderRadius: '4px',
            cursor: 'pointer',
          }}
        >
          重试
        </button>
      </div>
    )
  }
}
