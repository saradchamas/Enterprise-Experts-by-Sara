"""Project capability matrix: which expert areas and workflows apply to this
project, and which run-based checks are possible here.

Statuses:
  applicable      the project has this, and it will be assessed
  not_applicable  the project has nothing in this area (reason given; some need the user to confirm)
  not_assessed    it probably exists but nothing in the repository shows it; needs an answer or access
Run-based checks per stack are: available, tool_missing (-> Not assessed),
no_command (-> Not applicable for this project) or unsupported (no adapter for the stack).
"""
from .areas import AREAS

ALWAYS = {1: "every project has a structure to review", 2: "every project has an attack surface",
          9: "every project needs evidence that it works", 10: "every project is built and delivered somehow",
          17: "every project needs documentation", 19: "screening for applicable rules always applies",
          21: "direction and risk apply to every project", 22: "code and decision quality apply to every project",
          23: "findings always need a plan"}


def build(discovery):
    f = discovery.get("flags", {})
    service = f.get("has_api") or f.get("has_ui") or f.get("has_mobile") or f.get("has_database") \
        or f.get("has_containers") or f.get("has_data_pipeline")
    deployable = service or f.get("has_iac")
    infra_only = f.get("infrastructure_only")
    areas = {}

    def put(aid, status, reason, confirm=False):
        areas[aid] = {"id": aid, "name": AREAS[aid], "status": status, "reason": reason, "confirm_with_user": confirm}

    for aid, why in ALWAYS.items():
        put(aid, "applicable", why)
    if infra_only:
        put(9, "applicable", "infrastructure code: validation, linting and policy checks instead of unit tests")
    # runtime areas
    for aid in (3, 4, 5, 8, 18):
        if service or infra_only:
            put(aid, "applicable", "the project runs as a service or defines infrastructure")
        else:
            put(aid, "not_applicable", "nothing here runs as a service (looks like a library, script or document set)", True)
    put(6, "applicable", "database tools, schema or migrations found") if f.get("has_database") else \
        put(6, "not_applicable", "no database driver, schema or migration found in the repository", True)
    put(7, "applicable", "state or infrastructure that must be recoverable") if (f.get("has_database") or f.get("has_iac")) \
        else put(7, "not_applicable" if not service else "not_assessed",
                 "no stored state found in the repository" if not service
                 else "the service may hold state elsewhere; ask where data lives and how it is backed up", True)
    if f.get("has_iac") or f.get("has_containers") or f.get("has_ci"):
        put(11, "applicable", "infrastructure, container or deploy configuration found")
    elif deployable:
        put(11, "not_assessed", "no hosting configuration in the repository; ask where and how it is hosted", True)
    else:
        put(11, "not_applicable", "nothing deployable found", True)
    if f.get("has_paid_services") or f.get("has_ai") or f.get("has_iac"):
        put(12, "applicable", "paid or usage-based services found")
    elif deployable:
        put(12, "not_assessed", "costs are not visible in the repository; ask for hosting and service costs", True)
    else:
        put(12, "not_applicable", "nothing here incurs running costs", True)
    put(13, "applicable", "a user interface was found") if (f.get("has_ui") or f.get("has_mobile")) else \
        put(13, "not_applicable", "no user interface found")
    put(14, "applicable", "the project stores or moves data") if (f.get("has_database") or f.get("has_data_pipeline")) \
        else put(14, "not_applicable", "no stored data or pipelines found", True)
    put(15, "applicable", "an API framework or API specification was found") if f.get("has_api") else \
        put(15, "not_applicable", "no API framework or specification found", True)
    put(16, "not_applicable", "infrastructure-only repository: no business logic") if infra_only else \
        put(16, "applicable", "application code carries business rules")
    put(20, "applicable", "a product people use: usage can be measured") if (f.get("has_ui") or f.get("has_mobile") or f.get("has_api")) \
        else put(20, "not_applicable", "no product surface to measure", True)

    checks = []
    for s in discovery.get("stacks", []):
        tools_ok = all(s.get("prerequisites", {}).values())
        for name, cmd in s.get("commands", {}).items():
            if cmd:
                tool = cmd[0].lstrip("./")
                present = s.get("prerequisites", {}).get(tool, tools_ok)
                checks.append({"stack": s["path"], "adapter": s["adapter"], "check": name, "command": " ".join(cmd),
                               "status": "available" if present else "tool_missing",
                               "reason": "" if present else f"{tool} is not installed here: record as Not assessed"})
            else:
                checks.append({"stack": s["path"], "adapter": s["adapter"], "check": name, "command": None,
                               "status": "no_command", "reason": s.get("unavailable", {}).get(name, "")})
    for u in discovery.get("unsupported", []):
        checks.append({"stack": ".", "adapter": None, "check": "all run-based checks", "command": None,
                       "status": "unsupported", "reason": f"{u['language']}: {u['reason']}"})

    workflows = {
        "ai_engineering": {"active": bool(f.get("has_ai")),
                           "reason": "AI libraries found: " + ", ".join(discovery.get("ai_libraries", []))
                           if f.get("has_ai") else "no AI/LLM usage found; do not introduce AI unless the user asks"},
        "deployment_advisor": {"active": bool(deployable),
                               "reason": "the project is deployable" if deployable else "nothing deployable found"},
        "visual_documentation": {"active": bool(f.get("has_ui") or f.get("has_mobile")),
                                 "reason": "a user interface exists: capture real screenshots if it can be run"
                                 if (f.get("has_ui") or f.get("has_mobile")) else "no interface to capture"},
    }
    return {"areas": [areas[a] for a in sorted(areas)], "checks": checks, "workflows": workflows}


def to_markdown(matrix):
    o = ["# Capability matrix", "",
         "What applies to this project. Items marked *confirm* were decided from the repository alone; "
         "ask the user before treating them as settled.", "",
         "| # | Area | Status | Why |", "|---|---|---|---|"]
    o += [f"| {a['id']} | {a['name']} | {a['status'].replace('_', ' ')}{' (confirm)' if a['confirm_with_user'] else ''} "
          f"| {a['reason']} |" for a in matrix["areas"]]
    o += ["", "## Workflows", "", "| Workflow | Active | Why |", "|---|---|---|"]
    o += [f"| {k.replace('_', ' ')} | {'yes' if v['active'] else 'no'} | {v['reason']} |" for k, v in matrix["workflows"].items()]
    o += ["", "## Run-based checks", "", "| Stack | Check | Status | Command / reason |", "|---|---|---|---|"]
    o += [f"| `{c['stack']}` | {c['check']} | {c['status'].replace('_', ' ')} | "
          f"{'`' + c['command'] + '`' if c['command'] and c['status'] == 'available' else c['reason']} |" for c in matrix["checks"]]
    if not matrix["checks"]:
        o.append("| — | — | none | no supported stack: the project is reviewed by reading |")
    return "\n".join(o) + "\n"
