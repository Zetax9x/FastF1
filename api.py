from typing import Any, Dict, List, Optional

import fastf1
from fastf1 import get_event, get_event_schedule, get_events_remaining, get_session, plotting
from fastf1 import ergast as ff1_ergast
from fastapi import FastAPI, HTTPException, Query
import pandas as pd


# usa la stessa cartella di cache dello script di ingest
fastf1.Cache.enable_cache("fastf1_cache")


app = FastAPI(title="FastF1 API", version="1.0.0")


# ===== Helpers comuni ======================================================


def df_to_json_safe(df: pd.DataFrame) -> List[Dict[str, Any]]:
    """Converte un DataFrame in una lista di dict JSON-safe."""
    if df is None:
        return []

    df = df.copy()
    for col in df.columns:
        series = df[col]
        if pd.api.types.is_datetime64_any_dtype(series) or pd.api.types.is_timedelta64_dtype(series):
            df[col] = series.astype(str)
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
    return [2024, 2025, 2026]


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
    lap_min: Optional[int] = None,
    lap_max: Optional[int] = None,
    fastest_only: bool = False,
):
    """Tutti i giri di una sessione, con vari filtri."""
    session = load_session(year, round_number, session_code, telemetry=False)
    laps = session.laps
    if laps is None or laps.empty:
        raise HTTPException(status_code=404, detail="Nessun giro disponibile")

    if driver:
        laps = laps.pick_drivers(driver)
    if fastest_only:
        laps = laps.pick_fastest()
    if lap_min is not None:
        laps = laps[laps["LapNumber"] >= lap_min]
    if lap_max is not None:
        laps = laps[laps["LapNumber"] <= lap_max]

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
            "lap_min": lap_min,
            "lap_max": lap_max,
            "fastest_only": fastest_only,
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


@app.get("/sessions/{year}/{round_number}/{session_code}/telemetry")
def get_session_telemetry(
    year: int,
    round_number: int,
    session_code: str,
    driver: str = Query(..., description="Abbreviazione pilota, es. VER"),
    lap_number: Optional[int] = None,
    fastest: bool = False,
    columns: Optional[str] = Query(
        None, description="Lista di colonne separate da virgola da includere"
    ),
):
    """Telemetria della sessione per un driver (e opzionale giro)."""
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

    car_data = lap.get_car_data().add_distance()
    if columns:
        cols = [c.strip() for c in columns.split(",") if c.strip()]
        existing = [c for c in cols if c in car_data.columns]
        car_data = car_data[existing]

    return {
        "meta": {
            "year": year,
            "round_number": round_number,
            "session_code": session_code,
            "driver": driver,
            "lap_number": lap_number,
            "fastest": fastest,
            "columns": columns,
        },
        "data": df_to_json_safe(car_data.reset_index(drop=True)),
    }


@app.get("/sessions/{year}/{round_number}/{session_code}/circuit")
def get_session_circuit(year: int, round_number: int, session_code: str):
    """Informazioni basilari sul circuito associate alla sessione."""
    session = load_session(year, round_number, session_code, telemetry=False)
    event = session.event

    return {
        "meta": {
            "year": year,
            "round_number": round_number,
            "session_code": session_code,
        },
        "data": {
            "event_name": event.EventName,
            "country": event.Country,
            "location": event.Location,
            "official_event_name": event.OfficialEventName,
            "event_date": str(event.EventDate),
            "format": event.EventFormat,
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

