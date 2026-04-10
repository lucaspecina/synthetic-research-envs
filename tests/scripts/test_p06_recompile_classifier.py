"""Unit tests for the pure classifier helpers in scripts/p06_recompile_only.py.

Scope: only the classifier and route-shape predicates that map raw spec
dicts to G.1 metric buckets. No LLM, no SCM, no network. The tests load
the script via importlib because `scripts/` is not a package on the
test pythonpath.

These tests guard the C1a/C1b classification trap that Codex caught
during the G.1 design review:

  - A `route_*` shape that only appears as `support` MUST NOT be
    classified as route_causal / route_observational, because it would
    not influence the SQ verdict in the live runner under the
    required-fallback policy and would falsely inflate C1a.

  - A 1-arm `adjust + mean + identity` MUST NOT be classified as
    causal route — the strict shape requires 2 adjust arms +
    difference + ref_arm.

  - Signatures that round-trip through JSON (i.e. are reloaded from
    `recompile.json` by the --ground-sanity-only path) MUST still
    classify correctly. `spec_signature` builds `arm_kinds` as a tuple,
    but JSON has no tuple type so they come back as plain lists — any
    route-shape predicate that compares against a tuple literal would
    silently misclassify after the round trip.
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = REPO_ROOT / "scripts" / "p06_recompile_only.py"


def _load_module():
    spec = importlib.util.spec_from_file_location(
        "p06_recompile_only", SCRIPT_PATH
    )
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


M = _load_module()


# ---------------------------------------------------------------------------
# Spec dict fixtures (the only inputs the classifier sees)
# ---------------------------------------------------------------------------


def _adjust_arm(treatment: str, value: float, adjust_set: list[str]) -> dict:
    return {
        "kind": "adjust",
        "label": f"do_{treatment}_{value}",
        "treatment": treatment,
        "outcome": "Y",
        "values": {treatment: value},
        "adjust_set": adjust_set,
    }


def _baseline_arm() -> dict:
    return {"kind": "baseline", "label": "obs"}


def _causal_route_spec() -> dict:
    """Strict 2-arm adjust + mean + difference + ref_arm."""
    return {
        "spec_id": "spec_causal",
        "arms": [
            _adjust_arm("T", 1.0, ["W"]),
            _adjust_arm("T", 0.0, ["W"]),
        ],
        "measurement": {"kind": "mean", "target": "Y"},
        "comparison": {"kind": "difference", "ref_arm": "do_T_0.0"},
    }


def _observational_route_spec() -> dict:
    """Strict 1-arm baseline + pcor + identity."""
    return {
        "spec_id": "spec_obs",
        "arms": [_baseline_arm()],
        "measurement": {
            "kind": "partial_correlation",
            "lhs": "T",
            "rhs": "Y",
            "cond_set": ["W"],
        },
        "comparison": {"kind": "identity"},
    }


def _adjust_pcor_buggy_spec() -> dict:
    """The hybrid the validator now rejects: adjust arm + pcor."""
    return {
        "spec_id": "spec_buggy",
        "arms": [_adjust_arm("T", 1.0, ["W"])],
        "measurement": {
            "kind": "partial_correlation",
            "lhs": "T",
            "rhs": "Y",
            "cond_set": ["W"],
        },
        "comparison": {"kind": "identity"},
    }


def _one_arm_adjust_mean_identity_spec() -> dict:
    """Adjust + mean + identity (NOT a strict causal route — only 1 arm)."""
    return {
        "spec_id": "spec_one_arm",
        "arms": [_adjust_arm("T", 1.0, ["W"])],
        "measurement": {"kind": "mean", "target": "Y"},
        "comparison": {"kind": "identity"},
    }


# ---------------------------------------------------------------------------
# is_causal_route / is_observational_route — strict shape predicates
# ---------------------------------------------------------------------------


class TestRouteShapePredicates:
    def test_strict_causal_shape_recognized(self):
        sig = M.spec_signature(_causal_route_spec())
        assert M.is_causal_route(sig) is True
        assert M.is_observational_route(sig) is False

    def test_strict_observational_shape_recognized(self):
        sig = M.spec_signature(_observational_route_spec())
        assert M.is_observational_route(sig) is True
        assert M.is_causal_route(sig) is False

    def test_one_arm_adjust_mean_identity_is_NOT_causal_route(self):
        """Codex trap: a 1-arm adjust + mean + identity must NOT count."""
        sig = M.spec_signature(_one_arm_adjust_mean_identity_spec())
        assert M.is_causal_route(sig) is False

    def test_adjust_pcor_is_neither_route(self):
        sig = M.spec_signature(_adjust_pcor_buggy_spec())
        assert M.is_adjust_pcor(sig) is True
        assert M.is_causal_route(sig) is False
        assert M.is_observational_route(sig) is False

    def test_route_predicates_tolerate_json_roundtrip(self):
        """Codex post-G.1 trap: ground-sanity-only reloads signatures
        from recompile.json, and JSON has no tuple type — arm_kinds
        comes back as a list. Every route-shape predicate must still
        classify correctly after the round trip, otherwise the
        diagnostic silently skips the causal reroutes (which is exactly
        the bug the first G.1 run hit)."""
        causal_sig = json.loads(json.dumps(M.spec_signature(_causal_route_spec())))
        obs_sig = json.loads(json.dumps(M.spec_signature(_observational_route_spec())))
        buggy_sig = json.loads(json.dumps(M.spec_signature(_adjust_pcor_buggy_spec())))
        one_arm_sig = json.loads(
            json.dumps(M.spec_signature(_one_arm_adjust_mean_identity_spec()))
        )

        # arm_kinds must be a list after JSON round-trip (sanity check
        # that the test is actually exercising the failure mode).
        assert isinstance(causal_sig["arm_kinds"], list)
        assert isinstance(obs_sig["arm_kinds"], list)

        assert M.is_causal_route(causal_sig) is True
        assert M.is_observational_route(causal_sig) is False

        assert M.is_observational_route(obs_sig) is True
        assert M.is_causal_route(obs_sig) is False

        assert M.is_adjust_pcor(buggy_sig) is True
        assert M.is_causal_route(buggy_sig) is False
        assert M.is_observational_route(buggy_sig) is False

        assert M.is_causal_route(one_arm_sig) is False


# ---------------------------------------------------------------------------
# classify_sq — the role=required gate (the C1a inflation trap)
# ---------------------------------------------------------------------------


def _sig_with_role(spec_dict: dict, role: str) -> dict:
    sig = M.spec_signature(spec_dict)
    sig["role"] = role
    return sig


class TestClassifySQRoleGate:
    def test_route_causal_only_counts_when_required(self):
        """Codex trap: a route shape that only appears as `support`
        must NOT classify as route_*."""
        frozen_sigs = [_sig_with_role(_adjust_pcor_buggy_spec(), "required")]
        new_sigs_support_only = [
            _sig_with_role(_causal_route_spec(), "support"),
        ]
        status = M.classify_sq(
            frozen_sigs=frozen_sigs,
            new_sigs=new_sigs_support_only,
            abstained=False,
            compile_failed=False,
        )
        assert status == "other_change"

    def test_route_causal_counts_when_required(self):
        frozen_sigs = [_sig_with_role(_adjust_pcor_buggy_spec(), "required")]
        new_sigs_required = [
            _sig_with_role(_causal_route_spec(), "required"),
        ]
        status = M.classify_sq(
            frozen_sigs=frozen_sigs,
            new_sigs=new_sigs_required,
            abstained=False,
            compile_failed=False,
        )
        assert status == "route_causal"

    def test_route_observational_only_counts_when_required(self):
        frozen_sigs = [_sig_with_role(_adjust_pcor_buggy_spec(), "required")]
        new_sigs_support_only = [
            _sig_with_role(_observational_route_spec(), "support"),
        ]
        status = M.classify_sq(
            frozen_sigs=frozen_sigs,
            new_sigs=new_sigs_support_only,
            abstained=False,
            compile_failed=False,
        )
        assert status == "other_change"

    def test_route_observational_counts_when_required(self):
        frozen_sigs = [_sig_with_role(_adjust_pcor_buggy_spec(), "required")]
        new_sigs_required = [
            _sig_with_role(_observational_route_spec(), "required"),
        ]
        status = M.classify_sq(
            frozen_sigs=frozen_sigs,
            new_sigs=new_sigs_required,
            abstained=False,
            compile_failed=False,
        )
        assert status == "route_observational"

    def test_abstained_short_circuits(self):
        frozen_sigs = [_sig_with_role(_adjust_pcor_buggy_spec(), "required")]
        status = M.classify_sq(
            frozen_sigs=frozen_sigs,
            new_sigs=[],
            abstained=True,
            compile_failed=False,
        )
        assert status == "abstained"

    def test_compile_error_short_circuits(self):
        frozen_sigs = [_sig_with_role(_adjust_pcor_buggy_spec(), "required")]
        status = M.classify_sq(
            frozen_sigs=frozen_sigs,
            new_sigs=[],
            abstained=False,
            compile_failed=True,
        )
        assert status == "compile_error"

    def test_kept_when_signature_sets_match(self):
        frozen_sigs = [_sig_with_role(_observational_route_spec(), "required")]
        new_sigs = [_sig_with_role(_observational_route_spec(), "required")]
        status = M.classify_sq(
            frozen_sigs=frozen_sigs,
            new_sigs=new_sigs,
            abstained=False,
            compile_failed=False,
        )
        assert status == "kept"

    def test_role_change_breaks_kept(self):
        """A frozen `required` swapped to `support` must NOT count as kept."""
        frozen_sigs = [_sig_with_role(_observational_route_spec(), "required")]
        new_sigs = [_sig_with_role(_observational_route_spec(), "support")]
        status = M.classify_sq(
            frozen_sigs=frozen_sigs,
            new_sigs=new_sigs,
            abstained=False,
            compile_failed=False,
        )
        assert status == "other_change"


# ---------------------------------------------------------------------------
# spec_endpoint_vars / spec_control_vars — used by C1c reroute_quality
# ---------------------------------------------------------------------------


class TestSpecVariableExtraction:
    def test_endpoint_vars_from_arms_and_measurement(self):
        spec = _causal_route_spec()
        eps = M.spec_endpoint_vars(spec)
        assert "T" in eps
        assert "Y" in eps

    def test_control_vars_from_adjust_set(self):
        spec = _causal_route_spec()
        cs = M.spec_control_vars(spec)
        assert cs == {"W"}

    def test_control_vars_from_pcor_cond_set(self):
        spec = _observational_route_spec()
        cs = M.spec_control_vars(spec)
        assert cs == {"W"}
