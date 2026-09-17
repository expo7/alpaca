import Navbar from "./Navbar.jsx";

export default function ArticleNav({
    isAuthed,
    user,
    onNavigateDashboard = () => {},
    onNavigateSignals = () => {},
    onNavigateBilling = () => {},
    onNavigateOpportunities = () => {},
    onNavigateArticles = () => {},
    onNavigateAnalytics = () => {},
    onLogout = () => {},
}) {
    const handlers = {
        dashboard: onNavigateDashboard,
        signals: onNavigateSignals,
        billing: onNavigateBilling,
        opportunities: onNavigateOpportunities,
        articles: onNavigateArticles,
        analytics: onNavigateAnalytics,
    };

    return (
        <Navbar
            isAuthed={isAuthed}
            user={user}
            active="articles"
            onNavigate={(page) => handlers[page]?.()}
            onLogout={onLogout}
            v1Mode
        />
    );
}
