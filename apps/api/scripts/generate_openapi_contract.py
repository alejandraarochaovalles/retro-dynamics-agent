# Regenerates packages/contracts/openapi.yaml from apps/api/models.py.
#
# Run after changing models.py or a route's signature:
#   cd apps/api && source .venv/bin/activate
#   python scripts/generate_openapi_contract.py
#
# Pulls the schema straight from FastAPI's own app.openapi() — no server
# or DB needs to be running, since that's computed from route/pydantic
# definitions alone — then: strips the /api prefix each path was mounted
# under (the contract keeps the `servers: [{url: /api}]` + relative-path
# convention instead), keeps this file's own human `summary` per
# operationId, and drops the cosmetic auto "title" FastAPI stamps on every
# schema node (schema-aware: several models have a real *field* named
# "title" — e.g. ActionItem.title — which must survive the cleanup).
from __future__ import annotations

import sys
from pathlib import Path

import yaml

API_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(API_ROOT))

from main import app  # noqa: E402

OUTPUT = API_ROOT.parent.parent / "packages" / "contracts" / "openapi.yaml"

# Human-written one-liners, kept independent of whatever FastAPI infers
# from the function name. Add an entry here when adding a new route.
SUMMARIES = {
    "createTeam": "Create team",
    "connectIntegration": "Connect Jira or Azure DevOps",
    "generateDynamics": "Generate dynamic proposals (LLM)",
    "createSession": "Create retro session",
    "getSession": "Session state",
    "startSession": "Start session (lobby → active)",
    "advancePhase": "Advance phase",
    "joinSession": "Join a session with join_code",
    "closeSession": "Close session and sync from Liveblocks",
    "liveblocksAuth": "Authorize access to a Liveblocks room",
    "listGroups": "Groups suggested after closing",
    "updateGroup": "Edit a group's label or membership",
    "getVotesSummary": "Ranking of notes/groups by votes",
    "createActionItem": "Create action item from a group",
    "updateActionItem": "Edit action item",
    "deleteActionItem": "Discard action item",
    "exportActionItems": "Create tickets in Jira/Azure DevOps",
    "listTeamSessions": "Team's retro history",
    "getSessionSummary": "Final retro report",
}

EXCLUDED_PATHS = {"/health"}  # infra endpoint, not part of the frontend contract


def clean_schema(schema):
    """Strip the cosmetic auto "title" FastAPI adds to every schema *node*,
    without touching a "title" that is itself a field name inside a
    properties map (walks JSON Schema structure explicitly instead of
    blindly popping "title" from every dict, which would do that)."""
    if not isinstance(schema, dict):
        return schema
    schema = dict(schema)
    schema.pop("title", None)
    if "properties" in schema:
        schema["properties"] = {
            name: clean_schema(sub) for name, sub in schema["properties"].items()
        }
    if "items" in schema:
        schema["items"] = clean_schema(schema["items"])
    for key in ("anyOf", "allOf", "oneOf"):
        if key in schema:
            schema[key] = [clean_schema(s) for s in schema[key]]
    return schema


def build() -> dict:
    generated = app.openapi()

    new_paths = {}
    for full_path, methods in generated["paths"].items():
        if full_path in EXCLUDED_PATHS:
            continue
        assert full_path.startswith("/api"), full_path
        path = full_path[len("/api") :]

        new_methods = {}
        for method, op in methods.items():
            operation_id = op["operationId"]
            new_op = {"summary": SUMMARIES[operation_id], "operationId": operation_id}
            if "parameters" in op:
                params = []
                for p in op["parameters"]:
                    p = dict(p)
                    p["schema"] = {k: v for k, v in p["schema"].items() if k != "title"}
                    params.append(p)
                new_op["parameters"] = params
            if "requestBody" in op:
                new_op["requestBody"] = op["requestBody"]
            new_op["responses"] = {
                status: {
                    **resp,
                    "content": {
                        ct: {**c, "schema": clean_schema(c["schema"])}
                        for ct, c in resp.get("content", {}).items()
                    },
                }
                if resp.get("content")
                else resp
                for status, resp in op["responses"].items()
            }
            new_methods[method] = new_op
        new_paths[path] = new_methods

    schemas = {name: clean_schema(s) for name, s in generated["components"]["schemas"].items()}

    # Every field must survive cleaning — same set of properties/required
    # before and after, just without the cosmetic "title" noise.
    for name, original in generated["components"]["schemas"].items():
        before = set(original.get("properties", {}))
        after = set(schemas[name].get("properties", {}))
        assert before == after, f"{name}: properties changed! before={before} after={after}"
        assert original.get("required", []) == schemas[name].get(
            "required", []
        ), f"{name}: required changed!"

    return {
        "openapi": "3.1.0",
        "info": {
            "title": generated["info"]["title"],
            "version": generated["info"]["version"],
            "description": (
                "API contract between apps/web and apps/api. See docs/adr for the "
                "reasoning behind each architecture decision.\n\n"
                "components.schemas below is generated from apps/api/models.py — "
                "run apps/api/scripts/generate_openapi_contract.py to regenerate "
                "after changing models.py or a route's signature, rather than "
                "editing schemas here by hand."
            ),
        },
        "servers": [{"url": "/api"}],
        "paths": new_paths,
        "components": {"schemas": schemas},
    }


class _Dumper(yaml.SafeDumper):
    pass


def _str_presenter(dumper, data):
    style = "|" if "\n" in data else None
    return dumper.represent_scalar("tag:yaml.org,2002:str", data, style=style)


_Dumper.add_representer(str, _str_presenter)


def main() -> None:
    doc = build()
    with open(OUTPUT, "w") as f:
        yaml.dump(doc, f, Dumper=_Dumper, sort_keys=False, default_flow_style=False, allow_unicode=True, width=100)
    print(f"wrote {OUTPUT} ({len(doc['paths'])} paths, {len(doc['components']['schemas'])} schemas)")


if __name__ == "__main__":
    main()
