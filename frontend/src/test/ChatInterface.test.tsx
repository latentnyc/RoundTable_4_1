import { describe, it, expect, vi, beforeEach } from 'vitest'
import React from 'react'
import { render, screen, fireEvent } from '@testing-library/react'
import ChatInterface from '../components/ChatInterface'
import { useSocketStore } from '../lib/socket'
import { useSocketContext } from '../lib/SocketProvider'

// Mock context and stores
vi.mock('../lib/SocketProvider', () => {
  const mockSocket = {
    emit: vi.fn(),
    on: vi.fn(),
    off: vi.fn(),
  }
  return {
    useSocketContext: vi.fn().mockReturnValue({ socket: mockSocket }),
  }
})

vi.mock('../store/authStore', () => ({
  useAuthStore: vi.fn().mockImplementation((selector) => {
    const state = {
      profile: { id: 'player-1', username: 'Gimli' },
      user: { uid: 'user-123' },
    }
    return selector(state)
  }),
}))

// Mock CommandSuggestions to isolate ChatInterface testing
vi.mock('./CommandSuggestions', () => ({
  default: () => <div data-testid="command-suggestions" />
}))

describe('ChatInterface', () => {
  let mockSocket: any

  beforeEach(() => {
    vi.clearAllMocks()
    const context = useSocketContext()
    mockSocket = context.socket

    // Clear and configure Zustand store
    useSocketStore.getState().setMessages([])
    useSocketStore.getState().setGameState(null)
  })

  it('renders chat message chronicle empty state when there are no messages', () => {
    render(<ChatInterface campaignId="campaign-abc" />)
    expect(screen.getByText('The chronicle begins here...')).toBeInTheDocument()
  })

  it('renders messages correctly (Player, DM, and System messages)', () => {
    const messages = [
      { sender_id: 'player-1', sender_name: 'Gimli', content: 'I hit it with my axe!', timestamp: '12:00' },
      { sender_id: 'dm', sender_name: 'Dungeon Master', content: 'The monster roars in pain.', timestamp: '12:01' },
      { sender_id: 'system', sender_name: 'System', content: 'It is now Gimli turn!', timestamp: '12:02', is_system: true }
    ]

    useSocketStore.getState().setMessages(messages)

    render(<ChatInterface campaignId="campaign-abc" />)

    expect(screen.getByText('I hit it with my axe!')).toBeInTheDocument()
    expect(screen.getByText('The monster roars in pain.')).toBeInTheDocument()
    expect(screen.getByText('It is now Gimli turn!')).toBeInTheDocument()
  })

  it('emits chat_message and restores input focus when typing and clicking send', () => {
    render(<ChatInterface campaignId="campaign-abc" />)

    const input = screen.getByPlaceholderText(/What do you do\?/i) as HTMLInputElement
    const sendButton = screen.getByRole('button')

    // Simulate typing
    fireEvent.change(input, { target: { value: 'Hello DM!' } })
    expect(input.value).toBe('Hello DM!')

    // Click Send
    fireEvent.click(sendButton)

    expect(mockSocket.emit).toHaveBeenCalledWith('chat_message', expect.objectContaining({
      content: 'Hello DM!',
      sender_name: 'Gimli',
      sender_id: 'player-1'
    }))

    // Input should be cleared and focused
    expect(input.value).toBe('')
    expect(document.activeElement).toBe(input)
  })

  it('renders and triggers End Turn button when it is the player\'s turn in combat', () => {
    const characterId = 'player-1'

    // Configure combat active state
    useSocketStore.getState().setGameState({
      session_id: 'campaign-abc',
      turn_index: 2,
      phase: 'combat',
      active_entity_id: 'player-1', // active!
      party: [
        { id: 'player-1', name: 'Gimli', user_id: 'player-1', sheet_data: {} } as any
      ],
      enemies: [],
      npcs: [],
      turn_order: ['player-1'],
      combat_log: []
    })

    render(<ChatInterface campaignId="campaign-abc" characterId={characterId} />)

    const endTurnBtn = screen.getByText('End Turn')
    expect(endTurnBtn).toBeInTheDocument()

    // Click End Turn
    fireEvent.click(endTurnBtn)

    expect(mockSocket.emit).toHaveBeenCalledWith('chat_message', {
      content: '@endturn',
      sender_name: 'Gimli',
      sender_id: 'player-1',
    })
  })
})
