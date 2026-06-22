"""FastAPI app — athlete, team, brand scoring for all target sports."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from fastapi import Depends, FastAPI, Header, HTTPException, Query

from gravity_ml.inference.predict import SUPPORTED_SPORTS, score_athlete, score_brand, score_team
from gravity_ml.schemas import (
    ScoreAthleteRequest,
    ScoreAthleteResponse,
    ScoreBrandRequest,
    ScoreBrandResponse,
    ScoreFitRequest,
    ScoreFitResponse,
    ScoreTeamRequest,
    ScoreTeamResponse,
)


def _require_ml_key(authorization: Optional[str] = Header(None)) -> None:
    expected = os.environ.get("ML_API_KEY") or os.environ.get("ML_SERVICE_API_KEY")
    if not expected:
        return
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing Bearer token")
    token = authorization[7:].strip()
    if token != expected:
        raise HTTPException(status_code=403, detail="Invalid API key")


def create_app() -> FastAPI:
    app = FastAPI(title="gravity-ml", version="2.0.0")

    @app.get("/health")
    async def health():
        root = os.environ.get("MODEL_BUNDLE_ROOT") or os.environ.get("MODEL_BUNDLE_PATH")
        return {"status": "ok", "service": "gravity-ml", "bundle_root": root}

    @app.get("/health/ready")
    async def health_ready():
        from gravity_ml.inference.bundle_loader import get_bundle_loader

        root = os.environ.get("MODEL_BUNDLE_ROOT") or os.environ.get("MODEL_BUNDLE_PATH")
        loader = get_bundle_loader()
        champions = loader._index if loader.bundle_root else {}
        return {
            "status": "ready",
            "bundle_root": str(loader.bundle_root) if loader.bundle_root else None,
            "champion_models": champions,
            "sports": list(SUPPORTED_SPORTS),
        }

    @app.post("/admin/reload-models")
    async def reload_models(_: None = Depends(_require_ml_key)):
        import gravity_ml.inference.bundle_loader as bl

        bl._loader = None
        return {"status": "reloaded"}

    async def _score_athlete(req: ScoreAthleteRequest, include_shap: bool) -> ScoreAthleteResponse:
        result = score_athlete(req)
        if not include_shap:
            result.shap_values = None
        return result

    @app.post("/score/athlete", response_model=ScoreAthleteResponse)
    async def score_generic(
        req: ScoreAthleteRequest,
        include_shap: bool = Query(True),
        _: None = Depends(_require_ml_key),
    ):
        return await _score_athlete(req, include_shap)

    @app.post("/score/athlete/v2", response_model=ScoreAthleteResponse)
    async def score_v2(
        req: ScoreAthleteRequest,
        include_shap: bool = Query(True),
        _: None = Depends(_require_ml_key),
    ):
        return await _score_athlete(req, include_shap)

    for sport in SUPPORTED_SPORTS:
        sport_key = sport

        @app.post(f"/score/athlete/{sport_key}", response_model=ScoreAthleteResponse)
        async def score_by_sport(
            req: ScoreAthleteRequest,
            include_shap: bool = Query(True),
            _auth: None = Depends(_require_ml_key),
            bound_sport: str = sport_key,
        ):
            req.sport = bound_sport
            return await _score_athlete(req, include_shap)

    @app.post("/score/team", response_model=ScoreTeamResponse)
    async def score_team_generic(
        req: ScoreTeamRequest,
        _: None = Depends(_require_ml_key),
    ):
        return score_team(req)

    for sport in SUPPORTED_SPORTS:
        sport_key = sport

        @app.post(f"/score/team/{sport_key}", response_model=ScoreTeamResponse)
        async def score_team_by_sport(
            req: ScoreTeamRequest,
            _auth: None = Depends(_require_ml_key),
            bound_sport: str = sport_key,
        ):
            req.sport = bound_sport
            return score_team(req)

    @app.post("/score/brand", response_model=ScoreBrandResponse)
    async def score_brand_endpoint(
        req: ScoreBrandRequest,
        _: None = Depends(_require_ml_key),
    ):
        return score_brand(req)

    @app.post("/score/fit", response_model=ScoreFitResponse)
    async def score_fit(
        req: ScoreFitRequest,
        _: None = Depends(_require_ml_key),
    ):
        from gravity_ml.brand.taxonomy import get_taxonomy

        taxonomy = get_taxonomy()
        brand_name = str(req.raw_data.get("brand_name") or "")
        entry = taxonomy.match_brand(brand_name)
        fit = 62.0 if entry else 50.0
        return ScoreFitResponse(
            athlete_id=req.athlete_id,
            brand_id=req.brand_id,
            fit_score=fit,
            fallback_used=True,
        )

    return app


app = create_app()
