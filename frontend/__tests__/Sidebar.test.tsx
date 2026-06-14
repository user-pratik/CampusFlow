import { render, screen, act, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi, beforeEach } from "vitest";
import Sidebar from "@/components/Sidebar";

// Mock the api module
vi.mock("@/lib/api", () => ({
  fetchProfile: vi.fn().mockResolvedValue({ name: "Test User", reg_no: "21BCE0001" }),
  fetchAcademicProfile: vi.fn().mockResolvedValue({ cgpa: 8.5 }),
  fetchServiceStatus: vi.fn().mockResolvedValue({
    vtop: { session_valid: true },
    whatsapp: { connected: true, state: "open" },
    ngrok: { active: true, url: "https://test.ngrok.io" },
  }),
  checkSessionStatus: vi.fn(),
  triggerVtopSyncNew: vi.fn().mockResolvedValue({ status: "ok" }),
  fetchVtopSemesters: vi.fn().mockResolvedValue({
    semesters: { "Fall 2024": "FA2024", "Spring 2025": "SP2025" },
  }),
}));

// Mock the ThemeProvider
vi.mock("@/components/ThemeProvider", () => ({
  useTheme: () => ({ theme: "dark", toggle: vi.fn() }),
}));

import { checkSessionStatus } from "@/lib/api";

const mockedCheckSession = vi.mocked(checkSessionStatus);

describe("Sidebar handleSync", () => {
  const openPanel = vi.fn();

  beforeEach(() => {
    openPanel.mockClear();
    mockedCheckSession.mockReset();
  });

  it("opens semester selector when session is valid on sync click", async () => {
    mockedCheckSession.mockResolvedValue({ status: "valid" });

    render(<Sidebar openPanel={openPanel} activePanel="attendance" />);

    const syncButton = await screen.findByTitle(
      "Sync everything: VTOP login + data sync + WhatsApp QR"
    );
    await act(async () => {
      syncButton.click();
    });

    // Should open semester selector (portal rendered dialog with semester title)
    await waitFor(() => {
      expect(document.querySelector('[aria-labelledby="semester-selector-title"]')).toBeInTheDocument();
    });
  });

  it("opens login modal when session is expired on sync click", async () => {
    mockedCheckSession.mockResolvedValue({ status: "session_expired" });

    render(<Sidebar openPanel={openPanel} activePanel="attendance" />);

    const syncButton = await screen.findByTitle(
      "Sync everything: VTOP login + data sync + WhatsApp QR"
    );
    await act(async () => {
      syncButton.click();
    });

    // Should open the VTOP login modal
    await waitFor(() => {
      expect(document.querySelector('[aria-label="VTOP Login"]')).toBeInTheDocument();
    });
  });

  it("shows syncing state (disabled button) while checking session", async () => {
    // Create a promise that won't resolve immediately
    let resolveSession: (value: { status: "valid" | "session_expired" }) => void;
    const pendingPromise = new Promise<{ status: "valid" | "session_expired" }>((resolve) => {
      resolveSession = resolve;
    });
    mockedCheckSession.mockReturnValue(pendingPromise);

    render(<Sidebar openPanel={openPanel} activePanel="attendance" />);

    const syncButton = await screen.findByTitle(
      "Sync everything: VTOP login + data sync + WhatsApp QR"
    );
    await act(async () => {
      syncButton.click();
    });

    // Button should be disabled while syncing
    expect(syncButton).toBeDisabled();

    // Resolve to clean up
    await act(async () => {
      resolveSession!({ status: "valid" });
    });
  });
});
