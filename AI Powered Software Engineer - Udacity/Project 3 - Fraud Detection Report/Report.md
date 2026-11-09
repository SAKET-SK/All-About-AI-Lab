# Real-Time Fraud Detection Platform

**Solution architecture report (README edition)**
Author: Saket Khopkar, AI Software Engineer | Version 1.0 | November 2026 | Status: proposed architecture

> This README is a condensed version of the full report. The complete 27-page document, with every table and rationale, is in [`Fraud_Detection_Architecture_Report.pdf`](Fraud_Detection_Architecture_Report.pdf).

## Contents

1. [Overview](#1-overview)
2. [Requirements to technical objectives](#2-requirements-to-technical-objectives)
3. [Assumptions](#3-assumptions)
4. [Solution architecture](#4-solution-architecture)
5. [Microservices](#5-microservices)
6. [Event-driven design](#6-event-driven-design)
7. [End-to-end transaction flow](#7-end-to-end-transaction-flow)
8. [Compliance: capture and replay](#8-compliance-capture-and-replay)
9. [Frontend](#9-frontend)
10. [Service mesh and security](#10-service-mesh-and-security)
11. [Technology stack](#11-technology-stack)
12. [Scalability and elasticity](#12-scalability-and-elasticity)
13. [Resilience](#13-resilience)
14. [Observability and SLOs](#14-observability-and-slos)
15. [Peak usage and compliance events](#15-peak-usage-and-compliance-events)
16. [Deployment and migration](#16-deployment-and-migration)
17. [Trade-offs and risks](#17-trade-offs-and-risks)
18. [Next steps](#18-next-steps)

## 1. Overview

A major bank has moved its services to the cloud, but fraud detection still runs as an overnight batch. New regulation requires real-time detection. This design replaces the batch with an **event-driven streaming platform**: every transaction is ingested, enriched with features, scored by a machine-learning model, and given a decision, and fraud alerts are pushed to analysts within seconds.

Three ideas shape the design:

- **The event log is the backbone and the system of record.** Kafka carries every event between services, and an archive service writes every event to immutable (WORM) storage. This gives real-time processing, loose coupling, and replay for compliance.
- **Stateless, partitioned services scale elastically.** Each service scales on the metric that matters to it (mostly Kafka consumer lag), so cost follows demand. Only the messaging tier is sized for peak.
- **Observability and resilience are designed in.** OpenTelemetry signals are correlated, SLOs drive alerting, and every single point of failure has a mitigation and a recovery path.

**Headline targets**

| Target | Value |
|---|---|
| Detection latency | Transaction scored within 1 s (p99) of acceptance |
| Alert visibility | Alert on the analyst screen within 3 s (p99) |
| Throughput | 1,000 TPS peak, load-tested to 2,000 TPS |
| Durability | Zero loss of any acknowledged transaction |
| Compliance | Every event captured immutably and replayable |
| Cost | Compute scales with demand instead of being paid for at peak |

## 2. Requirements to technical objectives

| Business requirement | Technical objectives |
|---|---|
| Real-time analysis | Streaming processing, p99 scoring latency under 1 s, per-stage latency budgets |
| Captured and replayable transactions | Durable write before acknowledgement, immutable ordered archive, isolated deterministic replay |
| 1,000 TPS peak | Partitioned horizontal scaling, 2x tested headroom, back-pressure instead of collapse |
| Elastic scaling without constant peak cost | Stateless services, autoscaling on lag, node autoscaling, scheduled pre-scaling, spot capacity for batch |
| Real-time alerts for analysts | Server push (WebSocket) through a Backend for Frontend, alert visible within 3 s, safe reconnect |
| Observability and alerting | Correlated traces, metrics and logs, SLOs with burn-rate alerts, model-health monitoring |
| Financial-services standards (implicit) | Zero-trust security, tokenised PII, audit trail, tested disaster recovery |

## 3. Assumptions

- **Detection is near-real-time and advisory, not an inline gate.** Payments do not wait for the verdict, so a fraud-system outage cannot stop payments. A synchronous decision API could be added later.
- **Volume:** about 300 TPS on average, 1,000 TPS at peak, tested to 2,000 TPS. These are planning figures to confirm with the bank.
- **Data:** events carry tokenised identifiers, never raw card numbers. About 8 KB of events per transaction across all stages.
- **Retention:** 7 years for the immutable archive (to be confirmed by compliance).
- **Cloud:** AWS as the reference platform. The patterns are portable.
- **Model:** supplied by data science. A gradient-boosted tree model is the baseline because it is fast on CPU and explainable.
- **Alert volume:** roughly 0.1 to 1 percent of transactions raise high-confidence alerts.

## 4. Solution architecture

![Solution architecture](images/01-solution-architecture.png)

*Figure 1: components, interactions and the event backbone.*

| Part | What it achieves |
|---|---|
| WAF and API gateway | One authenticated, rate-limited entry point |
| Kafka and Schema Registry | Durable, ordered, replayable transport with contracts for every event |
| Services 1 to 4 (detection path) | Turn a raw transaction into a decision in under a second |
| Services 5, 6 and 9 (analyst path) | Queryable results and alerts visible in real time |
| Services 7 and 8 (compliance path) | Immutable capture and isolated replay |
| ML platform (service 10) | Offline training, evaluation, registry and promotion of models |

## 5. Microservices

| # | Service | Responsibility | Trigger | Output |
|---|---|---|---|---|
| 1 | Ingestion | Authenticate, validate, de-duplicate, stamp trace context, durably publish, acknowledge | HTTPS/gRPC request from a bank payment system | HTTP 202/4xx/429/503, `txn.received` |
| 2 | Feature Enrichment | Compute velocity, history, location and device features; keep online feature state | `txn.received`, `alert.disposition` | `txn.enriched` |
| 3 | Fraud Scoring | Run the promoted model; return score, confidence and top factors | `txn.enriched`, `model.lifecycle` | `txn.scored` |
| 4 | Decision & Alerting | Apply versioned policy; classify FRAUD, REVIEW or CLEAR | `txn.scored` | `txn.decided`, `fraud.alert.raised` |
| 5 | Alert Query & Case | Read model, search, assignment, analyst dispositions | Decision and alert events; queries from the BFF | Query results, `alert.disposition` |
| 6 | Notification & Real-time Gateway | Push alerts to browsers and external channels | `fraud.alert.raised`, WebSocket connect | Pushed messages |
| 7 | Archive | Write every event immutably with hash manifests | All topics | WORM objects, reconciliation metrics |
| 8 | Replay | Run approved replays in isolation and produce audit reports | `replay.command` | `txn.replay.received`, report |
| 9 | Analyst BFF | UI-shaped APIs, caching, authorisation | HTTPS request from the SPA | JSON, commands |
| 10 | ML Platform | Train, evaluate, register, promote models; monitor drift | Schedule, drift alert, new labels | Model artifacts, `model.lifecycle` |

**Why these boundaries:** enrichment (I/O and state heavy) is separate from scoring (CPU heavy). Decision is separate so the business can change thresholds without redeploying a model. Archive is off the critical path. Notification scales with connected analysts, not event rate.

**Coupling:** asynchronous through Kafka by default. The main coupling is the event schemas, managed by a Schema Registry, backward-compatible evolution in CI and versioned topics. No service reads another service's database.

## 6. Event-driven design

![Event flow](images/02-event-flow.png)

*Figure 2: every event type, its publisher, trigger and consumers.*

| Event (topic) | Publisher | When | Consumers |
|---|---|---|---|
| `txn.received.v1` | Ingestion | After validation and durable acceptance | Enrichment, Archive |
| `txn.enriched.v1` | Enrichment | After features are computed | Scoring, Archive |
| `txn.scored.v1` | Scoring | After model inference | Decision, Alert Query, Archive |
| `txn.decided.v1` | Decision | After thresholds applied (every transaction) | Alert Query, Archive |
| `fraud.alert.raised.v1` | Decision | Only for high-confidence FRAUD | Notification, Alert Query, Archive |
| `alert.disposition.v1` | Alert Query & Case | Analyst confirms or rejects an alert | Enrichment, ML platform, Archive |
| `model.lifecycle.v1` | ML platform | Model promoted or rolled back | Scoring, Archive |
| `replay.command.v1` | Compliance API | Auditor submits an approved replay | Replay |
| `txn.replay.received.v1` | Replay | As archived events are re-published | Replay-mode pipeline |
| `replay.results.v1` | Replay-mode pipeline | As replayed decisions are produced | Replay |

**Envelope (shared by all events):**

```json
{
  "event_id": "0b6f...e1",
  "event_type": "txn.scored",
  "schema_version": "1.2",
  "occurred_at": "2026-11-06T09:14:22.418Z",
  "published_at": "2026-11-06T09:14:22.601Z",
  "correlation_id": "txn-8c41...",
  "causation_id": "event_id of the triggering event",
  "traceparent": "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01",
  "producer": "fraud-scoring@1.14.2",
  "replay_id": null,
  "payload": {}
}
```

**Key design choices**

- **Partition key is the account token**, so per-account ordering holds (velocity features depend on it). 48 partitions leave room to scale.
- **At-least-once delivery with idempotent consumers.** Offsets are committed after processing and consumers de-duplicate on `event_id`.
- **Event time, not processing time**, so replays reproduce results.
- **Retry, then park:** `topic.retry` with back-off, then `topic.dlq` with an alert. A bad message never blocks a partition.

**Deliberate deviations from pure event-driven design**

| Interaction | Style | Why |
|---|---|---|
| Bank payment system to Ingestion | Synchronous request/response | Source needs an acknowledgement and a back-pressure signal; ack only after the Kafka write is durable |
| BFF to Alert Query | Synchronous REST/GraphQL | A user waiting on a screen needs an immediate answer |
| Analyst disposition | Synchronous command, then event | Needs strong consistency; event published after the write |
| Alerts to the browser | WebSocket push | Kafka is not exposed to browsers |
| Feature lookup | Synchronous Redis access | Sub-millisecond state lookup within one service |
| Model distribution | Event carries a pointer, artifact fetched from storage | Model files are too large for events |
| Telemetry | Outside the event backbone | Telemetry problems must never affect transactions |
| Reconciliation | Scheduled batch job | Periodic completeness check against the source ledger |

## 7. End-to-end transaction flow

![Transaction flow](images/03-transaction-flow.png)

*Figure 3: one transaction from the payment system to the analyst's screen.*

Only the first and last hops are synchronous. Everything between is a chain of Kafka events.

| Stage | Typical (ms, cumulative) | p99 budget (ms) |
|---|---|---|
| 1. Ingestion validates, writes durably, acknowledges | 50 | 100 |
| 2. Kafka hop and Enrichment | 110 | 200 |
| 3. Kafka hop and Scoring | 190 | 250 |
| 4. Kafka hop and Decision | 225 | 100 |
| 5. Kafka hop and push to browser | 275 | 200 |
| 6. Browser renders the alert | 400 | 250 |

Stages 2 and 3 total 450 ms against the 1 s scoring SLO. Stages 2 to 6 total 1,000 ms against the 3 s alert SLO, leaving more than 2x margin for queueing and pauses.

**When something is slow or failing:** if Kafka is unreachable, ingestion returns 503 and the source retries with the same idempotency key. If a consumer falls behind, events wait in Kafka and autoscaling reacts. If Redis is down, enrichment continues with default features and marks events degraded. A message that cannot be processed goes to the dead-letter queue.

## 8. Compliance: capture and replay

![Compliance capture and replay](images/04-compliance-replay.png)

*Figure 4: continuous capture path and on-demand isolated replay path.*

**Capture:** the Archive service subscribes to every topic and writes columnar files partitioned by date and hour to WORM object storage (object lock, versioning, KMS encryption, cross-region replication). Hash manifests make tampering evident, and an hourly reconciliation compares counts against the ingestion log and the bank's ledger. It is never on the critical path.

**Replay:** an auditor submits a request through the Compliance API (role-based access plus a second approver). The Replay service re-publishes archived events, in order, to isolated `txn.replay.*` topics. A replay-mode deployment of the same enrichment, scoring and decision images processes them and an audit report is produced.

- **Isolation:** separate topics, consumer groups, quotas and a spot node pool. Replayed events carry a `replay_id` and never reach live analysts.
- **Determinism:** event-time processing, pinned model version, feature state rebuilt from ordered events.
- **Two modes:** audit replay (what was decided then) and reprocess (apply a different model or policy to history).

**Retention versus privacy:** events hold opaque tokens, and the token-to-person mapping lives in a separate vault. Destroying a vault entry (crypto-shredding) satisfies erasure without altering the archive. Legal teams must confirm this per regulation.

**Sizing (illustrative):** about 26 million transactions a day, 8 KB each, is roughly 207 GB raw and 52 GB compressed per day, so about 130 TB over 7 years, held mostly in cold tiers.

## 9. Frontend

![Frontend data flow](images/05-frontend-data-flow.png)

*Figure 5: snapshot through the BFF, live updates over WebSocket.*

- **Snapshot, then stream.** The React SPA loads the queue through the BFF (cursor pagination), then receives new alerts over WebSocket. No polling.
- **Sequence numbers.** If the client sees a gap or reconnects, it requests alerts since its last sequence number, so the UI is never silently stale.
- **Summary first, detail on demand.** Lists show compact summaries; full detail loads when an alert is opened.
- **Consistent commands.** Confirm, reject and assign go through the BFF to PostgreSQL.
- **Why a BFF:** UI-shaped APIs, fewer round trips, one place for caching and authorisation, no fraud logic.

| Cache layer | What | Lifetime |
|---|---|---|
| CDN | Static SPA bundle | Content-hashed, long expiry |
| Browser query cache | Recent query results | Stale-while-revalidate |
| BFF response cache (Redis) | Queue counts, top open alerts, KPIs | 5 to 30 s, invalidated by events |
| Pre-aggregation in Alert Query | Dashboard counters | Updated incrementally from events |

Performance techniques: virtualised lists, UI updates batched about 4 times per second, compressed lean payloads, automatic reconnect with back-off and jitter, and a polling fallback if WebSocket is blocked.

## 10. Service mesh and security

A service mesh (Istio, or Linkerd) provides mutual TLS and workload identity, consistent retries, timeouts and circuit breaking, canary traffic shifting, and uniform request metrics without code changes. It adds latency and a control plane to run, and it does not cover Kafka traffic (protected by Kafka TLS, authentication and ACLs). The data plane keeps its last configuration if the control plane is briefly down.

| Layer | Controls |
|---|---|
| Identity and access | SSO with MFA, workload identities, least privilege, two-person approval for replay, audited break-glass |
| Network | WAF and rate limiting, private networking for data stores, default-deny network policies |
| Data protection | TLS everywhere, KMS keys per data store (separate key for the archive), tokenised identifiers, PII scrubbing in telemetry |
| Supply chain | Secrets manager with rotation, signed images, vulnerability scanning |
| Auditability | Immutable event archive plus a separate audit log of admin and analyst actions |
| Model governance | Signed artifacts, registry approval, recorded model version and explanation, shadow then canary promotion |

## 11. Technology stack

| Layer | Choice | Why |
|---|---|---|
| Compute | Kubernetes (managed, multi-AZ) | Portable, mature autoscaling (HPA, KEDA, node autoscaler) |
| Event backbone | Apache Kafka (managed) with Schema Registry | Durable replayable log, ordering per key, high throughput |
| Stream processing | Kafka Streams | Stateful processing inside normal services, scales with partitions |
| Model serving | Model embedded in the scoring service (ONNX or native runtime) | No network hop, steady latency, simple scaling |
| Online features | Redis (clustered, multi-AZ) | Sub-millisecond, rebuildable from Kafka |
| Alerts and cases | PostgreSQL (managed, multi-AZ) | Transactional integrity, point-in-time recovery |
| Search | OpenSearch | Fast filtering and search, rebuildable from the log |
| Archive | Object storage with Object Lock, columnar files | Cheap, durable, immutable, queryable |
| Analytics | Parquet or Iceberg, serverless SQL, ephemeral Spark | Keeps analytic load off real-time stores |
| ML platform | Managed training and registry (SageMaker or MLflow) | Reproducible, versioned, approval workflow |
| Frontend | React, TypeScript, TanStack Query, WebSocket | Mature, typed, built-in stale-while-revalidate |
| Service mesh | Istio (or Linkerd) | mTLS, policy, canaries, telemetry as a platform feature |
| Observability | OpenTelemetry, Prometheus or Mimir, Loki, Tempo, Grafana, Alertmanager | Open standards, one pipeline, strong correlation |
| Delivery | Terraform, GitOps (Argo CD), CI with contract tests | Reproducible and auditable change |

## 12. Scalability and elasticity

![Scaling loop](images/06-scaling-loop.png)

*Figure 6: elastic scaling control loop.*

![Elastic scaling versus peak provisioning](images/07-elastic-scaling.png)

*Figure 7: illustrative day, elastic capacity versus provisioning for peak.*

**Microservices:** stateless services scale by adding replicas. Consumers scale on Kafka lag (KEDA), ingestion and the BFF on request rate and CPU. Scale-down is slower than scale-up, uses stabilisation windows and graceful shutdown, and placeholder pods keep spare nodes warm.

| Service | Scaling signal | Min to max (illustrative) |
|---|---|---|
| Ingestion | Request rate, CPU, p99 latency | 3 to 12 |
| Feature Enrichment | Consumer lag | 3 to 12 |
| Fraud Scoring | Consumer lag, CPU | 3 to 20 (about 100 TPS per 2-vCPU pod) |
| Decision & Alerting | Consumer lag | 3 to 6 |
| Alert Query & Case | Request rate, lag | 3 to 8 |
| Notification gateway | Connected clients | 3 to 10 |
| Archive, Replay | Lag, job queue | 2 to 8, 0 to 10 |

In the illustrative profile (average about 290 TPS, peak 1,000), elastic scaling uses about 96 pod-hours a day against 240 for fixed peak provisioning, roughly **60 percent less compute**.

**Event messaging:** bandwidth is not the constraint (about 8 MB/s produced at peak). Parallelism equals partition count, so partitions are over-provisioned (48). Brokers scale horizontally but not instantly, so the **messaging tier is sized for peak plus headroom**. Quotas stop replay or a misbehaving consumer from starving live traffic.

**Analytic workloads:** training, compliance queries, replay and reports read from the archive and lake (never operational stores) on separate compute: ephemeral spot clusters for batch, a serverless SQL engine with per-team limits, replay on its own node pool, and pre-computed views for common audit reports.

## 13. Resilience

![Deployment and disaster recovery](images/08-deployment-dr.png)

*Figure 8: deployment view and disaster recovery (AWS as the reference).*

| Single point of failure | Mitigation | Residual risk |
|---|---|---|
| Kafka cluster | Three AZs, replication factor 3, min ISR 2, acks=all, cross-region mirror | Region loss: recover in DR region (RPO seconds) |
| Ingestion / edge | Stateless, 3+ pods across AZs; sources buffer and retry | Source must implement retry |
| Schema Registry | Replicated; clients cache schemas | Schema changes wait |
| Redis feature store | Clustered replicas; default features and degraded flag; rebuild from Kafka | Lower detection quality while degraded |
| Model registry | Scoring keeps last-known-good model | Model updates delayed |
| PostgreSQL | Multi-AZ failover, point-in-time recovery, cross-region replica | Brief failover pause |
| Notification gateway | Many pods; reconnect with resume; polling fallback | Slightly higher alert latency |
| Archive service | Kafka buffers 7 days; lag alert at 5 minutes | None if recovered in retention |
| Observability stack | Separate failure domain, HA, dead-man's switch | Reduced insight during an outage |
| Single region | Warm-standby DR region | RPO seconds, RTO tens of minutes |

**Durability rule:** a transaction is acknowledged to the bank only after it is durably written to three replicas.

| Data-loss scenario | Prevention | Recovery |
|---|---|---|
| Crash before the Kafka write | Never acknowledged; idempotency key | Source retries safely |
| Broker or AZ failure | Replication factor 3, min ISR 2, acks=all | Automatic leader election |
| Consumer crash | Offsets committed after processing; idempotent | Message reprocessed |
| Poison message | Retry then DLQ | Fix, then re-drive |
| Redis lost | Features are derived from events | Rebuild from Kafka or archive |
| Alert database corrupted | Point-in-time recovery; events archived | Restore, replay events since restore point |
| Archive object damaged | WORM, versioning, replica, hash manifests | Restore from replica, verify hashes |
| Regional disaster | Cross-region mirror and replicas | Fail over; reconcile against the bank's ledger and re-ingest any gap |

**Graceful degradation:** ingestion returns 429 rather than accept work it cannot process, scoring continues in degraded mode (and the degraded ratio is an SLO), non-essential work is shed first, and separate node pools keep live, replay and analytic work isolated.

## 14. Observability and SLOs

![Observability](images/09-observability.png)

*Figure 9: collection pipeline and correlation identifiers.*

| Signal | Instrumentation | Path | Retention |
|---|---|---|---|
| Traces | OpenTelemetry SDK; trace context in HTTP and Kafka headers | SDK, node agent, gateway (tail sampling), Tempo | 7 days; keep all errors, slow and alert traces plus 5 percent of the rest |
| Metrics | OpenTelemetry, Kafka and mesh exporters, synthetic canary | Collectors, Prometheus or Mimir | 15 days full resolution, 13 months downsampled |
| Logs | Structured JSON with trace_id, span_id, correlation_id; never PII | Agent, gateway (PII scrubbing), Loki | 30 days searchable, 1 year cold |

The business audit trail is the event archive, not logs or traces.

**Correlation:** one W3C `traceparent` follows the transaction across HTTP and Kafka (batch consumers use span links). Logs carry `trace_id`, latency histograms carry exemplars that link to traces, and `correlation_id` and `transaction_id` live on logs and spans (never as metric labels). `model_version` and `policy_version` tie quality changes to releases. A synthetic transaction every 10 seconds measures end-to-end latency even during quiet hours.

**Three key metrics**

| Key metric | Why | Alert condition |
|---|---|---|
| End-to-end detection latency | The real-time legal requirement | SLO burn-rate alerts; page if the synthetic probe exceeds 3 s twice in a row |
| Consumer lag (offset and time-based) | Earliest sign of a bottleneck; drives autoscaling | Warn over 5 s for 2 minutes; page over 30 s; archive lag over 5 minutes |
| Model health (score drift, alert rate, degraded ratio) | A fast but wrong system is worse than a slow one | PSI over 0.2 for 1 hour; alert rate outside 3 standard deviations; degraded ratio over 0.5 percent |

**SLOs (30-day rolling window)**

| SLO | Objective |
|---|---|
| 1. Detection latency | 99% of transactions scored within 1 s of acceptance; 99.9% within 5 s |
| 2. Alert visibility | 99% of fraud alerts visible in the analyst UI within 3 s of acceptance |
| 3. Ingestion | 99% of POST /v1/transactions under 100 ms; 99.9% non-5xx (excluding 429s for clients over agreed rates) |
| 4. Capture completeness | 99.999% of accepted transactions in the archive within 5 minutes; 100% within 24 hours |
| 5. Analyst API | 99% of GET calls from the UI to the BFF under 300 ms |
| 6. Scoring quality of service | 99.5% of daily transactions scored by the current model with complete features |

**Alerting:** alert on symptoms (SLOs) and investigate causes (lag, errors, saturation). Multi-window burn-rate alerts page when 2 percent of the monthly budget burns in 1 hour (confirmed over 5 minutes) or 5 percent in 6 hours (confirmed over 30 minutes), and open a ticket at 10 percent over 3 days. Alertmanager routes to PagerDuty and Slack, and a dead-man's switch detects a silent observability pipeline.

## 15. Peak usage and compliance events

| Event | Proactive measures |
|---|---|
| End of financial year, month end | Calendar-driven pre-scaling, raised minimum replicas, 2x load test beforehand, pre-computed reports, change freeze |
| Retail peaks | Pre-scale from last year's curve plus margin, confirm cloud quotas, verify Kafka headroom, double the on-call roster |
| Compliance audit | Replay on its own node pool, topics and quotas, throttled and off-peak; query workload limits; pre-built audit reports; early notice to reserve capacity |
| Fraud attack or alert storm | Alert grouping, per-queue rate limiting, severity routing, auto-escalation to a duty manager |
| Model or policy rollout in busy periods | Freeze windows, shadow then canary with automatic rollback |
| AZ or region outage at peak | Capacity sized so any two AZs can carry peak; tested failover runbook; quarterly game days |

## 16. Deployment and migration

**Reference deployment on AWS**

| Component | AWS service | Adaptation to watch |
|---|---|---|
| Kubernetes | EKS with Karpenter | Plan pod IP capacity; placeholder pods hide node start time |
| Kafka | Amazon MSK (or Confluent Cloud) | Broker and partition limits; provision for peak; tiered storage |
| Redis | ElastiCache (cluster mode, multi-AZ) | Not replicated cross-region (rebuilt) |
| PostgreSQL | Aurora PostgreSQL with Global Database | Connection pooling; failover takes tens of seconds |
| Search | Amazon OpenSearch Service | Multi-AZ with standby |
| Archive | S3 with Object Lock, replication, lifecycle tiers | Separate locked-down security account |
| ML and analytics | SageMaker, Athena and Glue, EMR Serverless | Spot for training; workgroup limits |
| Edge and DNS | CloudFront, WAF, load balancer, Route 53 failover | Health-checked failover to the DR region |
| Keys and secrets | KMS (separate archive keys), Secrets Manager | Key policies restrict archive decryption |

Use separate accounts for production, the security and archive vault, shared networking and non-production. The same design maps to Azure or GCP.

**Migration from the legacy batch system (strangler fig)**

| Phase | Activity | Exit criteria |
|---|---|---|
| 0. Foundations | Landing zone, Kafka, observability, CI/CD, security reviews | Platform passes security and resilience review |
| 1. Shadow mode | Mirror live transactions, compare with legacy and confirmed fraud | Detection at least equal to legacy; SLO 1 and 4 met for 30 days |
| 2. Analyst pilot | Small team uses the new UI alongside legacy tools | Analyst acceptance; alert quality validated |
| 3. Gradual cutover | Move traffic by segment; legacy stays as fallback | DR test passed; replay verified by compliance |
| 4. Decommission | Retire legacy; retain its historical results | Sign-off from risk and compliance |

## 17. Trade-offs and risks

| Decision | Benefit | Cost or risk | Why it is worthwhile |
|---|---|---|---|
| Detect after authorisation (advisory) | Fraud-system issues cannot stop payments | A fraudulent payment may complete first | Matches the requirement; a synchronous decision API can reuse the scoring components later |
| Event-driven, eventually consistent | Decoupling, burst absorption, replay | Read models lag by milliseconds to seconds | Alerts are advisory; analyst actions use strongly consistent writes |
| Kafka rather than a simple queue | Replay, per-key ordering, many consumers | Operational complexity, shared dependency | Replay and ordering are core requirements |
| At-least-once plus idempotency | Simple, fast, proven | Consumers must handle duplicates | Standard pattern; exactly-once only where needed |
| Ten components, not a monolith | Independent scaling and fault isolation | More deployments and network paths | Scaling profiles genuinely differ |
| Service mesh | mTLS and policy for all services | Latency and a control plane | Zero-trust is expected in banking |
| Messaging tier sized for peak | Predictable under surge | Pays for peak brokers always | Small share of cost; elasticity is in compute |
| Immutable archive | Strong audit evidence | Conflicts with erasure rights; storage cost | Tokenisation with crypto-shredding; cold tiers |
| Model embedded in scoring | Lower, steadier latency | Model and service releases are coupled | Small models today; a model server is an easy later change |
| Warm-standby DR, not active-active | Lower cost and complexity | Recovery takes tens of minutes | Fits an advisory system; reconciliation closes the gap |
| High-confidence alert threshold | Less analyst fatigue | Some fraud lands in the REVIEW band | Policy is tunable without redeploying a model |
| Tail-based trace sampling | Keeps important traces affordably | Normal traces are sampled | Compliance relies on the archive, not traces |

**Principal risks:** model drift and governance, alert fatigue and false positives, hot partitions from very busy accounts, schema evolution over seven years, operational skills for Kafka, Kubernetes and the mesh, regulatory variation across jurisdictions, and replay determinism (needs versioned models, policies and feature logic).

## 18. Next steps

1. Confirm volume, retention and the inline-blocking assumption with the business, risk and compliance.
2. Build a thin vertical slice (ingest, enrich, score, alert) and load test to 2,000 TPS.
3. Prove replay determinism with compliance using real historical samples.
4. Run a first disaster-recovery game day and start shadow mode against the legacy system.

## Repository layout

```
fraud-detection-architecture/
├── README.md                                   (this file)
├── Fraud_Detection_Architecture_Report.pdf     (full 27-page report)
└── images/                                     (9 diagrams used above)
```
