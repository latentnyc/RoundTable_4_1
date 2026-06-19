import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import ErrorBoundary from '../components/ErrorBoundary'

// A component that throws an error when told to
function BuggyComponent({ shouldThrow }: { shouldThrow: boolean }) {
  if (shouldThrow) {
    throw new Error('Component crashed!')
  }
  return <div>Safe Content</div>
}

describe('ErrorBoundary', () => {
  // Suppress console.error output during testing since throwing is expected
  let consoleErrorSpy: any

  beforeEach(() => {
    consoleErrorSpy = vi.spyOn(console, 'error').mockImplementation(() => {})
  })

  afterEach(() => {
    consoleErrorSpy.mockRestore()
  })

  it('renders children when there is no error', () => {
    render(
      <ErrorBoundary label="Test Section">
        <BuggyComponent shouldThrow={false} />
      </ErrorBoundary>
    )
    expect(screen.getByText('Safe Content')).toBeInTheDocument()
  })

  it('renders fallback UI when a child component throws', () => {
    render(
      <ErrorBoundary label="Test Section">
        <BuggyComponent shouldThrow={true} />
      </ErrorBoundary>
    )
    expect(screen.getByText('Test Section crashed.')).toBeInTheDocument()
    expect(screen.getByText('Error details')).toBeInTheDocument()
    expect(screen.getByText(/Component crashed!/)).toBeInTheDocument()
  })

  it('resets the error state when "Try Again" is clicked', () => {
    const { rerender } = render(
      <ErrorBoundary label="Test Section">
        <BuggyComponent shouldThrow={true} />
      </ErrorBoundary>
    )

    expect(screen.getByText('Test Section crashed.')).toBeInTheDocument()

    // Try again with safe content
    rerender(
      <ErrorBoundary label="Test Section">
        <BuggyComponent shouldThrow={false} />
      </ErrorBoundary>
    )

    const resetButton = screen.getByText('Try Again')
    fireEvent.click(resetButton)

    expect(screen.queryByText('Test Section crashed.')).not.toBeInTheDocument()
    expect(screen.getByText('Safe Content')).toBeInTheDocument()
  })
})
