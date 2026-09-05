import { render, screen, waitFor } from "@testing-library/react";
import { vi } from "vitest";
import MacroDashboardPage from "../pages/MacroDashboardPage.jsx";
import { AuthProvider } from "../AuthProvider.jsx";

const mockResponse = (data, ok = true, status = 200) => ({
    ok,
    status,
    text: async () => JSON.stringify(data),
});

describe("MacroDashboardPage", () => {
    test("loads and renders market direction, interpreted themes, and recommendations", async () => {
        localStorage.setItem("access", "token");

        vi.stubGlobal(
            "fetch",
            vi.fn((url) => {
                if (url.includes("/api/macro/dashboard/")) {
                    return Promise.resolve(
                        mockResponse({
                            as_of: "2026-03-25",
                            overall_regime: "Risk-On Expansion",
                            confidence: 72,
                            scores: {
                                growth: 31.2,
                                inflation: 12.4,
                                liquidity: 18.5,
                                risk_appetite: 28.1,
                            },
                            signals: [
                                {
                                    symbol: "SPY",
                                    name: "SPDR S&P 500 ETF",
                                    price: 550.12,
                                    ret_5d: 1.2,
                                    ret_20d: 3.5,
                                    ret_60d: 8.1,
                                    dist_50dma: 2.3,
                                    signal: "Bullish",
                                    interpretation: "Momentum is positive and price sits above its 50DMA.",
                                },
                            ],
                            narrative: "Current regime reads as Risk-On Expansion.",
                            playbook: {
                                favored_assets: ["SPY", "QQQ"],
                                unfavorable_assets: ["DXY"],
                                notes: "Stay pro-cyclical.",
                            },
                            options_engine: {
                                trade_context: {
                                    regime: "Risk-On Expansion",
                                    confidence: 72,
                                    risk_tolerance: "moderate",
                                    position_context: "flat",
                                    iv_context: "normal",
                                },
                                suggestions: [
                                    {
                                        strategy: "call_spread",
                                        label: "Bull Call Spread",
                                        priority: 78,
                                        reason: "Express upside bias with capped cost and bounded risk.",
                                        setup: {
                                            dte: "30-60",
                                            delta_target: "0.30-0.40 long call",
                                            bias: "bullish",
                                        },
                                        fits_when: ["risk_on", "uptrend"],
                                        avoid_when: ["strong_bear_trend"],
                                    },
                                ],
                            },
                        })
                    );
                }
                return Promise.resolve(mockResponse({}));
            })
        );

        render(
            <AuthProvider>
                <MacroDashboardPage />
            </AuthProvider>
        );

        await waitFor(() => expect(screen.getByText("Risk-On Expansion")).toBeInTheDocument());
        expect(screen.getByText("Today's decision")).toBeInTheDocument();
        expect(screen.getByText("Add exposure selectively on confirmed strength")).toBeInTheDocument();
        expect(screen.getByText("Do now")).toBeInTheDocument();
        expect(screen.getByText("Reassess when")).toBeInTheDocument();
        expect(screen.getByText("Market Momentum: Strong")).toBeInTheDocument();
        expect(screen.getByText("Inflation Pressure: Moderate")).toBeInTheDocument();
        expect(screen.getByText("Cross-Asset Recommendations")).toBeInTheDocument();
        expect(screen.getByText("Options Engine")).toBeInTheDocument();
        expect(screen.getAllByText("Bull Call Spread")).toHaveLength(2);
        expect(screen.getByText("SPY")).toBeInTheDocument();
    });
});
