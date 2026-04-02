"""
Engineer a fixed 250-dim feature vector from scraper-aligned dict rows.

Expects keys consistent with ``gravity.scrapers.models.GRAVITY_ML_RAW_FIELD_NAMES``
plus ``sport`` in {\"cfb\", \"ncaab_mens\", \"ncaab_womens\"}.
"""

from __future__ import annotations

import hashlib
import math
import re
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Mapping

import numpy as np
import pandas as pd

from gravity.scrapers.models import GRAVITY_ML_RAW_FIELD_NAMES

# Stage 1 target dimension for the neural net input.
N_FEATURE_COLUMNS = 250

_POSITION_BUCKET = [
    "QB", "RB", "WR", "TE", "OL", "DL", "LB", "DB", "K", "P",
    "PG", "SG", "SF", "PF", "C", "ATH", "UNKNOWN",
]


def _position_idx(pos: str | None) -> int:
    if not pos:
        return len(_POSITION_BUCKET) - 1
    p = pos.upper().strip()[:6]
    for i, b in enumerate(_POSITION_BUCKET):
        if p == b or p.startswith(b):
            return i
    return len(_POSITION_BUCKET) - 1


def _conference_idx(conf: str | None) -> int:
    if not conf:
        return 5
    c = conf.lower()
    if "sec" in c and "big" not in c:
        return 0
    if "big ten" in c or "big 10" in c:
        return 1
    if "big 12" in c:
        return 2
    if "acc" in c:
        return 3
    if "big east" in c:
        return 4
    return 5


def _sport_vec(sport: str | None) -> np.ndarray:
    v = np.zeros(3, dtype=np.float64)
    if sport == "cfb":
        v[0] = 1.0
    elif sport == "ncaab_mens":
        v[1] = 1.0
    elif sport == "ncaab_womens":
        v[2] = 1.0
    else:
        v[0] = 1.0
    return v


def _coerce_float(x: Any) -> float:
    if x is None or x == "ERROR":
        return math.nan
    if isinstance(x, bool):
        return float(x)
    if isinstance(x, (int, float)):
        if isinstance(x, float) and math.isnan(x):
            return math.nan
        return float(x)
    if isinstance(x, str):
        x = x.strip()
        if not x:
            return math.nan
        try:
            return float(x)
        except ValueError:
            return math.nan
    return math.nan


def _nil_valuation_to_scalar(s: Any) -> float:
    """Parse On3-style money strings to a dollar float (rough)."""
    if s is None or s == "ERROR":
        return math.nan
    if isinstance(s, (int, float)):
        return float(s)
    t = str(s).strip()
    if not t:
        return math.nan
    t = t.replace(",", "").replace("$", "")
    m = re.search(r"([\d.]+)\s*([kKmM]?)(?:illion|)?", t)
    if not m:
        return math.nan
    val = float(m.group(1))
    suf = (m.group(2) or "").upper()
    if suf == "K":
        val *= 1_000
    elif suf == "M":
        val *= 1_000_000
    elif "illion" in t.lower():
        val *= 1_000_000
    return val


def _draft_rank_proxy(s: Any) -> float:
    if s is None or s == "ERROR":
        return math.nan
    m = re.search(r"#\s*(\d+)", str(s))
    if m:
        return float(m.group(1))
    m2 = re.search(r"\b(\d{1,2})\b", str(s))
    if m2:
        return float(m2.group(1))
    return math.nan


def _parse_height_inches(h: Any) -> float:
    if h is None or h == "ERROR":
        return math.nan
    s = str(h).replace('"', "").replace("'", "-")
    if "-" in s:
        try:
            parts = s.split("-")
            ft = float(re.sub(r"[^\d.]", "", parts[0]) or math.nan)
            inch = float(re.sub(r"[^\d.]", "", parts[1]) or 0)
            return ft * 12 + inch
        except (ValueError, IndexError):
            pass
    return math.nan


def _parse_weight_lb(w: Any) -> float:
    if w is None or w == "ERROR":
        return math.nan
    m = re.search(r"([\d.]+)", str(w))
    if m:
        try:
            return float(m.group(1))
        except ValueError:
            pass
    return math.nan


def _years_in_school_approx(class_year: Any) -> float:
    if class_year is None:
        return math.nan
    s = str(class_year).upper()
    if "GRAD" in s or "SR" in s or "SENIOR" in s:
        return 4.0
    if "JR" in s or "JUNIOR" in s:
        return 3.0
    if "SO" in s or "SOPH" in s:
        return 2.0
    if "FR" in s or "FRESH" in s:
        return 1.0
    m = re.search(r"(\d+)", s)
    if m:
        try:
            return float(m.group(1))
        except ValueError:
            pass
    return math.nan


def _safe_len(x: Any) -> float:
    if x is None or x == "ERROR":
        return 0.0
    if isinstance(x, (list, tuple, dict)):
        return float(len(x))
    return 0.0


@dataclass
class CohortStats:
    team_followers_mean: dict[str, float] = field(default_factory=dict)
    conf_news_mean: dict[str, float] = field(default_factory=dict)
    conf_nil_mean: dict[str, float] = field(default_factory=dict)
    spos_ppg_mean: dict[tuple[str, int], float] = field(default_factory=dict)
    spos_recruit_rank_mean: dict[tuple[str, int], float] = field(default_factory=dict)
    global_trends_mean: float = 0.0
    global_ig_mean: float = 0.0


def build_cohort_stats(rows: list[Mapping[str, Any]]) -> CohortStats:
    """Aggregate reference stats from training corpus for ratio features."""
    cs = CohortStats()
    ig_by_team: dict[str, list[float]] = defaultdict(list)
    news_by_conf: dict[str, list[float]] = defaultdict(list)
    nil_by_conf: dict[str, list[float]] = defaultdict(list)
    ppg_by_spos: dict[tuple[str, int], list[float]] = defaultdict(list)
    rk_by_spos: dict[tuple[str, int], list[float]] = defaultdict(list)
    trends: list[float] = []
    all_ig: list[float] = []

    for r in rows:
        sport = str(r.get("sport") or "cfb")
        team = str(r.get("team") or "")
        conf = str(r.get("conference") or "")
        pos_i = _position_idx(r.get("position") if isinstance(r.get("position"), str) else None)
        ig = _coerce_float(r.get("instagram_followers"))
        news = _coerce_float(r.get("news_count_30d"))
        nils = _nil_valuation_to_scalar(r.get("nil_valuation"))
        ppg = _coerce_float(r.get("ppg"))
        rk = _coerce_float(r.get("recruiting_rank_national"))
        tr = _coerce_float(r.get("google_trends_score"))

        if team and not math.isnan(ig):
            ig_by_team[team].append(ig)
        if conf and not math.isnan(news):
            news_by_conf[conf].append(news)
        if conf and not math.isnan(nils):
            nil_by_conf[conf].append(nils)
        if not math.isnan(ppg):
            ppg_by_spos[(sport, pos_i)].append(ppg)
        if not math.isnan(rk):
            rk_by_spos[(sport, pos_i)].append(rk)
        if not math.isnan(tr):
            trends.append(tr)
        if not math.isnan(ig):
            all_ig.append(ig)

    for t, vals in ig_by_team.items():
        cs.team_followers_mean[t] = float(np.mean(vals)) if vals else 0.0
    for c, vals in news_by_conf.items():
        cs.conf_news_mean[c] = float(np.mean(vals)) if vals else 0.0
    for c, vals in nil_by_conf.items():
        cs.conf_nil_mean[c] = float(np.mean(vals)) if vals else 0.0
    for k, vals in ppg_by_spos.items():
        cs.spos_ppg_mean[k] = float(np.mean(vals)) if vals else 0.0
    for k, vals in rk_by_spos.items():
        cs.spos_recruit_rank_mean[k] = float(np.mean(vals)) if vals else 0.0

    cs.global_trends_mean = float(np.mean(trends)) if trends else 0.0
    cs.global_ig_mean = float(np.mean(all_ig)) if all_ig else 0.0
    return cs


def build_feature_names() -> list[str]:
    """Ordered names for the 250 input columns (matches SHAP / inference)."""
    names: list[str] = []
    # 0–99 core engineered
    core = [
        "age",
        "eligibility_years_remaining",
        "recruiting_stars",
        "recruiting_rank_national_inv",
        "recruiting_rank_position_inv",
        "heisman_votes_log1p",
        "all_american_count_log1p",
        "instagram_followers_log1p",
        "twitter_followers_log1p",
        "news_count_30d_log1p",
        "google_trends_score",
        "data_quality_score",
        "nil_valuation_log1p",
        "nil_deals_count",
        "ppg",
        "rpg",
        "apg",
        "fg_pct",
        "three_pt_pct",
        "ft_pct",
        "career_points_log1p",
        "career_rebounds_log1p",
        "career_assists_log1p",
        "conference_awards_count",
        "injury_history_count",
        "previous_schools_count",
        "wooden_flag",
        "naismith_flag",
        "has_current_injury",
        "is_transfer_portal",
        "draft_rank_proxy_inv",
        "height_inches",
        "weight_lb",
        "jersey_numeric",
        "years_in_school",
        "recruiting_stars_x_nil_log",
        "followers_x_recruiting_inv",
        "news_x_trends",
        "ppg_x_recruiting_inv",
        "nil_log_x_trends",
        "followers_per_year_school",
        "nil_value_per_recruiting_star",
        "news_per_year_school",
        "follower_vs_team_avg",
        "follower_vs_global_avg",
        "news_vs_conf_avg",
        "nil_vs_conf_avg",
        "ppg_vs_position_sport_avg",
        "recruit_rank_vs_position_sport_avg",
        "trends_vs_global",
        "stats_json_depth",
        "season_json_depth",
        "heisman_finalist_flag",
        "combined_social_log1p",
        "combined_social_x_star",
        "position_ordinal",
        "conference_ordinal",
    ]
    names.extend(core)
    # one-hot position (17)
    for p in _POSITION_BUCKET:
        names.append(f"pos_{p}")
    # one-hot conference bucket (6)
    for i in range(6):
        names.append(f"conf_bucket_{i}")
    # sport (3)
    names.extend(["sport_cfb", "sport_mcbb", "sport_wcbb"])
    # hash embeddings for team name (8 dims) — stable pseudo-embedding
    for i in range(8):
        names.append(f"team_hash_{i}")
    # padding / trajectory placeholders (reserved for stage 1b time-series)
    while len(names) < N_FEATURE_COLUMNS:
        names.append(f"trajectory_reserve_{len(names)}")
    return names[:N_FEATURE_COLUMNS]


FEATURE_NAMES: list[str] = build_feature_names()


def _team_hash_vec(team: str | None) -> np.ndarray:
    out = np.zeros(8, dtype=np.float64)
    if not team:
        return out
    h = hashlib.sha256(team.encode()).digest()
    for i in range(8):
        out[i] = h[i] / 255.0
    return out


def _inv_rank(x: float) -> float:
    if math.isnan(x) or x <= 0:
        return 0.0
    return 1.0 / x


def engineer_row(
    row: Mapping[str, Any],
    cohort: CohortStats | None = None,
) -> np.ndarray:
    """Single row → shape (250,) float64. NaNs replaced with 0 after ratios computed."""
    sport = str(row.get("sport") or "cfb")
    team = str(row.get("team") or "")
    conf = str(row.get("conference") or "")
    pos = row.get("position") if isinstance(row.get("position"), str) else None
    pos_i = _position_idx(pos)

    age = _coerce_float(row.get("age"))
    elig = _coerce_float(row.get("eligibility_years_remaining"))
    stars = _coerce_float(row.get("recruiting_stars"))
    rk_nat = _coerce_float(row.get("recruiting_rank_national"))
    rk_pos = _coerce_float(row.get("recruiting_rank_position"))
    heis = _coerce_float(row.get("heisman_votes"))
    aa = _coerce_float(row.get("all_american_count"))
    ig = _coerce_float(row.get("instagram_followers"))
    tw = _coerce_float(row.get("twitter_followers"))
    news = _coerce_float(row.get("news_count_30d"))
    tr = _coerce_float(row.get("google_trends_score"))
    dqs = _coerce_float(row.get("data_quality_score"))
    nil_s = _nil_valuation_to_scalar(row.get("nil_valuation"))
    ppg = _coerce_float(row.get("ppg"))
    rpg = _coerce_float(row.get("rpg"))
    apg = _coerce_float(row.get("apg"))
    fg = _coerce_float(row.get("fg_pct"))
    t3 = _coerce_float(row.get("three_pt_pct"))
    ft = _coerce_float(row.get("ft_pct"))
    cpts = _coerce_float(row.get("career_points"))
    crb = _coerce_float(row.get("career_rebounds"))
    cast = _coerce_float(row.get("career_assists"))
    draft_inv = _draft_rank_proxy(row.get("nba_draft_projection"))
    if math.isnan(draft_inv):
        draft_inv = _draft_rank_proxy(row.get("wnba_draft_projection"))
    draft_inv = _inv_rank(draft_inv) if not math.isnan(draft_inv) else 0.0

    yrs = _years_in_school_approx(row.get("class_year"))

    ig_log = math.log1p(max(0.0, ig)) if not math.isnan(ig) else 0.0
    tw_log = math.log1p(max(0.0, tw)) if not math.isnan(tw) else 0.0
    nil_log = math.log1p(max(0.0, nil_s)) if not math.isnan(nil_s) else 0.0

    rk_nat_inv = _inv_rank(rk_nat)
    rk_pos_inv = _inv_rank(rk_pos)

    stars_safe = 0.0 if math.isnan(stars) else stars
    nil_per_star = nil_log / (stars_safe + 0.001) if stars_safe > 0 else nil_log

    y_school = yrs if not math.isnan(yrs) and yrs > 0 else 1.0
    fol_per_yr = (math.expm1(ig_log) if ig_log > 0 else 0.0) / y_school
    news_val = 0.0 if math.isnan(news) else float(news)
    news_per_yr = news_val / y_school

    transfer = 0.0
    tps = row.get("transfer_portal_status")
    if tps and str(tps).strip() and str(tps).upper() != "NONE":
        transfer = 1.0
    prev_ct = _safe_len(row.get("previous_schools"))
    if prev_ct > 0:
        transfer = 1.0

    inj_ct = _safe_len(row.get("injury_history"))
    cur_inj = 1.0 if row.get("current_injury_status") else 0.0

    wooden = 1.0 if row.get("wooden_award_finalist") in (True, 1, "true", "True") else 0.0
    naism = 1.0 if row.get("naismith_finalist") in (True, 1, "true", "True") else 0.0
    heisman_f = 1.0 if (not math.isnan(heis) and heis > 0) else 0.0

    # Cohort ratios
    f_team = f_glob = f_news_c = f_nil_c = f_ppg_sp = f_rk_sp = t_vs_g = 0.0
    if cohort:
        tm = cohort.team_followers_mean.get(team, cohort.global_ig_mean)
        if tm and tm > 0 and not math.isnan(ig):
            f_team = ig / tm
        if cohort.global_ig_mean > 0 and not math.isnan(ig):
            f_glob = ig / cohort.global_ig_mean
        nm = cohort.conf_news_mean.get(conf, 0.0)
        if nm > 0 and not math.isnan(news):
            f_news_c = news / nm
        nm2 = cohort.conf_nil_mean.get(conf, 0.0)
        if nm2 > 0 and not math.isnan(nil_s):
            f_nil_c = nil_s / nm2
        pm = cohort.spos_ppg_mean.get((sport, pos_i), 0.0)
        if pm > 0 and not math.isnan(ppg):
            f_ppg_sp = ppg / pm
        rm = cohort.spos_recruit_rank_mean.get((sport, pos_i), 0.0)
        if rm > 0 and not math.isnan(rk_nat):
            f_rk_sp = rk_nat / rm
        if cohort.global_trends_mean and not math.isnan(tr):
            t_vs_g = tr / (cohort.global_trends_mean + 1e-6)

    cs = row.get("career_stats")
    ss = row.get("current_season_stats")
    d1 = float(len(cs)) if isinstance(cs, dict) else 0.0
    d2 = float(len(ss)) if isinstance(ss, dict) else 0.0

    jnum = _coerce_float(row.get("jersey_number"))

    vec: list[float] = [
        0.0 if math.isnan(age) else age,
        0.0 if math.isnan(elig) else elig,
        0.0 if math.isnan(stars) else stars,
        rk_nat_inv,
        rk_pos_inv,
        math.log1p(max(0.0, heis)) if not math.isnan(heis) else 0.0,
        math.log1p(max(0.0, aa)) if not math.isnan(aa) else 0.0,
        ig_log,
        tw_log,
        math.log1p(max(0.0, news)) if not math.isnan(news) else 0.0,
        0.0 if math.isnan(tr) else tr,
        0.0 if math.isnan(dqs) else dqs,
        nil_log,
        _safe_len(row.get("nil_deals")),
        0.0 if math.isnan(ppg) else ppg,
        0.0 if math.isnan(rpg) else rpg,
        0.0 if math.isnan(apg) else apg,
        0.0 if math.isnan(fg) else fg,
        0.0 if math.isnan(t3) else t3,
        0.0 if math.isnan(ft) else ft,
        math.log1p(max(0.0, cpts)) if not math.isnan(cpts) else 0.0,
        math.log1p(max(0.0, crb)) if not math.isnan(crb) else 0.0,
        math.log1p(max(0.0, cast)) if not math.isnan(cast) else 0.0,
        _safe_len(row.get("conference_awards")),
        inj_ct,
        prev_ct,
        wooden,
        naism,
        cur_inj,
        transfer,
        draft_inv,
        0.0 if math.isnan(_parse_height_inches(row.get("height"))) else _parse_height_inches(row.get("height")),
        0.0 if math.isnan(_parse_weight_lb(row.get("weight"))) else _parse_weight_lb(row.get("weight")),
        0.0 if math.isnan(jnum) else jnum,
        0.0 if math.isnan(yrs) else yrs,
        stars_safe * nil_log,
        ig_log * rk_nat_inv,
        (0.0 if math.isnan(news) else news) * (0.0 if math.isnan(tr) else tr),
        (0.0 if math.isnan(ppg) else ppg) * rk_nat_inv,
        nil_log * (0.0 if math.isnan(tr) else tr),
        fol_per_yr,
        nil_per_star,
        news_per_yr,
        f_team,
        f_glob,
        f_news_c,
        f_nil_c,
        f_ppg_sp,
        f_rk_sp,
        t_vs_g,
        d1,
        d2,
        heisman_f,
        math.log1p(math.expm1(ig_log) + math.expm1(tw_log)),
        ig_log * stars_safe,
        float(pos_i) / max(1, len(_POSITION_BUCKET) - 1),
        float(_conference_idx(conf)) / 6.0,
    ]

    poh = np.zeros(len(_POSITION_BUCKET), dtype=np.float64)
    poh[pos_i] = 1.0
    vec.extend(poh.tolist())

    coh = np.zeros(6, dtype=np.float64)
    ci = _conference_idx(conf)
    if ci < 6:
        coh[ci] = 1.0
    vec.extend(coh.tolist())

    vec.extend(_sport_vec(sport).tolist())
    vec.extend(_team_hash_vec(team).tolist())

    while len(vec) < N_FEATURE_COLUMNS:
        vec.append(0.0)

    arr = np.asarray(vec[:N_FEATURE_COLUMNS], dtype=np.float64)
    arr = np.nan_to_num(arr, nan=0.0, posinf=0.0, neginf=0.0)
    return arr


def engineer_dataframe(
    df: pd.DataFrame,
    cohort: CohortStats | None = None,
) -> np.ndarray:
    if cohort is None:
        cohort = build_cohort_stats(df.to_dict("records"))
    rows = df.to_dict("records")
    return np.stack([engineer_row(r, cohort) for r in rows], axis=0)


def validate_row_keys(row: Mapping[str, Any]) -> list[str]:
    """Return unknown keys (warning helpers during ETL)."""
    allowed = set(GRAVITY_ML_RAW_FIELD_NAMES)
    return [k for k in row if k not in allowed and k not in ("_id",)]


__all__ = [
    "CohortStats",
    "FEATURE_NAMES",
    "N_FEATURE_COLUMNS",
    "build_cohort_stats",
    "build_feature_names",
    "engineer_dataframe",
    "engineer_row",
    "validate_row_keys",
]
