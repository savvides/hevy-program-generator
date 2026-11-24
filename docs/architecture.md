# Architecture & Scientific Engine Specification

This document describes the architecture, accounting models, reconcile algorithms and configured QA policies of **Hevy Program Generator (`hevy-program-generator`)**.

The [November 2, 2026 review](research/2026-11-02-consensus-review.md) and current
[exercise](evidence_base.md) and [nutrition](nutrition_evidence_base.md) documents
lead scientific interpretation. Historical specifications, guides and cache summaries
do not override them. The preserved CSV and authority manifest identify source
membership; original papers qualify their exported takeaways.

---

## 1. Architectural Philosophy

`hevy-program-generator` uses four software and evidence-review principles:

1. **Training Program as Executable Code:** Rather than maintaining workout routines as manual app entries or disconnected text documents, training programs are declared as typed Python modules. They are subject to automated static analysis, deterministic compiler QA gates, and version-controlled sync.
2. **Dated evidence authority:** The selected October corpus leads covered topics. The two evidence documents distinguish findings, population limits and coaching choices. Only manifest-listed supplements can ground program citations; a background cache hit or nutrition-document mention does not grant that role.
3. **Latent-Deterministic Split:** Large Language Models (LLMs) excel at empathetic user elicitation, creative exercise variation, and personalized meal planning (latent space). However, LLMs are prone to arithmetic drift and physiological hallucination. Pure-Python gates verify volume accounting, configured spacing, estimated duration and source identity. They cannot verify physiological recovery, scientific validity, individual suitability or nutritional adequacy.
4. **Zero External Dependencies:** The entire engine runs on 100% Python 3 standard library modules (`urllib`, `json`, `dataclasses`, `argparse`, `math`, `pathlib`, `unittest`). No `pip install`, virtual environment management, or external package vulnerabilities.

---

## 2. System Architecture Diagram

```mermaid
graph TD
    subgraph "1. Dated Research Authority & Reviewed Guidance"
        EB["Exercise Physiology & Biomechanics<br/>(docs/evidence_base.md)"]
        NB["Nutritional Physiology & Bioenergetics<br/>(docs/nutrition_evidence_base.md)"]
    end

    subgraph "2. Program Definitions"
        P1["programs/starter_full_body_2x.py"]
        P2["programs/upper_lower_4x.py"]
        P3["programs/program.py (User Private)"]
    end

    subgraph "3. Engine & Schema Validation"
        Loader["scripts/program_loader.py"]
        P1 --> Loader
        P2 --> Loader
        P3 --> Loader
    end

    subgraph "4. Deterministic Pre-Flight QA Gatekeeper (qa_program.py)"
        Loader --> Gate1["Catalog & Structural Integrity<br/>(test_build_routines.py)"]
        Loader --> Gate2["Volume & Frequency Landmarks<br/>(eval_program_volume.py)"]
        Loader --> Gate3["Recovery & Spacing Kinetics<br/>(eval_recovery_interference.py)"]
        Loader --> Gate4["Session Duration Physics<br/>(estimate_session_time.py)"]
        EB -.-> Gate1 & Gate2 & Gate3 & Gate4
    end

    subgraph "5. Hevy Cloud Sync (build_routines.py)"
        Gate1 & Gate2 & Gate3 & Gate4 -->|All Gates Green| SyncEngine["Idempotent Reconcile Engine"]
        Cache[("data/exercise_templates.json<br/>(30-day TTL Cache)")] --> SyncEngine
        SyncEngine -->|REST API (PUT / POST)| HevyAPI["Hevy Cloud API<br/>(api.hevyapp.com/v1)"]
    end

    subgraph "6. Telemetry & Duration Calibration"
        Fetcher["scripts/fetch_workouts.py"] -->|GET /v1/workouts| Logs[("data/workouts/*.json")]
        Logs --> Calibrator["scripts/calibrate_session_time.py"]
        Calibrator -.->|Empirical Constant Tuning| Gate4
    end
```

---

## 3. Pluggable Program Architecture

Training programs are decoupled from the synchronization and evaluation engine.

### 3.1 Path Resolution Hierarchy

[`scripts/program_loader.py`](scripts/program_loader.py) resolves the active program file using the following precedence:

1. **CLI Flag:** `--program <path>` passed explicitly to any engine script.
2. **Environment Variable:** `HEVY_PROGRAM=<path>`.
3. **Local User Program:** `programs/program.py` (gitignored, private by default).
4. **Active Program Fallback:** `programs/starter_full_body_2x.py` (same default as `render_program.py`).

### 3.2 Program Schema Specification

Each program module must export three top-level dictionaries:

```python
PROGRAM_METADATA: dict[str, Any] = {
    "title": str,                      # Routine folder title in Hevy
    "version": str,                    # Semantic version string
    "target_demographic": str,         # Target population / focus
    "session_time_cap_minutes": int,   # Hard ceiling for duration simulator
    "min_recovery_buffer_hours": int,  # Required spacing between lower & VO2
    "description": str,                # Program summary
}

ROUTINES: list[dict[str, Any]] = [
    {
        "name": str,                   # e.g., "Full-Body A — Squat / Bench / Pull"
        "day_key": str,               # e.g., "Tuesday" (used for reconcile matching)
        "notes": str,                  # Routine-level guidance synced to Hevy
        "exercises": [
            {
                "name": str,                   # Exact or fuzzy Hevy catalog name
                "compound": bool,              # True for multi-joint, False for isolation
                "warmup_reps": list[int]|None, # [5, 5, 3] for compounds, None for isolations
                "work_sets": int,              # Positive integer set count
                "reps": str|int,               # e.g., "3-5" or 5 or "10-12"
                "rpe": float|int,              # Proximity to failure (<= 8.0 for compounds)
                "rest_seconds": int,           # Prescribed rest interval
                "muscle_groups": list[str],    # List of targeted muscle groups
                "evidence_citation": str,      # Mandatory citation from evidence_base.md
                "superset": int|None,          # Integer grouping ID, None for solo lift
            }
        ]
    }
]

CARDIO_SCHEDULE: list[dict[str, Any]] = [
    {
        "day": str,                    # e.g., "Thursday"
        "modality": str,               # e.g., "Stationary Bike"
        "type": str,                   # e.g., "VO2 Max 4x4" or "Zone 2"
        "duration_minutes": int,       # Total session duration
        "evidence_citation": str,      # Supporting literature citation
    }
]
```

---

## 4. Reconcile Algorithm & Fuzzy Exercise Matcher

The Hevy API synchronization client ([`scripts/build_routines.py`](scripts/build_routines.py)) implements an idempotent, state-reconciling architecture.

### 4.1 Fuzzy Exercise Resolution

Hevy stores thousands of exercise templates with varying naming conventions (e.g. `"Squat (Barbell)"` vs `"Barbell Full Squat"`). To provide offline resilience and robust name matching:

1. **Catalog Cache:** All account-accessible templates are fetched and cached in [`data/exercise_templates.json`](data/exercise_templates.json) with a 30-day Time-To-Live (TTL).
2. **String Normalization:** Both query names and catalog titles are normalized by lowercasing and stripping non-alphanumeric characters:
   $$\text{normalize}(s) = \text{re.sub}(r'[\text{\textasciicircum}a\text{-}z0\text{-}9]+', \text{' '}, s.\text{lower}()).\text{strip}()$$
3. **Alias Map:** Common nomenclature differences (e.g., `"palloff press"` $\rightarrow$ `"Cable Core Pallof Press"`) are normalized via `EXERCISE_ALIASES`.
4. **Token-Overlap Jaccard Scoring:**
   $$\text{Score}(A, B) = \frac{|T_A \cap T_B|}{\max(|T_A \cup T_B|, 1)}$$
   where $T_A$ and $T_B$ are the token sets of the normalized query and catalog title.
5. **Deterministic Tie-Breaking:** If multiple exact matches exist (e.g., custom vs. built-in), built-in templates are prioritized (`is_custom: False`), followed by lexicographically lowest template ID.
6. **Threshold:** Matches with $\text{Score} \ge 0.55$ are accepted. Unresolved exercises print candidate suggestions and abort execution before any API write.

### 4.2 Idempotent Reconcile Engine

To prevent creating duplicate routines upon repeated script executions:

- **Routine Key Identity:** Each routine's stable key is derived from its weekday prefix (`day_key`, e.g., `"tue"` for `"Tuesday — Full-Body A"`). For non-weekday routines, it falls back to the normalized full title.
- **Action Planning (`plan_reconcile`):**
  - **Match Found:** Existing routine in the target folder matches `routine_key` $\rightarrow$ Scheduled for in-place update via `PUT /v1/routines/{id}`.
  - **No Match:** Desired routine does not exist $\rightarrow$ Scheduled for creation via `POST /v1/routines` (with `folder_id` attached).
  - **Unmatched Extras:** Existing routines in the folder not present in the program definition are reported as stale extras. Because the Hevy API lacks a `DELETE /v1/routines/{id}` endpoint, these are clearly flagged for manual cleanup in the Hevy mobile app.

---

## 5. Configured Evaluator Mathematics

### 5.1 Volume Accounting ([`eval_program_volume.py`](scripts/eval_program_volume.py))

Weekly volume per muscle group $m$ is computed using direct and fractional synergist contributions:

$$V_{\text{direct}}(m) = \sum_{e \in \text{Primary}(m)} N_{\text{work}}(e)$$

$$V_{\text{weighted}}(m) = V_{\text{direct}}(m) + 0.5 \sum_{e \in \text{Secondary}(m)} N_{\text{work}}(e)$$

#### Repository screening bounds

Currier 2026 and Pelland 2026 inform broad adult dose discussions, not individual
MEV/MRV. The bounds below are retained coaching screens, including for the active
aerobic-primary plan. The 0.5 secondary-set weight is bookkeeping; catalog muscle
assignments and population transfer remain limitations.

- **Configured weekly floor:**
  $$\forall m \in \text{Gated Prime Movers}, \quad V_{\text{weighted}}(m) \ge 3.0 \text{ sets/week}$$
- **Configured review ceiling:**
  $$\forall m \in \text{Gated Prime Movers}, \quad V_{\text{weighted}}(m) \le 18.0 \text{ sets/week}$$
- **Minimum Frequency:**
  $$\forall m \in \text{Gated Prime Movers}, \quad \text{Freq}(m) \ge 1 \text{ session/week}$$
- **Advisory push/pull ratio (not a pass/fail gate):**
  $$\text{Ratio}_{\text{push/pull}} = \frac{V_{\text{chest}} + V_{\text{shoulders}} + V_{\text{triceps}}}{V_{\text{lats}} + V_{\text{upper\_back}} + V_{\text{biceps}}} \in [0.8, 1.2]$$
- **Advisory knee/hip ratio (not a pass/fail gate):**
  $$\text{Ratio}_{\text{knee/hip}} = \frac{V_{\text{quadriceps}}}{V_{\text{hamstrings}} + V_{\text{glutes}}} \in [0.8, 1.2]$$

### 5.2 Concurrent Training and Configured Spacing ([`eval_recovery_interference.py`](../scripts/eval_recovery_interference.py))

Schumann 2022 (online 2021) and Huiberts 2024 (online 2023) discuss concurrent
training outcomes. Neither establishes a universal 48-hour recovery requirement
or sex-dependent spacing formula. The current metadata buffer of 48 hours is a
start-to-start coaching policy, checked in both directions with weekly wraparound.
Optional local `start_time` values refine weekday spacing; missing times make
hourly estimates provisional. Passing this check does not prove actual recovery.

Cardio accounting separates explicit easy-session minutes, prescribed interval
work and unclassified warmup/recovery time. The interval-work fraction is
interval-work minutes divided by total scheduled cardio minutes, and has a 25%
review ceiling. This is
a configured screen, not a validated physiological ceiling or universal 80/20
minute distribution. Milanović 2015 supports average VO2max benefits, Buchheit &
Laursen 2013 covers interval variables and Seiler 2010 supplies endurance-athlete
context; none validates every shipped interval dose or a 20-minute weekly floor.

### 5.3 Nutrition Planning Scope ([`nutrition_evidence_base.md`](nutrition_evidence_base.md))

The nutrition document owns the reviewed claims and population limits. Adult
protein planning around 1.6 g/kg/day, with an optional 1.6–2.2 range, is not an
age-40 physiological floor. Nunes 2022's <65/≥65 analysis lacks older resistance
trials at ≥1.6 g/kg/day; it does not establish a lower older-adult optimum.
Meal distribution, carbohydrate, fed/fasted exercise and antioxidant context remain
qualified supplements, not compulsory software gates or universal anabolic switches.

`scripts/track_deficit.py` estimates energy-balance arithmetic from wearable energy
and estimated body composition. Its 1.18 g/lb estimated lean-mass protein multiplier
(about 2.6 g/kg estimated lean mass), 70 g/day fat and selected 0.55 lb/week loss
rate are personal choices. Research protein estimates generally use total body mass.
The 3,500 kcal/lb conversion and fixed-lean-mass projection are approximations.
The tracker does not diagnose low energy availability or change the chosen deficit
automatically. Murphy & Koehler's roughly 500 kcal/day regression is not a universal
safety threshold. Input and macro-feasibility checks do not establish adequacy.

Optional `age_years`, `sex` and `primary_goal` metadata are reported context only.
Omitted fields remain unknown; titles and focus labels do not supply them. The adult
generator stops for explicit age <18 without applying demographic doses. Joint tags
preserve elicited selection constraints and do not provide clinical clearance.

---

## 6. Session Duration Simulation Model (Gym Physics)

Gym session duration is deterministically modeled in [`scripts/estimate_session_time.py`](scripts/estimate_session_time.py) and calibrated against actual Hevy mobile app workout logs via [`scripts/calibrate_session_time.py`](scripts/calibrate_session_time.py).

### 6.1 Mathematical Formulation

A routine consists of an ordered sequence of exercise groups $G_1, G_2, \dots, G_k$. A group is either a single solo exercise or a superset pair/group sharing the same `superset` identifier:

$$T_{\text{session}} = \sum_{g \in G} \left( T_{\text{setup}}(g) + T_{\text{warmups}}(g) + T_{\text{work}}(g) \right)$$

1. **Setup Duration:**
   $$T_{\text{setup}}(g) = \sum_{e \in g} \begin{cases} 90\text{ s} & \text{if } e \text{ is compound (rack/bar/plates)} \\ 40\text{ s} & \text{if } e \text{ is isolation (dumbbells/cable/machine)} \end{cases}$$

2. **Warm-up Duration:**
   $$T_{\text{warmups}}(g) = \sum_{e \in g} |N_{\text{warmup}}(e)| \times 75\text{ s}$$
   *(75 s accounts for plate loading, collar clamping, execution, and brief breath).*

3. **Solo Work Set Duration ($|g| = 1$):**
   $$T_{\text{work}}(g) = \sum_{s=1}^{N_{\text{work}}} \left( T_{\text{exec}}(e) + T_{\text{rest}}(e) + T_{\text{overrun}} \right)$$
   where $T_{\text{exec}} = 45\text{ s}$ for compound, $30\text{ s}$ for isolation, and $T_{\text{overrun}} = 25\text{ s}$ (app logging + timer creep).

4. **Superset Work Set Duration ($|g| > 1$):**
   For a superset group with $R = \max_{e \in g} N_{\text{work}}(e)$ rounds:
   $$T_{\text{work}}(g) = \sum_{r=1}^R \left( \sum_{e \in g_r} T_{\text{exec}}(e) + (|g_r| - 1) \cdot T_{\text{internal\_rest}} + \max_{e \in g} T_{\text{rest}}(e) + T_{\text{overrun}} \right)$$
   where $T_{\text{internal\_rest}} = 40\text{ s}$ (station transition between paired lifts).

### 6.2 Calibrated Model Constants

| Constant | Value | Description |
| :--- | :--- | :--- |
| `CAP_MIN` | $50.0\text{--}60.0\text{ min}$ | Hard per-session duration cap (loaded from `PROGRAM_METADATA`) |
| `WARMUP_SET` | $75\text{ s}$ | One warmup ramp set including plate change and rest |
| `EXEC_COMPOUND` | $45\text{ s}$ | Heavy compound set: setup, unrack, execution, rerack |
| `EXEC_ISOLATION` | $30\text{ s}$ | Isolation set execution time |
| `SETUP_COMPOUND` | $90\text{ s}$ | Walk to rack, load barbell, set safety pins/box |
| `SETUP_OTHER` | $40\text{ s}$ | Select dumbbells, set bench angle, adjust cable pin |
| `SUPERSET_INTERNAL_REST` | $40\text{ s}$ | Transition time between paired exercises in a superset round |
| `REST_OVERRUN` | $25\text{ s}$ | Real-world timer delay + logging reps/weight in Hevy app |

---

## 7. Hevy REST API Specifications & Gotchas

| Feature / Endpoint | Behavior & Constraints | Architectural Handling |
| :--- | :--- | :--- |
| `GET /v1/routines` | Max `pageSize = 10` | Automatic pagination loop in `fetch_routines()` |
| `GET /v1/workouts` | Max `pageSize = 10` | Automatic pagination loop in `fetch_workouts.py` |
| `GET /v1/exercise_templates` | Max `pageSize = 100` | Paginated catalog fetch with 30-day disk caching |
| `POST /v1/routines` | Requires `routine.folder_id` | Attached during initial routine creation |
| `PUT /v1/routines/{id}` | **Rejects `routine.folder_id`** | Stripped from payload during in-place updates |
| `DELETE /v1/routines/{id}` | **Endpoint does not exist** | Extra/stale routines reported for manual removal |
| `routine.notes` | Write-only in API | Synced during push, not relied upon during reconcile |
| `exercise.superset_id` | Integer grouping index | Exercises with matching integer share one superset |

---

## 8. Privacy & Personal Data Isolation Architecture

To ensure complete athlete privacy and zero data leakage:

1. **Storage Decoupling (`HEVY_DATA_DIR`):**
   - Personal workout logs default to local `data/workouts/` (gitignored), or can be mapped entirely outside the repository directory using `HEVY_DATA_DIR` (e.g. `export HEVY_DATA_DIR=~/.hevy/workouts` or `--data-dir`).
   - [`fetch_workouts.py`](scripts/fetch_workouts.py), [`calibrate_session_time.py`](scripts/calibrate_session_time.py), and [`analyze_history.py`](scripts/analyze_history.py) consume this path dynamically.
2. **Personal Program Isolation (`HEVY_PROGRAM`):**
   - Custom program definitions reside in gitignored `programs/program.py` or an external path specified via `export HEVY_PROGRAM=/path/to/my_program.py`.
3. **Automated Pre-Commit Privacy Gatekeeper:**
   - [`scripts/check_privacy_leaks.py`](scripts/check_privacy_leaks.py) scans staged files before every commit, aborting if workout logs (`data/workouts/*`), environment secrets (`.env*`), custom routines (`programs/program.py`), or raw API keys are detected.
   - Installed into `.git/hooks/pre-commit` via `python3 scripts/install_hooks.py`.
