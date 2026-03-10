from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd
import fastf1
from fastf1 import get_event, get_event_schedule, get_events_remaining, get_session, plotting
from fastf1 import ergast as ff1_ergast
from fastapi import FastAPI, HTTPException, Query


# usa la stessa cartella di cache dello script di ingest
fastf1.Cache.enable_cache("fastf1_cache")


app = FastAPI(title="FastF1 API", version="1.0.0")


# ===== Helpers comuni ======================================================


def df_to_json_safe(df: pd.DataFrame) -> List[Dict[str, Any]]:
    """Converte un DataFrame in una lista di dict JSON-safe (NaN/inf → None, date → stringhe)."""
    if df is None:
        return []

    df = df.copy()
    for col in df.columns:
        series = df[col]
        if pd.api.types.is_datetime64_any_dtype(series) or pd.api.types.is_timedelta64_dtype(series):
            df[col] = series.astype(str)
    # NaN/inf non sono validi in JSON: sostituiamo con None
    df = df.replace([np.nan, np.inf, -np.inf], [None, None, None])
    return df.to_dict(orient="records")


def handle_fastf1_error(exc: Exception, status_code: int = 400) -> HTTPException:
    """Mappa un'eccezione FastF1 in un errore HTTP leggibile."""
    return HTTPException(status_code=status_code, detail=str(exc))


def load_session(
    year: int,
    round_number: int,
    session_code: str,
    telemetry: bool = False,
):
    """Carica una sessione FastF1 da cache/API."""
    try:
        session = get_session(year, round_number, session_code)
        session.load(telemetry=telemetry)
        return session
    except Exception as exc:  # noqa: PERF203
        raise handle_fastf1_error(exc)


# ===== Namespace /seasons ==================================================


@app.get("/seasons", response_model=List[int])
def list_seasons() -> List[int]:
    """Restituisce le stagioni per cui è possibile richiedere dati."""
    # per ora lista statica, modificabile in base alle tue esigenze
    return [2026]


@app.get("/seasons/{year}/events")
def get_events(year: int):
    """Calendario eventi (gara) per una stagione."""
    try:
        schedule = get_event_schedule(year)
    except Exception as exc:  # noqa: PERF203
        raise handle_fastf1_error(exc)

    return {
        "meta": {"year": year},
        "data": df_to_json_safe(schedule),
    }


@app.get("/seasons/{year}/events/remaining")
def get_events_remaining_for_year(year: int):
    """Eventi rimanenti nella stagione."""
    try:
        remaining = get_events_remaining()
        remaining = remaining[remaining["EventDate"].dt.year == year]
    except Exception as exc:  # noqa: PERF203
        raise handle_fastf1_error(exc)

    return {
        "meta": {"year": year},
        "data": df_to_json_safe(remaining),
    }


@app.get("/seasons/{year}/events/{round_number}")
def get_single_event(year: int, round_number: int):
    """Dettagli di un singolo evento (gara) per stagione/round."""
    try:
        event = get_event(year, round_number)
    except Exception as exc:  # noqa: PERF203
        raise handle_fastf1_error(exc)

    return {
        "meta": {"year": year, "round_number": round_number},
        "data": event.to_dict(),
    }


@app.get("/seasons/{year}/events/by-name")
def get_event_by_name(year: int, name: str = Query(..., description="Nome evento, nazione o circuito")):
    """Dettagli evento caricandolo per nome (o parte di nome)."""
    try:
        event = get_event(year, name)
    except Exception as exc:  # noqa: PERF203
        raise handle_fastf1_error(exc)

    return {
        "meta": {"year": year, "query": name},
        "data": event.to_dict(),
    }


# lista delle sessioni (FP1, FP2, FP3, Q, S, R, ...) per un weekend
@app.get("/seasons/{year}/events/{round_number}/sessions")
def list_event_sessions(year: int, round_number: int):
    """Elenco delle sessioni previste per un weekend di gara."""
    try:
        event = get_event(year, round_number)
    except Exception as exc:  # noqa: PERF203
        raise handle_fastf1_error(exc)

    code_map = {
        "Practice 1": "FP1",
        "Practice 2": "FP2",
        "Practice 3": "FP3",
        "Qualifying": "Q",
        "Race": "R",
        "Sprint Qualifying": "SQ",
        "Sprint": "S",
    }

    sessions: List[Dict[str, Any]] = []
    for idx in range(1, 6):
        name_key = f"Session{idx}"
        date_key_utc = f"Session{idx}DateUtc"
        date_key = f"Session{idx}Date"

        name = event.get(name_key)
        if not isinstance(name, str) or not name:
            continue

        date_utc = event.get(date_key_utc)
        if pd.isna(date_utc):
            date_utc = event.get(date_key)

        code = code_map.get(name)

        sessions.append(
            {
                "index": idx,
                "name": name,
                "code": code,
                "date_utc": str(date_utc) if not pd.isna(date_utc) else None,
            }
        )

    return {
        "meta": {"year": year, "round_number": round_number},
        "data": sessions,
    }


# ===== Namespace /sessions ================================================


@app.get("/sessions/{year}/{round_number}/{session_code}")
def get_session_meta(year: int, round_number: int, session_code: str):
    """Metadati di base per una sessione."""
    session = load_session(year, round_number, session_code, telemetry=False)

    event = session.event
    return {
        "meta": {
            "year": year,
            "round_number": round_number,
            "session_code": session_code,
        },
        "data": {
            "name": session.name,
            "date": str(session.date),
            "event": event.to_dict(),
        },
    }


@app.get("/sessions/{year}/{round_number}/{session_code}/drivers")
def get_session_drivers(year: int, round_number: int, session_code: str):
    """Elenco driver della sessione con informazioni derivate da SessionResults/DriverResult."""
    session = load_session(year, round_number, session_code, telemetry=False)
    results = session.results
    if results is None or results.empty:
        # se non ci sono risultati, usiamo solo session.drivers come fallback
        drivers = getattr(session, "drivers", []) or []
        data = [{"DriverNumber": drv} for drv in drivers]
    else:
        data = []
        for _, row in results.iterrows():
            # row è un DriverResult (Series)
            driver_number = row.get("DriverNumber")
            abbreviation = row.get("Abbreviation")
            full_name = row.get("FullName")
            team_name = row.get("TeamName")
            team_color = row.get("TeamColor")
            headshot_url = row.get("HeadshotUrl")
            country_code = row.get("CountryCode")
            # proprietà dnf dal DriverResult
            dnf = bool(getattr(row, "dnf", False))

            data.append(
                {
                    "DriverNumber": driver_number,
                    "Abbreviation": abbreviation,
                    "FullName": full_name,
                    "TeamName": team_name,
                    "TeamColor": team_color,
                    "HeadshotUrl": headshot_url,
                    "CountryCode": country_code,
                    "dnf": dnf,
                }
            )

    return {
        "meta": {
            "year": year,
            "round_number": round_number,
            "session_code": session_code,
        },
        "data": data,
    }


@app.get("/sessions/{year}/{round_number}/{session_code}/info")
def get_session_info(year: int, round_number: int, session_code: str):
    """Informazioni estese sulla sessione (session_info, total_laps, f1_api_support, date)."""
    session = load_session(year, round_number, session_code, telemetry=False)
    session_info = getattr(session, "session_info", {}) or {}

    return {
        "meta": {
            "year": year,
            "round_number": round_number,
            "session_code": session_code,
        },
        "data": {
            "session_info": session_info,
            "total_laps": getattr(session, "total_laps", None),
            "f1_api_support": getattr(session, "f1_api_support", None),
            "date": str(getattr(session, "date", None)),
        },
    }


@app.get("/sessions/{year}/{round_number}/{session_code}/track-status")
def get_session_track_status(year: int, round_number: int, session_code: str):
    """Track status (bandiere, SC/VSC, ecc.) per la sessione."""
    session = load_session(year, round_number, session_code, telemetry=False)
    status_df = getattr(session, "track_status", None)
    if status_df is None or status_df.empty:
        raise HTTPException(status_code=404, detail="Nessun track status disponibile")

    return {
        "meta": {
            "year": year,
            "round_number": round_number,
            "session_code": session_code,
        },
        "data": df_to_json_safe(status_df.reset_index(drop=True)),
    }


@app.get("/sessions/{year}/{round_number}/{session_code}/session-status")
def get_session_status(year: int, round_number: int, session_code: str):
    """Session status (Started/Finished/Aborted ecc.) per la sessione."""
    session = load_session(year, round_number, session_code, telemetry=False)
    status_df = getattr(session, "session_status", None)
    if status_df is None or status_df.empty:
        raise HTTPException(status_code=404, detail="Nessun session status disponibile")

    return {
        "meta": {
            "year": year,
            "round_number": round_number,
            "session_code": session_code,
        },
        "data": df_to_json_safe(status_df.reset_index(drop=True)),
    }


@app.get("/sessions/{year}/{round_number}/{session_code}/race-control-messages")
def get_race_control_messages(year: int, round_number: int, session_code: str):
    """Race Control messages (messaggi direzione gara) per la sessione."""
    session = load_session(year, round_number, session_code, telemetry=False)
    messages_df = getattr(session, "race_control_messages", None)
    if messages_df is None or messages_df.empty:
        raise HTTPException(status_code=404, detail="Nessun messaggio race control disponibile")

    return {
        "meta": {
            "year": year,
            "round_number": round_number,
            "session_code": session_code,
        },
        "data": df_to_json_safe(messages_df.reset_index(drop=True)),
    }


@app.get("/sessions/{year}/{round_number}/{session_code}/results")
def get_session_results(year: int, round_number: int, session_code: str, driver: Optional[str] = None):
    """Risultati di una sessione; opzionalmente filtrati per driver."""
    session = load_session(year, round_number, session_code, telemetry=False)
    results = session.results
    if results is None or results.empty:
        raise HTTPException(status_code=404, detail="Nessun risultato disponibile")

    if driver:
        results = results[results["Abbreviation"] == driver]
        if results.empty:
            raise HTTPException(status_code=404, detail="Nessun risultato per il driver richiesto")

    return {
        "meta": {
            "year": year,
            "round_number": round_number,
            "session_code": session_code,
            "driver": driver,
        },
        "data": df_to_json_safe(results),
    }


@app.get("/sessions/{year}/{round_number}/{session_code}/laps")
def get_session_laps(
    year: int,
    round_number: int,
    session_code: str,
    driver: Optional[str] = None,
    team: Optional[str] = None,
    compound: Optional[str] = None,
    lap_min: Optional[int] = None,
    lap_max: Optional[int] = None,
    fastest_only: bool = False,
    quicklaps_only: bool = False,
    threshold: Optional[float] = Query(
        None,
        description=(
            "Coefficiente per pick_quicklaps (es. 1.07 = 107% del miglior tempo). "
            "Se non specificato usa la QUICKLAP_THRESHOLD di FastF1."
        ),
    ),
    accurate_only: bool = False,
    exclude_box: bool = False,
    not_deleted: bool = False,
    track_status: Optional[str] = Query(
        None,
        description="Valore di TrackStatus da passare a pick_track_status (es. '1', '2', '4').",
    ),
    track_status_how: str = Query(
        "equals",
        description=(
            "Modalità per pick_track_status: equals|contains|excludes|any|none "
            "(defaults: equals)."
        ),
    ),
    box_laps: Optional[str] = Query(
        None,
        description="Filtra giri box: 'in', 'out' o 'both' (usa pick_box_laps).",
    ),
):
    """Tutti i giri di una sessione, con vari filtri."""
    session = load_session(year, round_number, session_code, telemetry=False)
    laps = session.laps
    if laps is None or laps.empty:
        raise HTTPException(status_code=404, detail="Nessun giro disponibile")

    # Filtri basati su metodi nativi Laps, in catena
    if driver:
        laps = laps.pick_drivers(driver)
    if team:
        laps = laps.pick_teams(team)
    if compound:
        laps = laps.pick_compounds(compound)
    if track_status:
        try:
            laps = laps.pick_track_status(track_status, how=track_status_how)
        except Exception as exc:  # noqa: PERF203
            raise handle_fastf1_error(exc)
    if box_laps:
        if box_laps not in {"in", "out", "both"}:
            raise HTTPException(
                status_code=400,
                detail="Parametro box_laps deve essere uno tra: 'in', 'out', 'both'",
            )
        laps = laps.pick_box_laps(which=box_laps)
    if exclude_box:
        laps = laps.pick_wo_box()
    if not_deleted:
        laps = laps.pick_not_deleted()
    if accurate_only:
        laps = laps.pick_accurate()
    if quicklaps_only:
        # se threshold non specificato, FastF1 userà QUICKLAP_THRESHOLD di default
        kwargs: Dict[str, Any] = {}
        if threshold is not None:
            kwargs["threshold"] = threshold
        laps = laps.pick_quicklaps(**kwargs)

    # Filtro per range di giri usando pick_laps
    if lap_min is not None or lap_max is not None:
        # determina bounds se uno dei due è mancante
        all_numbers = laps["LapNumber"].dropna().astype(int)
        if all_numbers.empty:
            raise HTTPException(status_code=404, detail="Nessun giro disponibile nel range richiesto")
        min_existing = int(all_numbers.min())
        max_existing = int(all_numbers.max())
        if lap_min is None:
            lap_min = min_existing
        if lap_max is None:
            lap_max = max_existing
        if lap_min > lap_max:
            raise HTTPException(status_code=400, detail="lap_min non può essere maggiore di lap_max")
        laps = laps.pick_laps(range(lap_min, lap_max + 1))

    if fastest_only:
        # pick_fastest può restituire un singolo Lap (Series)
        laps = laps.pick_fastest()

    if isinstance(laps, pd.Series):
        data = [laps.to_dict()]
    else:
        data = df_to_json_safe(laps.reset_index(drop=True))

    return {
        "meta": {
            "year": year,
            "round_number": round_number,
            "session_code": session_code,
            "driver": driver,
            "team": team,
            "compound": compound,
            "lap_min": lap_min,
            "lap_max": lap_max,
            "fastest_only": fastest_only,
            "quicklaps_only": quicklaps_only,
            "threshold": threshold,
            "accurate_only": accurate_only,
            "exclude_box": exclude_box,
            "not_deleted": not_deleted,
            "track_status": track_status,
            "track_status_how": track_status_how,
            "box_laps": box_laps,
        },
        "data": data,
    }


@app.get("/sessions/{year}/{round_number}/{session_code}/laps/{lap_number}")
def get_single_lap(
    year: int,
    round_number: int,
    session_code: str,
    lap_number: int,
    driver: Optional[str] = None,
):
    """Un singolo giro per numero (e opzionale driver)."""
    session = load_session(year, round_number, session_code, telemetry=False)
    laps = session.laps
    if laps is None or laps.empty:
        raise HTTPException(status_code=404, detail="Nessun giro disponibile")

    if driver:
        laps = laps.pick_drivers(driver)

    lap = laps[laps["LapNumber"] == lap_number]
    if lap.empty:
        raise HTTPException(status_code=404, detail="Giro non trovato")

    return {
        "meta": {
            "year": year,
            "round_number": round_number,
            "session_code": session_code,
            "driver": driver,
            "lap_number": lap_number,
        },
        "data": df_to_json_safe(lap.reset_index(drop=True)),
    }


@app.get("/sessions/{year}/{round_number}/{session_code}/tyres")
def get_session_tyres(
    year: int,
    round_number: int,
    session_code: str,
    driver: Optional[str] = Query(
        None,
        description="Abbreviazione pilota (es. VER) per limitare gli stint a un solo driver.",
    ),
):
    """Stint e compound usati, raggruppati per driver e stint."""
    session = load_session(year, round_number, session_code, telemetry=False)
    laps = session.laps
    if laps is None or laps.empty:
        raise HTTPException(status_code=404, detail="Nessun giro disponibile")

    if "Stint" not in laps.columns or "Compound" not in laps.columns:
        raise HTTPException(
            status_code=400,
            detail="Dati di stint/compound non disponibili per questa sessione",
        )

    if driver:
        laps = laps.pick_drivers(driver)
        if laps.empty:
            raise HTTPException(status_code=404, detail="Nessun giro per il driver richiesto")

    # Assicuriamoci che TyreLife esista: in molte sessioni è già presente
    tyre_life_col = "TyreLife" if "TyreLife" in laps.columns else None

    group_cols = ["Driver", "Stint"]
    agg_dict = {
        "Compound": "first",
        "LapNumber": ["min", "max", "count"],
    }
    if tyre_life_col:
        agg_dict[tyre_life_col] = ["min", "max"]

    grouped = laps.groupby(group_cols).agg(agg_dict)
    grouped.columns = ["_".join(col).strip("_") for col in grouped.columns.values]
    grouped = grouped.reset_index()

    # Rinomina colonne in qualcosa di piu leggibile per il frontend
    rename_map = {
        "LapNumber_min": "lap_start",
        "LapNumber_max": "lap_end",
        "LapNumber_count": "lap_count",
    }
    if tyre_life_col:
        rename_map[f"{tyre_life_col}_min"] = "tyre_life_min"
        rename_map[f"{tyre_life_col}_max"] = "tyre_life_max"
    grouped = grouped.rename(columns=rename_map)

    return {
        "meta": {
            "year": year,
            "round_number": round_number,
            "session_code": session_code,
            "driver": driver,
        },
        "data": df_to_json_safe(grouped),
    }


@app.get("/sessions/{year}/{round_number}/{session_code}/weather")
def get_session_weather(
    year: int,
    round_number: int,
    session_code: str,
    driver: Optional[str] = Query(
        None,
        description=(
            "Abbreviazione pilota (es. VER). Se fornito, usa laps.get_weather_data() "
            "per restituire un punto meteo per ogni giro del pilota."
        ),
    ),
):
    """Dati meteo della sessione.

    - Senza driver: usa session.weather_data (dati globali, 1-2 punti al minuto).
    - Con driver: usa session.laps.pick_drivers(driver).get_weather_data().
    """
    session = load_session(year, round_number, session_code, telemetry=False)

    if driver:
        laps = session.laps.pick_drivers(driver)
        if laps.empty:
            raise HTTPException(status_code=404, detail="Nessun giro per il driver richiesto")
        try:
            weather_df = laps.get_weather_data()
        except Exception as exc:  # noqa: PERF203
            raise handle_fastf1_error(exc)
    else:
        weather_df = getattr(session, "weather_data", None)
        if weather_df is None or weather_df.empty:
            raise HTTPException(status_code=404, detail="Nessun dato meteo disponibile")

    return {
        "meta": {
            "year": year,
            "round_number": round_number,
            "session_code": session_code,
            "driver": driver,
        },
        "data": df_to_json_safe(weather_df.reset_index(drop=True)),
    }


@app.get("/sessions/{year}/{round_number}/{session_code}/quicklaps")
def get_session_quicklaps(
    year: int,
    round_number: int,
    session_code: str,
    driver: Optional[str] = Query(
        None,
        description="Abbreviazione pilota (es. VER). Se fornito, filtra prima i giri del pilota.",
    ),
    threshold: Optional[float] = Query(
        None,
        description=(
            "Coefficiente per pick_quicklaps (es. 1.07 = 107% del miglior tempo). "
            "Se non specificato usa la QUICKLAP_THRESHOLD di FastF1."
        ),
    ),
):
    """Giri 'quick' (veloci) secondo la definizione FastF1 (Laps.pick_quicklaps)."""
    session = load_session(year, round_number, session_code, telemetry=False)
    laps = session.laps
    if laps is None or laps.empty:
        raise HTTPException(status_code=404, detail="Nessun giro disponibile")

    if driver:
        laps = laps.pick_drivers(driver)
        if laps.empty:
            raise HTTPException(status_code=404, detail="Nessun giro per il driver richiesto")

    kwargs: Dict[str, Any] = {}
    if threshold is not None:
        kwargs["threshold"] = threshold

    try:
        quick_laps = laps.pick_quicklaps(**kwargs)
    except Exception as exc:  # noqa: PERF203
        raise handle_fastf1_error(exc)

    if quick_laps is None or quick_laps.empty:
        raise HTTPException(status_code=404, detail="Nessun quick lap disponibile")

    return {
        "meta": {
            "year": year,
            "round_number": round_number,
            "session_code": session_code,
            "driver": driver,
            "threshold": threshold,
        },
        "data": df_to_json_safe(quick_laps.reset_index(drop=True)),
    }


@app.get("/sessions/{year}/{round_number}/{session_code}/qualifying-splits")
def get_session_qualifying_splits(
    year: int,
    round_number: int,
    session_code: str,
):
    """Split delle qualifiche in Q1/Q2/Q3 usando Laps.split_qualifying_sessions()."""
    session = load_session(year, round_number, session_code, telemetry=False)
    laps = session.laps
    if laps is None or laps.empty:
        raise HTTPException(status_code=404, detail="Nessun giro disponibile")

    try:
        q1, q2, q3 = laps.split_qualifying_sessions()
    except Exception as exc:  # noqa: PERF203
        raise handle_fastf1_error(exc)

    def _laps_to_data(part):
        if part is None or part.empty:
            return None
        return df_to_json_safe(part.reset_index(drop=True))

    return {
        "meta": {
            "year": year,
            "round_number": round_number,
            "session_code": session_code,
        },
        "data": {
            "Q1": _laps_to_data(q1),
            "Q2": _laps_to_data(q2),
            "Q3": _laps_to_data(q3),
        },
    }


@app.get("/sessions/{year}/{round_number}/{session_code}/telemetry")
def get_session_telemetry(
    year: int,
    round_number: int,
    session_code: str,
    driver: str = Query(..., description="Abbreviazione pilota, es. VER"),
    lap_number: Optional[int] = None,
    fastest: bool = False,
    type: str = Query(
        "car",
        description="Tipo di telemetria: 'car', 'pos' oppure 'merged' (get_telemetry).",
    ),
    add_distance: bool = Query(
        False,
        description="Se true, aggiunge la colonna Distance (add_distance).",
    ),
    add_driver_ahead: bool = Query(
        False,
        description="Se true, aggiunge DriverAhead e DistanceToDriverAhead (add_driver_ahead).",
    ),
    add_track_status: bool = Query(
        False,
        description="Se true, aggiunge TrackStatus (add_track_status).",
    ),
    columns: Optional[str] = Query(
        None,
        description="Lista di colonne separate da virgola da includere",
    ),
):
    """Telemetria della sessione per un driver (e opzionale giro), con scelta del tipo di dato."""
    session = load_session(year, round_number, session_code, telemetry=True)

    laps = session.laps.pick_drivers(driver)
    if laps.empty:
        raise HTTPException(status_code=404, detail="Nessun giro per il driver richiesto")

    if fastest:
        lap = laps.pick_fastest()
    elif lap_number is not None:
        lap = laps[laps["LapNumber"] == lap_number]
        if lap.empty:
            raise HTTPException(status_code=404, detail="Giro non trovato per il driver indicato")
        lap = lap.iloc[0]
    else:
        lap = laps.iloc[0]

    # Selezione tipo di telemetria
    type_lower = type.lower()
    if type_lower == "car":
        telemetry_df = lap.get_car_data()
    elif type_lower == "pos":
        telemetry_df = lap.get_pos_data()
    elif type_lower == "merged":
        telemetry_df = lap.get_telemetry()
    else:
        raise HTTPException(
            status_code=400,
            detail="Parametro 'type' deve essere uno tra: 'car', 'pos', 'merged'",
        )

    # Canali derivati
    if add_distance:
        telemetry_df = telemetry_df.add_distance()
    if add_driver_ahead:
        telemetry_df = telemetry_df.add_driver_ahead()
    if add_track_status:
        telemetry_df = telemetry_df.add_track_status()

    if columns:
        cols = [c.strip() for c in columns.split(",") if c.strip()]
        existing = [c for c in cols if c in telemetry_df.columns]
        telemetry_df = telemetry_df[existing]

    return {
        "meta": {
            "year": year,
            "round_number": round_number,
            "session_code": session_code,
            "driver": driver,
            "lap_number": lap_number,
            "fastest": fastest,
            "type": type_lower,
            "add_distance": add_distance,
            "add_driver_ahead": add_driver_ahead,
            "add_track_status": add_track_status,
            "columns": columns,
        },
        "data": df_to_json_safe(telemetry_df.reset_index(drop=True)),
    }


@app.get("/sessions/{year}/{round_number}/{session_code}/circuit")
def get_session_circuit(year: int, round_number: int, session_code: str):
    """Informazioni estese sul circuito associate alla sessione (CircuitInfo)."""
    session = load_session(year, round_number, session_code, telemetry=True)
    event = session.event
    circuit_info = session.get_circuit_info()

    corners = None
    marshal_lights = None
    marshal_sectors = None
    rotation = None

    if circuit_info is not None:
        corners = df_to_json_safe(circuit_info.corners) if circuit_info.corners is not None else None
        marshal_lights = (
            df_to_json_safe(circuit_info.marshal_lights) if circuit_info.marshal_lights is not None else None
        )
        marshal_sectors = (
            df_to_json_safe(circuit_info.marshal_sectors) if circuit_info.marshal_sectors is not None else None
        )
        rotation = circuit_info.rotation

    return {
        "meta": {
            "year": year,
            "round_number": round_number,
            "session_code": session_code,
        },
        "data": {
            "event": event.to_dict(),
            "circuit": {
                "corners": corners,
                "marshal_lights": marshal_lights,
                "marshal_sectors": marshal_sectors,
                "rotation": rotation,
            },
        },
    }


@app.get("/meta/compounds")
def list_compounds():
    """Elenco delle mescole disponibili."""
    compounds = plotting.list_compounds()
    return {"meta": {}, "data": compounds}


@app.get("/meta/compounds/{compound}/color")
def get_compound_color(compound: str):
    """Colore associato a una mescola."""
    try:
        color = plotting.get_compound_color(compound)
    except Exception as exc:  # noqa: PERF203
        raise handle_fastf1_error(exc)
    return {"meta": {"compound": compound}, "data": {"color": color}}


@app.get("/meta/compounds/mapping")
def get_compound_mapping():
    """Mapping completo delle mescole."""
    mapping = plotting.get_compound_mapping()
    return {"meta": {}, "data": mapping}


@app.get("/meta/drivers/color-mapping")
def get_driver_color_mapping():
    """Mapping globale driver → colore."""
    mapping = plotting.get_driver_color_mapping()
    return {"meta": {}, "data": mapping}


@app.get("/meta/sessions/{year}/{round_number}/{session_code}/drivers")
def get_session_drivers_meta(year: int, round_number: int, session_code: str):
    """Elenco driver (nomi e abbreviazioni) per una sessione."""
    session = load_session(year, round_number, session_code, telemetry=False)
    names = plotting.list_driver_names(session=session)
    abbreviations = plotting.list_driver_abbreviations(session=session)
    data = [
        {"name": name, "abbreviation": abbr}
        for name, abbr in zip(names, abbreviations)
    ]
    return {
        "meta": {
            "year": year,
            "round_number": round_number,
            "session_code": session_code,
        },
        "data": data,
    }


@app.get("/meta/drivers/{identifier}/name")
def get_driver_name(identifier: str):
    """Restituisce il nome completo di un driver dato un identificatore."""
    try:
        name = plotting.get_driver_name(identifier)
    except Exception as exc:  # noqa: PERF203
        raise handle_fastf1_error(exc)
    return {"meta": {"identifier": identifier}, "data": {"name": name}}


@app.get("/meta/drivers/{identifier}/abbreviation")
def get_driver_abbreviation(identifier: str):
    """Restituisce l'abbreviazione standard di un driver."""
    try:
        abbr = plotting.get_driver_abbreviation(identifier)
    except Exception as exc:  # noqa: PERF203
        raise handle_fastf1_error(exc)
    return {"meta": {"identifier": identifier}, "data": {"abbreviation": abbr}}


@app.get("/meta/drivers/{identifier}/color")
def get_driver_color(identifier: str):
    """Colore associato a un driver."""
    try:
        color = plotting.get_driver_color(identifier)
    except Exception as exc:  # noqa: PERF203
        raise handle_fastf1_error(exc)
    return {"meta": {"identifier": identifier}, "data": {"color": color}}


@app.get("/meta/drivers/{identifier}/style")
def get_driver_style(
    identifier: str,
    year: Optional[int] = None,
    round_number: Optional[int] = None,
    session_code: Optional[str] = None,
):
    """Stile di plotting per un driver (colore, linestyle, ecc.)."""
    session = None
    if year is not None and round_number is not None and session_code is not None:
        session = load_session(year, round_number, session_code, telemetry=False)
    try:
        style = plotting.get_driver_style(identifier=identifier, session=session)
    except Exception as exc:  # noqa: PERF203
        raise handle_fastf1_error(exc)
    return {
        "meta": {
            "identifier": identifier,
            "year": year,
            "round_number": round_number,
            "session_code": session_code,
        },
        "data": style,
    }


@app.get("/meta/teams")
def list_teams(
    year: Optional[int] = None,
    round_number: Optional[int] = None,
    session_code: Optional[str] = None,
):
    """Elenco team, opzionalmente per una specifica sessione."""
    session = None
    if year is not None and round_number is not None and session_code is not None:
        session = load_session(year, round_number, session_code, telemetry=False)
    teams = plotting.list_team_names(session=session)
    return {
        "meta": {
            "year": year,
            "round_number": round_number,
            "session_code": session_code,
        },
        "data": teams,
    }


@app.get("/meta/teams/{team_identifier}/name")
def get_team_name(team_identifier: str):
    """Nome normalizzato di un team."""
    try:
        name = plotting.get_team_name(team_identifier)
    except Exception as exc:  # noqa: PERF203
        raise handle_fastf1_error(exc)
    return {"meta": {"identifier": team_identifier}, "data": {"name": name}}


@app.get("/meta/teams/{team_identifier}/color")
def get_team_color(team_identifier: str):
    """Colore associato a un team."""
    try:
        color = plotting.get_team_color(team_identifier)
    except Exception as exc:  # noqa: PERF203
        raise handle_fastf1_error(exc)
    return {"meta": {"identifier": team_identifier}, "data": {"color": color}}


@app.get("/meta/drivers/{identifier}/team-name")
def get_team_name_by_driver(identifier: str):
    """Nome del team per un dato driver."""
    try:
        name = plotting.get_team_name_by_driver(identifier)
    except Exception as exc:  # noqa: PERF203
        raise handle_fastf1_error(exc)
    return {"meta": {"identifier": identifier}, "data": {"team_name": name}}


@app.get("/meta/teams/{team_name}/driver-abbreviations")
def get_driver_abbreviations_by_team(team_name: str):
    """Abbreviazioni dei driver di un team."""
    try:
        abbreviations = plotting.get_driver_abbreviations_by_team(team_name)
    except Exception as exc:  # noqa: PERF203
        raise handle_fastf1_error(exc)
    return {"meta": {"team_name": team_name}, "data": abbreviations}


@app.get("/ergast/seasons/{year}/results")
def ergast_season_results(year: int):
    """Risultati di campionato per una stagione tramite Ergast."""
    try:
        client = ff1_ergast.Ergast()
        resp = client.get_season_results(season=year, result_type="pandas")
        df = resp
    except Exception as exc:  # noqa: PERF203
        raise handle_fastf1_error(exc)

    if isinstance(df, pd.DataFrame):
        data = df_to_json_safe(df)
    else:
        # fallback generico
        data = df

    return {"meta": {"year": year}, "data": data}


@app.get("/ergast/seasons/{year}/rounds/{round_number}/results")
def ergast_round_results(year: int, round_number: int):
    """Risultati di un singolo round tramite Ergast."""
    try:
        client = ff1_ergast.Ergast()
        resp = client.get_race_results(season=year, round=round_number, result_type="pandas")
        df = resp
    except Exception as exc:  # noqa: PERF203
        raise handle_fastf1_error(exc)

    if isinstance(df, pd.DataFrame):
        data = df_to_json_safe(df)
    else:
        data = df

    return {"meta": {"year": year, "round_number": round_number}, "data": data}


@app.get("/ergast/drivers/{driver_id}/results")
def ergast_driver_results(driver_id: str):
    """Storico risultati per un pilota tramite Ergast."""
    try:
        client = ff1_ergast.Ergast()
        resp = client.get_driver_results(driver=driver_id, result_type="pandas")
        df = resp
    except Exception as exc:  # noqa: PERF203
        raise handle_fastf1_error(exc)

    if isinstance(df, pd.DataFrame):
        data = df_to_json_safe(df)
    else:
        data = df

    return {"meta": {"driver_id": driver_id}, "data": data}


@app.get("/health")
def health():
    return {"status": "ok"}

