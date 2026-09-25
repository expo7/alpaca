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
  test("opens sign in immediately from the header", async () => {
    const originalShowModal = HTMLDialogElement.prototype.showModal;
    const originalClose = HTMLDialogElement.prototype.close;
    HTMLDialogElement.prototype.showModal = function () { this.setAttribute("open", ""); };
    HTMLDialogElement.prototype.close = function () {
      this.removeAttribute("open");
      this.dispatchEvent(new Event("close"));
    };
    try {
    render(
      <AuthProvider>
        <Landing />
      </AuthProvider>
    );
    expect(screen.getByText(/Trade ideas with a plan/i)).toBeInTheDocument();
    expect(screen.getAllByText(/^QUANTELLE$/i).length).toBeGreaterThan(0);
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /^Sign in$/i }));
    expect(screen.getByRole("dialog", { name: "Quantelle sign in" })).toBeInTheDocument();
    expect(screen.getByRole("dialog").querySelector("input")).toHaveFocus();
    await userEvent.click(screen.getByRole("button", { name: /Close sign in/i }));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    } finally {
      HTMLDialogElement.prototype.showModal = originalShowModal;
      HTMLDialogElement.prototype.close = originalClose;
    }
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
