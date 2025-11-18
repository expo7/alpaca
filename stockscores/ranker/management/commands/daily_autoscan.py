# ranker/management/commands/daily_autoscan.py

from django.core.management.base import BaseCommand
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.mail import EmailMultiAlternatives
from django.utils import timezone

from ranker.scoring import technical_score, fundamental_score
from ranker.models import UserPreference

User = get_user_model()


class Command(BaseCommand):
    help = "Run a daily autoscan over a fixed ticker universe and email top picks (per-user prefs)."

    def handle(self, *args, **options):
        # 1) Load config (global)
        tickers = getattr(settings, "AUTOSCAN_TICKERS", [])
        top_n_default = int(getattr(settings, "AUTOSCAN_TOP_N", 5))
        tech_w = float(getattr(settings, "AUTOSCAN_TECH_WEIGHT", 0.6))
        fund_w = float(getattr(settings, "AUTOSCAN_FUND_WEIGHT", 0.4))

        if not tickers:
            self.stdout.write(self.style.WARNING("No AUTOSCAN_TICKERS configured."))
            return

        now = timezone.now()
        self.stdout.write(f"Running daily autoscan at {now.isoformat()}")

        # 2) Score the universe ONCE
        scored = []
        for sym in tickers:
            sym = sym.upper().strip()
            if not sym:
                continue
            try:
                tech, _ = technical_score(sym)
                fund, _ = fundamental_score(sym)
                final = tech_w * tech + fund_w * fund
                scored.append(
                    {
                        "symbol": sym,
                        "tech": tech,
                        "fund": fund,
                        "final": final,
                    }
                )
                self.stdout.write(
                    f" scored {sym}: tech={tech:.2f} fund={fund:.2f} final={final:.2f}"
                )
            except Exception as e:
                self.stderr.write(f"Error scoring {sym}: {e}")

        if not scored:
            self.stdout.write(
                self.style.WARNING("No symbols were successfully scored.")
            )
            return

        # sort by final score descending
        scored.sort(key=lambda x: x["final"], reverse=True)

        # 3) Find users who actually want the autoscan
        prefs_qs = (
            UserPreference.objects.filter(
                daily_scan_enabled=True,
                user__is_active=True,
                user__email__isnull=False,
            )
            .exclude(user__email__exact="")
            .select_related("user")
        )

        if not prefs_qs.exists():
            self.stdout.write(
                self.style.WARNING(
                    "No users with daily_scan_enabled=True; nothing to send."
                )
            )
            return

        from_email = getattr(settings, "DEFAULT_FROM_EMAIL", None)
        if not from_email:
            self.stdout.write(
                self.style.WARNING(
                    "DEFAULT_FROM_EMAIL not set; using alerts@example.com"
                )
            )
            from_email = "alerts@example.com"

        frontend_base = getattr(settings, "FRONTEND_BASE_URL", "http://127.0.0.1:5173")
        dashboard_url = f"{frontend_base}/"
        date_str = now.strftime("%Y-%m-%d")

        sent_count = 0

        # 4) Build & send per-user emails based on their prefs
        for prefs in prefs_qs:
            user = prefs.user
            email = user.email

            # Per-user filters
            min_score = float(prefs.daily_scan_min_score)
            max_ideas = int(prefs.daily_scan_max_ideas or top_n_default)

            # Start from globally sorted list, then apply per-user rules
            filtered = [row for row in scored if row["final"] >= min_score]
            picks = filtered[:max_ideas]

            if not picks:
                # Option 1: skip sending
                self.stdout.write(
                    f"User {user} ({email}) has no picks above min_score={min_score}; skipping email."
                )
                continue

            subject = f"[Stock Ranker] Daily autoscan – {len(picks)} ideas ({date_str})"

            # ------- Plain text body -------
            lines = [
                "Stock Ranker – Daily Autoscan",
                f"Date: {date_str}",
                "",
                f"Universe: {', '.join(tickers)}",
                f"Tech weight = {tech_w}, Fund weight = {fund_w}",
                f"User: {user.get_username()} (min score {min_score}, max ideas {max_ideas})",
                "",
                f"Top {len(picks)} by final score (after your filter):",
                "",
            ]
            for i, row in enumerate(picks, start=1):
                lines.append(
                    f"{i}. {row['symbol']}: final={row['final']:.2f}, "
                    f"tech={row['tech']:.2f}, fund={row['fund']:.2f}"
                )
            lines.append("")
            lines.append(
                "You’re receiving this because daily scan email is enabled "
                "for your account in Stock Ranker."
            )
            text_body = "\n".join(lines)

            # ------- HTML body -------
            rows_html = ""
            for i, row in enumerate(picks, start=1):
                rows_html += f"""
                  <tr>
                    <td style="padding:6px 8px; border-bottom:1px solid #1f2937;">{i}</td>
                    <td style="padding:6px 8px; border-bottom:1px solid #1f2937;">{row['symbol']}</td>
                    <td style="padding:6px 8px; text-align:right; border-bottom:1px solid #1f2937;">{row['final']:.2f}</td>
                    <td style="padding:6px 8px; text-align:right; border-bottom:1px solid #1f2937;">{row['tech']:.2f}</td>
                    <td style="padding:6px 8px; text-align:right; border-bottom:1px solid #1f2937;">{row['fund']:.2f}</td>
                  </tr>
                """

            html_body = f"""
            <html>
              <body style="font-family: system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background-color:#0f172a; color:#e5e7eb; padding:24px;">
                <div style="max-width:640px; margin:0 auto; background-color:#020617; border-radius:16px; border:1px solid #1f2937; padding:20px;">
                  <h1 style="margin:0 0 8px; font-size:20px;">Stock Ranker – Daily autoscan</h1>
                  <p style="margin:0 0 4px; font-size:13px; color:#9ca3af;">
                    Date: <strong style="color:#e5e7eb;">{date_str}</strong>
                  </p>
                  <p style="margin:0 0 4px; font-size:13px; color:#9ca3af;">
                    Universe: {', '.join(tickers)}
                  </p>
                  <p style="margin:0 0 10px; font-size:13px; color:#9ca3af;">
                    Weights: Tech = {tech_w}, Fund = {fund_w}
                  </p>
                  <p style="margin:0 0 12px; font-size:13px; color:#9ca3af;">
                    Your filter: min final score {min_score}, max ideas {max_ideas}
                  </p>

                  <h2 style="margin:16px 0 8px; font-size:14px;">Top {len(picks)} by final score</h2>
                  <table style="width:100%; border-collapse:collapse; font-size:13px;">
                    <thead>
                      <tr>
                        <th style="text-align:left; padding:6px 8px; color:#9ca3af;">#</th>
                        <th style="text-align:left; padding:6px 8px; color:#9ca3af;">Symbol</th>
                        <th style="text-align:right; padding:6px 8px; color:#9ca3af;">Final</th>
                        <th style="text-align:right; padding:6px 8px; color:#9ca3af;">Tech</th>
                        <th style="text-align:right; padding:6px 8px; color:#9ca3af;">Fund</th>
                      </tr>
                    </thead>
                    <tbody>
                      {rows_html}
                    </tbody>
                  </table>

                  <div style="margin-top:20px;">
                    <a href="{dashboard_url}"
                       style="display:inline-block; padding:8px 14px; font-size:13px; border-radius:999px; background-color:#4f46e5; color:white; text-decoration:none;">
                      Open Stock Ranker dashboard
                    </a>
                  </div>

                  <p style="margin-top:16px; font-size:11px; color:#6b7280;">
                    You’re receiving this because daily scan email is enabled for your account in Stock Ranker.
                  </p>
                </div>
              </body>
            </html>
            """

            try:
                msg = EmailMultiAlternatives(
                    subject=subject,
                    body=text_body,
                    from_email=from_email,
                    to=[email],
                )
                msg.attach_alternative(html_body, "text/html")
                msg.send(fail_silently=False)
                sent_count += 1
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Sent autoscan email to {user} <{email}> "
                        f"(ideas={len(picks)}, min_score={min_score})"
                    )
                )
            except Exception as e:
                self.stderr.write(f"Failed to send autoscan email to {email}: {e}")

        self.stdout.write(
            self.style.SUCCESS(f"Autoscan complete; sent to {sent_count} users.")
        )
