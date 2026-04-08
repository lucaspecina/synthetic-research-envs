#!/usr/bin/env python
"""P06 G.1 — Isolated compiler recompilation harness.

Re-invokes ONLY oi_sq_compiler.compile_sq_to_specs on the frozen
sub-question text_glosses from a baseline batch, using the new prompt
in working tree. Diffs the resulting verification_specs against the
frozen baseline.

Crucially this does NOT touch the solver, the orchestrator, or
generate_src.py. The only stochastic component is the compiler LLM
itself, which is the component being tested. The default mode is
**no grounding** — observe what (kind, measurement, comparison)
signatures the new prompt produces, not score them. The opt-in flag
`--ground-sanity` runs verify_atom on rerouted specs only.

Inputs (frozen, identical to what the original compiler saw):
  results/p05_canonical_batch/<case>/src.json   (problem + sub_questions_v2)

Outputs (per-case + batch summary):
  results/p06_recompile/<case>/recompile.json
  results/p06_recompile/_recompile_summary.json
  results/p06_recompile/_recompile_report.md   (human-readable G.1 verdict)

Per-SQ classification (the unit that maps to G.1 success criteria):

  kept                       — same set of structural signatures as the
                               frozen SQ
  route_causal               — frozen had at least one (adjust + pcor),
                               new uses the strict 2-arm causal route
                               (2 adjust + mean + difference + ref_arm)
  route_observational        — frozen had at least one (adjust + pcor),
                               new uses the strict observational route
                               (1 baseline/observe + pcor + identity)
  abstained                  — compiler returned an explicit empty array
                               via the new abstention contract
  compile_error              — LLM returned non-empty but no spec passed
                               AtomicSpec validation (e.g. still emitted
                               adjust + pcor → validator rejects)
  other_change               — different signature, neither route_* nor
                               kept (e.g. different number of specs,
                               unrelated kind change)

Aggregate metrics that map to G.1 success criteria:

  C1a — resolved_rate:       of SQs with frozen (adjust + pcor), fraction
                             whose status is route_causal, route_obs or
                             abstained (i.e. no longer emits adj+pcor and
                             either rerouted with role=required or
                             deliberately abstained)
  C1b — bad_replacement_rate: of SQs with frozen (adjust + pcor), fraction
                             whose status is compile_error or other_change.
                             High values mean the prompt removed adj+pcor
                             but failed to reroute it cleanly (damage,
                             not improvement). Denominator is the same
                             as C1a — they are complementary slices.
  C1c — reroute_quality:     of SQs classified as route_causal or
                             route_observational, per-component diagnostic
                             flags computed against the frozen *buggy*
                             specs only (not the whole SQ — comparing
                             against the whole SQ would mix unrelated
                             supports and penalize correct reroutes):
                               preserved_endpoints  (treatment & outcome
                                                     of the buggy spec
                                                     present in some new
                                                     required spec)
                               control_any_overlap  (any control variable
                                                     of the buggy spec
                                                     present in some new
                                                     required spec)
                               full_controls_preserved (all control vars
                                                     of the buggy spec
                                                     present in some new
                                                     required spec)
                               control_coverage     (|overlap| / |buggy
                                                     controls|, a ratio
                                                     not a boolean)
                               clean_compile        (the rerouted SQ has
                                                     no compile_warnings;
                                                     warnings indicate
                                                     LLM emitted invalid
                                                     extras that were
                                                     dropped)
                             Each flag is reported as a separate
                             fraction; the AND is reported separately
                             as `all_quality_checks_pass`.
  C2 — abstention_delta:     new_abstention_rate - frozen_abstention_rate
                             (positive = more abstentions; alarm if > 0.10)
  C5 — unaffected_regression: for cases without any frozen (adjust + pcor),
                             count how many SQs changed signature

C3 and C4 (calibration sets A/B) are produced by a separate fixture
(task #37) and are NOT computed here.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

# Inject repo root + load .env
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent.parent / ".env")
except ImportError:
    pass

sys.stdout.reconfigure(encoding="utf-8", errors="replace")


# ---------------------------------------------------------------------------
# World reconstruction (mirror p06_paired_run.py — deterministic from src.json)
# ---------------------------------------------------------------------------


def reconstruct_world(src: dict):
    """Reconstruct SCMWorld from frozen scm_construct args."""
    from sreg.models.scm_spec import SCMSpec
    from sreg.tools.scm_world_gen import SCMWorldGenTool

    scm_args = None
    for tc in src.get("process", {}).get("tools_called", []):
        if tc.get("tool") == "scm_construct":
            res = tc.get("result", {})
            if "world_id" in res or "error" not in res:
                scm_args = tc["args"]
                break
    if scm_args is None:
        for tc in src.get("process", {}).get("tools_called", []):
            if tc.get("tool") == "scm_construct":
                scm_args = tc["args"]
    if scm_args is None:
        raise ValueError("No scm_construct call found in src.json")

    if scm_args.get("edges") and isinstance(scm_args["edges"][0], dict):
        scm_args["edges"] = [(e["from"], e["to"]) for e in scm_args["edges"]]

    spec = SCMSpec(**scm_args)
    gen = SCMWorldGenTool()
    return gen.generate(spec, seed=42)


# ---------------------------------------------------------------------------
# LLM call factory (mirror orchestrator._call_text_model)
# ---------------------------------------------------------------------------


def build_text_llm(client, model: str):
    """Build a (system, user) -> str callable using Responses API."""

    def llm_call(system: str, user: str) -> str:
        resp = client.responses.create(
            model=model, instructions=system, input=user,
        )
        parts: list[str] = []
        for item in resp.output:
            if item.type == "message":
                for part in item.content:
                    if hasattr(part, "text"):
                        parts.append(part.text)
        return "".join(parts)

    return llm_call


# ---------------------------------------------------------------------------
# Spec signature extraction
# ---------------------------------------------------------------------------


def spec_signature(spec_dict: dict) -> dict[str, Any]:
    """Extract a structural fingerprint from a raw spec dict.

    The signature is a dict so we can include comparison.kind, ref_arm
    presence, n_arms and the role distribution — fields that distinguish
    a real causal route (2 adjust + difference + ref_arm) from a
    one-arm `adjust + mean + identity` that would otherwise look the
    same under the old (arm_kinds, meas_kind) tuple.

    Spec IDs, tolerances, exact arm labels and exact variable names are
    deliberately NOT in the signature — they vary with LLM stochasticity
    and do not change the verification semantics. Endpoint/control vars
    are surfaced separately via spec_endpoint_vars / spec_control_vars
    (see C1c reroute_quality).
    """
    arms = spec_dict.get("arms", []) or []
    arm_kinds = tuple(sorted(str(a.get("kind", "")) for a in arms))
    meas = spec_dict.get("measurement", {}) or {}
    meas_kind = str(meas.get("kind", ""))
    comp = spec_dict.get("comparison", {}) or {}
    comp_kind = str(comp.get("kind", ""))
    has_ref_arm = bool(comp.get("ref_arm"))
    return {
        "arm_kinds": arm_kinds,
        "n_arms": len(arms),
        "measurement": meas_kind,
        "comparison": comp_kind,
        "has_ref_arm": has_ref_arm,
    }


def is_adjust_pcor(sig: dict[str, Any]) -> bool:
    """The hybrid the validator now rejects: any adjust arm + partial_correlation."""
    return ("adjust" in sig["arm_kinds"]) and sig["measurement"] == "partial_correlation"


def is_causal_route(sig: dict[str, Any]) -> bool:
    """Strict causal route: 2 adjust arms + mean + difference + ref_arm.

    A one-arm `adjust + mean + identity` would NOT count — that is a
    different verification shape (single E[Y|do(X=x)], not a contrast).
    """
    return (
        sig["arm_kinds"] == ("adjust", "adjust")
        and sig["n_arms"] == 2
        and sig["measurement"] == "mean"
        and sig["comparison"] == "difference"
        and sig["has_ref_arm"]
    )


def is_observational_route(sig: dict[str, Any]) -> bool:
    """Strict observational route: 1 baseline/observe + pcor + identity.

    No adjust arm allowed; comparison must be identity (single arm,
    pure pcor). The frozen-baseline guarantees this is the only valid
    observational shape compatible with the validator.
    """
    arm_kinds = sig["arm_kinds"]
    if "adjust" in arm_kinds:
        return False
    has_obs_arm = bool(set(arm_kinds) & {"baseline", "observe"})
    return (
        has_obs_arm
        and sig["n_arms"] == 1
        and sig["measurement"] == "partial_correlation"
        and sig["comparison"] == "identity"
    )


def _signature_key(sig: dict[str, Any]) -> tuple:
    """Hashable key for set comparison (kept-vs-changed).

    Includes role so a frozen `required` swapped to `support` (or vice
    versa) does NOT count as kept — that is a structural change in the
    SQ's verification bundle even if every AtomicSpec stayed identical.
    """
    return (
        sig["arm_kinds"],
        sig["n_arms"],
        sig["measurement"],
        sig["comparison"],
        sig["has_ref_arm"],
        sig.get("role", "required"),
    )


def spec_endpoint_vars(spec_dict: dict) -> set[str]:
    """Extract endpoint variables (treatment/outcome/lhs/rhs) from a raw spec dict.

    Used by C1c reroute_quality to check that a rerouted spec preserves
    the endpoint variables of the frozen spec it replaces.
    """
    vars_: set[str] = set()
    for arm in spec_dict.get("arms", []) or []:
        if isinstance(arm, dict):
            t = arm.get("treatment")
            o = arm.get("outcome")
            if t:
                vars_.add(str(t))
            if o:
                vars_.add(str(o))
    meas = spec_dict.get("measurement", {}) or {}
    for k in ("treatment", "outcome", "lhs", "rhs", "target"):
        v = meas.get(k)
        if isinstance(v, str):
            vars_.add(v)
        elif isinstance(v, (list, tuple)):
            for item in v:
                if isinstance(item, str):
                    vars_.add(item)
    return vars_


def spec_control_vars(spec_dict: dict) -> set[str]:
    """Extract control variables (adjust_set / cond_set) from a raw spec dict."""
    vars_: set[str] = set()
    for arm in spec_dict.get("arms", []) or []:
        if isinstance(arm, dict):
            for v in arm.get("adjust_set", []) or []:
                if isinstance(v, str):
                    vars_.add(v)
    meas = spec_dict.get("measurement", {}) or {}
    for v in meas.get("cond_set", []) or []:
        if isinstance(v, str):
            vars_.add(v)
    return vars_


def signatures_from_frozen_sq(sq_dict: dict) -> list[dict[str, Any]]:
    """Extract spec signatures (with role) from a frozen sub_questions_v2 entry."""
    out: list[dict[str, Any]] = []
    for vs in sq_dict.get("verification_specs", []):
        sig = spec_signature(vs.get("spec", {}))
        sig["role"] = str(vs.get("role", "required"))
        out.append(sig)
    return out


def _spec_dict_from_compiled(spec) -> dict:
    """Convert a compiled AtomicSpec to a raw dict for signature extraction."""
    try:
        return spec.model_dump(mode="json")
    except Exception:
        return {}


def signatures_from_compiled_sq(sq) -> list[dict[str, Any]]:
    """Extract spec signatures (with role) from a freshly compiled SubQuestionIntentV2."""
    out: list[dict[str, Any]] = []
    for vs in sq.verification_specs:
        sig = spec_signature(_spec_dict_from_compiled(vs.spec))
        sig["role"] = str(getattr(vs, "role", "required"))
        out.append(sig)
    return out


# ---------------------------------------------------------------------------
# Per-SQ recompile + classification
# ---------------------------------------------------------------------------


def classify_sq(
    frozen_sigs: list[dict[str, Any]],
    new_sigs: list[dict[str, Any]],
    abstained: bool,
    compile_failed: bool,
) -> str:
    """Classify a single SQ recompile against the frozen baseline.

    A SQ counts as `route_causal` / `route_observational` only if at
    least one rerouted spec satisfies the strict route shape AND has
    `role=required`. A route shape that only appeared as a `support`
    spec does NOT count — it would not influence the SQ verdict in
    the live runner under the required-fallback policy and would
    falsely inflate C1a if accepted here.
    """
    if abstained:
        return "abstained"
    if compile_failed:
        return "compile_error"

    frozen_set = {_signature_key(s) for s in frozen_sigs}
    new_set = {_signature_key(s) for s in new_sigs}
    if frozen_set == new_set:
        return "kept"

    frozen_had_adjpcor = any(is_adjust_pcor(s) for s in frozen_sigs)
    if frozen_had_adjpcor:
        new_has_adjpcor = any(is_adjust_pcor(s) for s in new_sigs)
        if not new_has_adjpcor:
            has_required_causal = any(
                is_causal_route(s) and s.get("role") == "required" for s in new_sigs
            )
            has_required_obs = any(
                is_observational_route(s) and s.get("role") == "required" for s in new_sigs
            )
            if has_required_causal:
                return "route_causal"
            if has_required_obs:
                return "route_observational"

    return "other_change"


def recompile_one_sq(
    frozen_sq_dict: dict,
    summary,
    llm_call,
) -> dict[str, Any]:
    """Recompile one SQ and produce a diff record."""
    from sreg.models.open_investigation import SQTier
    from sreg.tools.oi_sq_compiler import compile_sq_to_specs

    sq_id = frozen_sq_dict.get("sq_id", "<unknown>")
    text_gloss = frozen_sq_dict.get("text_gloss", "")
    focus_vars = tuple(frozen_sq_dict.get("focus_variables", []) or [])
    tier_raw = frozen_sq_dict.get("tier", "high")
    try:
        tier = SQTier(tier_raw)
    except Exception:
        tier = SQTier.HIGH

    frozen_sigs = signatures_from_frozen_sq(frozen_sq_dict)
    frozen_has_adjpcor = any(is_adjust_pcor(s) for s in frozen_sigs)
    frozen_specs_raw = [
        vs.get("spec", {}) for vs in frozen_sq_dict.get("verification_specs", [])
    ]

    record = {
        "sq_id": sq_id,
        "text_gloss": text_gloss,
        "focus_variables": list(focus_vars),
        "frozen_n_specs": len(frozen_sigs),
        "frozen_signatures": frozen_sigs,
        "frozen_has_adjust_pcor": frozen_has_adjpcor,
    }

    if not text_gloss:
        record["status"] = "compile_error"
        record["error"] = "frozen sq has empty text_gloss"
        return record

    t0 = time.time()
    result = compile_sq_to_specs(
        sq_id=sq_id,
        text_gloss=text_gloss,
        focus_variables=focus_vars,
        tier=tier,
        summary=summary,
        llm_call=llm_call,
    )
    record["compile_seconds"] = round(time.time() - t0, 1)

    # Surface warnings/dropped-spec errors even when result.success=True.
    # The compiler can succeed with a non-empty result.errors list (e.g.
    # an LLM-emitted spec failed AtomicSpec validation and was dropped
    # from the bundle but other specs survived). Hiding these would mask
    # partial-failure modes during G.1 forensics.
    if result.errors:
        record["compile_warnings"] = list(result.errors)

    if result.success:
        new_sigs = signatures_from_compiled_sq(result.sq)
        record["new_n_specs"] = len(new_sigs)
        record["new_signatures"] = new_sigs
        record["new_has_adjust_pcor"] = any(is_adjust_pcor(s) for s in new_sigs)
        record["status"] = classify_sq(
            frozen_sigs, new_sigs, abstained=False, compile_failed=False
        )
        # Capture per-spec endpoint/control vars + role for C1c
        new_specs_meta = []
        for vs in result.sq.verification_specs:
            sd = _spec_dict_from_compiled(vs.spec)
            meta = {
                "role": getattr(vs, "role", "required"),
                "endpoints": sorted(spec_endpoint_vars(sd)),
                "controls": sorted(spec_control_vars(sd)),
                "signature": spec_signature(sd),
            }
            # Only persist the full spec dict when --persist-specs is set
            # (it bloats recompile.json by ~5x). Required by --ground-sanity.
            if _PERSIST_SPECS:
                meta["spec_dict"] = sd
            new_specs_meta.append(meta)
        record["new_specs_meta"] = new_specs_meta
        # C1c reference points: union of endpoints/controls from the
        # **frozen buggy specs only** (the adj+pcor ones we are trying
        # to reroute), NOT the union of the whole SQ. Comparing against
        # the whole SQ would mix in unrelated supports and falsely
        # penalize correct reroutes (per Codex review).
        frozen_buggy_endpoints: set[str] = set()
        frozen_buggy_controls: set[str] = set()
        for fs in frozen_specs_raw:
            if not isinstance(fs, dict):
                continue
            if is_adjust_pcor(spec_signature(fs)):
                frozen_buggy_endpoints |= spec_endpoint_vars(fs)
                frozen_buggy_controls |= spec_control_vars(fs)
        record["frozen_buggy_endpoints"] = sorted(frozen_buggy_endpoints)
        record["frozen_buggy_controls"] = sorted(frozen_buggy_controls)
    else:
        record["new_n_specs"] = 0
        record["new_signatures"] = []
        record["new_has_adjust_pcor"] = False
        # Use the explicit abstention contract from the compiler.
        # No more raw_response sniffing — the SQCompileResult object is
        # the canonical source.
        if getattr(result, "abstained", False):
            record["status"] = "abstained"
            record["abstention_marker"] = "explicit_contract"
            record["abstain_reason"] = getattr(result, "abstain_reason", None)
        else:
            record["status"] = "compile_error"
            record["compile_errors"] = result.errors

    return record


# ---------------------------------------------------------------------------
# Per-case driver
# ---------------------------------------------------------------------------


def recompile_case(
    case_name: str,
    baseline_dir: Path,
    out_dir: Path,
    llm_call,
) -> dict[str, Any]:
    """Recompile every SQ of a case and persist a diff record."""
    from sreg.models.research_problem import ResearchProblem
    from sreg.tools.oi_compiler import build_world_summary

    src_path = baseline_dir / case_name / "src.json"
    if not src_path.exists():
        return {"case": case_name, "ok": False, "error": f"missing {src_path}"}

    src = json.load(open(src_path, encoding="utf-8"))
    sqs_raw = src.get("sub_questions_v2", [])
    if not sqs_raw:
        return {"case": case_name, "ok": False, "error": "no sub_questions_v2"}

    problem = ResearchProblem(**src["problem"])
    world = reconstruct_world(src)

    target = getattr(problem, "target_variable", None) or world.variables[-1]
    summary = build_world_summary(world, target)

    sq_records = []
    for sq_dict in sqs_raw:
        rec = recompile_one_sq(sq_dict, summary, llm_call)
        sq_records.append(rec)
        print(
            f"  [{case_name}] {rec.get('sq_id', '?'):<8} "
            f"frozen_n={rec.get('frozen_n_specs', 0)} "
            f"new_n={rec.get('new_n_specs', 0)} "
            f"status={rec.get('status', '?')} "
            f"({rec.get('compile_seconds', 0)}s)"
        )

    case_out_dir = out_dir / case_name
    case_out_dir.mkdir(parents=True, exist_ok=True)
    case_record = {
        "case": case_name,
        "world_id": world.id,
        "n_sqs": len(sq_records),
        "sqs": sq_records,
    }
    with open(case_out_dir / "recompile.json", "w", encoding="utf-8") as f:
        json.dump(case_record, f, indent=2)

    return _summarize_case(case_record)


def _required_route_specs_meta(sq_record: dict) -> list[dict[str, Any]]:
    """Return the metadata of new specs that are role=required AND match a route shape.

    Used to compute C1c: the per-component diagnostic flags should only
    look at specs that actually count toward the SQ verdict (required)
    and match the strict route shapes (causal or observational).
    """
    out: list[dict[str, Any]] = []
    for meta in sq_record.get("new_specs_meta", []) or []:
        if not isinstance(meta, dict):
            continue
        if meta.get("role") != "required":
            continue
        sig = meta.get("signature") or {}
        if is_causal_route(sig) or is_observational_route(sig):
            out.append(meta)
    return out


def _quality_flags_for_sq(sq_record: dict) -> dict[str, Any] | None:
    """Compute the C1c per-component diagnostic flags for one SQ.

    Returns None if the SQ is not in {route_causal, route_observational}
    — C1c is only defined on rerouted SQs. Otherwise returns a dict
    with the 5 flags + the AND.
    """
    status = sq_record.get("status")
    if status not in ("route_causal", "route_observational"):
        return None

    buggy_endpoints = set(sq_record.get("frozen_buggy_endpoints", []) or [])
    buggy_controls = set(sq_record.get("frozen_buggy_controls", []) or [])

    required_routed = _required_route_specs_meta(sq_record)
    if not required_routed:
        # The classifier said route_*, so this should not happen given
        # the role-required gate in classify_sq. Defensive: if it does,
        # treat all flags as failing rather than crashing.
        return {
            "preserved_endpoints": False,
            "control_any_overlap": False,
            "full_controls_preserved": False,
            "control_coverage": 0.0,
            "clean_compile": False,
            "all_quality_checks_pass": False,
        }

    preserved_endpoints = False
    any_overlap = False
    full_preserved = False
    best_coverage = 0.0
    for meta in required_routed:
        ep = set(meta.get("endpoints", []) or [])
        co = set(meta.get("controls", []) or [])
        if buggy_endpoints and buggy_endpoints.issubset(ep):
            preserved_endpoints = True
        # Edge case: a frozen buggy spec with NO endpoints (degenerate)
        # — count as preserved by default; the bug would be the missing
        # endpoints in the original frozen spec, not in our reroute.
        if not buggy_endpoints:
            preserved_endpoints = True
        if buggy_controls:
            overlap = buggy_controls & co
            if overlap:
                any_overlap = True
            coverage = len(overlap) / len(buggy_controls)
            if coverage > best_coverage:
                best_coverage = coverage
            if buggy_controls.issubset(co):
                full_preserved = True
        else:
            # No frozen control vars to preserve. Codex policy: count as
            # vacuously preserved; the lack of controls is itself the
            # bug we are rerouting.
            any_overlap = True
            full_preserved = True
            best_coverage = 1.0

    clean_compile = not bool(sq_record.get("compile_warnings"))
    all_pass = (
        preserved_endpoints and full_preserved and clean_compile
    )

    return {
        "preserved_endpoints": preserved_endpoints,
        "control_any_overlap": any_overlap,
        "full_controls_preserved": full_preserved,
        "control_coverage": round(best_coverage, 3),
        "clean_compile": clean_compile,
        "all_quality_checks_pass": all_pass,
    }


def _summarize_case(case_record: dict) -> dict[str, Any]:
    """Aggregate per-case counters that feed into G.1 success criteria."""
    sqs = case_record["sqs"]
    n_sqs = len(sqs)

    n_kept = sum(1 for s in sqs if s.get("status") == "kept")
    n_route_causal = sum(1 for s in sqs if s.get("status") == "route_causal")
    n_route_obs = sum(1 for s in sqs if s.get("status") == "route_observational")
    n_abstained = sum(1 for s in sqs if s.get("status") == "abstained")
    n_compile_error = sum(1 for s in sqs if s.get("status") == "compile_error")
    n_other_change = sum(1 for s in sqs if s.get("status") == "other_change")

    n_frozen_adjpcor_sqs = sum(1 for s in sqs if s.get("frozen_has_adjust_pcor"))
    n_new_adjpcor_sqs = sum(1 for s in sqs if s.get("new_has_adjust_pcor"))

    n_frozen_specs_total = sum(s.get("frozen_n_specs", 0) for s in sqs)
    n_new_specs_total = sum(s.get("new_n_specs", 0) for s in sqs)

    # C1a / C1b: only computed for SQs whose frozen baseline had adj+pcor.
    # C1a = (route_causal + route_obs + abstained) / frozen_adjpcor_sqs
    # C1b = (compile_error + other_change) / frozen_adjpcor_sqs
    # By construction C1a + C1b = 1 - kept_frac (kept inside frozen-adjpcor
    # is impossible because the new sig set would equal frozen including
    # the buggy spec, which would also fail role=required check; but we
    # still surface n_kept_in_frozen_adjpcor for forensic completeness).
    frozen_adjpcor_records = [s for s in sqs if s.get("frozen_has_adjust_pcor")]
    n_resolved = sum(
        1 for s in frozen_adjpcor_records
        if s.get("status") in ("route_causal", "route_observational", "abstained")
    )
    n_bad_replacement = sum(
        1 for s in frozen_adjpcor_records
        if s.get("status") in ("compile_error", "other_change")
    )
    n_kept_in_frozen_adjpcor = sum(
        1 for s in frozen_adjpcor_records if s.get("status") == "kept"
    )

    # C1c: per-component diagnostic flags for rerouted SQs only.
    quality_records = [
        _quality_flags_for_sq(s) for s in frozen_adjpcor_records
    ]
    quality_records = [q for q in quality_records if q is not None]
    n_rerouted_for_quality = len(quality_records)

    def _frac(key: str) -> float:
        if not quality_records:
            return float("nan")
        return sum(1 for q in quality_records if q.get(key)) / n_rerouted_for_quality

    quality_summary = {
        "n_rerouted": n_rerouted_for_quality,
        "preserved_endpoints_frac": _frac("preserved_endpoints"),
        "control_any_overlap_frac": _frac("control_any_overlap"),
        "full_controls_preserved_frac": _frac("full_controls_preserved"),
        "clean_compile_frac": _frac("clean_compile"),
        "all_quality_checks_pass_frac": _frac("all_quality_checks_pass"),
        "control_coverage_mean": (
            round(
                sum(q.get("control_coverage", 0.0) for q in quality_records)
                / n_rerouted_for_quality,
                3,
            )
            if quality_records
            else float("nan")
        ),
    }

    return {
        "case": case_record["case"],
        "world_id": case_record["world_id"],
        "n_sqs": n_sqs,
        "n_kept": n_kept,
        "n_route_causal": n_route_causal,
        "n_route_observational": n_route_obs,
        "n_abstained": n_abstained,
        "n_compile_error": n_compile_error,
        "n_other_change": n_other_change,
        "n_frozen_adjpcor_sqs": n_frozen_adjpcor_sqs,
        "n_new_adjpcor_sqs": n_new_adjpcor_sqs,
        "n_frozen_specs_total": n_frozen_specs_total,
        "n_new_specs_total": n_new_specs_total,
        # G.1 metric components for this case
        "n_resolved_in_frozen_adjpcor": n_resolved,
        "n_bad_replacement_in_frozen_adjpcor": n_bad_replacement,
        "n_kept_in_frozen_adjpcor": n_kept_in_frozen_adjpcor,
        "quality": quality_summary,
    }


# ---------------------------------------------------------------------------
# Batch report (the only place that interprets results vs G.1 criteria)
# ---------------------------------------------------------------------------


def write_batch_report(case_summaries: list[dict], out_dir: Path) -> None:
    """Write the human-readable G.1 verdict report.

    Reports observations against the 5 G.1 criteria. Does NOT claim
    'system improved' — only describes what the prompt change did to
    the compiler's spec emission patterns.
    """
    total_sqs = sum(c.get("n_sqs", 0) for c in case_summaries)
    total_frozen_adjpcor = sum(c.get("n_frozen_adjpcor_sqs", 0) for c in case_summaries)
    total_new_adjpcor = sum(c.get("n_new_adjpcor_sqs", 0) for c in case_summaries)
    total_route_causal = sum(c.get("n_route_causal", 0) for c in case_summaries)
    total_route_obs = sum(c.get("n_route_observational", 0) for c in case_summaries)
    total_abstained = sum(c.get("n_abstained", 0) for c in case_summaries)
    total_compile_error = sum(c.get("n_compile_error", 0) for c in case_summaries)
    total_kept = sum(c.get("n_kept", 0) for c in case_summaries)
    total_other = sum(c.get("n_other_change", 0) for c in case_summaries)

    # C1a / C1b — computed from per-SQ status restricted to frozen adj+pcor
    total_resolved = sum(
        c.get("n_resolved_in_frozen_adjpcor", 0) for c in case_summaries
    )
    total_bad_replacement = sum(
        c.get("n_bad_replacement_in_frozen_adjpcor", 0) for c in case_summaries
    )
    total_kept_in_frozen_adjpcor = sum(
        c.get("n_kept_in_frozen_adjpcor", 0) for c in case_summaries
    )

    if total_frozen_adjpcor > 0:
        c1a_resolved_rate = total_resolved / total_frozen_adjpcor
        c1b_bad_replacement_rate = total_bad_replacement / total_frozen_adjpcor
    else:
        c1a_resolved_rate = float("nan")
        c1b_bad_replacement_rate = float("nan")

    # C1c — quality flags aggregated across cases
    quality_records: list[dict[str, Any]] = []
    n_rerouted_total = 0
    for c in case_summaries:
        q = c.get("quality") or {}
        n = q.get("n_rerouted", 0) or 0
        if n > 0:
            quality_records.append({"n": n, **q})
            n_rerouted_total += n

    def _q_frac(field: str) -> float:
        if n_rerouted_total == 0:
            return float("nan")
        s = 0.0
        for q in quality_records:
            v = q.get(field)
            if isinstance(v, float) and v == v:  # not NaN
                s += v * q["n"]
        return s / n_rerouted_total

    c1c = {
        "preserved_endpoints_frac": _q_frac("preserved_endpoints_frac"),
        "control_any_overlap_frac": _q_frac("control_any_overlap_frac"),
        "full_controls_preserved_frac": _q_frac("full_controls_preserved_frac"),
        "clean_compile_frac": _q_frac("clean_compile_frac"),
        "all_quality_checks_pass_frac": _q_frac("all_quality_checks_pass_frac"),
        "control_coverage_mean": _q_frac("control_coverage_mean"),
    }

    # C2 — abstention delta (new minus frozen abstention rate)
    # Frozen baseline never abstains explicitly (no [] markers in old prompt).
    frozen_abst_rate = 0.0
    new_abst_rate = total_abstained / total_sqs if total_sqs else 0.0
    c2_abstention_delta = new_abst_rate - frozen_abst_rate

    # C5 — unaffected regression (cases with NO frozen adj+pcor: did SQ
    # signatures change?)
    c5_cases = [c for c in case_summaries if c.get("n_frozen_adjpcor_sqs", 0) == 0]
    c5_changed = sum(
        c.get("n_route_causal", 0) + c.get("n_route_observational", 0)
        + c.get("n_abstained", 0) + c.get("n_compile_error", 0)
        + c.get("n_other_change", 0)
        for c in c5_cases
    )
    c5_total = sum(c.get("n_sqs", 0) for c in c5_cases)
    c5_change_rate = c5_changed / c5_total if c5_total else float("nan")

    def _pct(x: float) -> str:
        return "N/A" if x != x else f"{x:.0%}"

    lines = []
    lines.append("# P06 G.1 — Isolated compiler recompilation report")
    lines.append("")
    lines.append("## What this report IS NOT")
    lines.append("")
    lines.append(
        "This report does NOT claim the system improved. It describes what the"
    )
    lines.append(
        "new compiler prompt did to the spec-emission patterns on a frozen set"
    )
    lines.append(
        "of sub-question texts. The only stochastic component is the compiler"
    )
    lines.append("LLM. No solver, no orchestrator, no scoring (default mode).")
    lines.append("")
    lines.append("## Aggregate counters")
    lines.append("")
    lines.append(f"- cases: {len(case_summaries)}")
    lines.append(f"- total sub-questions: {total_sqs}")
    lines.append(f"- SQs with frozen adjust+pcor: {total_frozen_adjpcor}")
    lines.append(f"- SQs with new adjust+pcor:    {total_new_adjpcor}")
    lines.append("")
    lines.append("Per-SQ outcome distribution (all SQs):")
    lines.append(f"- kept:                  {total_kept}")
    lines.append(f"- route_causal:          {total_route_causal}")
    lines.append(f"- route_observational:   {total_route_obs}")
    lines.append(f"- abstained:             {total_abstained}")
    lines.append(f"- compile_error:         {total_compile_error}")
    lines.append(f"- other_change:          {total_other}")
    lines.append("")
    lines.append("## G.1 success criteria — observations")
    lines.append("")
    lines.append(
        "### C1a — resolved_rate (target: high; the prompt is doing its job)"
    )
    lines.append(
        "  Of SQs with frozen adj+pcor, fraction whose new status is "
        "route_causal | route_observational | abstained."
    )
    if total_frozen_adjpcor == 0:
        lines.append("  N/A — no frozen adjust+pcor SQs in this batch.")
    else:
        lines.append(
            f"  C1a = {_pct(c1a_resolved_rate)} "
            f"({total_resolved}/{total_frozen_adjpcor})"
        )
    lines.append("")
    lines.append(
        "### C1b — bad_replacement_rate (target: low; reroutes should be clean)"
    )
    lines.append(
        "  Of SQs with frozen adj+pcor, fraction whose new status is "
        "compile_error | other_change. Same denominator as C1a."
    )
    if total_frozen_adjpcor == 0:
        lines.append("  N/A — no frozen adjust+pcor SQs in this batch.")
    else:
        lines.append(
            f"  C1b = {_pct(c1b_bad_replacement_rate)} "
            f"({total_bad_replacement}/{total_frozen_adjpcor})"
        )
        if total_kept_in_frozen_adjpcor:
            lines.append(
                f"  (forensic: {total_kept_in_frozen_adjpcor} SQ(s) classified "
                f"as `kept` despite having frozen adj+pcor — investigate.)"
            )
    lines.append("")
    lines.append(
        "### C1c — reroute_quality (per-component diagnostic flags)"
    )
    lines.append(
        "  Each fraction is computed only over SQs whose status is "
        "route_causal or route_observational. Compared against the frozen "
        "**buggy** specs of each SQ — not the whole SQ — so unrelated "
        "supports do not contaminate the metric."
    )
    if n_rerouted_total == 0:
        lines.append("  N/A — no rerouted SQs in this batch.")
    else:
        lines.append(f"  rerouted SQs (denominator): {n_rerouted_total}")
        lines.append(
            f"  - preserved_endpoints:      {_pct(c1c['preserved_endpoints_frac'])}"
        )
        lines.append(
            f"  - control_any_overlap:      {_pct(c1c['control_any_overlap_frac'])}"
        )
        lines.append(
            f"  - full_controls_preserved:  {_pct(c1c['full_controls_preserved_frac'])}"
        )
        lines.append(
            f"  - control_coverage (mean):  {c1c['control_coverage_mean']:.2f}"
            if c1c['control_coverage_mean'] == c1c['control_coverage_mean']
            else "  - control_coverage (mean):  N/A"
        )
        lines.append(
            f"  - clean_compile (no warns): {_pct(c1c['clean_compile_frac'])}"
        )
        lines.append(
            f"  - all_quality_checks_pass:  {_pct(c1c['all_quality_checks_pass_frac'])}"
        )
    lines.append("")
    lines.append("### C2 — no false-abstention spike (target: delta < 10pp)")
    lines.append(
        f"  abstention rate: {frozen_abst_rate:.0%} → {new_abst_rate:.0%} "
        f"(delta = {c2_abstention_delta:+.0%})"
    )
    if abs(c2_abstention_delta) >= 0.10:
        lines.append("  ALARM: delta exceeds 10 percentage points.")
    lines.append("")
    lines.append("### C3 — calibration set A (handled by task #37, not this run)")
    lines.append("### C4 — calibration set B (handled by task #37, not this run)")
    lines.append("")
    lines.append("### C5 — no regression on unaffected cases")
    if c5_total == 0:
        lines.append("  N/A — every case had at least one frozen adj+pcor SQ.")
    else:
        lines.append(
            f"  unaffected SQs that changed signature: {c5_changed}/{c5_total} "
            f"({c5_change_rate:.0%})"
        )
        lines.append(
            "  (Compiler-LLM stochasticity policy: deltas <0.1 noise, "
            "0.1-0.2 tentative, >0.2 real signal.)"
        )
    lines.append("")
    lines.append("## Per-case breakdown")
    lines.append("")
    lines.append(
        "| case | sqs | frozen_adjpcor | new_adjpcor | causal | obs | abst | err | other | kept |"
    )
    lines.append("|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
    for c in case_summaries:
        lines.append(
            f"| {c.get('case', '?')} "
            f"| {c.get('n_sqs', 0)} "
            f"| {c.get('n_frozen_adjpcor_sqs', 0)} "
            f"| {c.get('n_new_adjpcor_sqs', 0)} "
            f"| {c.get('n_route_causal', 0)} "
            f"| {c.get('n_route_observational', 0)} "
            f"| {c.get('n_abstained', 0)} "
            f"| {c.get('n_compile_error', 0)} "
            f"| {c.get('n_other_change', 0)} "
            f"| {c.get('n_kept', 0)} |"
        )
    lines.append("")
    lines.append("## Interpretation rule (pre-registered)")
    lines.append("")
    lines.append(
        "C1a (resolved_rate) is the headline metric for G.1. The change is"
    )
    lines.append(
        "interpreted under the same noise policy as the rest of P06:"
    )
    lines.append("- delta < 0.10 absolute: noise, not interpretable")
    lines.append("- delta 0.10-0.20: tentative")
    lines.append("- delta > 0.20: real signal")
    lines.append("")
    lines.append(
        "G.1 closes only if C1a is in the 'real signal' band AND C1b is low"
    )
    lines.append(
        "AND C1c.all_quality_checks_pass is non-trivial AND C2 (abstention"
    )
    lines.append(
        "delta) and C5 (unaffected regression) are within their thresholds."
    )
    lines.append("Otherwise revisit prompt design.")
    lines.append("")

    with open(out_dir / "_recompile_report.md", "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


# ---------------------------------------------------------------------------
# Ground-sanity (opt-in)
# ---------------------------------------------------------------------------


# 5 hard-fail cases from p05_paired_R that motivated G.1.
# Per design discussion: this is the default set — anything else has to be
# explicit (--cases ... | --all-cases).
DEFAULT_HARD_FAIL_CASES = (
    "competing_mech",
    "coral_bleach",
    "immunotherapy",
    "microbiome",
    "selection_bias",
)


def _run_ground_sanity(
    case_name: str,
    baseline_dir: Path,
    out_dir: Path,
) -> dict[str, Any]:
    """Run verify_atom on rerouted required specs for one case.

    This is a DIAGNOSTIC pass — its purpose is to confirm the rerouted
    specs are physically executable against the reconstructed SCM, not
    to score them. Per Codex review, success criteria are:

      a. verify_atom did not raise (no `error` key in detail)
      b. detail is non-empty
      c. the inner measurement value is not NaN

    `solver_assertion_holds` is logged for transparency but is NOT used
    as pass/fail — assertions in the rerouted bundle are produced by an
    LLM with no calibration loop, so `holds=False` is expected and
    informative, not a failure signal.

    Only specs in SQs classified as `route_causal` or `route_observational`
    that have role=required are executed. Everything else is skipped.
    """
    from sreg.models.open_investigation import AtomicSpec
    from sreg.solver.scm_solver import SCMSolver
    from sreg.tools.oi_verifier import verify_atom

    recompile_path = out_dir / case_name / "recompile.json"
    src_path = baseline_dir / case_name / "src.json"
    if not recompile_path.exists():
        return {"case": case_name, "ok": False, "error": f"missing {recompile_path}"}
    if not src_path.exists():
        return {"case": case_name, "ok": False, "error": f"missing {src_path}"}

    case_record = json.load(open(recompile_path, encoding="utf-8"))
    src = json.load(open(src_path, encoding="utf-8"))
    world = reconstruct_world(src)
    solver = SCMSolver(world)

    sanity_records: list[dict[str, Any]] = []
    n_executed = 0
    n_no_exception = 0
    n_detail_nonempty = 0
    n_measurement_finite = 0

    for sq in case_record.get("sqs", []):
        if sq.get("status") not in ("route_causal", "route_observational"):
            continue
        sq_id = sq.get("sq_id", "?")

        # We need the original AtomicSpec objects, but recompile.json only
        # has signatures. Recompile is fast — re-fetch by re-reading the
        # frozen text and re-running compile_sq_to_specs is too expensive,
        # so instead we read recompile.json + reconstruct AtomicSpec from
        # the new_specs_meta dicts via Pydantic. To avoid that complexity
        # we instead serialize the spec dicts at recompile time. For now
        # the simplest path is: re-run compile_sq_to_specs(stub_llm) is
        # NOT possible — it would call the real LLM. So we expect that
        # `recompile_one_sq` was extended to persist the spec dicts on
        # disk. Since it currently only persists meta, this sanity pass
        # will note "no spec dicts on disk — pass --persist-specs" until
        # that field is added.
        for meta in sq.get("new_specs_meta", []) or []:
            if not isinstance(meta, dict):
                continue
            if meta.get("role") != "required":
                continue
            sig = meta.get("signature") or {}
            if not (is_causal_route(sig) or is_observational_route(sig)):
                continue
            spec_dict = meta.get("spec_dict")
            if not spec_dict:
                sanity_records.append({
                    "sq_id": sq_id,
                    "skipped": True,
                    "reason": "no spec_dict persisted (recompile this case with --persist-specs)",
                })
                continue
            try:
                spec_obj = AtomicSpec(**spec_dict)
            except Exception as e:
                sanity_records.append({
                    "sq_id": sq_id,
                    "skipped": True,
                    "reason": f"spec_dict failed AtomicSpec validation: {e}",
                })
                continue

            n_executed += 1
            # Per Codex review: verify_atom *should* trap its own
            # exceptions and surface them via detail["error"], but a
            # crashing reroute (or a bug in verify_atom itself, or a
            # KeyboardInterrupt-style hard exit) would otherwise abort
            # the entire batch — exactly where the diagnostic is
            # supposed to be measuring crashes. We wrap it defensively
            # and treat both "raised exception" and "error key in
            # detail" as no_exception=False so the metric is robust
            # to the verifier's internal contract drift.
            verdict = None
            raised = False
            raised_msg: str | None = None
            try:
                verdict = verify_atom(
                    spec_obj, world, solver, n_mc=10_000, seed=42,
                )
                detail = verdict.detail or {}
            except Exception as e:
                raised = True
                raised_msg = f"verify_atom raised: {e}"
                detail = {"error": raised_msg}

            had_error_key = "error" in detail
            no_exception_flag = (not raised) and (not had_error_key)
            detail_nonempty = bool(detail) and no_exception_flag

            measurements = detail.get("measurements") if detail_nonempty else None
            measurement_finite = False
            if isinstance(measurements, dict):
                vals: list[float] = []
                for v in measurements.values():
                    if isinstance(v, (int, float)):
                        vals.append(float(v))
                    elif isinstance(v, dict) and "value" in v:
                        try:
                            vals.append(float(v["value"]))
                        except (TypeError, ValueError):
                            pass
                if vals:
                    import math
                    measurement_finite = all(math.isfinite(x) for x in vals)

            if no_exception_flag:
                n_no_exception += 1
            if detail_nonempty:
                n_detail_nonempty += 1
            if measurement_finite:
                n_measurement_finite += 1

            sanity_records.append({
                "sq_id": sq_id,
                "spec_id": getattr(spec_obj, "spec_id", None),
                "no_exception": no_exception_flag,
                "detail_nonempty": detail_nonempty,
                "measurement_finite": measurement_finite,
                "raised_exception": raised,
                "raised_exception_msg": raised_msg,
                "detail_has_error_key": had_error_key,
                "holds_diagnostic": (
                    verdict.solver_assertion_holds if verdict is not None else None
                ),
                "score_diagnostic": (
                    verdict.score if verdict is not None else None
                ),
                "ground_truth_diagnostic": (
                    str(verdict.ground_truth)
                    if verdict is not None and verdict.ground_truth is not None
                    else None
                ),
            })

    out = {
        "case": case_name,
        "n_executed": n_executed,
        "n_no_exception": n_no_exception,
        "n_detail_nonempty": n_detail_nonempty,
        "n_measurement_finite": n_measurement_finite,
        "records": sanity_records,
    }
    sanity_path = out_dir / case_name / "ground_sanity.json"
    with open(sanity_path, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2)
    return out


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main():
    p = argparse.ArgumentParser()
    p.add_argument(
        "--baseline", default="results/p05_canonical_batch",
        help="Baseline batch dir with frozen src.json files",
    )
    p.add_argument(
        "--out", default="results/p06_recompile",
        help="Output dir for recompiled cases",
    )
    cases_group = p.add_mutually_exclusive_group()
    cases_group.add_argument(
        "--cases", nargs="*", default=None,
        help=(
            "Case names to recompile. If omitted (and --all-cases not set), "
            "defaults to the 5 hard-fail set: "
            + ", ".join(DEFAULT_HARD_FAIL_CASES)
        ),
    )
    cases_group.add_argument(
        "--all-cases", action="store_true",
        help="Recompile every case in --baseline (mutually exclusive with --cases)",
    )
    p.add_argument(
        "--compiler-model", default=None,
        help="Override compiler model (default: $AZURE_MODEL)",
    )
    p.add_argument(
        "--ground-sanity", action="store_true",
        help=(
            "After recompilation, run verify_atom on rerouted required specs "
            "as a diagnostic. Logs no_exception/detail_nonempty/"
            "measurement_finite per spec. Does NOT use holds=True as pass/fail."
        ),
    )
    p.add_argument(
        "--persist-specs", action="store_true",
        help=(
            "Persist full spec_dict in new_specs_meta on disk (required by "
            "--ground-sanity to reconstruct AtomicSpec objects)."
        ),
    )
    args = p.parse_args()

    if args.ground_sanity and not args.persist_specs:
        print(
            "NOTE: --ground-sanity needs spec dicts on disk; "
            "auto-enabling --persist-specs."
        )
        args.persist_specs = True

    baseline_dir = Path(args.baseline)
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    if args.cases:
        cases = list(args.cases)
    elif args.all_cases:
        cases = sorted(
            d.name for d in baseline_dir.iterdir()
            if d.is_dir() and (d / "src.json").exists()
        )
    else:
        cases = [
            c for c in DEFAULT_HARD_FAIL_CASES
            if (baseline_dir / c / "src.json").exists()
        ]
        missing = set(DEFAULT_HARD_FAIL_CASES) - set(cases)
        if missing:
            print(
                f"WARNING: default hard-fail cases not in baseline: "
                f"{sorted(missing)}"
            )

    base_url = os.environ.get("AZURE_FOUNDRY_BASE_URL", "")
    api_key = os.environ.get("AZURE_INFERENCE_CREDENTIAL", "")
    if not base_url or not api_key:
        print("ERROR: Azure env vars not set (.env)")
        sys.exit(1)

    compiler_model = args.compiler_model or os.environ.get("AZURE_MODEL", "gpt-5.4")

    from openai import OpenAI
    client = OpenAI(base_url=base_url, api_key=api_key)
    llm_call = build_text_llm(client, compiler_model)

    # Stash flag on a module-level so recompile_one_sq can pick it up
    # without changing every signature in the call chain.
    global _PERSIST_SPECS
    _PERSIST_SPECS = bool(args.persist_specs)

    print()
    print("=" * 80)
    print("  P06 G.1 — ISOLATED COMPILER RECOMPILATION")
    print("=" * 80)
    print(f"  baseline:        {baseline_dir}")
    print(f"  out:             {out_dir}")
    print(f"  compiler_model:  {compiler_model}")
    print(f"  cases:           {len(cases)} ({', '.join(cases)})")
    print(f"  ground_sanity:   {args.ground_sanity}")
    print(f"  persist_specs:   {args.persist_specs}")
    print()

    case_summaries: list[dict] = []
    for case in cases:
        try:
            summary = recompile_case(case, baseline_dir, out_dir, llm_call)
        except Exception as e:
            import traceback
            traceback.print_exc()
            summary = {"case": case, "ok": False, "error": str(e)}
        case_summaries.append(summary)

    summary_path = out_dir / "_recompile_summary.json"
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(case_summaries, f, indent=2)

    write_batch_report(case_summaries, out_dir)
    report_path = out_dir / "_recompile_report.md"

    sanity_summaries: list[dict[str, Any]] = []
    if args.ground_sanity:
        print()
        print("-" * 80)
        print("  GROUND-SANITY (diagnostic only — not pass/fail)")
        print("-" * 80)
        for case in cases:
            try:
                gs = _run_ground_sanity(case, baseline_dir, out_dir)
            except Exception as e:
                import traceback
                traceback.print_exc()
                gs = {"case": case, "ok": False, "error": str(e)}
            sanity_summaries.append(gs)
            print(
                f"  {gs.get('case', '?'):<18} "
                f"executed={gs.get('n_executed', 0)} "
                f"no_exc={gs.get('n_no_exception', 0)} "
                f"detail={gs.get('n_detail_nonempty', 0)} "
                f"finite={gs.get('n_measurement_finite', 0)}"
            )
        sanity_path = out_dir / "_ground_sanity_summary.json"
        with open(sanity_path, "w", encoding="utf-8") as f:
            json.dump(sanity_summaries, f, indent=2)
        print(f"  -> {sanity_path}")

    print()
    print("=" * 80)
    print("  RESULTS")
    print("=" * 80)
    for c in case_summaries:
        print(
            f"  {c.get('case', '?'):<18} "
            f"sqs={c.get('n_sqs', 0)} "
            f"frozen_adjpcor={c.get('n_frozen_adjpcor_sqs', 0)} "
            f"new_adjpcor={c.get('n_new_adjpcor_sqs', 0)} "
            f"causal={c.get('n_route_causal', 0)} "
            f"obs={c.get('n_route_observational', 0)} "
            f"abst={c.get('n_abstained', 0)}"
        )
    print()
    print(f"  Summary: {summary_path}")
    print(f"  Report:  {report_path}")
    print()


# Module-level flag set by main(); read by recompile_one_sq.
_PERSIST_SPECS = False


if __name__ == "__main__":
    main()
