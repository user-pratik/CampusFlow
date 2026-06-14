import { render, screen, act, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import SemesterSelector from "@/components/SemesterSelector";

// Mock the api module
vi.mock("@/lib/api", () => ({
  fetchVtopSemesters: vi.fn(),
}));

import { fetchVtopSemesters } from "@/lib/api";

const mockedFetchSemesters = vi.mocked(fetchVtopSemesters);

describe("SemesterSelector", () => {
  const onClose = vi.fn();
  const onConfirm = vi.fn();

  beforeEach(() => {
    onClose.mockClear();
    onConfirm.mockClear();
    mockedFetchSemesters.mockReset();
  });

  it("renders via portal into document.body", async () => {
    mockedFetchSemesters.mockResolvedValue({
      semesters: { "Fall 2024": "FA2024", "Spring 2025": "SP2025" },
    });

    render(<SemesterSelector onClose={onClose} onConfirm={onConfirm} />);

    const dialog = document.querySelector('[role="dialog"]');
    expect(dialog).toBeInTheDocument();
    expect(dialog?.parentElement).toBe(document.body);
  });

  it("fetches semesters on mount and displays them", async () => {
    mockedFetchSemesters.mockResolvedValue({
      semesters: { "Fall 2024": "FA2024", "Spring 2025": "SP2025" },
    });

    render(<SemesterSelector onClose={onClose} onConfirm={onConfirm} />);

    await waitFor(() => {
      expect(screen.getByText("Select Semester")).toBeInTheDocument();
    });

    expect(mockedFetchSemesters).toHaveBeenCalledTimes(1);
    expect(screen.getByText("Fall 2024")).toBeInTheDocument();
    expect(screen.getByText("Spring 2025")).toBeInTheDocument();
  });

  it("pre-selects the first semester", async () => {
    mockedFetchSemesters.mockResolvedValue({
      semesters: { "Fall 2024": "FA2024", "Spring 2025": "SP2025" },
    });

    render(<SemesterSelector onClose={onClose} onConfirm={onConfirm} />);

    await waitFor(() => {
      expect(screen.getByText("Select Semester")).toBeInTheDocument();
    });

    const select = screen.getByRole("combobox") as HTMLSelectElement;
    expect(select.value).toBe("FA2024");
  });

  it("auto-proceeds (calls onConfirm) when only one semester exists", async () => {
    mockedFetchSemesters.mockResolvedValue({
      semesters: { "Fall 2024": "FA2024" },
    });

    render(<SemesterSelector onClose={onClose} onConfirm={onConfirm} />);

    await waitFor(() => {
      expect(onConfirm).toHaveBeenCalledWith("FA2024");
    });
  });
});
