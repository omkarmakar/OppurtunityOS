"""Bundled finder plugins.

Each plugin provides a SearchProvider that specializes in a domain
(jobs, internships, scholarships, etc.) and a BasePlugin that
registers it with the framework.
"""

from plugins.bundled.competitions import CompetitionFinderPlugin
from plugins.bundled.conferences import ConferenceFinderPlugin
from plugins.bundled.grants import GrantFinderPlugin
from plugins.bundled.hackathons import HackathonFinderPlugin
from plugins.bundled.internships import InternshipFinderPlugin
from plugins.bundled.jobs import JobFinderPlugin
from plugins.bundled.research_papers import ResearchPaperFinderPlugin
from plugins.bundled.scholarships import ScholarshipFinderPlugin
from plugins.bundled.startup_hiring import StartupHiringFinderPlugin

ALL_BUNDLED_PLUGINS = [
    CompetitionFinderPlugin,
    ConferenceFinderPlugin,
    GrantFinderPlugin,
    HackathonFinderPlugin,
    InternshipFinderPlugin,
    JobFinderPlugin,
    ResearchPaperFinderPlugin,
    ScholarshipFinderPlugin,
    StartupHiringFinderPlugin,
]

__all__ = ["ALL_BUNDLED_PLUGINS"]
