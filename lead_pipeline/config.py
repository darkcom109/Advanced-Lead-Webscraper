from __future__ import annotations

from .models import Market

SERPAPI_ENGINE = "google_light"
GOOGLE_DOMAIN = "google.com"

DEFAULT_SEARCH_OUTPUT_PATH = "search_candidates.json"
DEFAULT_MAX_QUERIES = 24
DEFAULT_PAGES_PER_QUERY = 1
DEFAULT_SEARCH_DELAY_SECONDS = 0.25

DEFAULT_INSPECT_INPUT_PATH = "search_candidates.json"
DEFAULT_INSPECT_OUTPUT_PATH = "inspected_leads.json"
DEFAULT_TIMEOUT_SECONDS = 12
DEFAULT_INSPECTION_DELAY_SECONDS = 0.4
DEFAULT_MAX_PAGES_PER_COMPANY = 6

PRIMARY_MARKETS = [
    Market("United Kingdom", "London, England, United Kingdom", "uk", "primary"),
    Market("United States", "Austin, Texas, United States", "us", "primary"),
]

SECONDARY_MARKETS = [
    Market("Germany", "Berlin, Germany", "de", "secondary"),
    Market("France", "Paris, France", "fr", "secondary"),
    Market("Netherlands", "Amsterdam, Netherlands", "nl", "secondary"),
    Market("Ireland", "Dublin, Ireland", "ie", "secondary"),
    Market("Canada", "Toronto, Ontario, Canada", "ca", "secondary"),
    Market("Australia", "Sydney, New South Wales, Australia", "au", "secondary"),
]

INDUSTRY_PRIORITY = [
    "B2B SaaS",
    "FinTech",
    "HR Tech",
    "DevTools",
    "MarTech",
    "Professional Services",
]

TARGET_DECISION_MAKER_TITLES = [
    "Chief Executive Officer",
    "CEO",
    "Founder",
    "Co-Founder",
    "Managing Director",
    "Chief Revenue Officer",
    "CRO",
    "VP Sales",
    "VP Revenue",
    "VP Growth",
    "Head of Sales",
    "Head of Growth",
    "Head of RevOps",
    "Head of Revenue Operations",
]

SEARCH_SIGNAL_TEMPLATES = {
    "funding": '"{industry}" "B2B SaaS" "{market}" ("Series A" OR "Series B" OR "Series C" OR funding)',
    "hiring": '"{industry}" "{market}" (hiring OR careers OR jobs) ("VP Sales" OR CRO OR "Head of Sales" OR "Head of Growth" OR "Head of RevOps")',
    "visibility": '"{industry}" "{market}" ("product launch" OR "conference speaker" OR "podcast guest")',
    "leadership": '"{industry}" "B2B SaaS" "{market}" ("CEO" OR "Founder" OR "Managing Director")',
}

NON_COMPANY_DOMAINS = {
    "apollo.io",
    "aureliaventures.com",
    "bebee.com",
    "boards.greenhouse.io",
    "bouncewatch.com",
    "builtinnyc.com",
    "capterra.com",
    "crunchbase.com",
    "dailyremote.com",
    "expertini.com",
    "f6s.com",
    "facebook.com",
    "g2.com",
    "glassdoor.com",
    "greenhouse.io",
    "harringtonstarr.com",
    "incubatorlist.com",
    "indeed.com",
    "instagram.com",
    "jobleads.com",
    "jobtome.com",
    "lever.co",
    "linkedin.com",
    "meetfrank.com",
    "open.spotify.com",
    "podcasts.apple.com",
    "qubit.capital",
    "remotivatejobs.com",
    "rocketreach.co",
    "scaleupgroup.com",
    "smartrecruiters.com",
    "softwareadvice.com",
    "space-exec.com",
    "syndicateroom.com",
    "techstars.com",
    "trakstar.com",
    "twitter.com",
    "vestbee.com",
    "wellfound.com",
    "x.com",
    "youngcapital.uk",
    "youtube.com",
    "ziprecruiter.com",
    "zoominfo.com",
}

SEARCH_RESULT_TEXT_EXCLUSIONS = (
    "apply now with",
    "company profile",
    "funding & investors",
    "top companies",
    "salary",
    "recruitment",
    "remote jobs",
    "hiring now",
    "investors, contacts",
)

EXCLUDED_VERTICAL_TERMS = (
    "healthcare",
    "government",
    "education",
    "nonprofit",
    "non-profit",
    "public sector",
    "nhs",
    "charity",
)

EXISTING_REVOPS_TERMS = (
    "revops team",
    "revenue operations team",
    "vp revenue operations",
    "director of revenue operations",
)

EMAIL_PAGE_HINTS = ("contact", "about", "team", "company", "privacy", "legal", "impressum")

DEFAULT_PAGE_PATHS = (
    "",
    "/contact",
    "/contact-us",
    "/about",
    "/about-us",
    "/team",
    "/company",
    "/privacy",
    "/legal",
    "/impressum",
)

PUBLIC_EMAIL_PREFIXES = {
    "accounts",
    "admin",
    "billing",
    "bookings",
    "contact",
    "demo",
    "enquiries",
    "enquiry",
    "finance",
    "growth",
    "hello",
    "help",
    "hi",
    "info",
    "legal",
    "marketing",
    "media",
    "office",
    "operations",
    "ops",
    "partnership",
    "partnerships",
    "press",
    "privacy",
    "revenue",
    "sales",
    "success",
    "support",
    "team",
}

LEADERSHIP_TITLE_ALIASES = [
    ("chief executive officer", "CEO"),
    ("ceo", "CEO"),
    ("co-founder", "Co-Founder"),
    ("founder", "Founder"),
    ("managing director", "Managing Director"),
    ("chief revenue officer", "Chief Revenue Officer"),
    ("cro", "Chief Revenue Officer"),
    ("vp sales", "VP Sales"),
    ("vp revenue", "VP Revenue"),
    ("vp growth", "VP Growth"),
    ("head of sales", "Head of Sales"),
    ("head of growth", "Head of Growth"),
    ("head of revops", "Head of RevOps"),
    ("head of revenue operations", "Head of Revenue Operations"),
]
