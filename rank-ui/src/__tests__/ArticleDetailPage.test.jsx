import { render, screen, waitFor } from "@testing-library/react";
import { vi } from "vitest";
import ArticleDetailPage from "../pages/ArticleDetailPage.jsx";

function mockResponse(data, ok = true, status = 200) {
    return {
        ok,
        status,
        json: async () => data,
    };
}

describe("ArticleDetailPage markdown rendering", () => {
    test("renders markdown elements for headings, lists, emphasis, blockquote, and hr", async () => {
        const content = [
            "# Large Heading",
            "",
            "## Section Heading",
            "",
            "### Subheading",
            "",
            "This has **bold text** in a paragraph.",
            "",
            "- First bullet",
            "- Second bullet",
            "",
            "> Quoted insight",
            "",
            "---",
        ].join("\n");

        vi.stubGlobal(
            "fetch",
            vi.fn(() =>
                Promise.resolve(
                    mockResponse({
                        title: "Markdown Test",
                        slug: "markdown-test",
                        content,
                        created_at: "2026-03-29T12:00:00Z",
                    })
                )
            )
        );

        render(
            <ArticleDetailPage
                apiBase=""
                slug="markdown-test"
                isAuthed={false}
                user={null}
                onBackToArticles={() => { }}
                onNavigateDashboard={() => { }}
                onLogout={() => { }}
                onSignUp={() => { }}
                onLogIn={() => { }}
            />
        );

        await waitFor(() => {
            expect(screen.getByRole("heading", { name: "Large Heading", level: 1 })).toBeInTheDocument();
        });

        expect(screen.getByRole("heading", { name: "Section Heading", level: 2 })).toBeInTheDocument();
        expect(screen.getByRole("heading", { name: "Subheading", level: 3 })).toBeInTheDocument();
        expect(screen.getByText("bold text", { selector: "strong" })).toBeInTheDocument();

        const list = screen.getByRole("list");
        expect(list).toBeInTheDocument();
        expect(screen.getByText("First bullet", { selector: "li" })).toBeInTheDocument();
        expect(screen.getByText("Second bullet", { selector: "li" })).toBeInTheDocument();

        expect(screen.getByText("Quoted insight", { selector: "blockquote p" })).toBeInTheDocument();
        expect(document.querySelector("hr")).toBeTruthy();
    });
});
