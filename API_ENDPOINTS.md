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

  Query opzionali:
  - `driver` – filtra per pilota (abbreviazione)
  - `lap_min` – numero giro minimo
  - `lap_max` – numero giro massimo
  - `fastest_only` – `true` per solo giro più veloce (per sessione o pilota)

  Esempi:
  ```
  /sessions/2026/1/R/laps
  /sessions/2026/1/R/laps?driver=VER&fastest_only=true
  /sessions/2026/1/R/laps?driver=VER&lap_min=10&lap_max=20
  ```

- **GET `/sessions/{year}/{round_number}/{session_code}/laps/{lap_number}`**

  Query opzionale:
  - `driver` – se vuoi selezionare il giro n di un pilota specifico.

  Esempio:
  ```
  /sessions/2026/1/R/laps/15
  /sessions/2026/1/R/laps/15?driver=VER
  ```

#### 2.4 Telemetria

- **GET `/sessions/{year}/{round_number}/{session_code}/telemetry`**

  Query:
  - `driver` (obbligatorio) – abbreviazione pilota (es. `VER`)
  - `lap_number` – numero giro
  - `fastest` – `true` per usare il giro più veloce del pilota
  - `columns` – lista colonne separate da virgola (es. `Speed,Throttle,Brake,Distance`)

  Comportamento:
  - Se `fastest=true`, usa il giro più veloce del pilota.
  - Altrimenti, se `lap_number` è settato usa quel giro.
  - Se nessuno dei due, usa il primo giro disponibile del pilota.

  Esempi:
  ```
  /sessions/2026/1/R/telemetry?driver=VER&fastest=true&columns=Speed,Throttle,Brake
  /sessions/2026/1/R/telemetry?driver=VER&lap_number=10
  ```

#### 2.5 Informazioni circuito

- **GET `/sessions/{year}/{round_number}/{session_code}/circuit`**  
  Info basilari sull’evento/circuito (nome GP, country, location, data, formato).

  ```
  /sessions/2026/1/R/circuit
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

