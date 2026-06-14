"use client";

import { createContext, useContext, useState, useCallback, useRef } from "react";

export type WindowId = string;

export interface AgentWindow {
  id: WindowId;
  agentName: string;
  agentIcon: string;
  title: string;
  content: React.ReactNode;
  state: "open" | "minimized";
  position: { x: number; y: number };
  size: { width: number; height: number };
  zIndex: number;
  pinned: boolean;
  createdAt: Date;
}

interface WindowManagerContextType {
  windows: AgentWindow[];
  activeWindowId: WindowId | null;
  spawnWindow: (
    agentName: string,
    title: string,
    content: React.ReactNode,
    options?: Partial<Pick<AgentWindow, "agentIcon" | "size" | "position" | "pinned">>
  ) => WindowId;
  closeWindow: (id: WindowId) => void;
  minimizeWindow: (id: WindowId) => void;
  restoreWindow: (id: WindowId) => void;
  focusWindow: (id: WindowId) => void;
  moveWindow: (id: WindowId, position: { x: number; y: number }) => void;
  resizeWindow: (id: WindowId, size: { width: number; height: number }) => void;
  togglePin: (id: WindowId) => void;
  updateWindowContent: (id: WindowId, content: React.ReactNode) => void;
}

const WindowManagerContext = createContext<WindowManagerContextType | null>(null);

export function useWindowManager() {
  const ctx = useContext(WindowManagerContext);
  if (!ctx) throw new Error("useWindowManager must be used within WindowManagerProvider");
  return ctx;
}

const AGENT_ICONS: Record<string, string> = {
  "Deadline Agent": "⏰",
  "Academic Agent": "📊",
  "Notice Agent": "📢",
  "Schedule Agent": "📅",
  "Digest Agent": "📰",
  "Connector Agent": "🔗",
  "Action Agent": "⚡",
  "System": "🖥️",
  "Chat": "💬",
};

function getStaggeredPosition(index: number): { x: number; y: number } {
  const baseX = 80;
  const baseY = 80;
  const offset = 30;
  return {
    x: baseX + (index % 8) * offset,
    y: baseY + (index % 6) * offset,
  };
}

export function WindowManagerProvider({ children }: { children: React.ReactNode }) {
  const [windows, setWindows] = useState<AgentWindow[]>([]);
  const [activeWindowId, setActiveWindowId] = useState<WindowId | null>(null);
  const zIndexCounter = useRef(100);

  const spawnWindow = useCallback(
    (
      agentName: string,
      title: string,
      content: React.ReactNode,
      options?: Partial<Pick<AgentWindow, "agentIcon" | "size" | "position" | "pinned">>
    ): WindowId => {
      const id = `win-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
      zIndexCounter.current += 1;

      const newWindow: AgentWindow = {
        id,
        agentName,
        agentIcon: options?.agentIcon || AGENT_ICONS[agentName] || "🤖",
        title,
        content,
        state: "open",
        position: options?.position || getStaggeredPosition(windows.length),
        size: options?.size || { width: 420, height: 320 },
        zIndex: zIndexCounter.current,
        pinned: options?.pinned || false,
        createdAt: new Date(),
      };

      setWindows((prev) => [...prev, newWindow]);
      setActiveWindowId(id);
      return id;
    },
    [windows.length]
  );

  const closeWindow = useCallback((id: WindowId) => {
    setWindows((prev) => prev.filter((w) => w.id !== id));
    setActiveWindowId((prev) => (prev === id ? null : prev));
  }, []);

  const minimizeWindow = useCallback((id: WindowId) => {
    setWindows((prev) =>
      prev.map((w) => (w.id === id ? { ...w, state: "minimized" as const } : w))
    );
    setActiveWindowId((prev) => (prev === id ? null : prev));
  }, []);

  const restoreWindow = useCallback((id: WindowId) => {
    zIndexCounter.current += 1;
    setWindows((prev) =>
      prev.map((w) =>
        w.id === id ? { ...w, state: "open" as const, zIndex: zIndexCounter.current } : w
      )
    );
    setActiveWindowId(id);
  }, []);

  const focusWindow = useCallback((id: WindowId) => {
    zIndexCounter.current += 1;
    setWindows((prev) =>
      prev.map((w) => (w.id === id ? { ...w, zIndex: zIndexCounter.current } : w))
    );
    setActiveWindowId(id);
  }, []);

  const moveWindow = useCallback((id: WindowId, position: { x: number; y: number }) => {
    setWindows((prev) =>
      prev.map((w) => (w.id === id ? { ...w, position } : w))
    );
  }, []);

  const resizeWindow = useCallback((id: WindowId, size: { width: number; height: number }) => {
    setWindows((prev) =>
      prev.map((w) => (w.id === id ? { ...w, size } : w))
    );
  }, []);

  const togglePin = useCallback((id: WindowId) => {
    setWindows((prev) =>
      prev.map((w) => (w.id === id ? { ...w, pinned: !w.pinned } : w))
    );
  }, []);

  const updateWindowContent = useCallback((id: WindowId, content: React.ReactNode) => {
    setWindows((prev) =>
      prev.map((w) => (w.id === id ? { ...w, content } : w))
    );
  }, []);

  return (
    <WindowManagerContext.Provider
      value={{
        windows,
        activeWindowId,
        spawnWindow,
        closeWindow,
        minimizeWindow,
        restoreWindow,
        focusWindow,
        moveWindow,
        resizeWindow,
        togglePin,
        updateWindowContent,
      }}
    >
      {children}
    </WindowManagerContext.Provider>
  );
}
