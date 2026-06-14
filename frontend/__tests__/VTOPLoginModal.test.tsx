import { render, screen, act, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import VTOPLoginModal from "@/components/VTOPLoginModal";

// Mock the api module
vi.mock("@/lib/api", () => ({
  checkSessionStatus: vi.fn(),
}));

import { checkSessionStatus } from "@/lib/api";

const mockedCheckSession = vi.mocked(checkSessionStatus);

describe("VTOPLoginModal", () => {
  const onClose = vi.fn();
  const onLoginSuccess = vi.fn();

  beforeEach(() => {
    onClose.mockClear();
    onLoginSuccess.mockClear();
    mockedCheckSession.mockReset();
    // Default: session not valid yet
    mockedCheckSession.mockResolvedValue({ status: "session_expired" });
  });

  it("renders via portal into document.body", () => {
    render(<VTOPLoginModal onClose={onClose} onLoginSuccess={onLoginSuccess} />);
    // The modal should be a direct child of body (portal behavior)
    const dialog = document.querySelector('[role="dialog"]');
    expect(dialog).toBeInTheDocument();
    expect(dialog?.parentElement).toBe(document.body);
  });

  it("renders iframe with correct src", () => {
    render(<VTOPLoginModal onClose={onClose} onLoginSuccess={onLoginSuccess} />);
    const iframe = document.querySelector("iframe");
    expect(iframe).toBeInTheDocument();
    expect(iframe?.getAttribute("src")).toBe("/api/vtop/proxy/login");
  });

  it("has correct ARIA attributes (role=dialog, aria-modal, aria-label)", () => {
    render(<VTOPLoginModal onClose={onClose} onLoginSuccess={onLoginSuccess} />);
    const dialog = document.querySelector('[role="dialog"]');
    expect(dialog).toHaveAttribute("aria-modal", "true");
    expect(dialog).toHaveAttribute("aria-label", "VTOP Login");
  });

  it("calls onLoginSuccess when session poll returns valid", async () => {
    // Start with expired, then return valid on second call
    mockedCheckSession
      .mockResolvedValueOnce({ status: "session_expired" })
      .mockResolvedValue({ status: "valid" });

    render(<VTOPLoginModal onClose={onClose} onLoginSuccess={onLoginSuccess} />);

    // The component polls every 2s. Wait for onLoginSuccess to be called.
    await waitFor(
      () => {
        expect(onLoginSuccess).toHaveBeenCalledTimes(1);
      },
      { timeout: 6000 }
    );
  });
});
