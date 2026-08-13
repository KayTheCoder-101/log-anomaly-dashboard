# Log Analysis Dashboard with Anomaly Detection

An end-to-end system that generates, ingests, stores, and analyzes application logs in real time — using two complementary machine learning models to automatically flag anomalous behavior (traffic spikes, server errors, suspicious IP activity), with real-time Slack alerting, two live dashboards, and a Kubernetes deployment with real horizontal autoscaling.

Built as a learning project with a deliberate focus on measuring and improving real system behavior, not just wiring components together. Evaluation and testing discipline surfaced and fixed **five real production-grade bugs** across the ML pipeline and the Kubernetes deployment — each with a documented root cause, fix, and verification. See [Evaluation Results](#evaluation-results) and [Bugs Found & Fixed](#bugs-found--fixed-through-evaluation-and-testing) below.

## Architecture

```mermaid
flowchart TD
    A[Log Generator<br/>synthetic traffic + injected anomalies] -->|POST /logs| B[Ingestion API<br/>FastAPI + SQLAlchemy]
    A2[LogHub Loader<br/>real NASA HTTP logs] -->|POST /logs| B
    B -->|writes| C[(PostgreSQL<br/>logs table)]
    B -->|POST /predict| D[Isolation Forest<br/>single-row scoring]
    B -->|POST /predict_lstm| E[LSTM Autoencoder<br/>20-log sequence window]
    D -->|writes anomaly flags| C
    E -->|writes anomaly flags| C
    B -->|alert if flagged| G[Slack Webhook<br/>throttled, shared state in Postgres]
    C -->|reads directly| F[Streamlit Dashboard<br/>password-gated]
    B -->|GET /logs, CORS-enabled| H[React Dashboard<br/>nginx-served static build]
```

Every service runs in its own Docker container with a healthcheck, orchestrated with Docker Compose for local development — and can also run as a fully autoscaling deployment in Kubernetes (see [Kubernetes Deployment](#kubernetes-deployment)). Both ML models run inside the same `ml` service, sharing a single feature-engineering module (`ml/features.py`) so training and serving always compute features identically — the exact discipline that caught two of the five bugs documented below.

## Tech Stack

| Layer | Tool |
|---|---|
| Log generation | Python, Faker, real NASA HTTP access logs (LogHub) |
| Ingestion API | FastAPI, SQLAlchemy |
| Database | PostgreSQL, with a lightweight tracked migration system |
| ML — point anomalies | scikit-learn (Isolation Forest) |
| ML — sequential anomalies | PyTorch (LSTM Autoencoder) |
| Dashboards | Streamlit (password-gated) and React + Vite (nginx-served, dual-model detection view) |
| Alerting | Slack Incoming Webhooks, cross-replica-safe throttling |
| Containers | Docker, Docker Compose, healthchecks on all services |
| Orchestration | Kubernetes (manifests + HorizontalPodAutoscalers for ingestion and ml) |
| Testing | pytest — 25 tests across all 3 Python services |
| CI | GitHub Actions — runs the real test suite, not just a build check |

## Features

- Two interchangeable log sources: a synthetic generator (Faker, with injected traffic spikes, repeated errors, and IP hammering) and a real-world loader for the [NASA HTTP access log dataset](https://ita.ee.lbl.gov/html/contrib/NASA-HTTP.html) (LogHub), toggled via `LOG_SOURCE` env var
- FastAPI ingestion service storing logs in PostgreSQL, scoring every log with **both** models in real time, with bounded retry on transient scoring failures
- **Isolation Forest** — trained on response time, status code, and a 60-second time-windowed per-IP request count, for fast single-row anomaly scoring
- **LSTM Autoencoder** — trained on 20-log sliding windows in chronological order, for detecting sequential/temporal patterns (e.g. traffic ramp-ups) that a row-by-row model structurally cannot see
- A repeatable evaluation harness (`generator/eval_run.py` + `ml/evaluate.py`) that sends a controlled batch of known-labeled normal/anomalous logs and computes precision, recall, F1, and a confusion matrix for both models against ground truth
- **Slack alerting** on any anomaly flagged by either model, throttled to avoid burst spam, with cooldown state shared in Postgres so it stays correct across restarts or multiple replicas
- **Two dashboards**: a password-gated Streamlit app (quick internal tool), and a React + Vite production-style dashboard served via nginx — with real navigation, a detail drawer per log, and a combined "IF + LSTM" indicator showing when both models agree (a genuine improvement over Streamlit's single-model view), consuming the ingestion API directly rather than querying Postgres
- **Kubernetes deployment** with real, demonstrated horizontal autoscaling for `ingestion` (1-5 replicas) and `ml` (1-3 replicas) based on live CPU metrics — not just manifests sitting untested in a folder
- Fully Dockerized — one command runs the entire pipeline; every service has a healthcheck
- 25 automated tests across ingestion, ml, and generator, run in CI on every push
- A lightweight tracked migration system (`docs/migrate.py` + `docs/migrations/`) instead of ad-hoc manual schema changes

## Evaluation Results

Both models are evaluated against a controlled batch of known-labeled anomalies (repeated server errors, IP hammering bursts) injected alongside normal traffic:

| Metric | Isolation Forest | LSTM Autoencoder |
|---|---|---|
| Precision | **1.000** | 0.905 |
| Recall | 0.319 | **0.826** |
| F1 score | 0.484 | **0.864** |

**Takeaway:** Isolation Forest is conservative — in this run it had zero false positives, but still misses roughly 2 out of every 3 real anomalies. The LSTM catches far more real anomalies (82.6% recall) by using sequential context instead of scoring each log in isolation, at some cost to precision. Which model is preferable depends on the operational trade-off between missed incidents and alert fatigue — in practice, a combination (e.g. LSTM for alerting, Isolation Forest for high-confidence auto-triage) is likely the best of both.

## Bugs Found & Fixed Through Evaluation and Testing

Five real bugs were found and fixed during development, each with a measured before/after or concrete verification — the kind of thing evaluation and testing are actually for:

1. **Train/serve feature skew.** The Isolation Forest was trained on an *all-time cumulative* per-IP request count but served on a count computed incrementally as each log arrived. Fixing this (matching both to the same 60-second time-windowed count, in a shared `ml/features.py` module) roughly doubled recall.
2. **ML service startup race condition.** `ingestion` could start accepting traffic before `ml` had finished loading its models (including the larger PyTorch LSTM), silently leaving early logs unscored. Fixed with a proper `/health`-based Docker healthcheck and a `service_healthy` dependency, verified by re-running the evaluation harness with 0 missing scores (down from 51/269).
3. **Silent pandas data corruption.** `compute_windowed_ip_count`'s use of `groupby(...).apply(...)` had a known pandas edge case where per-group results could get silently reshaped into a DataFrame of NaNs instead of concatenated into a flat Series — with no error raised. Found by the very first unit test written for this function; fixed by building the result explicitly via `pd.concat`. Retraining after the fix visibly improved both models' evaluation scores.
4. **Kubernetes `$(VAR)`-style env var interpolation silently failing.** An attempt to compose `DATABASE_URL` from `$(POSTGRES_USER)`/`$(POSTGRES_PASSWORD)` inside a plain `value:` field passed the literal unexpanded string through instead of substituting — that syntax only reliably works between plain `value:` env vars in the same list, not when referencing `valueFrom.secretKeyRef` values. Caused `ingestion` and `ml` to CrashLoopBackOff with a Postgres auth failure. Fixed by storing a single pre-formed `DATABASE_URL` directly in the Kubernetes Secret.
5. **Python stdout buffering hiding logs in Kubernetes.** The `generator` pod showed zero output via `kubectl logs` despite the process actively running and sending traffic — Python's stdout is block-buffered by default when not attached to a terminal. Fixed with `PYTHONUNBUFFERED=1`.

## How to Run

```bash
git clone https://github.com/KayTheCoder-101/log-anomaly-dashboard.git
cd log-anomaly-dashboard
cp .env.example .env   # optional: fill in SLACK_WEBHOOK_URL / DASHBOARD_PASSWORD to enable those features
docker-compose up --build
```

Then open:
- React dashboard: http://localhost:3000
- Streamlit dashboard: http://localhost:8501
- Ingestion API docs: http://localhost:8000/docs
- ML scoring API docs: http://localhost:8001/docs

### Running with real data instead of synthetic

```bash
mkdir -p data/raw
curl -o data/raw/NASA_access_log_Jul95.gz https://ita.ee.lbl.gov/traces/NASA_access_log_Jul95.gz
gunzip data/raw/NASA_access_log_Jul95.gz
docker-compose run -e LOG_SOURCE=loghub generator
```

### Running the evaluation harness

```bash
docker-compose run -e GROUND_TRUTH_PATH=/data/ground_truth.jsonl generator python3 eval_run.py
docker-compose run -e GROUND_TRUTH_PATH=/data/ground_truth.jsonl ml python3 evaluate.py
```

### Retraining either model

```bash
docker-compose run ml python3 train.py        # Isolation Forest
docker-compose run ml python3 train_lstm.py   # LSTM Autoencoder
docker-compose restart ml
```

### Running the test suites

```bash
docker-compose run ml python3 -m pytest tests/ -v
docker-compose run generator python3 -m pytest tests/ -v
docker-compose run ingestion python3 -m pytest tests/ -v
```

### Applying database schema changes

Schema changes live as numbered SQL files in `docs/migrations/`, tracked in a `schema_migrations` table so re-running is always safe:

```bash
docker-compose run -e DATABASE_URL="postgresql://admin:admin123@postgres:5432/logdb" -v "$(pwd)/docs:/docs" --entrypoint python3 ml /docs/migrate.py
```

## Kubernetes Deployment

The full stack can also run in Kubernetes with real horizontal autoscaling for `ingestion` and `ml`. Full setup instructions, including the metrics-server dependency and known local-cluster gotchas, live in [`k8s/README.md`](k8s/README.md).

Quick start (against a local cluster, e.g. Docker Desktop's built-in Kubernetes):

```bash
kubectl apply -f k8s/00-namespace.yaml
kubectl apply -f k8s/01-config.yaml
kubectl apply -f k8s/02-secret.yaml
kubectl apply -f k8s/03-postgres.yaml
kubectl apply -f k8s/04-ml.yaml
kubectl apply -f k8s/05-ingestion.yaml
kubectl apply -f k8s/06-dashboard.yaml
kubectl apply -f k8s/07-frontend.yaml
kubectl apply -f k8s/08-generator.yaml
kubectl apply -f k8s/09-hpa.yaml
```

`ingestion` scales 1→5 replicas and `ml` scales 1→3 replicas based on live CPU utilization — verified in practice, not just configured (see `k8s/README.md` for how to watch it happen).

This deployment currently targets local clusters only (images are shared via Docker Desktop's local image store rather than pushed to a registry) — see Known Limitations below.

## Screenshots

**Dashboard Overview**
![Dashboard Overview](docs/screenshots/dashboard-overview.png)

**Live Anomaly Feed**
![Anomaly Feed](docs/screenshots/anomaly-feed.png)

## Database Schema

```sql
CREATE TABLE logs (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMP NOT NULL,
    source_ip VARCHAR(45) NOT NULL,
    endpoint VARCHAR(255) NOT NULL,
    method VARCHAR(10) NOT NULL,
    status_code INT NOT NULL,
    response_time_ms FLOAT,
    bytes_sent INT NOT NULL,
    user_agent TEXT,
    is_anomaly BOOLEAN DEFAULT NULL,
    anomaly_score FLOAT DEFAULT NULL,
    lstm_is_anomaly BOOLEAN DEFAULT NULL,
    lstm_anomaly_score FLOAT DEFAULT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE alert_state (
    id INT PRIMARY KEY DEFAULT 1,
    last_alert_sent_at TIMESTAMP
);
```

`response_time_ms` is nullable to accommodate real-world log sources (like NASA HTTP logs) that don't report it; both models handle this explicitly via a `has_response_time` feature flag plus median imputation, rather than silently failing or faking a value. `alert_state` holds a single shared row used to throttle Slack alerts consistently across restarts or multiple `ingestion` replicas — including the multiple replicas the Kubernetes HPA actually creates under load.

## Known Limitations

- **This is a local-only deployment story.** The Kubernetes manifests are tested and working against a local cluster (Docker Desktop's built-in Kubernetes), sharing its local Docker image store. A real cloud deployment would need images pushed to a container registry, an Ingress controller, TLS, and a real domain — none of which are set up here, by deliberate choice (see the project's cost/complexity discussion — an always-on cloud deployment wasn't judged worth the recurring cost for a portfolio project; local + this documentation is considered sufficient proof).
- The Streamlit dashboard still queries Postgres directly rather than through an API layer (the React dashboard, added later, consumes the ingestion API properly). Acceptable since Streamlit is the secondary/internal tool now.
- LSTM windowing recomputes per-IP request counts on every prediction, which is correctness-first but not optimized for high-throughput serving.
- No tests for the training scripts (`train.py`, `train_lstm.py`) or `predict_api.py` directly — only the shared `ml/features.py` feature-engineering module is unit tested. Training scripts are mostly I/O orchestration (DB reads, model fitting, file writes), which is expensive and low-value to unit test; the feature logic worth testing is already covered.
- No tests for `dashboard/app.py` or the React frontend — Streamlit apps are difficult to unit test meaningfully, and the React dashboard was validated through manual/visual testing rather than a JS test suite.
- Trained model artifacts (`.pkl`/`.pt`) are committed to git for convenience (clone-and-run works immediately). This doesn't scale well long-term; a production setup would use a model registry instead.
- The lightweight migration runner (`docs/migrate.py`) has no rollback support, by design — appropriately scoped for this project's size, but not a substitute for a full framework like Alembic at larger scale. It also isn't packaged for Kubernetes use yet — the `alert_state` table currently needs a manual one-time SQL command in a fresh cluster (documented in `k8s/README.md`).

## Future Improvements

- Push images to a real container registry and adapt the Kubernetes manifests for a cloud cluster, if this project ever needs to run somewhere reachable from the internet
- Package `docs/migrate.py` as a Kubernetes Job instead of a manual one-time SQL command
- Optimize LSTM serving-time feature computation (e.g. a rolling cache instead of recomputing per-window)
- Explore an ensemble approach that combines both models' scores rather than reporting them independently
- Add automated tests for the React frontend (component/interaction tests)
