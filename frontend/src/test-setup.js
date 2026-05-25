import '@testing-library/jest-dom'

// recharts uses ResizeObserver which is not available in jsdom
globalThis.ResizeObserver = class {
  observe() {}
  unobserve() {}
  disconnect() {}
}
