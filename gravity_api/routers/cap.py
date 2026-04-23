"""CapIQ — budgets, contracts, scenarios, utilization, outlook, rollup."""

from __future__ import annotations

import json
import uuid
from typing import Any, Dict, List, Optional

import asyncpg
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from gravity_api.auth_deps import require_user_id
from gravity_api.database import get_db
from gravity_api.services.athlete_score_sync import sync_athlete_score_from_ml
from gravity_api.services.cap_audit import write_cap_audit_log
from gravity_api.services.cap_metrics import (
    gravity_per_dollar_line,
    incentive_exposure_cents,
    latest_scores_for_athletes,
    weighted_aggregate_gravity,
)
from gravity_api.services.cap_sport import athlete_row_sport_to_cap, assert_cap_sport
from gravity_api.services.org_auth import (
    SchoolAuthContext,
    ensure_org_admin,
    ensure_sport_allowed,
    load_school_auth,
)
from gravity_api.services.cap_sport import CAP_SPORTS

router = APIRouter()


def _uuid(s: str, name: str = "id") -> uuid.UUID:
    try:
        return uuid.UUID(s)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid {name}") from e


async def _ctx(org_id: str, sport: str, user_id: uuid.UUID, db: asyncpg.Connection) -> tuple[SchoolAuthContext, str]:
    oid = _uuid(org_id, "org_id")
    sp = assert_cap_sport(sport)
    ctx = await load_school_auth(oid, user_id, db)
    ensure_sport_allowed(ctx, sp)
    return ctx, sp


class BudgetUpsertBody(BaseModel):
    org_id: str
    sport: str
    fiscal_year: int = Field(..., ge=2000, le=2100)
    total_allocation: Optional[int] = Field(None, description="Total cap in cents; null = undisclosed")
    notes: Optional[str] = None


@router.get("/budget/{org_id}/{sport}")
async def list_budgets(
    org_id: str,
    sport: str,
    db: asyncpg.Connection = Depends(get_db),
    user_id: uuid.UUID = Depends(require_user_id),
):
    ctx, sp = await _ctx(org_id, sport, user_id, db)
    rows = await db.fetch(
        """SELECT id, fiscal_year, total_allocation, notes, set_by, created_at, updated_at
           FROM nil_budgets WHERE org_id = $1 AND sport = $2 ORDER BY fiscal_year DESC""",
        ctx.org_id,
        sp,
    )
    return {
        "org_id": str(ctx.org_id),
        "sport": sp,
        "budgets": [
            {
                "id": str(r["id"]),
                "fiscal_year": r["fiscal_year"],
                "total_allocation": r["total_allocation"],
                "notes": r["notes"],
                "set_by": str(r["set_by"]) if r["set_by"] else None,
                "created_at": r["created_at"].isoformat() if r["created_at"] else None,
                "updated_at": r["updated_at"].isoformat() if r["updated_at"] else None,
            }
            for r in rows
        ],
    }


@router.post("/budget")
async def upsert_budget(
    body: BudgetUpsertBody,
    db: asyncpg.Connection = Depends(get_db),
    user_id: uuid.UUID = Depends(require_user_id),
):
    ctx, sp = await _ctx(body.org_id, body.sport, user_id, db)
    ensure_org_admin(ctx)
    oid = ctx.org_id
    row = await db.fetchrow(
        """INSERT INTO nil_budgets (org_id, sport, fiscal_year, total_allocation, notes, set_by)
           VALUES ($1, $2, $3, $4, $5, $6)
           ON CONFLICT (org_id, sport, fiscal_year) DO UPDATE SET
             total_allocation = EXCLUDED.total_allocation,
             notes = EXCLUDED.notes,
             set_by = EXCLUDED.set_by,
             updated_at = NOW()
           RETURNING id""",
        oid,
        sp,
        body.fiscal_year,
        body.total_allocation,
        body.notes,
        user_id,
    )
    rid = row["id"]
    await write_cap_audit_log(
        conn=db,
        org_id=oid,
        user_id=user_id,
        table_name="nil_budgets",
        record_id=rid,
        action="INSERT",
        new_values=body.model_dump(),
    )
    return {"id": str(rid), "ok": True}


@router.get("/utilization/{org_id}/{sport}/{year}")
async def utilization(
    org_id: str,
    sport: str,
    year: int,
    db: asyncpg.Connection = Depends(get_db),
    user_id: uuid.UUID = Depends(require_user_id),
):
    ctx, sp = await _ctx(org_id, sport, user_id, db)
    bud = await db.fetchrow(
        """SELECT total_allocation FROM nil_budgets
           WHERE org_id = $1 AND sport = $2 AND fiscal_year = $3""",
        ctx.org_id,
        sp,
        year,
    )
    rows = await db.fetch(
        """SELECT base_comp, incentives, third_party_flag FROM nil_roster_contracts
           WHERE org_id = $1 AND sport = $2 AND scenario_id IS NULL
             AND status = 'active' AND fiscal_year_start = $3""",
        ctx.org_id,
        sp,
        year,
    )
    committed = 0
    third_party = 0
    risk_exposure = 0
    for r in rows:
        base = int(r["base_comp"] or 0)
        inc = incentive_exposure_cents(r["incentives"])
        if r["third_party_flag"]:
            third_party += base + inc
        else:
            committed += base
            risk_exposure += inc
    alloc = int(bud["total_allocation"]) if bud and bud["total_allocation"] is not None else None
    pct = None
    if alloc and alloc > 0:
        pct = round(100.0 * committed / alloc, 2)
    return {
        "org_id": str(ctx.org_id),
        "sport": sp,
        "fiscal_year": year,
        "total_allocation_cents": alloc,
        "committed_cents": committed,
        "third_party_cents": third_party,
        "incentive_exposure_cents": risk_exposure,
        "utilization_pct": pct,
        "remaining_cents": (alloc - committed) if alloc is not None else None,
    }


class ContractCreateBody(BaseModel):
    org_id: str
    athlete_id: str
    sport: str
    base_comp: int = Field(..., ge=0)
    incentives: List[dict[str, Any]] = Field(default_factory=list)
    third_party_flag: bool = False
    payment_schedule: dict[str, Any] = Field(default_factory=dict)
    fiscal_year_start: int = Field(..., ge=2000, le=2100)
    eligibility_years_remaining: Optional[int] = None


class ContractPatchBody(BaseModel):
    base_comp: Optional[int] = None
    incentives: Optional[List[dict[str, Any]]] = None
    third_party_flag: Optional[bool] = None
    payment_schedule: Optional[dict[str, Any]] = None
    fiscal_year_start: Optional[int] = None
    eligibility_years_remaining: Optional[int] = None
    status: Optional[str] = None


@router.get("/contracts/{org_id}/{sport}")
async def list_contracts(
    org_id: str,
    sport: str,
    db: asyncpg.Connection = Depends(get_db),
    user_id: uuid.UUID = Depends(require_user_id),
):
    ctx, sp = await _ctx(org_id, sport, user_id, db)
    rows = await db.fetch(
        """SELECT c.*, a.name AS athlete_name
           FROM nil_roster_contracts c
           JOIN athletes a ON a.id = c.athlete_id
           WHERE c.org_id = $1 AND c.sport = $2 AND c.scenario_id IS NULL AND c.status = 'active'
           ORDER BY c.updated_at DESC""",
        ctx.org_id,
        sp,
    )
    return {"contracts": [_contract_row(r) for r in rows]}


def _contract_row(r: asyncpg.Record) -> dict[str, Any]:
    return {
        "id": str(r["id"]),
        "athlete_id": str(r["athlete_id"]),
        "athlete_name": r.get("athlete_name"),
        "sport": r["sport"],
        "base_comp": int(r["base_comp"]),
        "incentives": r["incentives"],
        "third_party_flag": r["third_party_flag"],
        "payment_schedule": r["payment_schedule"],
        "fiscal_year_start": r["fiscal_year_start"],
        "eligibility_years_remaining": r["eligibility_years_remaining"],
        "status": r["status"],
        "scenario_id": str(r["scenario_id"]) if r["scenario_id"] else None,
    }


@router.post("/contracts")
async def create_contract(
    body: ContractCreateBody,
    db: asyncpg.Connection = Depends(get_db),
    user_id: uuid.UUID = Depends(require_user_id),
):
    ctx, sp = await _ctx(body.org_id, body.sport, user_id, db)
    aid = _uuid(body.athlete_id, "athlete_id")
    ath = await db.fetchrow("SELECT id, sport FROM athletes WHERE id = $1", aid)
    if not ath:
        raise HTTPException(status_code=404, detail="Athlete not found")
    if athlete_row_sport_to_cap(ath["sport"]) != sp:
        raise HTTPException(status_code=400, detail="Athlete sport does not match cap sport")
    row = await db.fetchrow(
        """INSERT INTO nil_roster_contracts (
             org_id, athlete_id, sport, base_comp, incentives, third_party_flag,
             payment_schedule, fiscal_year_start, eligibility_years_remaining,
             status, scenario_id, created_by
           ) VALUES ($1,$2,$3,$4,$5::jsonb,$6,$7::jsonb,$8,$9,'active',NULL,$10)
           RETURNING id""",
        ctx.org_id,
        aid,
        sp,
        body.base_comp,
        json.dumps(body.incentives),
        body.third_party_flag,
        json.dumps(body.payment_schedule),
        body.fiscal_year_start,
        body.eligibility_years_remaining,
        user_id,
    )
    cid = row["id"]
    await write_cap_audit_log(
        conn=db,
        org_id=ctx.org_id,
        user_id=user_id,
        table_name="nil_roster_contracts",
        record_id=cid,
        action="INSERT",
        new_values=body.model_dump(),
    )
    return {"id": str(cid), "ok": True}


@router.patch("/contracts/{contract_id}")
async def patch_contract(
    contract_id: str,
    body: ContractPatchBody,
    db: asyncpg.Connection = Depends(get_db),
    user_id: uuid.UUID = Depends(require_user_id),
):
    cid = _uuid(contract_id, "contract_id")
    row = await db.fetchrow(
        "SELECT * FROM nil_roster_contracts WHERE id = $1 AND scenario_id IS NULL",
        cid,
    )
    if not row:
        raise HTTPException(status_code=404, detail="Contract not found")
    ctx = await load_school_auth(row["org_id"], user_id, db)
    ensure_sport_allowed(ctx, row["sport"])
    dump = body.model_dump(exclude_unset=True)
    if not dump:
        return {"ok": True}
    await db.execute(
        """UPDATE nil_roster_contracts SET
             base_comp = COALESCE($2, base_comp),
             incentives = COALESCE($3::jsonb, incentives),
             third_party_flag = COALESCE($4, third_party_flag),
             payment_schedule = COALESCE($5::jsonb, payment_schedule),
             fiscal_year_start = COALESCE($6, fiscal_year_start),
             eligibility_years_remaining = COALESCE($7, eligibility_years_remaining),
             status = COALESCE($8, status),
             updated_at = NOW()
           WHERE id = $1""",
        cid,
        dump.get("base_comp"),
        json.dumps(dump["incentives"]) if "incentives" in dump else None,
        dump.get("third_party_flag"),
        json.dumps(dump["payment_schedule"]) if "payment_schedule" in dump else None,
        dump.get("fiscal_year_start"),
        dump.get("eligibility_years_remaining"),
        dump.get("status"),
    )
    await write_cap_audit_log(
        conn=db,
        org_id=row["org_id"],
        user_id=user_id,
        table_name="nil_roster_contracts",
        record_id=cid,
        action="UPDATE",
        old_values=dict(row),
        new_values=dump,
    )
    return {"ok": True}


@router.delete("/contracts/{contract_id}")
async def delete_contract(
    contract_id: str,
    db: asyncpg.Connection = Depends(get_db),
    user_id: uuid.UUID = Depends(require_user_id),
):
    cid = _uuid(contract_id, "contract_id")
    row = await db.fetchrow(
        "SELECT * FROM nil_roster_contracts WHERE id = $1 AND scenario_id IS NULL",
        cid,
    )
    if not row:
        raise HTTPException(status_code=404, detail="Contract not found")
    ctx = await load_school_auth(row["org_id"], user_id, db)
    ensure_sport_allowed(ctx, row["sport"])
    await db.execute(
        "UPDATE nil_roster_contracts SET status = 'expired', updated_at = NOW() WHERE id = $1",
        cid,
    )
    await write_cap_audit_log(
        conn=db,
        org_id=row["org_id"],
        user_id=user_id,
        table_name="nil_roster_contracts",
        record_id=cid,
        action="DELETE",
        old_values=dict(row),
    )
    return {"ok": True}


class ScenarioCreateBody(BaseModel):
    org_id: str
    sport: str
    name: str = Field(..., min_length=1, max_length=200)
    base_roster_id: Optional[str] = None


@router.get("/org/{org_id}/scenarios/{sport}")
async def list_scenarios(
    org_id: str,
    sport: str,
    db: asyncpg.Connection = Depends(get_db),
    user_id: uuid.UUID = Depends(require_user_id),
):
    ctx, sp = await _ctx(org_id, sport, user_id, db)
    rows = await db.fetch(
        """SELECT id, name, status, aggregate_gravity_score, total_committed,
                  total_risk_exposure, created_at, updated_at, promoted_at
           FROM nil_scenarios WHERE org_id = $1 AND sport = $2 ORDER BY updated_at DESC""",
        ctx.org_id,
        sp,
    )
    return {
        "scenarios": [
            {
                "id": str(r["id"]),
                "name": r["name"],
                "status": r["status"],
                "aggregate_gravity_score": r["aggregate_gravity_score"],
                "total_committed": int(r["total_committed"]) if r["total_committed"] is not None else None,
                "total_risk_exposure": int(r["total_risk_exposure"]) if r["total_risk_exposure"] is not None else None,
                "created_at": r["created_at"].isoformat() if r["created_at"] else None,
                "updated_at": r["updated_at"].isoformat() if r["updated_at"] else None,
                "promoted_at": r["promoted_at"].isoformat() if r["promoted_at"] else None,
            }
            for r in rows
        ]
    }


@router.post("/scenarios")
async def create_scenario(
    body: ScenarioCreateBody,
    db: asyncpg.Connection = Depends(get_db),
    user_id: uuid.UUID = Depends(require_user_id),
):
    ctx, sp = await _ctx(body.org_id, body.sport, user_id, db)
    base_rid = None
    if body.base_roster_id:
        base_rid = _uuid(body.base_roster_id, "base_roster_id")
    row = await db.fetchrow(
        """INSERT INTO nil_scenarios (org_id, sport, name, base_roster_id, status, created_by)
           VALUES ($1,$2,$3,$4,'draft',$5) RETURNING id""",
        ctx.org_id,
        sp,
        body.name.strip(),
        base_rid,
        user_id,
    )
    sid = row["id"]
    await write_cap_audit_log(
        conn=db,
        org_id=ctx.org_id,
        user_id=user_id,
        table_name="nil_scenarios",
        record_id=sid,
        action="INSERT",
        new_values=body.model_dump(),
    )
    return {"id": str(sid), "ok": True}


@router.get("/scenarios/{scenario_id}")
async def scenario_detail(
    scenario_id: str,
    db: asyncpg.Connection = Depends(get_db),
    user_id: uuid.UUID = Depends(require_user_id),
):
    sid = _uuid(scenario_id, "scenario_id")
    scen = await db.fetchrow("SELECT * FROM nil_scenarios WHERE id = $1", sid)
    if not scen:
        raise HTTPException(status_code=404, detail="Scenario not found")
    ctx = await load_school_auth(scen["org_id"], user_id, db)
    ensure_sport_allowed(ctx, scen["sport"])
    crows = await db.fetch(
        """SELECT c.*, a.name AS athlete_name FROM nil_roster_contracts c
           JOIN athletes a ON a.id = c.athlete_id
           WHERE c.scenario_id = $1 ORDER BY c.created_at""",
        sid,
    )
    return {
        "scenario": {
            "id": str(scen["id"]),
            "org_id": str(scen["org_id"]),
            "sport": scen["sport"],
            "name": scen["name"],
            "status": scen["status"],
            "aggregate_gravity_score": scen["aggregate_gravity_score"],
            "total_committed": int(scen["total_committed"]) if scen["total_committed"] is not None else None,
            "total_risk_exposure": int(scen["total_risk_exposure"]) if scen["total_risk_exposure"] is not None else None,
        },
        "contracts": [_contract_row(r) for r in crows],
    }


class ScenarioContractBody(BaseModel):
    athlete_id: str
    base_comp: int = Field(..., ge=0)
    incentives: List[dict[str, Any]] = Field(default_factory=list)
    third_party_flag: bool = False
    payment_schedule: dict[str, Any] = Field(default_factory=dict)
    fiscal_year_start: int = Field(..., ge=2000, le=2100)
    eligibility_years_remaining: Optional[int] = None


@router.post("/scenarios/{scenario_id}/contracts")
async def upsert_scenario_contract(
    scenario_id: str,
    body: ScenarioContractBody,
    db: asyncpg.Connection = Depends(get_db),
    user_id: uuid.UUID = Depends(require_user_id),
):
    sid = _uuid(scenario_id, "scenario_id")
    scen = await db.fetchrow("SELECT * FROM nil_scenarios WHERE id = $1", sid)
    if not scen or scen["status"] != "draft":
        raise HTTPException(status_code=404, detail="Scenario not found or not draft")
    ctx = await load_school_auth(scen["org_id"], user_id, db)
    ensure_sport_allowed(ctx, scen["sport"])
    aid = _uuid(body.athlete_id, "athlete_id")
    existing = await db.fetchrow(
        "SELECT id FROM nil_roster_contracts WHERE scenario_id = $1 AND athlete_id = $2",
        sid,
        aid,
    )
    if existing:
        row = await db.fetchrow(
            """UPDATE nil_roster_contracts SET
                 base_comp=$1, incentives=$2::jsonb, third_party_flag=$3,
                 payment_schedule=$4::jsonb, fiscal_year_start=$5,
                 eligibility_years_remaining=$6, updated_at=NOW()
               WHERE id=$7 RETURNING id""",
            body.base_comp,
            json.dumps(body.incentives),
            body.third_party_flag,
            json.dumps(body.payment_schedule),
            body.fiscal_year_start,
            body.eligibility_years_remaining,
            existing["id"],
        )
        cid = row["id"]
    else:
        row = await db.fetchrow(
            """INSERT INTO nil_roster_contracts (
                 org_id, athlete_id, sport, base_comp, incentives, third_party_flag,
                 payment_schedule, fiscal_year_start, eligibility_years_remaining,
                 status, scenario_id, created_by
               ) VALUES ($1,$2,$3,$4,$5::jsonb,$6,$7::jsonb,$8,$9,'draft',$10,$11)
               RETURNING id""",
            scen["org_id"],
            aid,
            scen["sport"],
            body.base_comp,
            json.dumps(body.incentives),
            body.third_party_flag,
            json.dumps(body.payment_schedule),
            body.fiscal_year_start,
            body.eligibility_years_remaining,
            sid,
            user_id,
        )
        cid = row["id"]
    await write_cap_audit_log(
        conn=db,
        org_id=scen["org_id"],
        user_id=user_id,
        table_name="nil_roster_contracts",
        record_id=cid,
        action="INSERT" if not existing else "UPDATE",
        new_values=body.model_dump(),
    )
    return {"id": str(cid), "ok": True}


@router.delete("/scenarios/{scenario_id}/contracts/{contract_id}")
async def delete_scenario_contract(
    scenario_id: str,
    contract_id: str,
    db: asyncpg.Connection = Depends(get_db),
    user_id: uuid.UUID = Depends(require_user_id),
):
    sid = _uuid(scenario_id, "scenario_id")
    cid = _uuid(contract_id, "contract_id")
    row = await db.fetchrow(
        "SELECT c.*, s.org_id, s.sport, s.status AS scen_status FROM nil_roster_contracts c "
        "JOIN nil_scenarios s ON s.id = c.scenario_id WHERE c.id = $1 AND c.scenario_id = $2",
        cid,
        sid,
    )
    if not row or row["scen_status"] != "draft":
        raise HTTPException(status_code=404, detail="Contract not found")
    ctx = await load_school_auth(row["org_id"], user_id, db)
    ensure_sport_allowed(ctx, row["sport"])
    await db.execute("DELETE FROM nil_roster_contracts WHERE id = $1", cid)
    await write_cap_audit_log(
        conn=db,
        org_id=row["org_id"],
        user_id=user_id,
        table_name="nil_roster_contracts",
        record_id=cid,
        action="DELETE",
        old_values=dict(row),
    )
    return {"ok": True}


async def _roster_state(
    conn: asyncpg.Connection,
    org_id: uuid.UUID,
    sport: str,
    scenario_id: Optional[uuid.UUID],
) -> Dict[str, Any]:
    if scenario_id:
        crows = await conn.fetch(
            """SELECT c.*, a.name AS athlete_name, a.sport AS athlete_db_sport
               FROM nil_roster_contracts c
               JOIN athletes a ON a.id = c.athlete_id
               WHERE c.scenario_id = $1 AND c.status IN ('active','draft')""",
            scenario_id,
        )
    else:
        crows = await conn.fetch(
            """SELECT c.*, a.name AS athlete_name, a.sport AS athlete_db_sport
               FROM nil_roster_contracts c
               JOIN athletes a ON a.id = c.athlete_id
               WHERE c.org_id = $1 AND c.sport = $2 AND c.scenario_id IS NULL AND c.status = 'active'""",
            org_id,
            sport,
        )
    aids = [str(r["athlete_id"]) for r in crows]
    scores = await latest_scores_for_athletes(conn, aids)
    pairs: List[tuple[Any, int]] = []
    athletes_out: List[dict[str, Any]] = []
    total_cents = 0
    for r in crows:
        base = int(r["base_comp"] or 0)
        if not r["third_party_flag"]:
            total_cents += base
        rec = scores.get(str(r["athlete_id"]))
        pairs.append((rec, max(base, 1)))
        athletes_out.append(
            {
                **_contract_row(r),
                "gravity_score": float(rec["gravity_score"]) if rec else None,
                "risk_score": float(rec["risk_score"]) if rec else None,
            }
        )
    agg_g, avg_r = weighted_aggregate_gravity([(p[0], max(p[1], 1)) for p in pairs])
    return {
        "athletes": athletes_out,
        "aggregate_gravity": agg_g,
        "total_committed_cents": total_cents,
        "avg_risk_score": avg_r,
    }


@router.get("/scenarios/{scenario_id}/compare")
async def compare_scenario(
    scenario_id: str,
    db: asyncpg.Connection = Depends(get_db),
    user_id: uuid.UUID = Depends(require_user_id),
):
    sid = _uuid(scenario_id, "scenario_id")
    scen = await db.fetchrow("SELECT * FROM nil_scenarios WHERE id = $1", sid)
    if not scen:
        raise HTTPException(status_code=404, detail="Scenario not found")
    ctx = await load_school_auth(scen["org_id"], user_id, db)
    ensure_sport_allowed(ctx, scen["sport"])
    org_id = scen["org_id"]
    sport = scen["sport"]
    scen_contracts = await db.fetch(
        "SELECT athlete_id FROM nil_roster_contracts WHERE scenario_id = $1", sid
    )
    for r in scen_contracts:
        aid = r["athlete_id"]
        has_score = await db.fetchval(
            "SELECT EXISTS(SELECT 1 FROM athlete_gravity_scores WHERE athlete_id = $1)",
            aid,
        )
        if not has_score:
            try:
                await sync_athlete_score_from_ml(db, str(aid))
            except Exception:
                pass
    official = await _roster_state(db, org_id, sport, None)
    scenario = await _roster_state(db, org_id, sport, sid)
    dg = round(scenario["aggregate_gravity"] - official["aggregate_gravity"], 4)
    dc = scenario["total_committed_cents"] - official["total_committed_cents"]
    dr = round(scenario["avg_risk_score"] - official["avg_risk_score"], 4)
    off_line = gravity_per_dollar_line(official["aggregate_gravity"], official["total_committed_cents"])
    scen_line = gravity_per_dollar_line(scenario["aggregate_gravity"], scenario["total_committed_cents"])
    return {
        "official": official,
        "scenario": scenario,
        "delta": {
            "gravity": dg,
            "cost_cents": dc,
            "risk": dr,
            "gravity_per_dollar": f"official: {off_line}; scenario: {scen_line}",
        },
    }


@router.post("/scenarios/{scenario_id}/promote")
async def promote_scenario(
    scenario_id: str,
    db: asyncpg.Connection = Depends(get_db),
    user_id: uuid.UUID = Depends(require_user_id),
):
    sid = _uuid(scenario_id, "scenario_id")
    scen = await db.fetchrow("SELECT * FROM nil_scenarios WHERE id = $1", sid)
    if not scen or scen["status"] != "draft":
        raise HTTPException(status_code=400, detail="Scenario not promotable")
    ctx = await load_school_auth(scen["org_id"], user_id, db)
    ensure_sport_allowed(ctx, scen["sport"])
    ensure_org_admin(ctx)
    org_id = scen["org_id"]
    sport = scen["sport"]
    async with db.transaction():
        await db.execute(
            """UPDATE nil_roster_contracts SET status = 'expired', updated_at = NOW()
               WHERE org_id = $1 AND sport = $2 AND scenario_id IS NULL AND status = 'active'""",
            org_id,
            sport,
        )
        await db.execute(
            """UPDATE nil_roster_contracts SET scenario_id = NULL, status = 'active', updated_at = NOW()
               WHERE scenario_id = $1""",
            sid,
        )
        await db.execute(
            """UPDATE nil_scenarios SET status = 'promoted', promoted_at = NOW(), promoted_by = $2, updated_at = NOW()
               WHERE id = $1""",
            sid,
            user_id,
        )
    await write_cap_audit_log(
        conn=db,
        org_id=org_id,
        user_id=user_id,
        table_name="nil_scenarios",
        record_id=sid,
        action="UPDATE",
        new_values={"promoted": True},
    )
    return {"ok": True}


@router.get("/outlook/{org_id}/{sport}")
async def outlook(
    org_id: str,
    sport: str,
    db: asyncpg.Connection = Depends(get_db),
    user_id: uuid.UUID = Depends(require_user_id),
):
    ctx, sp = await _ctx(org_id, sport, user_id, db)
    from datetime import date

    y0 = date.today().year
    years = list(range(y0, y0 + 5))
    rows_out = []
    for fy in years:
        bud = await db.fetchrow(
            """SELECT total_allocation FROM nil_budgets
               WHERE org_id = $1 AND sport = $2 AND fiscal_year = $3""",
            ctx.org_id,
            sp,
            fy,
        )
        crows = await db.fetch(
            """SELECT base_comp, incentives, third_party_flag, eligibility_years_remaining
               FROM nil_roster_contracts
               WHERE org_id = $1 AND sport = $2 AND scenario_id IS NULL AND status = 'active'
                 AND fiscal_year_start = $3""",
            ctx.org_id,
            sp,
            fy,
        )
        committed = 0
        inc_exp = 0
        heads = 0
        for r in crows:
            if not r["third_party_flag"]:
                committed += int(r["base_comp"] or 0)
                heads += 1
            inc_exp += incentive_exposure_cents(r["incentives"])
        alloc = int(bud["total_allocation"]) if bud and bud["total_allocation"] is not None else None
        rows_out.append(
            {
                "fiscal_year": fy,
                "committed_cents": committed,
                "incentive_exposure_cents": inc_exp,
                "headcount": heads,
                "available_cap_cents": (alloc - committed) if alloc is not None else None,
            }
        )
    return {"org_id": str(ctx.org_id), "sport": sp, "years": rows_out}


@router.get("/rollup/{org_id}")
async def rollup(
    org_id: str,
    db: asyncpg.Connection = Depends(get_db),
    user_id: uuid.UUID = Depends(require_user_id),
):
    """School admin: all Cap sports utilization summary for the org."""
    oid = _uuid(org_id, "org_id")
    ctx = await load_school_auth(oid, user_id, db)
    ensure_org_admin(ctx)
    out = []
    for sp in sorted(CAP_SPORTS):
        bud_rows = await db.fetch(
            "SELECT fiscal_year, total_allocation FROM nil_budgets WHERE org_id = $1 AND sport = $2 ORDER BY fiscal_year DESC LIMIT 1",
            oid,
            sp,
        )
        fy = bud_rows[0]["fiscal_year"] if bud_rows else None
        if fy is None:
            out.append({"sport": sp, "fiscal_year": None, "utilization_pct": None, "committed_cents": 0})
            continue
        urow = await db.fetchrow(
            """SELECT COALESCE(SUM(base_comp),0)::bigint AS c FROM nil_roster_contracts
               WHERE org_id = $1 AND sport = $2 AND scenario_id IS NULL AND status = 'active'
                 AND fiscal_year_start = $3 AND third_party_flag = false""",
            oid,
            sp,
            fy,
        )
        committed = int(urow["c"] or 0)
        alloc = bud_rows[0]["total_allocation"]
        pct = None
        if alloc and int(alloc) > 0:
            pct = round(100.0 * committed / int(alloc), 2)
        out.append(
            {
                "sport": sp,
                "fiscal_year": fy,
                "committed_cents": committed,
                "total_allocation_cents": int(alloc) if alloc is not None else None,
                "utilization_pct": pct,
            }
        )
    return {"org_id": str(oid), "sports": out}
