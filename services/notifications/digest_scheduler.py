"""Per-user timezone-aware digest scheduling with instant alerts."""

from __future__ import annotations

import logging
from datetime import datetime, time, timezone, timedelta
from typing import Any

import pytz
from sqlalchemy.orm import Session

from database.models.notifications import Notification
from database.models.opportunities import Opportunity
from database.models.profiles import Profile
from database.repositories.profile_repository import ProfileRepository
from services.notifications.digest import DailyDigestService
from services.notifications.providers import EmailNotificationProvider

logger = logging.getLogger(__name__)


class DigestScheduler:
    """Manages per-user timezone-aware digest scheduling and instant alerts."""

    def __init__(
        self,
        db: Session,
        email_provider: EmailNotificationProvider | None = None,
    ) -> None:
        self._db = db
        self._profile_repo = ProfileRepository(db)
        self._email = email_provider
        self._digest_service = DailyDigestService(db, email_provider)

    def should_run_digest(self, profile: Profile) -> bool:
        """Check if digest should run for profile based on schedule and timezone.

        Args:
            profile: Profile with digest scheduling settings

        Returns:
            True if digest should run now in the profile's timezone
        """
        if profile.digest_timezone not in pytz.all_timezones:
            logger.warning(f"Invalid timezone: {profile.digest_timezone}")
            return False

        try:
            tz = pytz.timezone(profile.digest_timezone)
            now_in_tz = datetime.now(tz)

            # Check frequency
            if profile.digest_frequency == "weekly":
                # Check if today is the scheduled day (0=Monday, 6=Sunday)
                if now_in_tz.weekday() != profile.digest_weekly_day:
                    return False
            # For daily, always proceed

            # Check time window (allow 5-minute window)
            target_time = time(profile.digest_schedule_hour, profile.digest_schedule_minute)
            target_dt = now_in_tz.replace(
                hour=target_time.hour, minute=target_time.minute, second=0, microsecond=0
            )
            window_start = target_dt
            window_end = target_dt + timedelta(minutes=5)

            return window_start <= now_in_tz <= window_end

        except Exception as e:
            logger.error(f"Error checking digest schedule for profile {profile.id}: {e}")
            return False

    def send_instant_alert(
        self,
        profile: Profile,
        opportunity: Opportunity,
        score: int,
        user_email: str,
    ) -> bool:
        """Send instant alert for high-scoring opportunity if enabled.

        Args:
            profile: Profile with alert settings
            opportunity: Opportunity that triggered alert
            score: Relevance score (0-100)
            user_email: User email address

        Returns:
            True if alert was sent
        """
        if not profile.instant_alert_enabled:
            return False

        if score < profile.instant_alert_threshold:
            return False

        if not self._email or not user_email:
            return False

        try:
            subject = f"High-Match Opportunity: {opportunity.title} ({score}/100)"
            body = self._format_alert_body(opportunity, score, profile)

            sent = self._email.send(
                str(profile.user_id),
                subject,
                body,
                email_to=user_email,
            )

            if sent:
                logger.info(
                    f"Instant alert sent for opportunity {opportunity.id} "
                    f"to profile {profile.id} (score={score})"
                )

            return sent
        except Exception as e:
            logger.error(f"Error sending instant alert: {e}")
            return False

    def _format_alert_body(self, opp: Opportunity, score: int, profile: Profile) -> str:
        """Format instant alert email body."""
        return f"""
High-Match Opportunity Alert

Title: {opp.title}
Company: {opp.company or 'N/A'}
Score: {score}/100

URL: {opp.url or 'N/A'}

This opportunity matches your profile criteria and passed the instant alert threshold ({profile.instant_alert_threshold}/100).

Review it now: {opp.url}
"""

    def run_scheduled_digests(self) -> dict[str, Any]:
        """Run digests for all profiles that have scheduled delivery time now.

        Returns:
            Summary of digests run
        """
        try:
            all_profiles = self._profile_repo.list()
            digests_run = 0
            digests_failed = 0

            for profile in all_profiles:
                if not self.should_run_digest(profile):
                    continue

                try:
                    user = profile.user
                    if not user or not user.email:
                        continue

                    result = self._digest_service.run(
                        user_id=user.id,
                        profile_id=profile.id,
                        profile_name=profile.display_name or profile.name,
                        user_email=user.email,
                    )

                    if result.get("email_sent"):
                        digests_run += 1
                    else:
                        digests_failed += 1

                except Exception as e:
                    logger.error(f"Error running digest for profile {profile.id}: {e}")
                    digests_failed += 1

            return {
                "digests_run": digests_run,
                "digests_failed": digests_failed,
                "total": digests_run + digests_failed,
            }

        except Exception as e:
            logger.error(f"Error in run_scheduled_digests: {e}")
            return {"digests_run": 0, "digests_failed": 1, "total": 1, "error": str(e)}
