import logging
import resend
from starlette.concurrency import run_in_threadpool
from app.config import settings

logger = logging.getLogger("dukani.email")


class EmailService:
    async def send_password_reset(self, to_email: str, full_name: str, reset_url: str) -> None:
        resend.api_key = settings.RESEND_API_KEY
        html = f"""
        <div style="font-family: sans-serif; max-width: 480px; margin: 0 auto;">
          <h2>DUKANI POS — Kuweka upya Nenosiri</h2>
          <p>Habari {full_name},</p>
          <p>Tumepokea ombi la kuweka upya nenosiri lako. Bofya kiungo hapa chini
          kuweka nenosiri jipya. Kiungo hiki kitaisha muda baada ya
          {settings.PASSWORD_RESET_EXPIRE_MINUTES} dakika.</p>
          <p><a href="{reset_url}" style="background:#2563EB;color:#fff;padding:10px 20px;
          border-radius:8px;text-decoration:none;display:inline-block;">Weka Nenosiri Jipya</a></p>
          <p style="color:#888;font-size:12px;">Kama hukuomba hili, puuza barua pepe hii —
          nenosiri lako halitabadilika.</p>
        </div>
        """
        try:
            # resend's SDK is a synchronous HTTP client — run off the event loop
            # so a slow/hanging call to Resend never blocks other requests.
            await run_in_threadpool(
                resend.Emails.send,
                {
                    "from": settings.RESEND_FROM_EMAIL,
                    "to": [to_email],
                    "subject": "DUKANI POS — Kuweka upya Nenosiri",
                    "html": html,
                },
            )
        except Exception as e:
            # Never let an email-provider hiccup surface to the client as a 500,
            # and never let it reveal whether the address was valid — just log.
            logger.error(f"Failed to send password reset email to {to_email}: {e}")


email_service = EmailService()
