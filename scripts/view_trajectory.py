#!/usr/bin/env python3
"""View agent and teacher trajectories side by side.

Usage:
    python scripts/view_trajectory.py trajectory.json
    python scripts/view_trajectory.py trajectory.json --comparison comparison.json
    python scripts/view_trajectory.py --generate --seed 42 [--save DIR]
"""

from __future__ import annotations

import argparse
import json
import sys
import textwrap

# -- display helpers (self-contained, no dependency on sreg.display) --


def _c(code: str, text: str) -> str:
    if not sys.stdout.isatty():
        return str(text)
    return f"{code}{text}\033[0m"


B = "\033[1m"
DIM = "\033[2m"
RED = "\033[91m"
GRN = "\033[92m"
YLW = "\033[93m"
BLU = "\033[94m"
MAG = "\033[95m"
CYN = "\033[96m"
WHT = "\033[97m"


def _line(char: str = "-", width: int = 80) -> None:
    print(_c(DIM, char * width))


def _header(text: str) -> None:
    print()
    _line("=")
    print(_c(B + BLU, f"  {text}"))
    _line("=")


def _safe(text: str) -> str:
    enc = getattr(sys.stdout, "encoding", "utf-8") or "utf-8"
    return text.encode(enc, errors="replace").decode(enc)


def _wrap(text: str, width: int = 74, indent: int = 6) -> str:
    return textwrap.fill(
        text, width=width,
        initial_indent=" " * indent, subsequent_indent=" " * indent,
    )


def _fmt_dist(dist: dict) -> str:
    parts = [f"{k}: {v:.4f}" for k, v in sorted(dist.items())]
    return "{" + ", ".join(parts) + "}"


# -- agent trajectory viewer --


def show_agent_trajectory(data: dict) -> None:
    _header("AGENT TRAJECTORY")

    print(f"    {_c(DIM, 'World:')} {data.get('world_id', '?')}")
    print(f"    {_c(DIM, 'Seed:')} {data.get('seed', '?')}")
    print(f"    {_c(DIM, 'Target:')} {data.get('target_node', '?')}")
    print(f"    {_c(DIM, 'Budget:')} {data.get('budget_used', '?')}/{data.get('budget', '?')}")
    score = data.get("score")
    if score is not None:
        print(f"    {_c(DIM, 'KL score:')} {_c(B, f'{score:.4f}')}")
    print()

    steps = data.get("steps", [])
    for s in steps:
        step_num = s.get("step", "?")

        thinking = s.get("thinking")
        tool_call = s.get("tool_call")
        observation = s.get("observation")
        error = s.get("error")
        is_submit = s.get("is_submit", False)

        # Step header
        if is_submit:
            label = _c(B + GRN, f"STEP {step_num} -- SUBMIT")
        elif error:
            label = _c(B + RED, f"STEP {step_num} -- ERROR")
        elif tool_call:
            label = _c(B + CYN, f"STEP {step_num} -- {tool_call}")
        else:
            label = _c(B + WHT, f"STEP {step_num} -- thinking")

        print(f"    {label}")

        if thinking:
            trunc = thinking[:300] + ("..." if len(thinking) > 300 else "")
            print(_wrap(_safe(trunc), indent=8))

        if tool_call and not is_submit:
            args = s.get("tool_args", {})
            print(f"        {_c(CYN, 'Call:')} {tool_call}({json.dumps(args)})")

        if observation:
            print(f"        {_c(YLW, 'Obs:')} {observation}")

        if error:
            print(f"        {_c(RED, 'Error:')} {_safe(error[:200])}")

        if is_submit:
            dist = s.get("tool_args", {}).get("distribution", {})
            if dist:
                print(f"        {_c(GRN, 'Distribution:')} {_fmt_dist(dist)}")

        print()

    # Final answer
    answer = data.get("submitted_answer")
    if answer:
        print(f"    {_c(B + GRN, 'Final answer:')} {_fmt_dist(answer)}")
    else:
        print(f"    {_c(B + RED, 'No answer submitted')}")

    reasoning = data.get("reasoning")
    if reasoning:
        print(f"    {_c(DIM, 'Reasoning:')} {_safe(reasoning[:200])}")

    confidence = data.get("confidence")
    if confidence is not None:
        print(f"    {_c(DIM, 'Confidence:')} {confidence:.2f}")

    print()


# -- comparison viewer --


def show_comparison(data: dict) -> None:
    _header("TRAJECTORY COMPARISON: AGENT vs TEACHER")

    print(f"    {_c(DIM, 'World:')} {data.get('world_id', '?')}")
    print(f"    {_c(DIM, 'Target:')} {data.get('target_node', '?')}")
    print(f"    {_c(DIM, 'True state:')} {_c(B + YLW, data.get('true_state', '?'))}")
    print(f"    {_c(DIM, 'Budget:')} {data.get('budget', '?')}")

    verdict = data.get("verdict", "?")
    verdict_color = {
        "EXCELLENT": GRN, "GOOD": GRN, "FAIR": YLW, "POOR": RED, "NO_SUBMIT": RED,
    }.get(verdict, WHT)
    print(f"    {_c(DIM, 'Verdict:')} {_c(B + verdict_color, verdict)}")
    print()

    teacher_steps = data.get("teacher_steps", [])
    agent_steps = data.get("agent_steps", [])
    max_steps = max(len(teacher_steps), len(agent_steps))

    for i in range(max_steps):
        _line("-", 80)

        # Teacher step
        if i < len(teacher_steps):
            ts = teacher_steps[i]
            ig = ts.get("info_gain", 0)
            post = ts.get("posterior", {})
            step_n = ts.get("step", "?")
            action_n = ts.get("action", "?")
            obs_raw = ts.get("observation", "?")
            obs_val = obs_raw.split("= ")[-1] if "= " in obs_raw else obs_raw
            label = "TEACHER step %s:" % step_n
            print(
                "    %s observe %s = %s  (IG: %.4f)"
                % (_c(B + GRN, label), _c(B, action_n), _c(YLW, obs_val), ig)
            )
            print("      posterior: %s" % _fmt_dist(post))
        else:
            done_msg = "TEACHER: (done at step %d)" % len(teacher_steps)
            print("    %s" % _c(DIM, done_msg))

        # Agent step
        if i < len(agent_steps):
            ag = agent_steps[i]
            action = ag.get("action", "")
            obs = ag.get("observation", "")
            thinking = ag.get("thinking", "")
            error = ag.get("error", "")

            parts = []
            if action:
                args = ag.get("args", {})
                parts.append(f"{action}({json.dumps(args)})")
            if obs:
                parts.append(f"-> {obs}")
            if error:
                parts.append(_c(RED, f"ERROR: {error[:80]}"))

            step_n = ag.get("step", "?")
            step_label = "AGENT step %s:" % step_n
            action_str = " ".join(parts) if parts else "(thinking only)"
            print("    %s %s" % (_c(B + BLU, step_label), action_str))

            if thinking:
                trunc = thinking[:150] + ("..." if len(thinking) > 150 else "")
                print("      %s" % _c(DIM, _safe(trunc)))

            if "submitted" in ag:
                print("      %s %s" % (_c(GRN, "submitted:"), _fmt_dist(ag["submitted"])))
        else:
            done_msg = "AGENT: (done at step %d)" % len(agent_steps)
            print("    %s" % _c(DIM, done_msg))

        print()

    # Final comparison
    _line("=", 80)
    print(f"    {_c(B, 'TEACHER')}:")
    tf = data.get("teacher_final_posterior", {})
    print(f"      posterior: {_fmt_dist(tf)}")
    print(f"      budget: {data.get('teacher_budget_used', '?')}/{data.get('budget', '?')}")
    print(f"      KL: {data.get('teacher_kl', 0):.6f}")
    print()

    print(f"    {_c(B, 'AGENT')}:")
    af = data.get("agent_final_posterior")
    if af:
        print(f"      posterior: {_fmt_dist(af)}")
    else:
        print(f"      {_c(RED, 'no answer submitted')}")
    print(f"      budget: {data.get('agent_budget_used', '?')}/{data.get('budget', '?')}")
    akl = data.get("agent_kl")
    if akl is not None:
        print(f"      KL: {akl:.6f}")
    print()


# -- main --


def main():
    parser = argparse.ArgumentParser(
        description="View agent/teacher trajectories"
    )
    parser.add_argument(
        "file", nargs="?",
        help="Path to agent trajectory JSON or comparison JSON"
    )
    parser.add_argument(
        "--comparison", "-c", type=str, default=None,
        help="Path to comparison JSON file"
    )
    args = parser.parse_args()

    if args.comparison:
        with open(args.comparison, encoding="utf-8") as f:
            data = json.load(f)
        show_comparison(data)
    elif args.file:
        with open(args.file, encoding="utf-8") as f:
            data = json.load(f)

        # Detect type by presence of key fields
        if "teacher_steps" in data and "agent_steps" in data:
            show_comparison(data)
        elif "steps" in data:
            show_agent_trajectory(data)
        else:
            print("Unknown file format. Expected agent trajectory or comparison JSON.")
            sys.exit(1)
    else:
        parser.print_help()
        sys.exit(1)

    print()


if __name__ == "__main__":
    main()
