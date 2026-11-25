"""ESPN play-by-play for the GameTracker chart (IU games only, post-game)."""
from datetime import datetime
from zoneinfo import ZoneInfo

from . import config, ingest


def _et_date(iso: str) -> str:
    """ESPN timestamps are UTC; a 7 PM ET tip is already 'tomorrow' in UTC."""
    if not iso:
        return ""
    dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    return dt.astimezone(ZoneInfo("America/New_York")).date().isoformat()


def clock_seconds(period: int, clock: str, periods_reg: int = 2, reg_len: int = 1200, ot_len: int = 300) -> float:
    """Elapsed game seconds at a play (college: two 20-minute halves, 5-minute OTs)."""
    mm, ss = (clock.split(":") + ["0"])[:2] if ":" in clock else ("0", clock)
    left = int(mm) * 60 + float(ss)
    if period <= periods_reg:
        return (period - 1) * reg_len + (reg_len - left)
    return periods_reg * reg_len + (period - periods_reg - 1) * ot_len + (ot_len - left)


def completed_events(year: int, team_id: int = config.ESPN_CENTER_TEAM_ID) -> list[dict]:
    d = ingest.espn_json(config.ESPN_SCHEDULE.format(team_id=team_id, year=year),
                         f"espn_{year}_schedule_{team_id}.json")
    out = []
    for e in d.get("events", []):
        c = e["competitions"][0]
        if c["status"]["type"].get("completed"):
            out.append({"id": e["id"], "date": _et_date(e["date"]), "name": e["name"]})
    return out


def scoring_progression(event_id: str, refresh: bool = False) -> dict:
    """Scoring plays with clock times, verified against the final score.
    Completed games never change, so the cache is reused (refresh=False)."""
    d = ingest.espn_json(config.ESPN_SUMMARY.format(event_id=event_id),
                         f"espn_summary_{event_id}.json", refresh)
    comp = d["header"]["competitions"][0]
    teams = {c["homeAway"]: {"name": c["team"]["displayName"], "abbr": c["team"]["abbreviation"],
                              "id": c["team"]["id"], "score": int(c["score"])}
             for c in comp["competitors"]}
    pts = [{"period": p["period"]["number"], "clock": p["clock"]["displayValue"],
            "t": clock_seconds(p["period"]["number"], p["clock"]["displayValue"]),
            "home": int(p["homeScore"]), "away": int(p["awayScore"]),
            "team_id": p.get("team", {}).get("id"), "text": p.get("text", "")}
           for p in d.get("plays", []) if p.get("scoringPlay")]
    # ESPN occasionally lists plays sharing one clock second out of order (e.g. two
    # free-throw trips at 16:38).  Cumulative scores must ascend, so order within a
    # second by total score; the monotonic check below still catches real feed errors.
    pts.sort(key=lambda x: (x["t"], x["home"] + x["away"]))
    final_ok = bool(pts) and pts[-1]["home"] == teams["home"]["score"] and pts[-1]["away"] == teams["away"]["score"]
    monotonic = all(b["t"] >= a["t"] and b["home"] >= a["home"] and b["away"] >= a["away"]
                    for a, b in zip(pts, pts[1:]))
    return {"event_id": event_id, "date": _et_date(comp.get("date", "")), "teams": teams,
            "neutral": bool(comp.get("neutralSite")), "periods": max((p["period"] for p in pts), default=0),
            "scoring_plays": pts, "verified": {"final_score_matches": final_ok, "monotonic": monotonic}}
