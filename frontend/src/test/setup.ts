import '@testing-library/jest-dom'

// Mock matchMedia
Object.defineProperty(window, 'matchMedia', {
  writable: true,
  value: vi.fn().mockImplementation(query => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: vi.fn(), // deprecated
    removeListener: vi.fn(), // deprecated
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    dispatchEvent: vi.fn(),
  })),
})

// Mock scrollIntoView
window.HTMLElement.prototype.scrollIntoView = vi.fn()

// Mock ResizeObserver
class ResizeObserverMock {
  observe = vi.fn()
  unobserve = vi.fn()
  disconnect = vi.fn()
}
window.ResizeObserver = ResizeObserverMock

// Mock localStorage / sessionStorage (jsdom's are unreliable under an opaque origin)
class StorageMock implements Storage {
  private store: Record<string, string> = {}
  getItem = vi.fn((key: string) => (key in this.store ? this.store[key] : null))
  setItem = vi.fn((key: string, value: string) => { this.store[key] = String(value) })
  removeItem = vi.fn((key: string) => { delete this.store[key] })
  clear = vi.fn(() => { this.store = {} })
  key = vi.fn((index: number) => Object.keys(this.store)[index] ?? null)
  get length() { return Object.keys(this.store).length }
  [name: string]: any
}
Object.defineProperty(window, 'localStorage', { writable: true, value: new StorageMock() })
Object.defineProperty(window, 'sessionStorage', { writable: true, value: new StorageMock() })
