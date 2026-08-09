import { Component, type ErrorInfo, type ReactNode } from 'react'
import ErrorState from '../ui/ErrorState'

interface Props {
  children: ReactNode
}

interface State {
  error: Error | null
}

/**
 * The app uses BrowserRouter + <Routes>, not a data router, so there is no
 * `errorElement` to fall back on. Keyed on pathname by the caller, so
 * navigating away clears a crashed subtree.
 */
export default class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null }

  static getDerivedStateFromError(error: Error): State {
    return { error }
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error('Unhandled render error:', error, info.componentStack)
  }

  render() {
    if (this.state.error) {
      return (
        <ErrorState
          title="This page hit an error"
          message={this.state.error.message || 'An unexpected error occurred while rendering.'}
          onRetry={() => this.setState({ error: null })}
          backTo="/"
          backLabel="Go home"
        />
      )
    }
    return this.props.children
  }
}
