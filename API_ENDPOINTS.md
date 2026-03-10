### FastF1 REST API – Overview

Backend FastAPI definito in `api.py`. Base URL (sviluppo):

```text
http://localhost:8000
```

Tutte le risposte hanno struttura:

```json
{
  "meta": { ... },   // contesto (filtri, anno, sessione, ecc.)
  "data": ...        // payload (lista di record, oggetto, mapping)
}
```

Laddove non specificato, i metodi sono `GET`.

---

### 1. Seasons & Events (`/seasons`)

- **GET `/seasons`**  
  Restituisce lista delle stagioni supportate.

  Esempio risposta:
  ```json
  [2024, 2025, 2026]
  ```

- **GET `/seasons/{year}/events`**  
  Wrapper di `fastf1.get_event_schedule(year)`. Restituisce tutte le gare dell’anno.

  Esempio:
  ```
  /seasons/2026/events
  ```

- **GET `/seasons/{year}/events/remaining`**  
  Eventi non ancora disputati per l’anno indicato (basato su `get_events_remaining()`).

- **GET `/seasons/{year}/events/{round}`**  
  Dettaglio evento per round, wrapper di `get_event(year, round)`.

  ```
  /seasons/2026/events/1
  ```

- **GET `/seasons/{year}/events/by-name?name=...`**  
  Carica l’evento per nome/country/location, wrapper di `get_event(year, name)`.

  ```
  /seasons/2026/events/by-name?name=Bahrain
  ```

- **GET `/seasons/{year}/events/{round}/sessions`**  
  Restituisce la lista delle sessioni previste per quel weekend (Practice, Qualifying, Sprint, Race).

  Esempio `data`:
  ```json
  [
    { "index": 1, "name": "Practice 1", "code": "FP1", "date_utc": "2026-03-06 11:30:00" },
    { "index": 2, "name": "Practice 2", "code": "FP2", "date_utc": "2026-03-06 15:00:00" },
    { "index": 3, "name": "Practice 3", "code": "FP3", "date_utc": "2026-03-07 12:30:00" },
    { "index": 4, "name": "Qualifying", "code": "Q",   "date_utc": "2026-03-07 16:00:00" },
    { "index": 5, "name": "Race",       "code": "R",   "date_utc": "2026-03-08 15:00:00" }
  ]
  ```

  - `name` è il nome completo usato da FastF1 (es. `Practice 1`).
  - `code` è la sigla comoda da usare negli altri endpoint `/sessions/...` (es. `FP1`, `Q`, `R`).

---

### 2. Session Data (`/sessions`)

Tutti questi endpoint richiedono:
- `year` – anno (es. `2026`)  
- `round_number` – numero round (es. `1`)  
- `session_code` – codice sessione: `FP1`, `FP2`, `FP3`, `Q`, `S`, `R`, ecc.

#### 2.1 Meta info sessione

- **GET `/sessions/{year}/{round_number}/{session_code}`**  
  Metadati base della sessione (nome, data, info evento).

  ```
  /sessions/2026/1/R
  ```

#### 2.2 Risultati

- **GET `/sessions/{year}/{round_number}/{session_code}/results`**  
  Restituisce `SessionResults` completi.

  Query opzionale:
  - `driver` – abbreviazione pilota (es. `VER`) per filtrare un solo pilota.

  Esempi:
  ```
  /sessions/2026/1/R/results
  /sessions/2026/1/R/results?driver=VER
  ```

#### 2.3 Giri (`Laps` / `Lap`)

- **GET `/sessions/{year}/{round_number}/{session_code}/laps`**

  Query opzionali (tutti mappano a metodi nativi di `fastf1.core.Laps`):
  - `driver` – `pick_drivers(driver)` (abbreviazione pilota)
  - `team` – `pick_teams(team)` (nome team)
  - `compound` – `pick_compounds(compound)` (SOFT, MEDIUM, HARD, INTERMEDIATE, WET, ...)
  - `track_status` – `pick_track_status(track_status, how=track_status_how)`
  - `track_status_how` – una tra `equals`|`contains`|`excludes`|`any`|`none` (default `equals`)
  - `box_laps` – `pick_box_laps(which)` dove `which` è `in`|`out`|`both`
  - `exclude_box` – `true` per usare `pick_wo_box()` (esclude in-lap/out-lap)
  - `not_deleted` – `true` per usare `pick_not_deleted()`
  - `accurate_only` – `true` per usare `pick_accurate()` (solo giri marcati come accurati)
  - `quicklaps_only` – `true` per usare `pick_quicklaps(threshold)`
  - `threshold` – coefficiente per `pick_quicklaps` (es. `1.07` = 107% del miglior tempo); se non specificato usa `Laps.QUICKLAP_THRESHOLD`
  - `lap_min` / `lap_max` – range giri, applicato tramite `pick_laps(range(lap_min, lap_max+1))`
  - `fastest_only` – `true` per restituire solo il giro più veloce (usa `pick_fastest()`)

  Esempi:
  ```text
  /sessions/2026/1/R/laps
  /sessions/2026/1/R/laps?driver=VER&fastest_only=true
  /sessions/2026/1/R/laps?driver=VER&lap_min=10&lap_max=20
  /sessions/2026/1/R/laps?team=Red%20Bull&compound=SOFT&quicklaps_only=true
  /sessions/2026/1/R/laps?track_status=4&track_status_how=contains&exclude_box=true
  ```

- **GET `/sessions/{year}/{round_number}/{session_code}/laps/{lap_number}`**

  Query opzionale:
  - `driver` – se vuoi selezionare il giro n di un pilota specifico.

  Esempio:
  ```
  /sessions/2026/1/R/laps/15
  /sessions/2026/1/R/laps/15?driver=VER
  ```

#### 2.3.1 Stint e gomme

- **GET `/sessions/{year}/{round_number}/{session_code}/tyres`**

  Query opzionale:
  - `driver` – abbreviazione pilota (es. `VER`) per limitare gli stint a un solo pilota.

  Restituisce una lista di stint raggruppati per `(Driver, Stint)` con:
  - `Driver` – abbreviazione
  - `Stint` – numero di stint
  - `Compound` – mescola usata nello stint
  - `lap_start` / `lap_end` – range di giri dello stint
  - `lap_count` – numero di giri nello stint
  - `tyre_life_min` / `tyre_life_max` – vita gomma minima/massima (se `TyreLife` disponibile nei dati FastF1)

  Esempio:
  ```text
  /sessions/2026/1/R/tyres
  /sessions/2026/1/R/tyres?driver=VER
  ```

#### 2.3.2 Quicklaps

- **GET `/sessions/{year}/{round_number}/{session_code}/quicklaps`**

  Query opzionali:
  - `driver` – filtra prima i giri del pilota, poi applica `pick_quicklaps`
  - `threshold` – coefficiente per `pick_quicklaps` (es. `1.07` = 107% del miglior tempo). Se omesso usa la soglia di default `Laps.QUICKLAP_THRESHOLD`.

  Esempio:
  ```text
  /sessions/2026/1/Q/quicklaps
  /sessions/2026/1/Q/quicklaps?driver=VER&threshold=1.05
  ```

#### 2.4 Telemetria

- **GET `/sessions/{year}/{round_number}/{session_code}/telemetry`**

  Query:
  - `driver` (obbligatorio) – abbreviazione pilota (es. `VER`)
  - `lap_number` – numero giro da usare
  - `fastest` – `true` per usare il giro più veloce del pilota
  - `type` – tipo di telemetria:
    - `car` → `Lap.get_car_data()` (dati originali auto: Speed, RPM, nGear, Throttle, Brake, DRS, ecc.)
    - `pos` → `Lap.get_pos_data()` (coordinate X, Y, Z, Status)
    - `merged` → `Lap.get_telemetry()` (merge car+pos con canali derivati)
  - `add_distance` – `true` per chiamare `add_distance()` (colonna Distance)
  - `add_driver_ahead` – `true` per chiamare `add_driver_ahead()` (DriverAhead, DistanceToDriverAhead)
  - `add_track_status` – `true` per chiamare `add_track_status()` (TrackStatus)
  - `columns` – lista colonne separate da virgola (es. `Speed,Throttle,Brake,Distance`)

  Comportamento:
  - Se `fastest=true`, usa il giro più veloce del pilota (`pick_fastest`).
  - Altrimenti, se `lap_number` è settato usa quel giro.
  - Se nessuno dei due, usa il primo giro disponibile del pilota.

  Esempi:
  ```text
  /sessions/2026/1/R/telemetry?driver=VER&fastest=true&type=car&columns=Speed,Throttle,Brake
  /sessions/2026/1/R/telemetry?driver=VER&lap_number=10&type=merged&add_distance=true
  /sessions/2026/1/R/telemetry?driver=VER&type=pos&add_track_status=true
  ```

#### 2.5 Informazioni circuito

- **GET `/sessions/{year}/{round_number}/{session_code}/circuit`**  
  Info estese sul circuito (wrapper di `Session.get_circuit_info()` + `Event`):

  `data.event`:
  - dizionario evento FastF1 (`event.to_dict()`), include `EventName`, `OfficialEventName`, `Country`, `Location`, `EventDate`, `EventFormat`, ecc.

  `data.circuit`:
  - `corners` – lista di corner con colonne: `X`, `Y`, `Number`, `Letter`, `Angle`, `Distance`
  - `marshal_lights` – posizione delle luci dei commissari (stessa struttura di `corners`)
  - `marshal_sectors` – posizione dei settori dei commissari (stessa struttura di `corners`)
  - `rotation` – rotazione del circuito in gradi, utile per allineare la mappa

  ```text
  /sessions/2026/1/R/circuit
  ```

#### 2.6 Session extra: drivers, info, status, race control

- **GET `/sessions/{year}/{round_number}/{session_code}/drivers`**  
  Lista driver della sessione con info derivate da `SessionResults` / `DriverResult`:

  Ogni elemento contiene:
  - `DriverNumber`
  - `Abbreviation`
  - `FullName`
  - `TeamName`
  - `TeamColor`
  - `HeadshotUrl`
  - `CountryCode`
  - `dnf` – boolean (true se il pilota non ha terminato, da `DriverResult.dnf`)

  ```text
  /sessions/2026/1/R/drivers
  ```

- **GET `/sessions/{year}/{round_number}/{session_code}/info`**  
  Info avanzate sulla sessione:
  - `session_info` – dict con meeting, session, country, circuit id (wrapper di `Session.session_info`)
  - `total_laps` – giri totali previsti (per race-like session)
  - `f1_api_support` – boolean, se la sessione ha supporto dati completo
  - `date` – data sessione (string)

- **GET `/sessions/{year}/{round_number}/{session_code}/track-status`**  
  Track status per la sessione (DataFrame convertito in lista di record), wrapper di `Session.track_status`.

- **GET `/sessions/{year}/{round_number}/{session_code}/session-status`**  
  Session status (Started/Finished/Aborted ecc.), wrapper di `Session.session_status`.

- **GET `/sessions/{year}/{round_number}/{session_code}/race-control-messages`**  
  Messaggi di Race Control, wrapper di `Session.race_control_messages`.

#### 2.7 Meteo sessione

- **GET `/sessions/{year}/{round_number}/{session_code}/weather`**

  Query opzionale:
  - `driver` – se valorizzato, usa `session.laps.pick_drivers(driver).get_weather_data()` per avere un punto meteo per giro.

  Comportamento:
  - Senza `driver`: usa `session.weather_data` (dati meteo globali della sessione, aggiornati circa ogni minuto).
  - Con `driver`: restituisce DataFrame prodotto da `Laps.get_weather_data()` per i giri del pilota.

  ```text
  /sessions/2026/1/Q/weather
  /sessions/2026/1/Q/weather?driver=VER
  ```

#### 2.8 Split qualifiche Q1/Q2/Q3

- **GET `/sessions/{year}/{round_number}/{session_code}/qualifying-splits`**

  Wrapper di `Laps.split_qualifying_sessions()`:

  ```json
  {
    "meta": { ... },
    "data": {
      "Q1": [ ... ],  // lista laps Q1 o null se sessione cancellata
      "Q2": [ ... ],
      "Q3": [ ... ]
    }
  }
  ```

  ```text
  /sessions/2026/1/Q/qualifying-splits
  ```

---

### 3. Plotting & Meta Data (`/meta`)

Questi endpoint espongono i metadati usati da FastF1 per styling e mapping.

#### 3.1 Compounds (gomme)

- **GET `/meta/compounds`**  
  Restituisce elenco dei nomi delle mescole (SOFT, MEDIUM, HARD, INTER, WET, ecc.).

- **GET `/meta/compounds/{compound}/color`**  
  Colore associato alla mescola (stringa HEX).

  ```
  /meta/compounds/SOFT/color
  ```

- **GET `/meta/compounds/mapping`**  
  Mapping completo di tutte le mescole con le loro proprietà.

#### 3.2 Driver

- **GET `/meta/sessions/{year}/{round_number}/{session_code}/drivers`**  
  Elenco driver presenti in una sessione (nome + abbreviazione).

  ```
  /meta/sessions/2026/1/R/drivers
  ```

- **GET `/meta/drivers/{identifier}/name`**  
  Nome completo di un driver dato un identificatore (abbr, nome, ecc.).

- **GET `/meta/drivers/{identifier}/abbreviation`**  
  Abbreviazione standard (es. `VER`).

- **GET `/meta/drivers/{identifier}/color`**  
  Colore usato per il pilota.

- **GET `/meta/drivers/{identifier}/style`**  
  Stile di plotting per il driver.

  Query opzionali (per contestualizzare al weekend):
  - `year`
  - `round_number`
  - `session_code`

  Esempio:
  ```
  /meta/drivers/VER/style?year=2026&round_number=1&session_code=R
  ```

- **GET `/meta/drivers/color-mapping`**  
  Mapping completo `driver → color`.

#### 3.3 Team

- **GET `/meta/teams`**  
  Elenco team.  
  Query opzionali per limitarlo a una sessione:
  - `year`
  - `round_number`
  - `session_code`

  ```
  /meta/teams
  /meta/teams?year=2026&round_number=1&session_code=R
  ```

- **GET `/meta/teams/{team_identifier}/name`**  
  Nome normalizzato di un team.

- **GET `/meta/teams/{team_identifier}/color`**  
  Colore del team.

- **GET `/meta/drivers/{identifier}/team-name`**  
  Nome team dato un driver.

- **GET `/meta/teams/{team_name}/driver-abbreviations`**  
  Abbreviazioni dei driver associati a un team.

---

### 4. Ergast Historical Data (`/ergast`)

Questi endpoint usano l’interfaccia `fastf1.ergast.Ergast` per accedere ai dati storici dell’API Ergast.

- **GET `/ergast/seasons/{year}/results`**  
  Risultati di campionato per una stagione (classifiche, risultati gara per gara).

  ```
  /ergast/seasons/2020/results
  ```

- **GET `/ergast/seasons/{year}/rounds/{round_number}/results`**  
  Risultati di uno specifico round.

  ```
  /ergast/seasons/2020/rounds/1/results
  ```

- **GET `/ergast/drivers/{driver_id}/results`**  
  Storico risultati per un pilota (driver ID Ergast, es. `max_verstappen`).  

  ```
  /ergast/drivers/max_verstappen/results
  ```

Le risposte sono DataFrame Ergast convertiti in liste di record JSON-safe.

---

### 5. Health Check

- **GET `/health`**  
  Semplice endpoint per verificare che il backend sia up:

  ```json
  { "status": "ok" }
  ```

---

### 6. Note per il frontend

- Tutti gli endpoint sono `GET` e restituiscono JSON.
- Per i dati pesanti (laps, telemetry, Ergast intero campionato) è consigliato:
  - usare filtri (`driver`, `lap_min`, `lap_max`, `columns`, ecc.);
  - cache lato frontend o lato API gateway se necessario.
- I nomi delle colonne in `results`, `laps` e `telemetry` seguono la documentazione ufficiale FastF1 ([API Reference](https://docs.fastf1.dev/api_reference/index.html)); se devi sapere cosa significa una colonna, puoi riferirti lì.

