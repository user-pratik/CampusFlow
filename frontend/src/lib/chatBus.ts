/**
 * Lightweight event bus for passing messages from the global Command Palette
 * into the already-mounted Chat window without prop drilling or remounting.
 *
 * Usage:
 *   Sender:   chatBus.send("hello world")
 *   Listener: chatBus.subscribe((msg) => sendMessage(msg))
 */

type ChatBusListener = (message: string) => void;

class ChatBus {
  private listeners: Set<ChatBusListener> = new Set();

  subscribe(fn: ChatBusListener) {
    this.listeners.add(fn);
    return () => { this.listeners.delete(fn); };
  }

  send(message: string) {
    this.listeners.forEach((fn) => fn(message));
  }
}

export const chatBus = new ChatBus();
