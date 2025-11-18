# ranker/management/commands/check_alerts.py

from django.core.management.base import BaseCommand
from django.utils import timezone
from django.core.mail import EmailMultiAlternatives
from django.conf import settings

from ranker.models import Alert, WatchlistItem, AlertEvent
from ranker.scoring import technical_score, fundamental_score


class Command(BaseCommand):
    help = "Check active alerts and send email notifications when triggered."

    def handle(self, *args, **options):
        now = timezone.now()
        alerts = Alert.objects.filter(active=True)

        if not alerts.exists():
            self.stdout.write("No active alerts.")
            return

        for alert in alerts:
            # ----- determine symbols to check -----
            symbols = []

            if alert.alert_type == Alert.TYPE_SYMBOL and alert.symbol:
                symbols = [alert.symbol.upper()]
            elif alert.alert_type == Alert.TYPE_WATCHLIST and alert.watchlist:
                symbols = list(
                    WatchlistItem.objects.filter(watchlist=alert.watchlist)
                    .values_list("symbol", flat=True)
                )

            if not symbols:
                continue

            # ----- evaluate each symbol in this alert -----
            for sym in symbols:
                try:
                    tech_score, _ = technical_score(sym)
                    fund_score, _ = fundamental_score(sym)
                    # you can adjust to match your final_score logic
                    final_score = 0.6 * tech_score + 0.4 * fund_score
                except Exception as e:
                    self.stderr.write(f"Error scoring {sym}: {e}")
                    continue

                # ----- check thresholds -----
                if final_score < alert.min_final_score:
                    continue
                if (
                    alert.min_tech_score is not None
                    and tech_score < alert.min_tech_score
                ):
                    continue
                if (
                    alert.min_fund_score is not None
                    and fund_score < alert.min_fund_score
                ):
                    continue

                # ====== TRIGGERED ======
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Alert {alert.id} triggered for {sym}: final={final_score:.2f}"
                    )
                )

                # update alert state
                alert.last_triggered_at = now
                if alert.trigger_once:
                    alert.active = False
                alert.save(update_fields=["last_triggered_at", "active"])

                # record event in history
                AlertEvent.objects.create(
                    alert=alert,
                    symbol=sym,
                    final_score=final_score,
                    tech_score=tech_score,
                    fund_score=fund_score,
                    triggered_at=now,
                )

                # ----- pretty HTML email -----
                user = alert.user
                if not user.email:
                    continue

                subject = f"[Stock Ranker] Alert for {sym}: {final_score:.2f}"

                # plain-text fallback
                text_body = (
                    f"Stock Ranker Alert\n\n"
                    f"User: {user.get_username()}\n"
                    f"Symbol: {sym}\n"
                    f"Alert type: {alert.get_alert_type_display()}\n"
                    f"Triggered at: {now.isoformat()}\n\n"
                    f"Scores:\n"
                    f"  Final: {final_score:.2f}\n"
                    f"  Tech:  {tech_score:.2f}\n"
                    f"  Fund:  {fund_score:.2f}\n\n"
                    f"Thresholds:\n"
                    f"  Final ≥ {alert.min_final_score}\n"
                    f"  Tech  ≥ {alert.min_tech_score if alert.min_tech_score is not None else '-'}\n"
                    f"  Fund  ≥ {alert.min_fund_score if alert.min_fund_score is not None else '-'}\n\n"
                    f"This alert has now been "
                    f"{'deactivated' if alert.trigger_once else 'left active'}.\n"
                )

                frontend_base = getattr(
                    settings, "FRONTEND_BASE_URL", "http://127.0.0.1:5173"
                )
                dashboard_url = f"{frontend_base}/"

                html_body = f"""
                <html>
                  <body style="font-family: system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background-color: #0f172a; color: #e5e7eb; padding: 24px;">
                    <div style="max-width: 640px; margin: 0 auto; background-color: #020617; border-radius: 16px; border: 1px solid #1f2937; padding: 20px;">
                      <h1 style="margin: 0 0 12px; font-size: 20px; color: #e5e7eb;">
                        Stock Ranker Alert
                      </h1>
                      <p style="margin: 0 0 8px; font-size: 13px; color: #9ca3af;">
                        An alert for <strong style="color:#a5b4fc;">{sym}</strong> has been triggered.
                      </p>

                      <table style="width: 100%; border-collapse: collapse; margin-top: 16px; font-size: 13px;">
                        <tbody>
                          <tr>
                            <td style="padding: 6px 8px; color:#9ca3af;">Symbol</td>
                            <td style="padding: 6px 8px; text-align:right; font-weight:600;">{sym}</td>
                          </tr>
                          <tr>
                            <td style="padding: 6px 8px; color:#9ca3af;">Alert type</td>
                            <td style="padding: 6px 8px; text-align:right;">
                              {alert.get_alert_type_display()}
                            </td>
                          </tr>
                          <tr>
                            <td style="padding: 6px 8px; color:#9ca3af;">Triggered at</td>
                            <td style="padding: 6px 8px; text-align:right;">
                              {now.strftime("%Y-%m-%d %H:%M:%S")}
                            </td>
                          </tr>
                        </tbody>
                      </table>

                      <h2 style="margin: 20px 0 8px; font-size: 14px; color:#e5e7eb;">Scores</h2>
                      <table style="width: 100%; border-collapse: collapse; font-size: 13px;">
                        <thead>
                          <tr>
                            <th style="text-align:left; padding: 6px 8px; color:#9ca3af;">Metric</th>
                            <th style="text-align:right; padding: 6px 8px; color:#9ca3af;">Value</th>
                          </tr>
                        </thead>
                        <tbody>
                          <tr>
                            <td style="padding: 6px 8px;">Final score</td>
                            <td style="padding: 6px 8px; text-align:right; font-weight:600;">{final_score:.2f}</td>
                          </tr>
                          <tr>
                            <td style="padding: 6px 8px;">Tech score</td>
                            <td style="padding: 6px 8px; text-align:right;">{tech_score:.2f}</td>
                          </tr>
                          <tr>
                            <td style="padding: 6px 8px;">Fundamental score</td>
                            <td style="padding: 6px 8px; text-align:right;">{fund_score:.2f}</td>
                          </tr>
                        </tbody>
                      </table>

                      <h2 style="margin: 20px 0 8px; font-size: 14px; color:#e5e7eb;">Thresholds</h2>
                      <table style="width: 100%; border-collapse: collapse; font-size: 13px;">
                        <thead>
                          <tr>
                            <th style="text-align:left; padding: 6px 8px; color:#9ca3af;">Metric</th>
                            <th style="text-align:right; padding: 6px 8px; color:#9ca3af;">Threshold</th>
                          </tr>
                        </thead>
                        <tbody>
                          <tr>
                            <td style="padding: 6px 8px;">Final</td>
                            <td style="padding: 6px 8px; text-align:right;">≥ {alert.min_final_score}</td>
                          </tr>
                          <tr>
                            <td style="padding: 6px 8px;">Tech</td>
                            <td style="padding: 6px 8px; text-align:right;">
                              ≥ {alert.min_tech_score if alert.min_tech_score is not None else '-'}
                            </td>
                          </tr>
                          <tr>
                            <td style="padding: 6px 8px;">Fund</td>
                            <td style="padding: 6px 8px; text-align:right;">
                              ≥ {alert.min_fund_score if alert.min_fund_score is not None else '-'}
                            </td>
                          </tr>
                        </tbody>
                      </table>

                      <div style="margin-top: 20px; font-size: 12px; color:#9ca3af;">
                        This alert is now
                        <strong style="color:#e5e7eb;">
                          {" deactivated" if alert.trigger_once else " still active"}
                        </strong>.
                      </div>

                      <div style="margin-top: 20px;">
                        <a href="{dashboard_url}"
                           style="display:inline-block; padding: 8px 14px; font-size: 13px; border-radius: 999px; background-color:#4f46e5; color:white; text-decoration:none;">
                          Open Stock Ranker dashboard
                        </a>
                      </div>

                      <p style="margin-top: 16px; font-size: 11px; color:#6b7280;">
                        You are receiving this email because you created an alert in Stock Ranker.
                      </p>
                    </div>
                  </body>
                </html>
                """

                try:
                    msg = EmailMultiAlternatives(
                        subject=subject,
                        body=text_body,
                        from_email=getattr(settings, "DEFAULT_FROM_EMAIL", None),
                        to=[user.email],
                    )
                    msg.attach_alternative(html_body, "text/html")
                    msg.send(fail_silently=True)
                except Exception as e:
                    self.stderr.write(
                        f"Failed to send email for alert {alert.id}: {e}"
                    )
