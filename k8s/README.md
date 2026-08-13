# Kubernetes Deployment

Manifests for running the full log-anomaly-dashboard stack in Kubernetes, with horizontal autoscaling for `ingestion` and `ml` — the two services that would actually see load scale with traffic.

Tested against Docker Desktop's built-in Kubernetes (a local `kind`-based single-node cluster). Should work against any standard cluster with minor adjustments (see Notes below).

## Prerequisites

- A local Kubernetes cluster (Docker Desktop's built-in Kubernetes is the simplest option — Settings → Kubernetes → Create cluster)
- `kubectl` (`brew install kubectl`)
- The application images already built locally: `docker-compose build`
- [metrics-server](#metrics-server) installed (required for the HPAs to function — see below)

## Deploy

Apply manifests in order (the numbering encodes real dependencies — e.g. Postgres before anything that connects to it):

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

Watch everything come up:

```bash
kubectl get pods -n log-anomaly -w
```

### One-time setup: run database migrations

`docs/migrate.py` and `docs/migrations/*.sql` are also copied into `ml/` (as `ml/migrate.py` / `ml/migrations/`) so they're baked into the `ml` image and can run as a proper Kubernetes Job — this creates `alert_state` (used for cross-replica Slack alert throttling) and applies any future schema changes the same way:

```bash
kubectl apply -f k8s/10-migrate-job.yaml
kubectl wait --for=condition=complete --timeout=60s job/migrate -n log-anomaly
kubectl logs -n log-anomaly job/migrate
```

**Known gotcha:** if you rebuild the `ml` image locally after already loading an older version into the cluster, Kubernetes can keep using a stale cached image under the `latest` tag (`imagePullPolicy: IfNotPresent` means "don't re-pull if a `latest` tag already exists locally," and Docker Desktop's Kubernetes doesn't always notice the tag now points to new content). If a rebuilt image doesn't seem to be picked up, force a rollout restart on the relevant Deployment (`kubectl rollout restart deployment/ml -n log-anomaly`), or tag the image explicitly (e.g. `docker tag log-anomaly-dashboard-ml:latest log-anomaly-dashboard-ml:v2`) and reference that tag in the manifest instead of relying on `latest`. This was hit and confirmed during development — the failing pod was found to be running an image digest from hours earlier despite a fresh local rebuild.

Re-running the Job is always safe — `migrate.py` tracks applied migrations in a `schema_migrations` table and skips anything already applied. Delete and re-apply the Job to run it again (`kubectl delete job migrate -n log-anomaly --ignore-not-found`).

### metrics-server

The HPAs need real CPU metrics to function. Docker Desktop's Kubernetes doesn't include metrics-server by default:

```bash
kubectl apply -f https://github.com/kubernetes-sigs/metrics-server/releases/latest/download/components.yaml
kubectl patch deployment metrics-server -n kube-system --type='json' \
  -p='[{"op": "add", "path": "/spec/template/spec/containers/0/args/-", "value": "--kubelet-insecure-tls"}]'
```

The `--kubelet-insecure-tls` flag is needed specifically because Docker Desktop's local cluster uses self-signed kubelet certs; a real cloud cluster typically wouldn't need this.

Verify it's working:

```bash
kubectl top pods -n log-anomaly
kubectl get hpa -n log-anomaly
```

## Access the dashboards

Docker Desktop's Kubernetes doesn't reliably expose NodePort services on `localhost` (a known local-networking quirk, not a manifest issue) — `port-forward` is the reliable option for local testing:

```bash
kubectl port-forward -n log-anomaly svc/frontend 3000:80 &
kubectl port-forward -n log-anomaly svc/dashboard 8501:8501 &
```

Then open:
- React dashboard: http://localhost:3000
- Streamlit dashboard: http://localhost:8501 (password: whatever's set in `02-secret.yaml`'s `DASHBOARD_PASSWORD` — `changeme` by default in this template, override it for anything beyond local testing)

## Verify autoscaling is real, not just configured

Watch the `ingestion` HPA scale up under load from the continuously-running `generator`:

```bash
kubectl get hpa -n log-anomaly -w
```

You should see `ingestion-hpa` scale from 1 → 2+ replicas once CPU utilization crosses 70%, entirely automatically.

## Notes

- **Images are loaded via Docker Desktop's shared image store**, not a container registry. Every Deployment uses `imagePullPolicy: IfNotPresent` and references locally-tagged images (e.g. `log-anomaly-dashboard-ml:latest`). This works because Docker Desktop's Kubernetes shares the same image store as `docker build`/`docker-compose build`. A cluster that isn't Docker Desktop (e.g. a real cloud cluster, or a standalone `kind`/`minikube` cluster) would need images pushed to a registry and the manifests updated with real image references instead.
- **`PYTHONUNBUFFERED=1` is set on the `generator` deployment.** Without it, Python's stdout buffering meant `kubectl logs` showed nothing for the running container even though it was actively sending logs — a real gotcha caught during testing, not a hypothetical one.
- **`DATABASE_URL` is a single pre-formed Secret value**, not composed from other env vars via `$(POSTGRES_USER)`-style interpolation. That interpolation syntax only works reliably between plain `value:` env vars defined in the same list — it silently failed when referencing `valueFrom.secretKeyRef` values, another real bug caught and fixed during testing (see git history for the exact failure).
