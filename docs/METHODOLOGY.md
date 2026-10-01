# Methodology frozen with Draft 1

## What an hour and a session mean

TraceLab's accounting unit is a **session/model group**, not a request and not reliably a complete parent/child workflow. Runs are assigned to their first priceable model; mixed-model calls retain their own prices. Groups unite runs with the same provider, pseudonymous contributor, session and assigned model. Residual priceable Codex rounds with usable timestamps may become synthetic-start runs. Missing timing and unpriceable-model exclusions follow the original audited code. Source identities are used only in memory in the full rebuild; they are not exported.

Within each group, merge run windows. Preserve the union of model-response intervals and known machine-tool execution, including finished shell continuation chains. Remove identified human-only approval waits; simultaneous machine/model work takes precedence. Exclude idle time between distinct run windows. Cap each remaining uncovered within-run interval at 300 seconds in the report (60/30-second sensitivities are also retained). **Known tool/model work is never truncated by this cap.** Uncovered time is not proven human time.

WEKA's unit is a **root session tree**, containing parent and child calls. Its numerator includes both; its wall clock unions their response intervals rather than summing overlapping durations. It retains up to 300 seconds of each gap between response intervals within that root. There is no cross-root timeline union. Without tool labels, gaps cannot be separated reliably into human versus tool waits. The primary eligibility clock drops gaps at or above 300 seconds; the report's cap300 clock retains 300 seconds of those gaps. These are different operations.

Neither denominator is pure generation time. TraceLab and WEKA group semantics and available timing evidence differ. Do not infer that matching pooled rates imply equal tasks, tail distributions, root-tree coverage, or hardware replay intensity.

## Costs, tokens and sample membership

Pooled rate = sum of API-equivalent cost / sum of adjusted hours. All included groups contribute, including short groups. Plotted percentiles/ECDFs weight each eligible group equally, using the original fixed requirement of at least five primary active minutes. Membership is fixed when comparing alternative caps. Quantiles use linear interpolation. A median session rate is not a pooled rate; quantiles of summed costs cannot be calculated by summing token-component quantiles.

Figure 3 uses retained-cache accounting, a 300-second gap cap, and the all-nonread-written GPT-5.6 scenario. Claude >500k subsets include the **whole group** if any included call strictly exceeds 500,000 input-context tokens. They are not only the portion of a session above 500k. Subset rows overlap full cohorts and must not be added again.

The four main rows contain 3,390 session/model groups but 3,382 distinct source sessions: four source sessions appear in both GPT rows and four in both Claude rows. Source-session counts across models are therefore not additive. Figure 3 has 1,069/206/1,947/168 pooled groups for GPT-5.5/GPT-5.6 Sol/Opus 4.8/Fable 5; plotted groups are 513/140/855/55. The >500k subsets have 48/10 pooled and 48/9 plotted groups. Five unpriced mixed calls in the GPT-5.5 group are omitted from cost but retained in its timeline. Seven mixed, priceable Fable calls use their own tariffs.

Figure 4 pools seven shared Claude model labels without reweighting their shares: Fable 5, Opus 4.8/4.7/4.6, Sonnet 4.6/4.5, Haiku 4.5. The dated Sonnet 4.5 alias is canonicalized. It includes 5,079 TraceLab groups and 393 WEKA roots. These source groups contain 98,827 WEKA calls, including 42,029 children. Non-read input means all input not counted as cache reads, **not necessarily novel text**. Input = cached input + non-read input in every scenario.

## Cache reconstruction and prices

TraceLab recorded categories supply the baseline. The retained-cache counterfactual uses the audited context-length transform only for qualifying user-start events with a same-session, same-model predecessor and an observed idle gap exceeding the saved TTL threshold: GPT-5.6 Sol 1,800 seconds, GPT-5.5 86,400 seconds, and 300 seconds for other model labels in the frozen implementation (including Claude). The original implementation does not extend the Sol-specific threshold to every GPT-5.6 variant. See `cache.load_cache_states` for precise event and context-length gates. This is a heuristic, not observed provider cache capacity or proof of achievable billing. It changes token allocation/cost, not recorded latency.

WEKA provides prefix-block hashes, not billed Anthropic cache counters. Only **previously completed same-model** requests are candidates; overlapping unfinished calls cannot provide future cache. `recent` checks the latest completed same-model request globally and in-stream. `ttl300` additionally requires completion within 300 seconds. `ideal` searches all completed same-model prefixes without expiry. The main retained comparison uses TraceLab retained versus WEKA ideal. Prefix matching is block-granular and capped by input length; output tokens are unchanged.

WEKA's input counts derive from 64-token prefix blocks rather than true tokenization. The source card documents occasional overcount and a 990,016-token per-request filtering limit. Do not describe the resulting token amounts as exact invoices or assume all >500k groups ran at full 1M context.

`data/prices.json` freezes the saved September 8 overlay; Claude source tariffs were collected August 21, 2026, and Codex standard tariffs rechecked September 14. No current pricing lookup occurs during builds. GPT-5.6's unobserved write allocation is represented by two explicit scenarios: all nonreads written versus no write surcharge. The main chart uses the former. Models with the saved long-context flag use the existing >272k input multiplier (2x input and 1.5x output). Fast-mode execution is not inferred from traces or simulated. No speed changes accompany repricing.

## InferenceX and economics

The September 15 UTC benchmark snapshot has 722 records. The report excludes GLM 5.1 and holds VR200 out of benchmark comparisons; the snapshot retains their records for provenance. Normalize physical GPU counts including both prefill and decode pools for disaggregated runs. Aggregate role-count inconsistencies are corrected only when TP×PP×PCP agrees with independently reported throughput normalization. There are 91 corrected records in this snapshot; unknown mismatches fail closed.

Construct speed/concurrency Pareto frontiers per model and hardware. Interpolate linearly in original units between bracketing frontier points; plotting log axes does not change interpolation. If the highest-concurrency frontier point exceeds the target speed, use it without extrapolation. No qualifying point is missing coverage, not zero capacity. These envelopes can connect different software/deployment configurations. P90 streaming speed is not a P90 latency guarantee and excludes time to first token; Table A1 separately selects measured Kimi configurations for TTFT.

Price measured input/output throughput using each endpoint's theoretical cached-input fraction and frozen API rates. Interpolate endpoint billing at the same weight used for concurrency. For each model/tier and speed target, select the hardware with lowest rental cost per client-hour; that need not maximize revenue/rental multiple K. MiniMax uses the <=512k tariff. Table 2 does not multiply source-corpus hourly costs by benchmark clients.

Capacity arithmetic: sessions/GPU = G×K/S; effective GB300 equivalents = (HBM3E + u×HBM4) / 288 GB. Multiply these and allocation f for potential sessions. Default S=$30/hour, G=$5/GPU-hour, K=5–10, u=2 (sensitivity 1–4), f=100%. HBM totals are derived from cited public thresholds used as point assumptions, not a reproduced proprietary forecast. 2026/2027 cumulative supply includes eligible shipments since 2025, not just that year's shipments. B4 extends the cost grid to $2.5–$200 and open-model scenarios. B5 applies n+(1−n)r for accelerator mix. Manufacturer specifications in Tables 3/C1 are frozen cited constants, not empirical analyses.

## Replay clocks are a separate measurement

The optional artifact audit covers 13 sampled configurations across nine runs, **not every snapshot endpoint**. They pin SemiAnalysis's harness commit `754356e9a39acc6cc6afb242d123bb57c3fb6f75`, with a 300-second per-root runtime idle watchdog and a 10-second system-wide guard. These differ from the current upstream documentation and from merely compressing a source timeline offline. Replay uses target-model service times, warmup, sampled starting points and root recycling.

Configured clients are session trees, not simultaneous model instances or decode concurrency. The five request-record audits union HTTP intervals per root within the actual dispatch window. That fraction is **request occupancy, not GPU utilization**. No-request time also includes tool work and scheduling; do not remove it all as human waiting. Three observed inter-request gaps exceed 301 seconds; this remains an unresolved boundary/coverage/runtime caveat, not a claim of perfectly enforced caps.

Reducing the source cap from 300 to 60 seconds raises WEKA pooled token rates about 55.42%, but TraceLab only about 0.038%. The selected five-minute source agreement is therefore conditional, not proof of interchangeable continuously working agent populations.
