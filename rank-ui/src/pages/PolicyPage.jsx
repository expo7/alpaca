import SiteFooter from "../components/SiteFooter";
import { APP_NAME } from "../brand";

const updated = "September 9, 2026";

const policies = {
  support: {
    eyebrow: "Customer support",
    title: "How can we help?",
    intro: "Questions about Quantelle, your account, or a future subscription can be sent directly to our support team.",
    sections: [
      { title: "Contact us", body: <p>Email <a className="text-indigo-300 hover:text-indigo-200" href="mailto:support@quantelle.io">support@quantelle.io</a>. Include the email address connected to your account and a short description of the issue. Never send passwords, brokerage credentials, or complete payment-card information.</p> },
      { title: "Billing and cancellations", body: <p>When paid subscriptions become available, billing questions, cancellation requests, and suspected unauthorized charges may be sent to the same address. Cancellation will stop future renewals and will not ordinarily remove access already paid for through the end of the billing period.</p> },
      { title: "Market information", body: <p>Quotes and market data can be delayed, incomplete, or unavailable. Support can investigate a display or recordkeeping problem, but cannot provide individualized investment advice or make trading decisions for you.</p> },
    ],
  },
  privacy: {
    eyebrow: "Privacy policy",
    title: "Your privacy at Quantelle",
    intro: "This policy explains what information Quantelle collects, why we use it, and the choices available to you.",
    sections: [
      { title: "Information we collect", body: <><p>When you create an account, we collect information such as your username and email address. We also store information you intentionally create in the product, including watchlists, alerts, settings, and other account activity.</p><p>Our first-party analytics record page and product events, the page path, device category, referring website domain, time of the event, and a pseudonymous visitor identifier. That identifier is created by cryptographically hashing network and browser information; Quantelle does not store the raw IP address in its analytics-event record. If you are signed in, an event may be associated with your account. We filter known automated bots and respect the browser Do Not Track setting.</p></> },
      { title: "How we use information", body: <p>We use information to provide and secure the service, authenticate accounts, remember preferences, understand which research and product features are useful, troubleshoot problems, prevent abuse, communicate with users, and administer subscriptions.</p> },
      { title: "Payments and service providers", body: <p>If you purchase a subscription, payment information will be processed by Stripe. Quantelle does not receive or store your complete card number. We may use infrastructure, email, market-data, security, and analytics providers when necessary to operate the service. These providers receive only the information reasonably required to perform their services and are subject to their own privacy terms.</p> },
      { title: "Storage, disclosure, and retention", body: <p>We do not sell personal information. We may disclose information to service providers, to comply with law or valid legal process, to protect users and the service, or as part of a business reorganization. We retain information for as long as reasonably necessary to operate the service, maintain security and financial records, resolve disputes, and meet legal obligations.</p> },
      { title: "Your choices", body: <p>You may enable Do Not Track in your browser to prevent Quantelle&apos;s client-side analytics events. You may request access, correction, or deletion of account information by emailing <a className="text-indigo-300 hover:text-indigo-200" href="mailto:support@quantelle.io">support@quantelle.io</a>. Some records may be retained when required for security, legal, or financial purposes.</p> },
      { title: "Security, children, and changes", body: <p>We use reasonable administrative and technical safeguards, but no internet service can guarantee absolute security. Quantelle is not directed to children under 18. We may update this policy as the product develops; material changes will be reflected by a new effective date on this page.</p> },
    ],
  },
  terms: {
    eyebrow: "Terms of service",
    title: "Terms for using Quantelle",
    intro: "By accessing Quantelle, you agree to these terms. If you do not agree, do not use the service.",
    sections: [
      { title: "Research—not individualized advice", body: <p>Quantelle provides general, impersonal market research and educational information to all users or subscribers receiving the same service. It does not consider your financial circumstances, objectives, risk tolerance, tax situation, or portfolio. Quantelle is not a broker-dealer, does not hold customer funds, and does not execute trades in subscriber brokerage accounts.</p> },
      { title: "Investment risk and data limitations", body: <p>Stocks and options involve substantial risk. Options can expire worthless, and you can lose your entire investment. Published setups, ratings, targets, stops, news, sentiment, quotes, and other information may be inaccurate, delayed, incomplete, or unavailable. Nothing on Quantelle guarantees a profit or prevents a loss. You are solely responsible for verifying information and deciding whether and how to trade.</p> },
      { title: "Paper performance and trade records", body: <p>Records identified as paper trades are simulated and are not evidence that an identical live trade could have been executed. Results may exclude or estimate commissions, slippage, liquidity constraints, taxes, assignment risk, and differences in execution. Past and simulated performance do not predict future results. Quantelle may correct genuine data or display errors, while preserving a transparent record of substantive trade updates whenever reasonably possible.</p> },
      { title: "Accounts and acceptable use", body: <p>You must provide accurate account information, safeguard your credentials, and promptly report unauthorized use. You may not disrupt the service, bypass access controls, scrape or redistribute paid content, misuse market data, impersonate another person, or use Quantelle unlawfully. We may restrict or terminate access when reasonably necessary to protect the service or enforce these terms.</p> },
      { title: "Subscriptions, renewal, and cancellation", body: <p>When paid plans become available, the price and billing interval will be shown before checkout. Subscriptions renew automatically until canceled. You may cancel before the next renewal to prevent another charge and ordinarily retain access through the paid billing period. Except where law requires otherwise or a checkout offer expressly states otherwise, charges already incurred are non-refundable. Contact <a className="text-indigo-300 hover:text-indigo-200" href="mailto:support@quantelle.io">support@quantelle.io</a> about billing errors or unauthorized charges.</p> },
      { title: "Availability and intellectual property", body: <p>Quantelle may add, change, suspend, or discontinue features and does not promise uninterrupted availability. Quantelle&apos;s software, branding, original research, presentation, and other content are protected by applicable intellectual-property laws. These terms grant you a limited, personal, revocable right to use the service; they do not transfer ownership.</p> },
      { title: "Disclaimers and limitation of liability", body: <p>To the fullest extent permitted by law, the service is provided “as is” and “as available,” without warranties of merchantability, fitness for a particular purpose, accuracy, or non-infringement. Quantelle and its operators will not be liable for trading losses, lost profits, lost data, or indirect, incidental, special, consequential, or punitive damages arising from use of the service. Where liability cannot legally be excluded, aggregate liability will not exceed the amount you paid Quantelle during the twelve months before the event giving rise to the claim.</p> },
      { title: "Changes and contact", body: <p>We may revise these terms as the service changes. Continued use after updated terms take effect constitutes acceptance where permitted by law. Questions may be sent to <a className="text-indigo-300 hover:text-indigo-200" href="mailto:support@quantelle.io">support@quantelle.io</a>.</p> },
    ],
  },
};

export default function PolicyPage({ type }) {
  const policy = policies[type] || policies.support;
  return (
    <div className="flex min-h-screen flex-col bg-slate-950 text-slate-100">
      <header className="border-b border-slate-800/80 bg-slate-950/90">
        <div className="mx-auto flex w-full max-w-5xl items-center justify-between px-4 py-4 sm:px-6">
          <a href="/" className="flex items-center gap-3"><span className="flex h-9 w-9 items-center justify-center rounded-xl bg-indigo-600 text-sm font-bold">Q</span><span className="font-semibold tracking-wide">{APP_NAME}</span></a>
          <a href="/dashboard" className="rounded-full border border-slate-700 px-3 py-1.5 text-sm text-slate-200 hover:bg-slate-900">Open Quantelle</a>
        </div>
      </header>
      <main className="mx-auto w-full max-w-3xl flex-1 px-4 py-10 sm:px-6 sm:py-14">
        <div className="text-xs font-bold uppercase tracking-[0.18em] text-indigo-300">{policy.eyebrow}</div>
        <h1 className="mt-3 text-3xl font-bold tracking-tight sm:text-4xl">{policy.title}</h1>
        <p className="mt-4 max-w-2xl leading-7 text-slate-300">{policy.intro}</p>
        {type !== "support" && <p className="mt-3 text-xs text-slate-500">Effective {updated}</p>}
        <div className="mt-10 space-y-8">
          {policy.sections.map((section) => <section key={section.title} className="border-t border-slate-800 pt-6"><h2 className="text-xl font-semibold">{section.title}</h2><div className="mt-3 space-y-3 text-sm leading-7 text-slate-300">{section.body}</div></section>)}
        </div>
      </main>
      <SiteFooter />
    </div>
  );
}
