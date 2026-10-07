# AURIS Capability Ladder Audit

This ledger applies the user's thirteen-level learning and implementation order to the live repository. A topic is not marked complete merely because an endpoint, interface label, or model prompt exists.

| Level | Current state | Evidence in AURIS | Principal gap |
| --- | --- | --- | --- |
| 1 Foundations | Tested | Python services, bounded algorithms and data structures, authenticated APIs, SQLite migrations, workflow persistence, and release scripts | CI-backed production database operations and broader Git acceptance |
| 2 Machine learning | Integrated runtime | Pretrained speech, embedding, and language-model runtimes are connected through bounded adapters | AURIS does not train deep networks; no training-data or model-development pipeline is claimed |
| 3 LLM systems | Tested prototype | Local fast/quality inference routing, context budgets, token limits, embeddings, provider adapters, and warm-run telemetry | Quantization benchmarking, larger-context evaluation, and production cloud provider acceptance |
| 4 Retrieval | Tested prototype | Semantic plus lexical memory retrieval, evidence research, provenance, deduplication, and a deterministic operations graph | Measured hybrid fusion, learned reranking, production vector service, and full Graph RAG evaluation |
| 5 Context and tools | Tested prototype | Temporal memory, scoped context, structured decision outputs, signed tool envelopes, and explicit approval state | Long-horizon context quality and cross-device memory recovery |
| 6 Agents | Tested prototype | Supervisor, specialist routing, durable workflows, checkpoints, events, recovery, and verification | General MCP client/server fabric, distributed worker ownership, and arbitrary project sandboxing |
| 7 Multimodal and computer use | Live-tested prototype | Persistent speech input, neural speech output, temporary screen analysis, signed Windows control, and bounded UI Automation | Browser DOM automation, full duplex acoustic acceptance, broader visual checkpoints |
| 8 Distributed systems | Contract-tested prototype | Cloud API/device channel contracts, signed envelopes, leases, nonces, revocation, Android build, and local realtime brokers | Production cloud, trusted ingress, physical mobile enrolment, and cross-device continuity |
| 9 Security | Security-reviewed locally | Session/CSRF auth, DPAPI keys, least-privilege scopes, approvals, prompt-injection boundaries, sandbox rules, audit, emergency stop | Authenticode service, production identity/vault, independent penetration test |
| 10 Evaluation and trust | Tested initial slice | Verifier reports, evidence coverage, uncertainty states, Brier scoring, sample gates, and failure-preserving acceptance | Domain datasets, long-horizon evaluation, calibration beyond the minimum sample, external evaluation |
| 11 Causal and decision intelligence | Tested prototype | Hypotheses, counterevidence, weighted decisions, scenario utility, counterfactual deltas, a structured operational world model, and bounded direct-action causal interventions with explicit mediators, confounders, and non-identifiable downstream effects | Learned world models, empirically identified downstream causal graphs, and domain-specific simulation adapters |
| 12 Outcome and predictive intelligence | Live-tested prototype | Five-role council, verifier veto, expected-versus-actual outcomes, root cause, lessons, sample-gated performance, seven evidence-bound forecasts, and durable restart-safe threshold watches with cooldown, transition deduplication, local notification, voice/text control, and no-action policy | True multi-provider independence, longitudinal predictive evaluation, external-signal forecasts, remote notification delivery, and broader proactive-policy evaluation |
| 13 Advanced research | Research-only | The directives are preserved as a research horizon and require measurable evidence before exposure | Novel architecture experiments and quantum adapters; no quantum advantage is claimed or prioritized |

## Ordering Rule

New work should close measured gaps in Levels 1 through 12 before experimental Level 13 work. Reinforcement-learning ideas remain confined to bounded simulation or offline evaluation. Outcome feedback is advisory and cannot silently modify authorization, security policy, or model weights.
