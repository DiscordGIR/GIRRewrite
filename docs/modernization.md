# Modernization implementation and rollout

This branch starts the incremental modernization proposed in the architecture
review. It is a first rollout batch, not completion of the full migration.
No live Discord actions, production database migrations, or deployments have
been performed.

## Review order

Each change is committed separately, in dependency order:

| Commit | Change |
| --- | --- |
| `af7b28c` | Exclude secrets from images; inject environment through Compose |
| `70c414f` | Atomic case-number reservation; regression harness and CI |
| `bcea227` | Await scheduled operations; deterministic IDs; safe timeout expiry |
| `1dc4194` | Shared HTTP connections, explicit shutdown, validated external catalogs |
| `e41c6d6` | Atomic XP awards in a bounded worker pool; remove redundant filter query |
| `c87f021` | Move synchronous Spotify calls off the event loop |
| `a055c4b` | Bounded image queue; inexpensive abuse checks before image inspection |
| `af2ae1b` | Timeout ownership checks on dismissal; shared mute/unmute commands |
| `efc36c3` | Preserve historical case dates; continue birthdays after missing members |
| `03af431` | Runtime measurements; explicit database startup; extension-loading smoke test |
| `cb1c8b2` | Shared ban execution; record successful actions after Discord accepts them |
| `16ec679` | Idempotent setup and profile creation |
| `4216922` | Shared kick execution; record successful removals |
| `47949f9` | Bounded webhook-log delivery with shared HTTP pooling |
| `0eed001` | Remove obsolete moderation reads; offload command-ban lookup |
| `4ebe3f6` | Real MongoDB service for integration tests in CI |
| `d7ec0f2` | Apply image deadlines before moderation begins |
| `8c4e6a7` | Run concurrency assertions against real MongoDB, not mongomock |

The local signing agent failed during this work. The rebased commits are unsigned;
the repository's signing configuration is unchanged.

## Validation

```sh
python -m pip install -r requirements-test.txt
python -m unittest discover -s tests -v
python -m compileall -q main.py cogs data utils tests
```

Local result: 39 discovered tests, 36 passed, 3 explicitly skipped because they
require a real MongoDB server. The tests load all configured extensions and close
the bot with example configuration, no credentials, and no Discord connection.
Local execution used Python 3.9 and the repository's pinned runtime packages;
CI uses Python 3.10. The full image build and real-MongoDB test run were not
verified locally because the Docker daemon was unavailable. CI has been configured
but has not been run remotely from this task.

For an **isolated disposable** MongoDB instance:

```sh
GIR_TEST_MONGO_URI=mongodb://127.0.0.1:27017/gir_tests \
  python -m unittest discover -s tests -v
```

These integration tests drop test collections in `gir_tests`. Never point them
at a production server. Mongomock does not implement atomic find-and-modify,
so its threaded results cannot establish production concurrency guarantees.

## Behavior and operational changes

- Existing-user XP awards use one database operation when the level is unchanged.
  New profiles and level changes need extra operations. XP amount and legacy
  thresholds are preserved; no XP cooldown or lossy batching was introduced.
- Database workers are limited to four and Spotify workers to two. Cancellation
  does not free a worker slot until its synchronous operation has actually ended.
- Image processing has two workers and at most 32 queued messages. On saturation,
  additional scans are skipped and counted; overload is never evidence of abuse.
  Inspection and evidence collection have a 30-second deadline. Discord actions
  and report delivery are outside that deadline. This bounds memory at the cost
  of explicitly reduced image coverage under overload.
- Discord expires native timeouts. Old expiry jobs no longer actively remove a
  timeout and therefore cannot clear a still-active punishment. Expiry logs still
  depend on a successful scheduled callback.
- Report dismissal fetches current member state and compares the exact timeout
  deadline. A report whose timeout failed cannot unmute someone. Discord does not
  provide compare-and-swap timeout updates: an external moderator action between
  the fetch and update is still a race requiring operational awareness.
- Scheduler callback names remain compatible with stored jobs. New IDs are
  namespaced, and matching old IDs are removed when jobs are replaced/cancelled.
  Old randomly named new-member jobs are consolidated when rescheduled.
- Application webhook logging queues at most 200 fragments. On overload, excess
  fragments are dropped; stdout remains the authoritative log. Startup/shutdown
  logs are not forwarded, and queued fragments are not guaranteed on shutdown.
- Runtime logs every minute report loop-lag p95/max, RSS, completed database
  worker operations, cumulative worker time, image backlog, and skipped images.
  Worker-operation counts are not MongoDB query counts. These metrics establish
  a baseline; no production latency or throughput improvement is claimed yet.
- Case numbers may have gaps after failed actions. Bans/kicks are written as
  successful cases only after Discord accepts the action. A database failure
  after a successful Discord action still needs durable reconciliation work.

## Staging gate for this batch

1. Run CI, including the real-MongoDB pass, and build the production image.
2. Back up the database, including `jobs`, and verify restore in isolation.
3. Use a staging guild to check manual/automatic mute, ban, kick, report dismissal,
   existing persisted jobs, permission failures, reconnect, and graceful shutdown.
4. Replay representative normal traffic and sustained image floods. Measure event
   loop lag, command acknowledgements, moderation outcomes, MongoDB operations,
   memory, and skipped scans. Adjust queue sizes against measured workload.
5. Observe at least one scheduled timeout, birthday removal, and reminder across
   restart. Verify newer punishments survive old report dismissal and expiry jobs.

Suggested initial performance target: p99 event-loop lag below 100 ms at an agreed
replay load, bounded image backlog/RSS, and no lost/duplicate punishments. The
minute-level logger reports p95/max; use a dedicated replay sampler for p99.

Rolling back application code alone does not restore old scheduler cancellation
semantics: the old code cannot recognize namespaced job IDs. Reconcile/restore
the jobs collection together with an application rollback, accounting for jobs
already delivered. Avoid simultaneously running old and new schedulers against
one job store.

## Remaining work, in dependency order

### 1. Complete moderation recovery and persistent reports

Introduce a durable operation/report model with operation IDs, target/action,
punishment version, and pending/applied/failed/resolved state. Make case insertion
idempotent, record reconciliation work before Discord actions, and retry only
unfinished notifications. Restore report views with stable component IDs on
startup. Test crashes at every persistence/Discord boundary and competing clicks.
Current report views still live in memory and do not survive restart.

### 2. Extend the async persistence boundary

Move remaining synchronous queries, saves, cache misses, and report/history reads
behind explicit async repositories. The worker pool is an incremental bridge;
most legacy service methods remain synchronous. Return immutable snapshots rather
than lazy MongoEngine querysets across worker boundaries. Add operation timing
and query-count instrumentation, then assess native PyMongo Async against the
same replay workload. Do not introduce a second driver without compatibility and
schema tests.

### 3. Inspect production query shapes before changing storage

Read actual indexes and explain plans, case-array sizes, leaderboard access, and
report query frequency. Add measured indexes. Backfill individual case documents
with existing IDs and original dates, compare counts and sampled histories, then
switch paginated reads behind a reversible configuration flag. Keep old data
until reconciliation and rollback exercises pass. No schema migration is included
in this batch.

### 4. Centralize detection and configuration

Have filter/anti-raid detectors return findings to one coordinator so independent
listeners cannot issue conflicting punishments or duplicate reports. Establish
message-level idempotency, explicit priority, and tests for detector combinations.
Cache validated configuration snapshots and preprocessed filter/catalog data;
invalidate after successful writes. Replace repeated reconnect history scans with
managed refresh tasks and isolate optional-feed outages. Complete the application
factory and remove the remaining configuration/logger import side effects.

### 5. Upgrade and harden deployment

Audit dependency advisories and compatibility, choose a supported Python/runtime
baseline, lock direct and transitive dependencies, and test libvips fingerprints
before image-library upgrades. Add a non-root image with writable token storage,
health/readiness reporting, backup drills, and separate optional integration
configuration. Reduce gateway intents only after documenting member/presence
requirements. The existing Python image and package versions remain unchanged.

### 6. Expand coverage and establish measured acceptance

Add golden tests for Unicode/invite/word filtering, scam-image false positives,
permission tiers, report restarts, and concurrent moderation. Measure command
latency and action completion separately from optional notifications. Review
giveaway idempotency, warn lifting, profile transfer, and aggregate statistics.
Keep each behavior change and migration independently reviewable in its own commit.
