"""Enhanced digest email formatter with rich opportunity data."""

import json
from typing import Any

from database.models.notifications import Notification
from database.models.opportunities import Opportunity


class DigestFormatter:
    """Formats digest notifications into rich, actionable email content."""

    @staticmethod
    def format_digest_html(
        notifications: list[Notification],
        opportunities: dict[str, Opportunity],
    ) -> str:
        """Format digest as HTML email.

        Args:
            notifications: List of notification records
            opportunities: Dict mapping opportunity_id to Opportunity object

        Returns:
            HTML email string
        """
        html_lines = [
            "<!DOCTYPE html>",
            "<html>",
            "<head>",
            '<meta charset="utf-8">',
            '<meta name="viewport" content="width=device-width">',
            "<style>",
            "body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto; color: #333; }",
            "a { color: #7c3aed; text-decoration: none; }",
            ".header { background: linear-gradient(135deg, #7c3aed 0%, #5b21b6 100%); color: white; padding: 24px; }",
            ".container { max-width: 600px; margin: 0 auto; }",
            ".opportunity { border: 1px solid #e5e7eb; border-radius: 8px; margin: 12px 0; padding: 16px; }",
            ".opportunity.high { border-left: 4px solid #10b981; }",
            ".opportunity.medium { border-left: 4px solid #f59e0b; }",
            ".opportunity.low { border-left: 4px solid #ef4444; }",
            ".score-badge { display: inline-block; background: #f3f4f6; padding: 4px 8px; border-radius: 4px; font-weight: bold; }",
            ".score-high { background: #d1fae5; color: #065f46; }",
            ".score-medium { background: #fef3c7; color: #92400e; }",
            ".score-low { background: #fee2e2; color: #7f1d1d; }",
            ".company { color: #6b7280; font-size: 14px; }",
            ".skills { margin: 8px 0; font-size: 13px; }",
            ".skill-tag { display: inline-block; background: #f3f4f6; padding: 2px 6px; margin: 2px 2px 2px 0; border-radius: 3px; }",
            ".skill-match { background: #d1fae5; color: #065f46; }",
            ".skill-gap { background: #fee2e2; color: #7f1d1d; }",
            ".cta { background: #7c3aed; color: white; padding: 8px 12px; border-radius: 4px; display: inline-block; }",
            ".footer { color: #9ca3af; font-size: 12px; margin-top: 24px; padding-top: 16px; border-top: 1px solid #e5e7eb; }",
            "</style>",
            "</head>",
            "<body>",
            '<div class="container">',
            '<div class="header">',
            f"<h1>✉️ Your Daily Opportunities</h1>",
            f"<p>{len(notifications)} new opportunity(ies) matched to your profile</p>",
            "</div>",
        ]

        # Group by score range
        high_score = []
        med_score = []
        low_score = []

        for notif in notifications:
            try:
                metadata = json.loads(notif.metadata_json) if notif.metadata_json else {}
            except Exception:
                metadata = {}

            score = metadata.get("score", 0)
            opp_id = metadata.get("opportunity_id") or notif.opportunity_id

            if score >= 75:
                high_score.append((notif, metadata, score, opp_id))
            elif score >= 50:
                med_score.append((notif, metadata, score, opp_id))
            else:
                low_score.append((notif, metadata, score, opp_id))

        # Render high-score opportunities first
        if high_score:
            html_lines.append("<h2>🌟 Top Matches</h2>")
            for notif, metadata, score, opp_id in high_score:
                html_lines.append(
                    DigestFormatter._format_opportunity_html(
                        notif, metadata, score, opp_id, opportunities, "high"
                    )
                )

        if med_score:
            html_lines.append("<h2>👀 Review These</h2>")
            for notif, metadata, score, opp_id in med_score:
                html_lines.append(
                    DigestFormatter._format_opportunity_html(
                        notif, metadata, score, opp_id, opportunities, "medium"
                    )
                )

        if low_score:
            html_lines.append("<h2>📋 Long Shot</h2>")
            for notif, metadata, score, opp_id in low_score:
                html_lines.append(
                    DigestFormatter._format_opportunity_html(
                        notif, metadata, score, opp_id, opportunities, "low"
                    )
                )

        # Footer
        html_lines.extend(
            [
                '<div class="footer">',
                "<p>Manage your preferences in OpportunityOS</p>",
                "</div>",
                "</div>",
                "</body>",
                "</html>",
            ]
        )

        return "\n".join(html_lines)

    @staticmethod
    def _format_opportunity_html(
        notif: Notification,
        metadata: dict[str, Any],
        score: int,
        opp_id: str,
        opportunities: dict[str, Opportunity],
        score_category: str,
    ) -> str:
        """Format single opportunity as HTML."""
        score_class = "high" if score >= 75 else "medium" if score >= 50 else "low"
        
        opp = opportunities.get(opp_id)
        company = opp.company if opp else metadata.get("company", "Unknown")
        url = opp.url if opp else metadata.get("url", "#")
        required_skills = metadata.get("required_skills", [])
        missing_skills = metadata.get("missing_skills", [])

        html = f'''<div class="opportunity {score_category}">
  <div style="display: flex; justify-content: space-between; align-items: start;">
    <div>
      <h3 style="margin: 0 0 4px 0;">{notif.title}</h3>
      <p class="company">{company or "Company TBD"}</p>
    </div>
    <span class="score-badge score-{score_class}">{score}/100</span>
  </div>
'''
        if required_skills or missing_skills:
            html += '<div class="skills">'
            for skill in required_skills[:3]:
                if skill not in (missing_skills or []):
                    html += f'<span class="skill-tag skill-match">✓ {skill}</span>'
            for skill in (missing_skills or [])[:2]:
                html += f'<span class="skill-tag skill-gap">✗ {skill}</span>'
            html += "</div>"

        if metadata.get("reasoning"):
            html += f'<p style="font-size: 13px; color: #6b7280; margin: 8px 0;">{metadata["reasoning"]}</p>'

        html += f'<a href="{url}" class="cta">View & Apply →</a>'
        html += "</div>"

        return html

    @staticmethod
    def format_digest_text(
        notifications: list[Notification],
        opportunities: dict[str, Opportunity],
    ) -> str:
        """Format digest as plain text email."""
        lines = [
            "=" * 70,
            "OpportunityOS — Daily Digest",
            "=" * 70,
            f"\nYou have {len(notifications)} new opportunities\n",
        ]

        # Group by score
        grouped = {}
        for notif in notifications:
            try:
                metadata = json.loads(notif.metadata_json) if notif.metadata_json else {}
            except Exception:
                metadata = {}

            score = metadata.get("score", 0)
            category = "TOP" if score >= 75 else "REVIEW" if score >= 50 else "LONG-SHOT"
            if category not in grouped:
                grouped[category] = []
            grouped[category].append((notif, metadata, score))

        for category in ["TOP", "REVIEW", "LONG-SHOT"]:
            if category not in grouped:
                continue

            lines.append(f"\n{category} MATCHES:")
            lines.append("-" * 70)

            for notif, metadata, score in grouped[category]:
                opp = opportunities.get(metadata.get("opportunity_id") or notif.opportunity_id)
                company = opp.company if opp else metadata.get("company", "Unknown")
                url = opp.url if opp else metadata.get("url", "")

                lines.append(f"\n{notif.title}")
                lines.append(f"  Company: {company}")
                lines.append(f"  Score: {score}/100")

                if metadata.get("reasoning"):
                    lines.append(f"  Why: {metadata['reasoning']}")

                if url:
                    lines.append(f"  Apply: {url}")

        lines.extend(
            [
                "\n" + "=" * 70,
                "Manage preferences: https://opportunityos.app",
                "=" * 70,
            ]
        )

        return "\n".join(lines)
