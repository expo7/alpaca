import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi } from "vitest";
import Landing from "../Landing.jsx";
import Login from "../Login.jsx";
import { AuthProvider } from "../AuthProvider.jsx";

const mockResponse = (data, ok = true, status = 200) => ({
  ok,
  status,
  json: async () => data,
});

describe("Landing page", () => {
  test("shows marketing copy and embedded login form", () => {
    render(
      <AuthProvider>
        <Landing />
      </AuthProvider>
    );
    expect(screen.getByText(/Rank stocks by/i)).toBeInTheDocument();
    expect(screen.getByText(/Sign in to your dashboard/i)).toBeInTheDocument();
    expect(screen.getAllByRole("button", { name: /Sign in/i }).length).toBeGreaterThan(0);
  });
});

describe("Login form", () => {
  test("submits credentials and stores token on success", async () => {
    const fetchMock = vi.fn(() =>
      Promise.resolve(mockResponse({ access: "abc123", username: "alice" }))
    );
    vi.stubGlobal("fetch", fetchMock);
    render(
      <AuthProvider>
        <Login />
      </AuthProvider>
    );

    const usernameInput = screen.getAllByRole("textbox")[0];
    const passwordInput = screen.getByText(/Password/i).parentElement.querySelector("input[type='password']");

    await userEvent.type(usernameInput, "alice");
    await userEvent.type(passwordInput, "secret");
    const signInButtons = screen.getAllByRole("button", { name: /Sign in/i });
    const submitButton = signInButtons.find((btn) => btn.type === "submit") || signInButtons[0];
    await userEvent.click(submitButton);

    await waitFor(() => expect(localStorage.getItem("access")).toBe("abc123"));
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining("/api/token/"),
      expect.objectContaining({ method: "POST" })
    );
  });

  test("shows error on failed login", async () => {
    vi.stubGlobal("fetch", vi.fn(() => Promise.resolve(mockResponse({}, false, 400))));
    render(
      <AuthProvider>
        <Login />
      </AuthProvider>
    );

    const usernameInput = screen.getAllByRole("textbox")[0];
    const passwordInput = screen.getByText(/Password/i).parentElement.querySelector("input[type='password']");

    await userEvent.type(usernameInput, "bob");
    await userEvent.type(passwordInput, "wrong");
    const signInButtons = screen.getAllByRole("button", { name: /Sign in/i });
    const submitButton = signInButtons.find((btn) => btn.type === "submit") || signInButtons[0];
    await userEvent.click(submitButton);

    await waitFor(() =>
      expect(screen.getByText(/Login failed/i)).toBeInTheDocument()
    );
  });
});
