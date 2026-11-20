"""Project intake: the questions asked before a review, and the risk profile they imply.

Questions are tailored to what discovery found, so a project without a database is
never asked about backups of one. Answers live in <review_dir>/intake.json.
"""
import json
from pathlib import Path

from .areas import MODES, RISK_PROFILES, RISK_RANK

INTAKE_NAME = "intake.json"
UNKNOWN = "unknown"


def q(key, question, kind="text", options=None, required=False, when=None, experts=(), why=""):
    return {"key": key, "question": question, "type": kind, "options": options or [], "required": required,
            "when": when, "experts": list(experts), "why": why}


DATA_TYPES = ["none", "personal", "credentials", "payment_card", "financial_records", "health",
              "government_id", "children", "business_confidential"]
INDUSTRIES = ["healthcare", "finance", "government", "education", "ecommerce", "logistics",
              "internal_tool", "other"]

QUESTIONS = [
    # --- always asked -----------------------------------------------------
    q("purpose", "In one or two sentences: what does this project do, and for whom?", required=True,
      experts=[1, 16, 21], why="Every expert calibrates severity to what the system is for."),
    q("stage", "What stage is the project at?", "choice", ["prototype", "pre_launch", "production"], True,
      experts=[21, 23], why="A prototype and a live system need different bars."),
    q("exposure", "Who can reach it?", "choice", ["internal", "partners", "public"], True,
      experts=[2, 11], why="Public exposure raises the security and reliability bar."),
    q("industry", "Which industry or domain is it in?", "choice", INDUSTRIES, True,
      experts=[19], why="Decides which regulations may apply."),
    q("data_types", "Which kinds of data does it store or process? (choose all that apply)", "multi", DATA_TYPES, True,
      experts=[2, 14, 19], why="Drives the risk profile and the release gates."),
    q("handles_money", "Does it move or charge money (payments, payouts, wallets, invoices)?", "choice",
      ["yes", "no"], True, experts=[2, 16, 19], why="Money flows need tests, idempotency and audit trails."),
    q("review_mode", "Which review do you want?", "choice", list(MODES), True,
      why="Full = all 23 experts, quick = 8 core areas, focused = the areas you name."),
    q("focus_areas", "For a focused review: which areas (numbers 1-23 or names)?", when="mode_focused",
      why="Sets the required scope for the scorecard."),
    q("change_permission", "May I change code, or assess only?", "choice",
      ["assess_only", "fix_on_branch_after_approval"], True,
      why="Assessment is read-only by default; fixes need your approval of a plan first."),
    q("environments_allowed", "Which environments may I run things against? (choose all that apply)", "multi",
      ["none_read_code_only", "local", "staging"], True, experts=[3, 4, 5, 9],
      why="Load, resilience and E2E tests only run where you allow. Production is never a test target."),
    q("critical_journeys", "What are the 3-5 things that must never break (e.g. login, checkout, report export)?",
      experts=[5, 9, 13, 16], why="Tests, SLOs and UX review focus on these."),
    q("users_scale", "Roughly how many users/requests now, and what do you expect in 12 months?",
      experts=[4, 11, 12], why="Capacity and cost plans need a target."),
    q("users_regions", "Which countries are your users and your company in?", experts=[19, 14],
      why="Determines which privacy laws to check (e.g. GDPR, Lebanon Law 81/2018)."),
    q("deadline", "Is there a launch date or deadline this review should serve?", experts=[23]),
    q("known_problems", "Any known problems or worries you want checked first?", experts=[22]),
    q("team", "Who maintains this (team size, roles)? Who should own fixes?", experts=[23, 18]),
    q("out_of_scope", "Anything I must not touch or look at?", why="Respected by every expert."),
    q("report_language", "Which language for reports?", "choice", ["english", "arabic", "both"]),
    # --- only when discovery found the relevant part ------------------------
    q("db_environment", "Which database is used in production, and is there a local/staging copy I can use?",
      when="has_database", experts=[6, 3]),
    q("backups", "Are backups configured? How often, where are they stored, and who can delete them?",
      when="has_database", experts=[7]),
    q("restore_tested", "Has a restore from backup ever been tested? When?", "choice",
      ["yes", "no", UNKNOWN], when="has_database", experts=[7],
      why="An untested backup counts as unknown, not as protection."),
    q("rto_rpo", "How long can the system be down, and how much data could you afford to lose (RTO/RPO)?",
      when="has_database", experts=[7, 5]),
    q("hosting", "Where is it hosted (provider, plan), and can I get read-only access to that configuration?",
      experts=[11, 12, 10]),
    q("deploy_process", "How is it deployed today, and how do you roll back?", experts=[10, 18]),
    q("ci_access", "Can I see CI run history (e.g. GitHub Actions)?", "choice", ["yes", "no"], when="has_ci",
      experts=[10]),
    q("monitoring_tools", "Which monitoring/error tracking tools exist, and can I get read access?",
      experts=[8, 5, 18]),
    q("alert_recipient", "When it breaks at 3 a.m., who gets notified and how?", experts=[8, 18]),
    q("latency_targets", "Any speed targets (e.g. page loads under 2.5 s, API under 300 ms)?", experts=[3, 5]),
    q("billing_access", "Can you share current monthly costs or invoices (hosting, APIs, SaaS)?",
      when="has_paid_services", experts=[12],
      why="Without billing data the cost analysis is an estimate and is labelled as one."),
    q("spend_caps", "Are spending limits or budget alerts set on the paid services?", "choice",
      ["yes", "no", UNKNOWN], when="has_paid_services", experts=[12, 2]),
    q("ai_usage", "What does the AI/LLM do here, can users influence the prompt, and what tools/data can it reach?",
      when="has_ai", experts=[2, 12], why="Needed to assess prompt injection, data leakage and inference cost."),
    q("ui_audience", "Who uses the interface (devices, languages, RTL/Arabic, accessibility needs)?",
      when="has_ui", experts=[13]),
    q("mobile_release", "Which app stores/platforms do you ship to, and how are builds signed and released?",
      when="has_mobile", experts=[10, 13]),
    q("api_consumers", "Who consumes the API (your own apps, partners, public)? Any versioning promises?",
      when="has_api", experts=[15]),
    q("monorepo_scope", "This is a monorepo. Which apps/packages are in scope?", when="is_monorepo",
      experts=[1]),
    q("compliance_targets", "Any standards or certifications you must meet (SOC 2, ISO 27001, HIPAA, PCI DSS...)?",
      experts=[19]),
    q("data_owner", "Who owns customer data decisions (retention, deletion requests)?", experts=[14, 19]),
    q("kpis", "Which numbers tell you the product is succeeding?", experts=[20]),
    q("issue_tracker", "Do you want findings created as tickets (Jira/GitHub/Linear)? Which project?",
      experts=[23]),
    q("budget_limits", "Any limit on time or AI usage for this review?",
      why="Lets the orchestrator choose depth and parallelism."),
]
QUESTION_KEYS = {x["key"] for x in QUESTIONS}
REQUIRED_KEYS = [x["key"] for x in QUESTIONS if x["required"]]


def questions_for(flags=None, mode=None):
    """The questions to ask, given discovery flags (dict of booleans)."""
    flags = dict(flags or {})
    flags["mode_focused"] = mode == "focused"
    return [x for x in QUESTIONS if x["when"] is None or flags.get(x["when"])]


def derive_risk_profile(answers):
    """Deterministic risk profile from the intake answers. Unknown data types are treated
    as sensitive, because not knowing what data you hold is itself a risk."""
    data = answers.get("data_types")
    data = set(data if isinstance(data, list) else [data]) if data else {UNKNOWN}
    industry = answers.get("industry")
    if data & {"health", "payment_card", "government_id", "children"} or industry in ("healthcare", "finance", "government"):
        return "regulated"
    if (data & {"personal", "credentials", "financial_records", "business_confidential", UNKNOWN}
            or answers.get("handles_money") in ("yes", UNKNOWN, None)
            or (answers.get("exposure") == "public" and answers.get("stage") == "production")):
        return "sensitive"
    return "standard"


def validate_intake(intake):
    errors = []
    if not isinstance(intake, dict) or not isinstance(intake.get("answers"), dict):
        return ["intake.json must be an object with an 'answers' object"]
    answers = intake["answers"]
    by_key = {x["key"]: x for x in QUESTIONS}
    for key in REQUIRED_KEYS:
        if answers.get(key) in (None, "", []):
            errors.append(f"intake: required answer missing: {key} (ask the user; use 'unknown' only if they don't know)")
    for key, value in answers.items():
        spec = by_key.get(key)
        if not spec or value == UNKNOWN:
            continue
        if spec["type"] == "choice" and value not in spec["options"]:
            errors.append(f"intake: {key} must be one of {spec['options']} or 'unknown', got {value!r}")
        if spec["type"] == "multi":
            if not isinstance(value, list) or any(v not in spec["options"] + [UNKNOWN] for v in value):
                errors.append(f"intake: {key} must be a list drawn from {spec['options']}")
    if answers.get("review_mode") == "focused" and not answers.get("focus_areas"):
        errors.append("intake: focused review needs focus_areas")
    declared = intake.get("risk_profile")
    if declared is not None and declared not in RISK_PROFILES:
        errors.append(f"intake: risk_profile must be one of {list(RISK_PROFILES)}")
    return errors


def load_intake(review_dir):
    path = Path(review_dir) / INTAKE_NAME
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def effective_risk_profile(intake):
    """The derived profile, or a stricter one the user chose. It can be raised, never lowered."""
    derived = derive_risk_profile(intake.get("answers", {}))
    declared = intake.get("risk_profile")
    if declared in RISK_RANK and RISK_RANK[declared] > RISK_RANK[derived]:
        return declared
    return derived
