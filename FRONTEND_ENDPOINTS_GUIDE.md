### FastF1 – Guida endpoint per il frontend

Questa guida riassume **solo** gli endpoint più utili per il frontend, organizzati per schermata/caso d’uso. Tutte le strutture di risposta seguono il pattern:

```json
{
  "meta": { ... },
  "data": ...
}
```

---

### 1. Home / Selezione stagione & evento

- **Lista stagioni disponibili**
  - **Endpoint**: `GET /seasons`
  - **Uso tipico**: popolazione di un select di stagioni.

- **Calendario eventi di una stagione**
  - **Endpoint**: `GET /seasons/{year}/events`
  - **Uso tipico**: lista GP dell’anno (calendar view, cards per ogni round).

- **Dettaglio singolo evento**
  - **Endpoint**: `GET /seasons/{year}/events/{round}`
  - **Uso tipico**: info testuali del weekend (nome, paese, data, formato).

- **Eventi rimanenti nella stagione**
  - **Endpoint**: `GET /seasons/{year}/events/remaining`
  - **Uso tipico**: sezione “Upcoming races”.

---

### 2. Weekend view (lista sessioni & info evento)

- **Lista sessioni del weekend**
  - **Endpoint**: `GET /seasons/{year}/events/{round}/sessions`
  - **Risultato**: lista di sessioni con:
    - `name`: es. `Practice 1`, `Qualifying`, `Race`
    - `code`: `FP1`, `FP2`, `FP3`, `Q`, `S`, `R`
    - `date_utc`
  - **Uso tipico**: pulsanti/tiles per entrare nella singola sessione usando `{year}/{round}/{code}`.

- **Info estese su circuito + evento**
  - **Endpoint**: `GET /sessions/{year}/{round}/{session_code}/circuit`
  - **Uso tipico**:
    - pannello info circuito (nome, location, formato weekend)
    - dati per mappa circuito (corners, marshal lights, marshal sectors, rotation).

---

### 3. Session view – Panoramica

- **Meta info sessione**
  - **Endpoint**: `GET /sessions/{year}/{round}/{session_code}`
  - **Uso tipico**: header della pagina (nome sessione, data, info GP).

- **Info avanzate sessione**
  - **Endpoint**: `GET /sessions/{year}/{round}/{session_code}/info`
  - **Uso tipico**: dettagli per pannelli tecnici (total_laps, f1_api_support, session_info).

- **Lista driver con meta dati**
  - **Endpoint**: `GET /sessions/{year}/{round}/{session_code}/drivers`
  - **Uso tipico**:
    - elenco piloti con nome completo, team, colore team, headshot
    - flag `dnf` per badge “DNF” nelle classify views.

---

### 4. Risultati & classifiche

- **Risultati sessione (classifica)**
  - **Endpoint**: `GET /sessions/{year}/{round}/{session_code}/results`
  - **Query opzionale**: `driver=VER` per un solo pilota.
  - **Uso tipico**:
    - tabella “Results” (Position, ClassifiedPosition, Points, Status, ecc.)
    - card driver detail.

- **Storico Ergast (campionato, non solo 2026)**
  - **Endpoint**:
    - `GET /ergast/seasons/{year}/results`
    - `GET /ergast/seasons/{year}/rounds/{round}/results`
    - `GET /ergast/drivers/{driver_id}/results`
  - **Uso tipico**: pagine “Stats / History” (campionati passati).

---

### 5. Laps & stint (race pace, qualifying pace)

- **Laps generali con filtri potenti**
  - **Endpoint**: `GET /sessions/{year}/{round}/{session_code}/laps`
  - **Filtri principali**:
    - `driver` – solo giri di un pilota
    - `team` – solo giri di un team
    - `compound` – es. `SOFT`, `MEDIUM`, `HARD`
    - `lap_min`, `lap_max` – range di giri
    - `fastest_only` – solo giro più veloce (rispetto al filtro corrente)
    - `quicklaps_only`, `threshold` – solo giri “quick” (in base alla regola 107% o custom)
    - `exclude_box`, `box_laps`, `not_deleted`, `accurate_only`, `track_status`, `track_status_how`
  - **Uso tipico**:
    - tabelle “All laps” filtrabili
    - grafici tempo sul giro vs numero di giro
    - analisi pace per team/compound.

- **Stint & gomme**
  - **Endpoint**: `GET /sessions/{year}/{round}/{session_code}/tyres?driver=VER`
  - **Uso tipico**:
    - grafico “stint chart” per ogni driver (blocco orizzontale per stint, colorato per compound)
    - tabella riassuntiva stint (lap_start, lap_end, lap_count, compound, tyre life).

- **Quicklaps dedicato**
  - **Endpoint**: `GET /sessions/{year}/{round}/{session_code}/quicklaps?driver=VER&threshold=1.07`
  - **Uso tipico**:
    - highlight dei giri veloci in una qualifying
    - filtri veloci per outlier “buoni” in long run.

- **Split qualifiche Q1/Q2/Q3**
  - **Endpoint**: `GET /sessions/{year}/{round}/{session_code}/qualifying-splits`
  - **Uso tipico**:
    - 3 tabelle/distinte charts per Q1, Q2, Q3
    - comparazione performance per fase della qualifica.

---

### 6. Meteo & status sessione

- **Meteo sessione**
  - **Endpoint**: `GET /sessions/{year}/{round}/{session_code}/weather`
  - **Query opzionale**: `driver=VER` per meteo per-lap del pilota.
  - **Uso tipico**:
    - grafici AirTemp / TrackTemp / WindSpeed nel tempo
    - overlay meteo vs pace.

- **Track status**
  - **Endpoint**: `GET /sessions/{year}/{round}/{session_code}/track-status`
  - **Uso tipico**:
    - timeline bandiere (verde/giallo/rosso/SC/VSC)
    - overlay su grafici di telemetry/laps.

- **Session status**
  - **Endpoint**: `GET /sessions/{year}/{round}/{session_code}/session-status`
  - **Uso tipico**:
    - capire fasi della sessione (start, finish, aborted, ecc.).

- **Race Control messages**
  - **Endpoint**: `GET /sessions/{year}/{round}/{session_code}/race-control-messages`
  - **Uso tipico**:
    - log eventi testuali (incidenti, investigazioni, decisioni).

---

### 7. Telemetry (onboard / comparison view)

- **Telemetry singolo giro**
  - **Endpoint**: `GET /sessions/{year}/{round}/{session_code}/telemetry`
  - **Query principali**:
    - `driver` (obbligatorio)
    - `lap_number` **oppure** `fastest=true`
    - `type=car|pos|merged`
      - `car` – Speed, RPM, nGear, Throttle, Brake, DRS, ecc.
      - `pos` – X, Y, Z, Status
      - `merged` – merge di car+pos con canali derivati
    - `add_distance`, `add_driver_ahead`, `add_track_status`
    - `columns=Speed,Throttle,Brake,Distance`
  - **Uso tipico**:
    - grafici Speed / Throttle / Brake / Gear su Distance o Time
    - overlay track map (usando X/Y da `type=pos` o `merged`)
    - grafici distanza dal driver davanti (`add_driver_ahead`).

Per confronti fra piloti/giri diversi, tipicamente:
1. Chiamare questo endpoint più volte (una per combinazione driver+giro).
2. Allineare client-side per `Distance` o `Time`.

---

### 8. Meta dati per colori & nomi

- **Colori & meta driver/team (per legende/plot)**
  - `GET /meta/compounds`
  - `GET /meta/compounds/{compound}/color`
  - `GET /meta/compounds/mapping`
  - `GET /meta/teams`
  - `GET /meta/teams/{team}/color`
  - `GET /meta/drivers/{identifier}/color`
  - `GET /meta/drivers/color-mapping`
  - `GET /meta/sessions/{year}/{round}/{session_code}/drivers`

**Uso tipico**: palette consistente per grafici (team/driver/compound), tooltips più leggibili (nomi estesi).

---

### 9. Endpoints più importanti (shortlist)

Se vuoi partire con il **minimo set** per una UI completa race/qualifying:

- Navigazione:
  - `/seasons`
  - `/seasons/{year}/events`
  - `/seasons/{year}/events/{round}/sessions`
- Session overview:
  - `/sessions/{year}/{round}/{session_code}`
  - `/sessions/{year}/{round}/{session_code}/info`
  - `/sessions/{year}/{round}/{session_code}/drivers`
- Risultati & laps:
  - `/sessions/{year}/{round}/{session_code}/results`
  - `/sessions/{year}/{round}/{session_code}/laps`
  - `/sessions/{year}/{round}/{session_code}/quicklaps`
  - `/sessions/{year}/{round}/{session_code}/qualifying-splits`
  - `/sessions/{year}/{round}/{session_code}/tyres`
- Telemetry & circuito:
  - `/sessions/{year}/{round}/{session_code}/telemetry`
  - `/sessions/{year}/{round}/{session_code}/circuit`
- Meteo & status:
  - `/sessions/{year}/{round}/{session_code}/weather`
  - `/sessions/{year}/{round}/{session_code}/track-status`
  - `/sessions/{year}/{round}/{session_code}/race-control-messages`

