"""The 23 expert areas, review modes, waves and risk profiles."""

AREAS = {
    1: "Architecture", 2: "Security", 3: "Performance", 4: "Scalability", 5: "Reliability",
    6: "Database", 7: "Disaster Recovery", 8: "Observability", 9: "Quality Assurance", 10: "DevOps",
    11: "Infrastructure", 12: "Cost", 13: "UI/UX", 14: "Data Governance", 15: "APIs",
    16: "Business Logic", 17: "Documentation", 18: "Incident Management", 19: "Compliance",
    20: "Analytics", 21: "Technology Strategy", 22: "Technical Leadership", 23: "Engineering Delivery",
}

# Later waves depend on every area of the earlier waves that is in scope.
WAVES = [
    ("Foundation", [1, 16, 6, 15]),
    ("Protection", [2, 14, 19]),
    ("Runtime", [3, 4, 5, 8, 7, 18]),
    ("Delivery", [9, 10, 11, 12, 13, 20]),
    ("Synthesis", [17, 22, 21, 23]),
]

MODES = ("full", "quick", "focused")
QUICK_AREAS = frozenset({1, 2, 5, 6, 7, 8, 9, 10})

RISK_PROFILES = ("standard", "sensitive", "regulated")
RISK_RANK = {name: i for i, name in enumerate(RISK_PROFILES)}

# Release gates per risk profile: which areas are "core" (weight 2, must be
# assessed and backed by Verified evidence) and the score a core area needs for GO.
BASE_CORE = frozenset({2, 5, 6, 7, 9, 10})
GATES = {
    "standard": {"core": BASE_CORE, "go_score": 80, "block_score": 60},
    "sensitive": {"core": BASE_CORE | {8, 14, 18}, "go_score": 85, "block_score": 65},
    "regulated": {"core": BASE_CORE | {8, 14, 18, 19}, "go_score": 90, "block_score": 70},
}

AREA_STATUSES = ("assessed", "partial", "not_assessed", "not_applicable")
SEVERITIES = ("critical", "high", "medium", "low", "info")
# pending_decision: a fix exists and is verified, but the user still has to decide (for example it
# is correct but slower). It counts as open for every gate until they do.
FINDING_STATUSES = ("open", "fixed", "accepted", "false_positive", "pending_decision")
UNRESOLVED = ("open", "pending_decision")
CHECK_RESULTS = ("pass", "fail", "not_assessed", "not_applicable")


def required_areas(mode, scope=None):
    """Areas that must be accounted for in findings.json for a review mode."""
    if mode == "full":
        return set(AREAS)
    if mode == "quick":
        return set(QUICK_AREAS)
    if mode == "focused":
        return set(scope or [])
    return set()
