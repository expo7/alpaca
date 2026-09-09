import { APP_NAME } from "../brand";

export default function SiteFooter() {
  return (
    <footer className="border-t border-slate-800/80 bg-slate-950 px-4 py-6 text-xs text-slate-500">
      <div className="mx-auto flex max-w-6xl flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <span>© {new Date().getFullYear()} {APP_NAME}</span>
        <nav className="flex flex-wrap gap-x-5 gap-y-2" aria-label="Legal and support">
          <a href="/support" className="hover:text-slate-300">Support</a>
          <a href="/privacy" className="hover:text-slate-300">Privacy</a>
          <a href="/terms" className="hover:text-slate-300">Terms</a>
        </nav>
        <span>Research only · No guarantees · Markets involve risk</span>
      </div>
    </footer>
  );
}
