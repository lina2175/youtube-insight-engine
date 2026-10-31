# Proposed next milestone — Phase 3B.0 offline integration contract

Status: proposal only, not implemented or authorized by the review. The product remains multi-channel; no fixed artist identity is assumed. Live use and persistence remain disabled in the Phase 3A path.

## Objective

Rehearse the extraction → normalization → transactional load → expiry/deletion chain using synthetic API-shaped HTTP fixtures, while preserving provenance and the real API client's existing contract. Resolve integration decisions before obtaining live data. This is not a dashboard, analytics or revenue phase.

## Current boundary that must remain intact

The Phase 2 `ExtractionSample` contains one `channel`, `videos`, `playlist` coverage and collection metadata. Phase 3A accepts a `dataset_kind='synthetic'` envelope with `channels`/`videos` lists, synthetic IDs, strict fields and bounded integer counts. SQLite v2 constrains every domain source to synthetic. A direct Phase 2 sample is intentionally rejected. Never solve that mismatch by renaming real IDs or relabeling actual API data as synthetic.

## Proposed implementation deliverables

1. **Mapping contract and field matrix.** Define a source-aware normalized observation boundary, separately from the synthetic-only entry point. Preserve provider IDs, channel association, aware UTC publication/collection timestamps, null counts and collection coverage. Specify which Phase 2 fields are stored, deferred or deliberately dropped: uploads playlist ID, descriptions, creator country, channel video count, tags, category, duration, captions, license and broadcast markers. Creator country is not viewer geography.
2. **Explicit quality decisions.** Phase 2 permits missing titles/channel IDs and nonnegative counts without a signed-64-bit upper bound; Phase 3A requires nonblank titles, complete channel references and strict Int64 counts. Decide and test rejection/quarantine behavior; do not fabricate titles, silently convert nulls to zero, infer ownership, truncate counts or omit rejected-row evidence. Decide clock-skew/chronology behavior explicitly.
3. **Synthetic API-shaped fixtures and adapter.** Use `httpx.MockTransport` with clearly fictional provider-shaped payloads. The harness must know they are fixtures and must not accept arbitrary live samples via a synthetic label. Exercise the real client methods with fake clock/sleep and verify the agreed projection through Pandas. Keep the current synthetic pipeline's rejection behavior intact.
4. **Offline transaction rehearsal.** Load only fictional mapped observations into a separate temporary database. Validate multi-channel ownership, idempotence and newer/older/equal conflicts. Propagate bounded/partial coverage into the run result. A missing ID in a limited page/batch is not a source-deletion instruction. A later page/batch failure must not publish a misleading complete run.
5. **Persistence design, not live enablement.** Specify the future versioned migration for provider IDs/provenance and additional metadata. Do not remove v2 synthetic constraints to accommodate real data during this milestone. If an offline test schema is required, isolate it and label it as synthetic; production/live schema changes need explicit follow-up scope.
6. **Retention/deletion rehearsal.** Use synthetic clocks and data to test no extension after failed refresh, exact expiry, independent parent/video expiry, selective source deletion versus transient unavailability, run-record minimization, and cascade/full purge. Design read-time freshness enforcement and global policy-change cleanup before exposing data. Include hypothetical future caches/exports/backups in the design without creating them.
7. **Operator evidence.** Provide one offline integration command and a report giving extraction counts, coverage, accepted/rejected/skipped rows, safe error categories and database outcomes. No API key or network should be needed; do not store raw response/error bodies in execution records.

## Acceptance scenarios

| Scenario | Required evidence |
| --- | --- |
| Two channels, multiple video pages, >50 IDs | Correct IDs/ownership; 50-ID batch cap; normalized projection agrees with expected rows |
| Hidden/missing/zero counts; large integers | Null vs zero preserved; no float rounding; overflow explicitly rejected |
| Missing optional title/channel association | Chosen quality policy documented and observable; no fabricated identity |
| Duplicate IDs and equal-time conflicts | Deterministic behavior; no silent conflicting overwrite |
| Bounded sample or missing videos | Coverage remains incomplete/unknown as appropriate; no mass deletion |
| Invalid key, quota, timeout, malformed data, later-batch failure | Safe outcomes; no partial successful load; failure evidence persists where possible |
| Repeated load, older update, newer update | Stable cardinality; correct timestamps; expiry not reset by replay |
| Expiry, explicit removal, parent cascade, purge | Expected remaining rows; no retained payload in run evidence |
| Offline transport guard | Any accidental real HTTPX request fails the test |

Run the full existing backend suite plus adapter integration cases, Ruff, all frontend tests, TypeScript and build. Keep live verification distinct from passing mocked tests.

## Later controlled live milestone — Phase 3B.1 (gated)

Before attempting any live sample:

- Review the current official YouTube terms, developer policies, key requirements and quota costs; record dated source clauses and concrete requirements, not an assumed universal 30-day permission.
- Configure a backend-only key securely, restrict it to YouTube Data API and supported server restrictions, and verify quota/usage controls. Do not put the key in chat, command arguments, frontend variables or logs.
- Use the supported environment settings to permit `www.googleapis.com`, `www.youtube.com` and `developers.google.com`; preserve proxy/TLS controls. Do not bypass destination restrictions.
- Select a channel explicitly. Verify the returned ID and public identity against its public profile/expected owner before relying on it. The optional Faouzia ID has not been verified.
- Make one explicitly bounded extraction of at most five entries, with no uncontrolled test-network calls and no automatic persistence. Validate its actual response in memory using the reviewed source-aware adapter. Report sanitized status/count/coverage only; never commit captured live payloads.
- Enable real storage only after a separately reviewed migration and current retention/expiry/deletion/read-freshness rules are implemented and tested. Logical SQL deletion alone is not an end-to-end retention guarantee.

Current official review targets:

- https://developers.google.com/youtube/terms/api-services-terms-of-service
- https://developers.google.com/youtube/terms/developer-policies
- https://developers.google.com/youtube/v3/docs
- https://developers.google.com/youtube/v3/determine_quota_cost

This proposal requires a new implementation instruction. No adapter, migration, live loading or later product feature was implemented by the current review.
