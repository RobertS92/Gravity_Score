import json
import uuid
import decimal
import datetime
from typing import Any, AsyncGenerator, Dict, List, Optional

import asyncpg

try:
    import anthropic
    from anthropic import AsyncAnthropic
except ImportError:
    anthropic = None  # type: ignore
    AsyncAnthropic = None  # type: ignore

from gravity_api.config import get_settings


def _json_safe(obj: Any) -> Any:
    """Recursively convert non-JSON-serializable types from asyncpg results."""
    if isinstance(obj, dict):
        return {k: _json_safe(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_json_safe(i) for i in obj]
    if isinstance(obj, uuid.UUID):
        return str(obj)
    if isinstance(obj, decimal.Decimal):
        return float(obj)
    if isinstance(obj, (datetime.datetime, datetime.date)):
        return obj.isoformat()
    return obj

GRAVITY_SYSTEM_PROMPT = """You are the Gravity NIL Intelligence engine. You help
sports agents, NIL attorneys, and brand teams make data-driven decisions about
college athlete commercial value.

You have access to these tools:
- search_athletes: Search the Gravity database by any combination of filters
- get_athlete_score: Get full score breakdown for a specific athlete
- get_comparables: Get the comparable athlete set for a given athlete
- assess_deal: Evaluate a proposed NIL deal against range of compensation
- get_program_nil_data: Get NIL environment data for a specific school
- filter_by_brand_fit: Find athletes matching brand criteria

When answering queries:
- Always cite which data points drove your assessment
- Surface the SHAP factors that matter most
- Be direct about confidence levels when data is thin
- Format numbers cleanly: scores to 1 decimal, values with $ and M/K notation
- When asked about deals, always reference the CSC range of compensation standard

You are precise, data-driven, and direct. You do not speculate beyond what the
data supports."""

TOOLS: List[Dict[str, Any]] = [
    {
        "name": "search_athletes",
        "description": "Search and filter college athletes by sport, conference, position, score components",
        "input_schema": {
            "type": "object",
            "properties": {
                "sport": {"type": "string", "enum": ["cfb", "mcbb"]},
                "conference": {"type": "string"},
                "position_group": {"type": "string"},
                "school": {"type": "string"},
                "min_gravity": {"type": "number"},
                "max_gravity": {"type": "number"},
                "min_brand": {"type": "number"},
                "max_brand": {"type": "number"},
                "min_proof": {"type": "number"},
                "max_risk": {"type": "number"},
                "sort_by": {"type": "string"},
                "limit": {"type": "integer", "default": 20},
            },
        },
    },
    {
        "name": "get_athlete_score",
        "description": "Get full Gravity Score breakdown for a specific athlete",
        "input_schema": {
            "type": "object",
            "properties": {
                "athlete_id": {"type": "string"},
                "athlete_name": {"type": "string"},
            },
        },
    },
    {
        "name": "get_comparables",
        "description": "Get up to 15 similar athletes for compensation analysis",
        "input_schema": {
            "type": "object",
            "properties": {
                "athlete_id": {"type": "string"},
                "filters": {"type": "object"},
            },
            "required": ["athlete_id"],
        },
    },
    {
        "name": "assess_deal",
        "description": "Evaluate a proposed NIL deal vs comparable range",
        "input_schema": {
            "type": "object",
            "properties": {
                "athlete_id": {"type": "string"},
                "proposed_value": {"type": "number"},
                "deal_type": {"type": "string"},
                "brand_category": {"type": "string"},
                "duration_days": {"type": "integer"},
            },
            "required": ["athlete_id", "proposed_value", "deal_type"],
        },
    },
    {
        "name": "get_program_nil_data",
        "description": "Get NIL environment data for a school",
        "input_schema": {
            "type": "object",
            "properties": {"school": {"type": "string"}, "sport": {"type": "string"}},
            "required": ["school"],
        },
    },
    {
        "name": "filter_by_brand_fit",
        "description": "Find athletes matching brand campaign constraints",
        "input_schema": {
            "type": "object",
            "properties": {
                "brand_category": {"type": "string"},
                "budget_max": {"type": "number"},
                "audience_target": {"type": "string"},
                "max_risk": {"type": "number", "default": 30},
                "sport": {"type": "string"},
                "conference": {"type": "string"},
                "limit": {"type": "integer", "default": 15},
            },
            "required": ["brand_category"],
        },
    },
]

_SORT_SQL = {
    "gravity_score": "s.gravity_score",
    "brand_score": "s.brand_score",
    "proof_score": "s.proof_score",
    "proximity_score": "s.proximity_score",
    "velocity_score": "s.velocity_score",
    "risk_score": "s.risk_score",
    "name": "a.name",
}


class GravityQueryAgent:
    # Always use a model that exists; fall back to a stable alias
    _PREFERRED_MODELS = [
        "claude-sonnet-4-5",
        "claude-3-5-sonnet-20241022",
        "claude-3-sonnet-20240229",
    ]

    def __init__(self, db: asyncpg.Connection):
        self.db = db
        self.settings = get_settings()
        api_key = self.settings.anthropic_api_key
        # Use the configured model or the first preferred fallback
        cfg_model = (self.settings.anthropic_model or "").strip()
        self.model = cfg_model if cfg_model else self._PREFERRED_MODELS[0]
        self.client: "AsyncAnthropic | None" = (
            AsyncAnthropic(api_key=api_key) if AsyncAnthropic and api_key else None
        )

    async def execute_tool(self, tool_name: str, tool_input: Dict[str, Any]) -> Dict[str, Any]:
        if tool_name == "search_athletes":
            return await self._search_athletes(tool_input)
        if tool_name == "get_athlete_score":
            return await self._get_athlete_score(tool_input)
        if tool_name == "get_comparables":
            return await self._get_comparables(tool_input)
        if tool_name == "assess_deal":
            return await self._assess_deal(tool_input)
        if tool_name == "get_program_nil_data":
            return await self._get_program_nil_data(tool_input)
        if tool_name == "filter_by_brand_fit":
            return await self._filter_by_brand_fit(tool_input)
        return {"error": f"Unknown tool: {tool_name}"}

    async def _search_athletes(self, params: Dict[str, Any]) -> Dict[str, Any]:
        conditions: List[str] = ["TRUE"]
        values: List[Any] = []
        idx = 1

        field_map = {
            "sport": ("a.sport", "="),
            "conference": ("a.conference", "ILIKE"),
            "position_group": ("a.position_group", "="),
            "school": ("a.school", "ILIKE"),
            "min_gravity": ("s.gravity_score", ">="),
            "max_gravity": ("s.gravity_score", "<="),
            "min_brand": ("s.brand_score", ">="),
            "max_brand": ("s.brand_score", "<="),
            "min_proof": ("s.proof_score", ">="),
            "max_risk": ("s.risk_score", "<="),
        }

        for key, (col, op) in field_map.items():
            if key in params and params[key] is not None:
                val: Any = params[key]
                if op == "ILIKE":
                    val = f"%{val}%"
                conditions.append(f"{col} {op} ${idx}")
                values.append(val)
                idx += 1

        sort_col = str(params.get("sort_by") or "gravity_score")
        order_expr = _SORT_SQL.get(sort_col, "s.gravity_score")
        limit = min(int(params.get("limit") or 20), 50)
        values.append(limit)

        sql = f"""
            SELECT a.id, a.name, a.sport, a.school, a.conference,
                   a.position, a.position_group,
                   s.gravity_score, s.brand_score, s.proof_score,
                   s.proximity_score, s.velocity_score, s.risk_score,
                   s.confidence
            FROM athletes a
            LEFT JOIN LATERAL (
                SELECT * FROM athlete_gravity_scores
                WHERE athlete_id = a.id
                ORDER BY calculated_at DESC LIMIT 1
            ) s ON true
            WHERE {' AND '.join(conditions)}
            ORDER BY {order_expr} DESC NULLS LAST
            LIMIT ${idx}
        """
        rows = await self.db.fetch(sql, *values)
        return {"athletes": [dict(r) for r in rows], "count": len(rows)}

    async def _get_athlete_score(self, params: Dict[str, Any]) -> Dict[str, Any]:
        if params.get("athlete_id"):
            row = await self.db.fetchrow(
                """SELECT a.*, s.gravity_score, s.brand_score, s.proof_score,
                          s.proximity_score, s.velocity_score, s.risk_score,
                          s.confidence, s.shap_values, s.top_factors_up,
                          s.top_factors_down, s.calculated_at
                   FROM athletes a
                   LEFT JOIN LATERAL (
                       SELECT * FROM athlete_gravity_scores
                       WHERE athlete_id = a.id
                       ORDER BY calculated_at DESC LIMIT 1
                   ) s ON true
                   WHERE a.id = $1""",
                params["athlete_id"],
            )
        else:
            row = await self.db.fetchrow(
                """SELECT a.*, s.gravity_score, s.brand_score, s.proof_score,
                          s.proximity_score, s.velocity_score, s.risk_score,
                          s.confidence, s.shap_values, s.top_factors_up,
                          s.top_factors_down, s.calculated_at
                   FROM athletes a
                   LEFT JOIN LATERAL (
                       SELECT * FROM athlete_gravity_scores
                       WHERE athlete_id = a.id
                       ORDER BY calculated_at DESC LIMIT 1
                   ) s ON true
                   WHERE a.name ILIKE $1
                   ORDER BY s.gravity_score DESC NULLS LAST
                   LIMIT 1""",
                f"%{params.get('athlete_name', '')}%",
            )
        if not row:
            return {"error": "Athlete not found"}
        return dict(row)

    async def _get_comparables(self, params: Dict[str, Any]) -> Dict[str, Any]:
        rows = await self.db.fetch(
            """SELECT a.id, a.name, a.school, a.conference, a.position,
                      s.gravity_score, s.brand_score, s.proof_score,
                      s.proximity_score, s.velocity_score, s.risk_score,
                      cs.similarity_score, cs.matching_dimensions
               FROM comparable_sets cs
               JOIN athletes a ON a.id = cs.comparable_athlete_id
               LEFT JOIN LATERAL (
                   SELECT * FROM athlete_gravity_scores
                   WHERE athlete_id = a.id
                   ORDER BY calculated_at DESC LIMIT 1
               ) s ON true
               WHERE cs.subject_athlete_id = $1
               ORDER BY cs.similarity_score DESC
               LIMIT 15""",
            params["athlete_id"],
        )
        return {"comparables": [dict(r) for r in rows]}

    async def _assess_deal(self, params: Dict[str, Any]) -> Dict[str, Any]:
        athlete = await self._get_athlete_score({"athlete_id": params["athlete_id"]})
        if "error" in athlete:
            return athlete

        comps = await self._get_comparables({"athlete_id": params["athlete_id"]})
        comp_scores = [
            c["gravity_score"] for c in comps["comparables"] if c.get("gravity_score") is not None
        ]

        if comp_scores:
            avg_comp = sum(comp_scores) / len(comp_scores)
            base_range_low = avg_comp * 800
            base_range_high = avg_comp * 1500
        else:
            g = athlete.get("gravity_score") or 50
            base_range_low = float(g) * 600
            base_range_high = float(g) * 1200

        proposed = float(params["proposed_value"])
        in_range = base_range_low <= proposed <= base_range_high
        likelihood = (
            "HIGH" if in_range else ("MEDIUM" if proposed <= base_range_high * 1.3 else "LOW")
        )

        return {
            "athlete_name": athlete.get("name"),
            "gravity_score": athlete.get("gravity_score"),
            "proposed_value": proposed,
            "range_low": round(base_range_low),
            "range_high": round(base_range_high),
            "in_range": in_range,
            "csc_clearance_likelihood": likelihood,
            "comparables_used": len(comp_scores),
            "assessment": (
                f"${proposed:,.0f} falls {'within' if in_range else 'outside'} "
                f"the comparable range of ${base_range_low:,.0f}–${base_range_high:,.0f}"
            ),
        }

    async def _get_program_nil_data(self, params: Dict[str, Any]) -> Dict[str, Any]:
        row = await self.db.fetchrow(
            """SELECT * FROM programs
               WHERE school ILIKE $1
               AND ($2::text IS NULL OR sport = $2)""",
            f"%{params['school']}%",
            params.get("sport"),
        )
        if not row:
            return {"error": f"Program not found: {params['school']}"}
        return dict(row)

    async def _filter_by_brand_fit(self, params: Dict[str, Any]) -> Dict[str, Any]:
        conditions = ["s.risk_score <= $1", "s.brand_score IS NOT NULL"]
        values: List[Any] = [params.get("max_risk", 30)]
        idx = 2

        if "sport" in params and params["sport"]:
            conditions.append(f"a.sport = ${idx}")
            values.append(params["sport"])
            idx += 1
        if "conference" in params and params["conference"]:
            conditions.append(f"a.conference ILIKE ${idx}")
            values.append(f"%{params['conference']}%")
            idx += 1

        limit = min(int(params.get("limit") or 15), 30)
        values.append(limit)

        sql = f"""
            SELECT a.id, a.name, a.sport, a.school, a.conference, a.position,
                   s.gravity_score, s.brand_score, s.proximity_score,
                   s.risk_score, s.velocity_score
            FROM athletes a
            LEFT JOIN LATERAL (
                SELECT * FROM athlete_gravity_scores
                WHERE athlete_id = a.id
                ORDER BY calculated_at DESC LIMIT 1
            ) s ON true
            WHERE {' AND '.join(conditions)}
            ORDER BY s.brand_score DESC NULLS LAST
            LIMIT ${idx}
        """
        rows = await self.db.fetch(sql, *values)
        return {"athletes": [dict(r) for r in rows], "count": len(rows)}

    def _classify_query(self, query: str) -> str:
        q = query.lower()
        # Campaign-style briefs before generic "deal" to avoid mis-routing.
        if any(
            phrase in q
            for phrase in (
                "find athletes",
                "for a campaign",
                "budget per athlete",
                "regional bank",
                "max 2 transfer",
                "controversy history",
            )
        ):
            return "brand_match"
        if "deal ceiling" in q or "ceiling for" in q:
            return "category_ceiling"
        if any(w in q for w in ["deal", "contract", "worth", "pay"]) or "assess a" in q:
            return "deal_assessment"
        if any(w in q for w in ["brand", "sponsor", "endorse", "partner"]):
            return "brand_match"
        if any(w in q for w in ["transfer", "transferred", "portal"]):
            return "program_comparison"
        if "gravity" in q and "score" in q and "from" in q and "to" in q:
            return "program_comparison"
        if any(w in q for w in ["risk", "injury", "controversy"]):
            return "risk_analysis"
        return "athlete_search"

    async def run_sync(
        self, query: str, context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        if not self.client:
            return {
                "response": (
                    "Agent offline: set ANTHROPIC_API_KEY and install the anthropic package "
                    "(pip install anthropic)."
                ),
                "tool_calls": [],
                "athlete_ids": [],
                "query_type": self._classify_query(query),
                "summary": "Agent unavailable",
            }

        user_content = query
        if context:
            user_content = query + "\n\nContext:\n" + json.dumps(context)

        messages: List[Dict[str, Any]] = [{"role": "user", "content": user_content}]
        tool_results: List[Dict[str, Any]] = []

        response = await self.client.messages.create(
            model=self.model,
            max_tokens=4096,
            system=GRAVITY_SYSTEM_PROMPT,
            tools=TOOLS,
            messages=messages,
        )

        while response.stop_reason == "tool_use":
            tool_calls = [b for b in response.content if b.type == "tool_use"]
            tool_result_content: List[Dict[str, Any]] = []

            for tool_call in tool_calls:
                result = await self.execute_tool(tool_call.name, dict(tool_call.input))
                safe_result = _json_safe(result)
                tool_result_content.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": tool_call.id,
                        "content": json.dumps(safe_result),
                    }
                )
                tool_results.append({"tool": tool_call.name, "input": tool_call.input, "result": safe_result})

            messages.append({"role": "assistant", "content": response.content})
            messages.append({"role": "user", "content": tool_result_content})

            response = await self.client.messages.create(
                model=self.model,
                max_tokens=4096,
                system=GRAVITY_SYSTEM_PROMPT,
                tools=TOOLS,
                messages=messages,
            )

        final_text = next((b.text for b in response.content if getattr(b, "type", None) == "text"), "")
        if not final_text:
            final_text = ""

        athlete_ids: List[str] = []
        for tr in tool_results:
            r = tr.get("result") or {}
            if "athletes" in r:
                athlete_ids.extend(a["id"] for a in r["athletes"] if isinstance(a, dict) and "id" in a)
            elif r.get("id"):
                athlete_ids.append(str(r["id"]))

        return {
            "response": final_text,
            "tool_calls": tool_results,
            "athlete_ids": list(dict.fromkeys(athlete_ids)),
            "query_type": self._classify_query(query),
            "summary": final_text[:200] if final_text else "",
        }

    async def run(self, query: str, context: Optional[Dict[str, Any]] = None) -> AsyncGenerator:
        yield {"type": "thinking", "content": "Analyzing query..."}
        result = await self.run_sync(query, context or {})
        yield {"type": "tool_calls", "calls": result["tool_calls"]}
        yield {"type": "athletes", "ids": result["athlete_ids"]}
        yield {"type": "response", "content": result["response"]}
        yield {"type": "query_type", "value": result["query_type"]}
