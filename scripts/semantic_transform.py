"""Transform an SRC's semantic layer to abstract or fictional mode.

Takes an existing src.json and produces a new version with transformed
variable names, narratives, and questions. The BN structure, CPDs, and
scoring remain identical.

Usage:
    python scripts/semantic_transform.py experiments/eval_smoking_v3/src.json --mode abstract -o experiments/eval_smoking_v3_abstract/
    python scripts/semantic_transform.py experiments/eval_smoking_v3/src.json --mode fictional -o experiments/eval_smoking_v3_fictional/
"""

import argparse
import csv
import io
import json
import os
import re
import string
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


def _build_abstract_rename(node_names: list[str], target_node: str) -> dict[str, str]:
    """Map node names to abstract labels: V1, V2, ..., Y (target)."""
    rename = {}
    counter = 1
    for name in node_names:
        if name == target_node:
            rename[name] = "Y"
        else:
            rename[name] = f"V{counter}"
            counter += 1
    return rename


def _apply_rename_to_text(text: str, rename: dict[str, str]) -> str:
    """Replace all occurrences of old names with new names in text."""
    # Sort by length descending to avoid partial replacements
    for old, new in sorted(rename.items(), key=lambda x: -len(x[0])):
        # Replace with word boundaries (underscores count as word chars)
        # Also handle variants with spaces instead of underscores
        text = text.replace(old, new)
        # Handle "human readable" versions (underscores -> spaces)
        human_old = old.replace("_", " ")
        if human_old != old:
            text = re.sub(re.escape(human_old), new.replace("_", " "), text, flags=re.IGNORECASE)
    return text


def transform_abstract(src: dict) -> dict:
    """Transform SRC to abstract mode: V1, V2, ..., Y."""
    src = json.loads(json.dumps(src))  # deep copy

    world = src["world"]
    tasks = src["tasks"]
    problem = src["problem"]

    # Find target node
    target_node = None
    for n in world["nodes"]:
        if n["type"] == "target":
            target_node = n["name"]
            break
    if not target_node and tasks:
        target_node = tasks[0].get("target_node", world["nodes"][-1]["name"])

    # Build rename map
    node_names = [n["name"] for n in world["nodes"]]
    rename = _build_abstract_rename(node_names, target_node)

    # Transform world
    world["scenario_title"] = "System analysis"
    world["scenario_description"] = (
        "An observed system with multiple interacting variables. "
        "Some variables are directly observable, others are hidden. "
        "The goal is to understand causal relationships and answer "
        "questions about the system using available data."
    )
    world["domain"] = "abstract causal system"
    world["theoretical_context"] = (
        "The system contains observable and latent variables connected "
        "by causal relationships. Data has been collected from the system."
    )

    # Rename nodes
    for node in world["nodes"]:
        old_name = node["name"]
        node["name"] = rename[old_name]
        # Rename states to generic
        if "states" in node:
            node["states"] = [f"s{i}" for i in range(len(node["states"]))]

    # Rename edges
    for edge in world["edges"]:
        edge["from_node"] = rename.get(edge["from_node"], edge["from_node"])
        edge["to_node"] = rename.get(edge["to_node"], edge["to_node"])

    # Rename CPDs
    cpds = world.get("cpds", [])
    if isinstance(cpds, list):
        for cpd in cpds:
            if "node" in cpd:
                cpd["node"] = rename.get(cpd["node"], cpd["node"])
            if "parents" in cpd:
                cpd["parents"] = [rename.get(p, p) for p in cpd["parents"]]
    elif isinstance(cpds, dict):
        new_cpds = {}
        for old_name, cpd in cpds.items():
            new_cpds[rename.get(old_name, old_name)] = cpd
        world["cpds"] = new_cpds

    # Transform tasks — rewrite questions to be fully abstract
    _abstract_questions = {
        "causal_effect": "If V{intervention} were set to a specific value, how would Y change?",
        "should_condition": "Should an analyst condition on {cond_var} when estimating the effect of {treat_var} on Y?",
        "adjustment_set": "Which variables should be controlled for when estimating the causal effect of {treat_var} on Y?",
        "infer_latent_cause": "What hidden variable best explains residual variation in {target} among similar observed cases?",
        "infer_target": "Given the observed data, what is the most likely value of Y?",
        "best_intervention": "Which single variable, if intervened on, would most increase the probability of Y being {state}?",
        "compare_interventions": "Which intervention has a larger effect on Y: setting {a} to a value, or setting {b} to a value?",
        "next_best_observation": "Which unobserved variable would be most informative to measure next?",
        "hypothesis_selection": "Which hypothesis best explains the observed data?",
    }

    for task in tasks:
        old_target = task["target_node"]
        task["target_node"] = rename.get(task["target_node"], task["target_node"])

        # Try to build a clean abstract question
        ttype = task.get("type", "")
        if ttype == "causal_effect":
            # Find intervention node from the question or intervention field
            int_node = ""
            if task.get("intervention") and isinstance(task["intervention"], dict):
                int_node = list(task["intervention"].keys())[0]
                int_node = rename.get(int_node, int_node)
            task["question"] = f"If {int_node or 'the exposure variable'} were set to a specific value, how would {rename.get(old_target, 'Y')} change?"
        elif ttype == "should_condition":
            # Extract conditioning variable from question
            task["question"] = _apply_rename_to_text(task["question"], rename)
            # Strip domain-specific language
            task["question"] = f"Should an analyst condition on {task['question'].split('condition on ')[-1].split(' when')[0]} when estimating the causal effect on {rename.get(old_target, 'Y')}?"
        elif ttype == "adjustment_set":
            task["question"] = f"Which observed variables should be controlled for to estimate the causal effect on {rename.get(old_target, 'Y')} from observational data?"
        elif ttype == "infer_latent_cause":
            task["question"] = f"What hidden variable best explains why some cases with similar observed values have different outcomes for {rename.get(old_target, 'Y')}?"
        elif ttype == "infer_target":
            task["question"] = f"Given the observed data, what is the most likely value of {rename.get(old_target, 'Y')}?"
        elif ttype == "best_intervention":
            task["question"] = f"Which single variable, if intervened on, would most change the probability of {rename.get(old_target, 'Y')}?"
        elif ttype == "compare_interventions":
            task["question"] = _apply_rename_to_text(task["question"], rename)
        elif ttype == "next_best_observation":
            task["question"] = f"Which unobserved variable would be most informative to measure next for predicting {rename.get(old_target, 'Y')}?"
        else:
            task["question"] = _apply_rename_to_text(task["question"], rename)

        if task.get("available_evidence"):
            if isinstance(task["available_evidence"], dict):
                new_ev = {}
                for k, v in task["available_evidence"].items():
                    new_ev[rename.get(k, k)] = v
                task["available_evidence"] = new_ev
        if task.get("given_evidence"):
            if isinstance(task["given_evidence"], dict):
                new_ev = {}
                for k, v in task["given_evidence"].items():
                    new_ev[rename.get(k, k)] = v
                task["given_evidence"] = new_ev
        if task.get("intervention"):
            if isinstance(task["intervention"], dict):
                new_int = {}
                for k, v in task["intervention"].items():
                    new_int[rename.get(k, k)] = v
                task["intervention"] = new_int

    # Transform problem
    problem["scenario_title"] = "System analysis"
    problem["domain"] = "abstract causal system"
    problem["narrative"] = (
        "You are analyzing an observed system with multiple interacting variables. "
        "Some variables are directly measured, at least one is hidden. "
        "Your task is to answer research questions about this system "
        "using the available data."
    )
    problem["theoretical_context"] = (
        "The system has been observed over time. The data below represent "
        "measurements from this system. Not all relevant variables may be "
        "directly observable."
    )
    if problem.get("primary_question"):
        problem["primary_question"] = _apply_rename_to_text(
            problem["primary_question"], rename
        )

    # Transform data assets (rename columns)
    for asset in problem.get("data_assets", []):
        asset["name"] = "Dataset"
        asset["description"] = "Observed measurements from the system."
        if asset.get("columns"):
            asset["columns"] = [rename.get(c, c) for c in asset["columns"]]
        if asset.get("data"):
            if isinstance(asset["data"], str):
                # CSV string — rename header
                lines = asset["data"].split("\n")
                if lines:
                    header = lines[0]
                    for old, new in sorted(rename.items(), key=lambda x: -len(x[0])):
                        header = header.replace(old, new)
                    lines[0] = header
                    asset["data"] = "\n".join(lines)
            elif isinstance(asset["data"], list):
                # List of dicts — rename keys
                new_data = []
                for row in asset["data"]:
                    new_row = {}
                    for k, v in row.items():
                        new_row[rename.get(k, k)] = v
                    new_data.append(new_row)
                asset["data"] = new_data

    # Transform available_actions
    for action in problem.get("available_actions", []):
        if action.get("nodes"):
            action["nodes"] = [rename.get(n, n) for n in action["nodes"]]
        if action.get("node"):
            action["node"] = rename.get(action["node"], action["node"])
        if action.get("description"):
            action["description"] = _apply_rename_to_text(
                action["description"], rename
            )

    # Store rename map in metadata for reference
    src.setdefault("metadata", {})["semantic_mode"] = "abstract"
    src["metadata"]["rename_map"] = rename

    return src


def transform_fictional(src: dict, client=None, model: str = None) -> dict:
    """Transform SRC to fictional mode: invented names, fictional domain."""
    from openai import OpenAI

    src = json.loads(json.dumps(src))  # deep copy

    if not client:
        client = OpenAI(
            base_url=os.environ["AZURE_FOUNDRY_BASE_URL"],
            api_key=os.environ["AZURE_INFERENCE_CREDENTIAL"],
        )
    if not model:
        model = os.environ.get("AZURE_MODEL", "gpt-5.4")

    world = src["world"]
    tasks = src["tasks"]
    problem = src["problem"]

    # Gather current names and context
    node_names = [n["name"] for n in world["nodes"]]
    target_node = None
    for n in world["nodes"]:
        if n["type"] == "target":
            target_node = n["name"]
            break

    node_info = []
    for n in world["nodes"]:
        node_info.append(f"- {n['name']} ({n['type']}): states={n.get('states', [])}")

    questions = []
    for t in tasks:
        questions.append(f"- ({t['type']}) {t['question'][:150]}")

    prompt = f"""\
You are transforming a synthetic research case from a realistic domain into a
COMPLETELY FICTIONAL domain. The goal: a solver should NOT be able to use
real-world knowledge to answer questions. All names, domains, and context must
be invented. BUT the causal structure and scientific reasoning must stay intact.

CURRENT SRC:
- Domain: {world.get('domain', '?')}
- Title: {world.get('scenario_title', '?')}
- Variables:
{chr(10).join(node_info)}
- Questions:
{chr(10).join(questions)}

INSTRUCTIONS:
1. Invent a FICTIONAL domain (not real science — made-up substances, organisms,
   phenomena, or processes). Use invented proper nouns (places, compounds,
   species) that don't exist.
2. Rename EVERY variable to a fictional but semantically meaningful name.
   Keep the causal ROLE clear (exposure stays exposure, outcome stays outcome,
   latent stays latent). Don't use generic names like X1 — use invented terms.
3. Rewrite the scenario title, narrative (2-3 paragraphs), domain, and
   theoretical context using the fictional domain.
4. Rewrite each question using the new variable names. Keep the same
   scientific reasoning type.
5. Rename variable states to match the fictional domain.

Return ONLY valid JSON:
{{
  "domain": "fictional domain name",
  "scenario_title": "fictional title",
  "narrative": "2-3 paragraph fictional scenario",
  "theoretical_context": "1 paragraph fictional background",
  "rename_map": {{"old_name": "new_name", ...}},
  "state_renames": {{"old_name": {{"old_state": "new_state", ...}}, ...}},
  "questions": ["rewritten question 1", "rewritten question 2", ...]
}}
"""

    try:
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
        )
    except Exception:
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
        )

    raw = response.choices[0].message.content or "{}"
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1] if "\n" in raw else raw[3:]
    if raw.endswith("```"):
        raw = raw[:-3]
    raw = raw.strip()

    try:
        result = json.loads(raw)
    except json.JSONDecodeError:
        print(f"ERROR: Failed to parse LLM response: {raw[:500]}")
        return src

    rename = result.get("rename_map", {})
    state_renames = result.get("state_renames", {})

    # Apply renames to world
    world["scenario_title"] = result.get("scenario_title", world["scenario_title"])
    world["scenario_description"] = result.get("narrative", world.get("scenario_description", ""))
    world["domain"] = result.get("domain", world["domain"])
    world["theoretical_context"] = result.get("theoretical_context", world.get("theoretical_context", ""))

    # Rename nodes and states
    for node in world["nodes"]:
        old_name = node["name"]
        node["name"] = rename.get(old_name, old_name)
        sr = state_renames.get(old_name, {})
        if sr and "states" in node:
            node["states"] = [sr.get(s, s) for s in node["states"]]

    # Rename edges
    for edge in world["edges"]:
        edge["from_node"] = rename.get(edge["from_node"], edge["from_node"])
        edge["to_node"] = rename.get(edge["to_node"], edge["to_node"])

    # Rename CPDs
    cpds = world.get("cpds", [])
    if isinstance(cpds, list):
        for cpd in cpds:
            if "node" in cpd:
                cpd["node"] = rename.get(cpd["node"], cpd["node"])
            if "parents" in cpd:
                cpd["parents"] = [rename.get(p, p) for p in cpd["parents"]]
    elif isinstance(cpds, dict):
        new_cpds = {}
        for old_name, cpd in cpds.items():
            new_cpds[rename.get(old_name, old_name)] = cpd
        world["cpds"] = new_cpds

    # Transform tasks
    new_questions = result.get("questions", [])
    for i, task in enumerate(tasks):
        task["target_node"] = rename.get(task["target_node"], task["target_node"])
        if i < len(new_questions):
            task["question"] = new_questions[i]
        else:
            task["question"] = _apply_rename_to_text(task["question"], rename)
        # Rename evidence keys
        for field in ("available_evidence", "given_evidence", "intervention"):
            if task.get(field) and isinstance(task[field], dict):
                new_dict = {}
                for k, v in task[field].items():
                    new_dict[rename.get(k, k)] = v
                task[field] = new_dict

    # Transform problem
    problem["scenario_title"] = result.get("scenario_title", problem.get("scenario_title", ""))
    problem["domain"] = result.get("domain", problem.get("domain", ""))
    problem["narrative"] = result.get("narrative", problem.get("narrative", ""))
    problem["theoretical_context"] = result.get(
        "theoretical_context", problem.get("theoretical_context", "")
    )
    if problem.get("primary_question"):
        problem["primary_question"] = _apply_rename_to_text(
            problem["primary_question"], rename
        )

    # Transform data assets
    for asset in problem.get("data_assets", []):
        asset["description"] = _apply_rename_to_text(asset.get("description", ""), rename)
        if asset.get("columns"):
            asset["columns"] = [rename.get(c, c) for c in asset["columns"]]
        if asset.get("data"):
            if isinstance(asset["data"], str):
                lines = asset["data"].split("\n")
                if lines:
                    header = lines[0]
                    for old, new in sorted(rename.items(), key=lambda x: -len(x[0])):
                        header = header.replace(old, new)
                    lines[0] = header
                    asset["data"] = "\n".join(lines)
            elif isinstance(asset["data"], list):
                new_data = []
                for row in asset["data"]:
                    new_row = {}
                    for k, v in row.items():
                        new_row[rename.get(k, k)] = v
                    new_data.append(new_row)
                asset["data"] = new_data

    # Transform actions
    for action in problem.get("available_actions", []):
        if action.get("nodes"):
            action["nodes"] = [rename.get(n, n) for n in action["nodes"]]
        if action.get("node"):
            action["node"] = rename.get(action["node"], action["node"])
        if action.get("description"):
            action["description"] = _apply_rename_to_text(action["description"], rename)

    src.setdefault("metadata", {})["semantic_mode"] = "fictional"
    src["metadata"]["rename_map"] = rename

    return src


def export_src(src: dict, output_dir: str):
    """Export transformed SRC to output directory."""
    os.makedirs(output_dir, exist_ok=True)

    # Save src.json
    with open(os.path.join(output_dir, "src.json"), "w", encoding="utf-8") as f:
        json.dump(src, f, indent=2, ensure_ascii=False)

    # Save datasets as CSV
    for i, asset in enumerate(src.get("problem", {}).get("data_assets", [])):
        if asset.get("data"):
            suffix = f"_{i}" if i > 0 else ""
            path = os.path.join(output_dir, f"dataset{suffix}.csv")
            data = asset["data"]
            with open(path, "w", encoding="utf-8", newline="") as f:
                if isinstance(data, str):
                    f.write(data)
                elif isinstance(data, list) and data:
                    writer = csv.DictWriter(f, fieldnames=data[0].keys())
                    writer.writeheader()
                    writer.writerows(data)

    print(f"Exported to {output_dir}")
    print(f"  Mode: {src.get('metadata', {}).get('semantic_mode', '?')}")
    print(f"  Rename map: {src.get('metadata', {}).get('rename_map', {})}")


def main():
    parser = argparse.ArgumentParser(description="Transform SRC semantic layer")
    parser.add_argument("src_json", help="Path to src.json")
    parser.add_argument("--mode", choices=["abstract", "fictional"], required=True)
    parser.add_argument("-o", "--output", required=True, help="Output directory")
    args = parser.parse_args()

    with open(args.src_json, encoding="utf-8") as f:
        src = json.load(f)

    if args.mode == "abstract":
        transformed = transform_abstract(src)
    else:
        transformed = transform_fictional(src)

    export_src(transformed, args.output)


if __name__ == "__main__":
    main()
