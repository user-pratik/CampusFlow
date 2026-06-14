"use client";

import { useRef, useCallback, useState } from "react";
import { AgentWindow, useWindowManager } from "@/lib/windowManager";

interface FloatingWindowProps {
  window: AgentWindow;
}

export default function FloatingWindow({ window: win }: FloatingWindowProps) {
  const { closeWindow, minimizeWindow, focusWindow, moveWindow, resizeWindow, togglePin } =
    useWindowManager();
  const dragRef = useRef<{ startX: number; startY: number; originX: number; originY: number } | null>(null);
  const resizeRef = useRef<{ startX: number; startY: number; originW: number; originH: number } | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [isResizing, setIsResizing] = useState(false);

  const handleMouseDownDrag = useCallback(
    (e: React.MouseEvent) => {
      e.preventDefault();
      focusWindow(win.id);
      dragRef.current = {
        startX: e.clientX,
        startY: e.clientY,
        originX: win.position.x,
        originY: win.position.y,
      };
      setIsDragging(true);

      const handleMove = (ev: MouseEvent) => {
        if (!dragRef.current) return;
        const dx = ev.clientX - dragRef.current.startX;
        const dy = ev.clientY - dragRef.current.startY;
        moveWindow(win.id, {
          x: Math.max(0, dragRef.current.originX + dx),
          y: Math.max(0, dragRef.current.originY + dy),
        });
      };

      const handleUp = () => {
        dragRef.current = null;
        setIsDragging(false);
        document.removeEventListener("mousemove", handleMove);
        document.removeEventListener("mouseup", handleUp);
      };

      document.addEventListener("mousemove", handleMove);
      document.addEventListener("mouseup", handleUp);
    },
    [win.id, win.position, focusWindow, moveWindow]
  );

  const handleMouseDownResize = useCallback(
    (e: React.MouseEvent) => {
      e.preventDefault();
      e.stopPropagation();
      focusWindow(win.id);
      resizeRef.current = {
        startX: e.clientX,
        startY: e.clientY,
        originW: win.size.width,
        originH: win.size.height,
      };
      setIsResizing(true);

      const handleMove = (ev: MouseEvent) => {
        if (!resizeRef.current) return;
        const dx = ev.clientX - resizeRef.current.startX;
        const dy = ev.clientY - resizeRef.current.startY;
        resizeWindow(win.id, {
          width: Math.max(280, resizeRef.current.originW + dx),
          height: Math.max(180, resizeRef.current.originH + dy),
        });
      };

      const handleUp = () => {
        resizeRef.current = null;
        setIsResizing(false);
        document.removeEventListener("mousemove", handleMove);
        document.removeEventListener("mouseup", handleUp);
      };

      document.addEventListener("mousemove", handleMove);
      document.addEventListener("mouseup", handleUp);
    },
    [win.id, win.size, focusWindow, resizeWindow]
  );

  if (win.state === "minimized") return null;

  return (
    <div
      className={`absolute rounded-lg shadow-2xl border border-border bg-panel-bg flex flex-col overflow-hidden transition-shadow ${
        isDragging || isResizing ? "shadow-xl ring-1 ring-accent/30" : ""
      }`}
      style={{
        left: win.position.x,
        top: win.position.y,
        width: win.size.width,
        height: win.size.height,
        zIndex: win.zIndex,
      }}
      onMouseDown={() => focusWindow(win.id)}
    >
      {/* Title bar */}
      <div
        className="h-9 bg-surface flex items-center justify-between px-3 shrink-0 cursor-grab active:cursor-grabbing select-none border-b border-border"
        onMouseDown={handleMouseDownDrag}
      >
        <div className="flex items-center gap-2 min-w-0">
          <span className="text-sm shrink-0">{win.agentIcon}</span>
          <span className="text-xs font-medium text-foreground truncate">
            {win.title}
          </span>
          <span className="text-[10px] text-secondary hidden sm:inline">
            — {win.agentName}
          </span>
        </div>
        <div className="flex items-center gap-1 shrink-0">
          {/* Pin button */}
          <button
            onClick={(e) => { e.stopPropagation(); togglePin(win.id); }}
            className={`w-5 h-5 flex items-center justify-center rounded text-xs transition-colors ${
              win.pinned ? "text-accent bg-accent-light" : "text-secondary hover:text-foreground hover:bg-surface-hover"
            }`}
            aria-label={win.pinned ? "Unpin window" : "Pin window"}
            title={win.pinned ? "Unpin" : "Pin"}
          >
            📌
          </button>
          {/* Minimize button */}
          <button
            onClick={(e) => { e.stopPropagation(); minimizeWindow(win.id); }}
            className="w-5 h-5 flex items-center justify-center rounded text-secondary hover:text-foreground hover:bg-surface-hover transition-colors"
            aria-label="Minimize window"
          >
            <svg className="w-3 h-3" viewBox="0 0 12 12" fill="none" stroke="currentColor" strokeWidth={2}>
              <path d="M2 6h8" />
            </svg>
          </button>
          {/* Close button */}
          <button
            onClick={(e) => { e.stopPropagation(); closeWindow(win.id); }}
            className="w-5 h-5 flex items-center justify-center rounded text-secondary hover:text-urgent hover:bg-urgent/10 transition-colors"
            aria-label="Close window"
          >
            <svg className="w-3 h-3" viewBox="0 0 12 12" fill="none" stroke="currentColor" strokeWidth={2}>
              <path d="M2 2l8 8M10 2l-8 8" />
            </svg>
          </button>
        </div>
      </div>

      {/* Content area */}
      <div className="flex-1 overflow-auto p-3 text-sm text-foreground">
        {win.content}
      </div>

      {/* Resize handle */}
      <div
        className="absolute bottom-0 right-0 w-4 h-4 cursor-se-resize"
        onMouseDown={handleMouseDownResize}
      >
        <svg className="w-3 h-3 absolute bottom-0.5 right-0.5 text-secondary/50" viewBox="0 0 12 12" fill="currentColor">
          <circle cx="10" cy="10" r="1.5" />
          <circle cx="6" cy="10" r="1.5" />
          <circle cx="10" cy="6" r="1.5" />
        </svg>
      </div>
    </div>
  );
}
