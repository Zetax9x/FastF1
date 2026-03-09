import gc

import fastf1
from fastf1 import get_event_schedule, get_session


# abilita la cache locale di FastF1 (così non riscarica tutto ogni volta)
fastf1.Cache.enable_cache("fastf1_cache")


# stagioni e sessioni da pre-caricare in cache
YEARS = [2026]
# tutte le sessioni standard (Practice 1-3, Qualifying, Sprint, Race)
SESSION_NAMES = ["FP1", "FP2", "FP3", "Q", "S", "R"]


def ingest_season(year: int) -> None:
    """Carica in cache tutte le sessioni selezionate per una stagione."""
    print(f"=== Inizio ingest stagione {year} ===")

    schedule = get_event_schedule(year)

    for event in schedule.itertuples():
        for s_name in SESSION_NAMES:
            print(f"- {year} Round {event.RoundNumber} {event.EventName} / {s_name} ...", end=" ")
            try:
                session = get_session(year, event.RoundNumber, s_name)
                # non carico la telemetria per ridurre memoria
                session.load(telemetry=True)
                print("OK")
            except Exception as exc:  # noqa: PERF203 - eccezioni ampie ma loggate
                print(f"SKIP ({exc})")
                continue
            finally:
                # libera memoria dopo ogni sessione
                try:
                    del session
                except NameError:
                    pass
                gc.collect()

    print(f"=== Fine ingest stagione {year} ===")


def main() -> None:
    for year in YEARS:
        ingest_season(year)


if __name__ == "__main__":
    main()
    print("Ingest completato. Dati salvati nella cache FastF1.")