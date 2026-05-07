import { Component, type ErrorInfo, type ReactNode } from 'react'

type Props = {
  name?: string
  children: ReactNode
}

type State = {
  hasError: boolean
}

export class ErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false }

  static getDerivedStateFromError(): State {
    return { hasError: true }
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error(`[ErrorBoundary:${this.props.name ?? 'unknown'}]`, error, errorInfo)
  }

  render() {
    if (this.state.hasError) {
      return (
        <div style={{ padding: 16, color: 'var(--accent-red)', fontFamily: 'var(--font-data)' }}>
          {this.props.name ?? 'View'} failed to render.
        </div>
      )
    }
    return this.props.children
  }
}
