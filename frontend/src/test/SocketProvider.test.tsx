import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import React from 'react'
import { act, renderHook } from '@testing-library/react'
import { SocketProvider, useSocketContext } from '../lib/SocketProvider'
import { useSocketStore } from '../lib/socket'
import { io } from 'socket.io-client'

// Mock socket.io-client
vi.mock('socket.io-client', () => {
  const socketInstance = {
    connected: false,
    auth: {},
    query: {},
    on: vi.fn(),
    once: vi.fn(),
    off: vi.fn(),
    emit: vi.fn(),
    disconnect: vi.fn(),
    connect: vi.fn(),
    io: {
      on: vi.fn(),
    },
  }
  return {
    io: vi.fn().mockReturnValue(socketInstance),
    Socket: vi.fn(),
  }
})

// Mock authStore
vi.mock('../store/authStore', () => ({
  useAuthStore: vi.fn().mockImplementation((selector) => {
    const state = {
      token: 'test-token',
      user: { uid: 'user-123' },
    }
    return selector(state)
  }),
}))

describe('SocketProvider', () => {
  let mockSocket: any
  let listeners: Record<string, ((...args: any[]) => void)[]> = {}
  let ioListeners: Record<string, ((...args: any[]) => void)[]> = {}

  beforeEach(() => {
    vi.clearAllMocks()
    listeners = {}
    ioListeners = {}

    // Grab the mocked socket instance
    mockSocket = vi.mocked(io).mock.results[0]?.value || (io as any)()

    mockSocket.on.mockImplementation((event: string, cb: (...args: any[]) => void) => {
      if (!listeners[event]) listeners[event] = []
      listeners[event].push(cb)
    })

    mockSocket.once.mockImplementation((event: string, cb: (...args: any[]) => void) => {
      if (!listeners[event]) listeners[event] = []
      listeners[event].push(cb)
    })

    mockSocket.off.mockImplementation((event: string, cb: (...args: any[]) => void) => {
      if (listeners[event]) {
        listeners[event] = listeners[event].filter((l) => l !== cb)
      }
    })

    mockSocket.io.on.mockImplementation((event: string, cb: (...args: any[]) => void) => {
      if (!ioListeners[event]) ioListeners[event] = []
      ioListeners[event].push(cb)
    })

    // Reset Zustand store state
    useSocketStore.getState().setGameState(null)
    useSocketStore.getState().setConnected(false)
    useSocketStore.getState().setMessages([])
  })

  afterEach(() => {
    // Clear connection promise and disconnect
    const { result } = renderHook(() => useSocketContext(), {
      wrapper: ({ children }) => <SocketProvider>{children}</SocketProvider>,
    })
    act(() => {
      result.current.disconnect()
    })
  })

  const triggerEvent = (event: string, ...args: any[]) => {
    if (listeners[event]) {
      listeners[event].forEach((cb) => cb(...args))
    }
  }

  const triggerIOEvent = (event: string, ...args: any[]) => {
    if (ioListeners[event]) {
      ioListeners[event].forEach((cb) => cb(...args))
    }
  }

  it('establishes a connection and joins the campaign', async () => {
    const wrapper = ({ children }: { children: React.ReactNode }) => (
      <SocketProvider>{children}</SocketProvider>
    )
    const { result } = renderHook(() => useSocketContext(), { wrapper })

    let connectPromise: Promise<void>
    act(() => {
      connectPromise = result.current.connect('campaign-abc')
    })

    // Simulate connection event
    act(() => {
      triggerEvent('connect')
    })

    await act(async () => {
      await connectPromise
    })

    expect(io).toHaveBeenCalledWith(
      expect.any(String),
      expect.objectContaining({
        auth: { token: 'test-token' },
        query: { campaignId: 'campaign-abc' },
        transports: ['websocket'],
      })
    )

    expect(mockSocket.emit).toHaveBeenCalledWith('join_campaign', {
      user_id: 'user-123',
      campaign_id: 'campaign-abc',
    })
    expect(useSocketStore.getState().isConnected).toBe(true)
  })

  it('updates game state when receiving full game_state_update', async () => {
    const wrapper = ({ children }: { children: React.ReactNode }) => (
      <SocketProvider>{children}</SocketProvider>
    )
    const { result } = renderHook(() => useSocketContext(), { wrapper })

    act(() => {
      result.current.connect('campaign-abc')
      triggerEvent('connect')
    })

    const mockState: any = {
      session_id: 'campaign-abc',
      turn_index: 0,
      phase: 'exploration',
      active_entity_id: null,
      party: [],
      enemies: [],
      npcs: [],
      turn_order: [],
      combat_log: [],
    }

    act(() => {
      triggerEvent('game_state_update', mockState)
    })

    expect(useSocketStore.getState().gameState).toEqual(mockState)
  })

  it('applies patches incrementally with game_state_patch', async () => {
    const wrapper = ({ children }: { children: React.ReactNode }) => (
      <SocketProvider>{children}</SocketProvider>
    )
    const { result } = renderHook(() => useSocketContext(), { wrapper })

    act(() => {
      result.current.connect('campaign-abc')
      triggerEvent('connect')
    })

    const baseState: any = {
      session_id: 'campaign-abc',
      turn_index: 0,
      phase: 'exploration',
      active_entity_id: null,
      party: [{ id: 'p1', name: 'Adventurer', hp_current: 10, hp_max: 10, ac: 15, initiative: 0, speed: 30, position: { q: 0, r: 0, s: 0 }, inventory: [], conditions: [] }],
      enemies: [],
      npcs: [],
      turn_order: [],
      combat_log: [],
    }

    act(() => {
      useSocketStore.getState().setGameState(baseState)
    })

    // JSON patch to change hp_current of party member p1 to 5
    const patch = [
      { op: 'replace', path: '/party/0/hp_current', value: 5 }
    ]

    act(() => {
      triggerEvent('game_state_patch', patch)
    })

    const updatedState = useSocketStore.getState().gameState
    expect(updatedState?.party[0].hp_current).toBe(5)
  })

  it('resyncs or reconnects on consecutive patch failures', async () => {
    const wrapper = ({ children }: { children: React.ReactNode }) => (
      <SocketProvider>{children}</SocketProvider>
    )
    const { result } = renderHook(() => useSocketContext(), { wrapper })

    act(() => {
      result.current.connect('campaign-abc')
      triggerEvent('connect')
    })

    const baseState: any = {
      session_id: 'campaign-abc',
      turn_index: 0,
      phase: 'exploration',
      active_entity_id: null,
      party: [],
      enemies: [],
      npcs: [],
      turn_order: [],
      combat_log: [],
    }

    act(() => {
      useSocketStore.getState().setGameState(baseState)
    })

    // Patch that fails (referencing non-existent index)
    const badPatch = [
      { op: 'replace', path: '/party/10/hp_current', value: 5 }
    ]

    // Strike 1
    act(() => {
      triggerEvent('game_state_patch', badPatch)
    })
    expect(mockSocket.emit).toHaveBeenLastCalledWith('request_full_state', {
      user_id: 'user-123',
      campaign_id: 'campaign-abc',
    })

    // Strike 2
    act(() => {
      triggerEvent('game_state_patch', badPatch)
    })
    expect(mockSocket.emit).toHaveBeenLastCalledWith('request_full_state', {
      user_id: 'user-123',
      campaign_id: 'campaign-abc',
    })

    // Strike 3 - triggers reconnect
    act(() => {
      triggerEvent('game_state_patch', badPatch)
    })
    expect(mockSocket.disconnect).toHaveBeenCalled()
    expect(mockSocket.connect).toHaveBeenCalled()
  })

  it('requests full state on socket reconnection event', async () => {
    const wrapper = ({ children }: { children: React.ReactNode }) => (
      <SocketProvider>{children}</SocketProvider>
    )
    const { result } = renderHook(() => useSocketContext(), { wrapper })

    act(() => {
      result.current.connect('campaign-abc')
      triggerEvent('connect')
    })

    act(() => {
      triggerIOEvent('reconnect')
    })

    expect(mockSocket.emit).toHaveBeenCalledWith('join_campaign', {
      user_id: 'user-123',
      campaign_id: 'campaign-abc',
    })
  })

  it('requests a full-state resync when a patch reports a version gap', async () => {
    const wrapper = ({ children }: { children: React.ReactNode }) => (
      <SocketProvider>{children}</SocketProvider>
    )
    const { result } = renderHook(() => useSocketContext(), { wrapper })

    act(() => {
      result.current.connect('campaign-abc')
      triggerEvent('connect')
    })

    const baseState: any = {
      session_id: 'campaign-abc',
      version: 5,
      turn_index: 0,
      phase: 'exploration',
      active_entity_id: null,
      party: [{ id: 'p1', name: 'Adventurer', hp_current: 10, hp_max: 10, ac: 15, initiative: 0, speed: 30, position: { x: 0, y: 0 }, inventory: [], conditions: [] }],
      enemies: [],
      npcs: [],
      turn_order: [],
      combat_log: [],
    }

    act(() => {
      useSocketStore.getState().setGameState(baseState)
    })

    // base_version 7 != local version 5 -> we missed a delta; must resync, not apply.
    const gappedPatch = {
      base_version: 7,
      version: 8,
      patch: [{ op: 'replace', path: '/party/0/hp_current', value: 5 }],
    }

    act(() => {
      triggerEvent('game_state_patch', gappedPatch)
    })

    expect(mockSocket.emit).toHaveBeenLastCalledWith('request_full_state', {
      user_id: 'user-123',
      campaign_id: 'campaign-abc',
    })
    expect(useSocketStore.getState().gameState?.party[0].hp_current).toBe(10)
  })

  it('applies a versioned patch when base_version matches local version', async () => {
    const wrapper = ({ children }: { children: React.ReactNode }) => (
      <SocketProvider>{children}</SocketProvider>
    )
    const { result } = renderHook(() => useSocketContext(), { wrapper })

    act(() => {
      result.current.connect('campaign-abc')
      triggerEvent('connect')
    })

    const baseState: any = {
      session_id: 'campaign-abc',
      version: 5,
      turn_index: 0,
      phase: 'exploration',
      active_entity_id: null,
      party: [{ id: 'p1', name: 'Adventurer', hp_current: 10, hp_max: 10, ac: 15, initiative: 0, speed: 30, position: { x: 0, y: 0 }, inventory: [], conditions: [] }],
      enemies: [],
      npcs: [],
      turn_order: [],
      combat_log: [],
    }

    act(() => {
      useSocketStore.getState().setGameState(baseState)
    })

    const goodPatch = {
      base_version: 5,
      version: 6,
      patch: [
        { op: 'replace', path: '/version', value: 6 },
        { op: 'replace', path: '/party/0/hp_current', value: 3 },
      ],
    }

    act(() => {
      triggerEvent('game_state_patch', goodPatch)
    })

    const updated = useSocketStore.getState().gameState
    expect(updated?.party[0].hp_current).toBe(3)
    expect(updated?.version).toBe(6)
  })
})
