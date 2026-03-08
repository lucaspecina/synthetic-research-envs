"""Pretty display for SREG objects in terminal (ANSI) and Jupyter (HTML)."""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sreg.models.research_problem import ResearchProblem
    from sreg.models.score import Score
    from sreg.models.world import World


def _in_notebook() -> bool:
    """Detect if running inside a Jupyter notebook."""
    try:
        from IPython import get_ipython

        shell = get_ipython()
        if shell is None:
            return False
        return shell.__class__.__name__ == "ZMQInteractiveShell"
    except ImportError:
        return False


# -------------------------------------------------------------------
# ANSI helpers
# -------------------------------------------------------------------


class _C:
    """ANSI color codes."""

    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"
    WHITE = "\033[97m"


def _supports_color() -> bool:
    if not hasattr(sys.stdout, "isatty"):
        return False
    return sys.stdout.isatty()


def _c(code: str, text: str) -> str:
    """Wrap text in ANSI code if colors supported."""
    if not _supports_color():
        return text
    return f"{code}{text}{_C.RESET}"


def _bar(fraction: float, width: int = 20) -> str:
    """Render a mini horizontal bar chart (ASCII-safe)."""
    filled = round(fraction * width)
    return "#" * filled + "." * (width - filled)


def _safe_print(text: str) -> None:
    """Print text, replacing unencodable chars on Windows."""
    try:
        sys.stdout.write(text + "\n")
        sys.stdout.flush()
    except UnicodeEncodeError:
        enc = getattr(sys.stdout, "encoding", "utf-8") or "utf-8"
        safe = text.encode(enc, errors="replace").decode(enc)
        sys.stdout.write(safe + "\n")
        sys.stdout.flush()


# -------------------------------------------------------------------
# Box drawing (ASCII-safe)
# -------------------------------------------------------------------


def _box(
    title: str,
    lines: list[str],
    color: str = _C.BLUE,
    width: int = 60,
) -> str:
    """Render a bordered box with title."""
    bc = color if _supports_color() else ""
    rs = _C.RESET if _supports_color() else ""
    iw = width - 2

    top = f"{bc}+{'-' * iw}+{rs}"
    sep = f"{bc}+{'-' * iw}+{rs}"
    bot = f"{bc}+{'-' * iw}+{rs}"

    # Title line with BOLD
    bold_title = _c(_C.BOLD, title)
    ansi_extra = len(bold_title) - len(title)
    tl = f"{bc}|{rs} {bold_title:<{iw - 1 + ansi_extra}}{bc}|{rs}"

    body = []
    for line in lines:
        vis = len(line.encode("ascii", "ignore").decode("ascii"))
        extra = len(line) - vis
        padded = f"{line:<{iw - 1 + extra}}"
        body.append(f"{bc}|{rs} {padded}{bc}|{rs}")

    return "\n".join([top, tl, sep, *body, bot])


# -------------------------------------------------------------------
# Public display functions
# -------------------------------------------------------------------


def _node_styles() -> tuple[dict[str, str], dict[str, str]]:
    """Return (icon_map, color_map) for node types. Single source of truth."""
    icons = {"latent": "*", "observable": "o", "target": "@"}
    colors = {"latent": _C.RED, "observable": _C.GREEN, "target": _C.YELLOW}
    return icons, colors


def show_world(world: World) -> None:
    """Pretty-print a World object."""
    if _in_notebook():
        _show_world_html(world)
        return

    _type_icon, _type_color = _node_styles()
    type_badge = {k: _c(v, k.upper()[:6]) for k, v in _type_color.items()}

    lines = [
        f"ID:         {_c(_C.CYAN, world.id)}",
        f"Template:   {world.template_family}",
        f"Dificultad: {_c(_C.BOLD, world.difficulty.level)}",
        f"Nodos: {len(world.nodes)}  |  Conexiones: {len(world.edges)}",
        "",
    ]
    for n in world.nodes:
        icon = _type_icon.get(n.type, "?")
        badge = type_badge.get(n.type, n.type)
        states = ", ".join(n.states)
        lines.append(f"  {icon} {_c(_C.BOLD, n.name):<30} {badge:<20} [{states}]")
    lines.append("")
    for e in world.edges:
        lines.append(f"  {e.from_node}  -->  {e.to_node}")

    _safe_print(_box("MUNDO", lines, _C.BLUE))


def show_validation(
    passed: bool,
    failures: list[str],
    metrics: dict[str, float],
) -> None:
    """Pretty-print validation results."""
    if _in_notebook():
        _show_validation_html(passed, failures, metrics)
        return

    if passed:
        header = _c(_C.GREEN, "[OK] VALIDACION EXITOSA")
    else:
        header = _c(_C.RED, "[X] VALIDACION FALLIDA")

    lines = [header, ""]
    if not passed:
        for f in failures:
            lines.append(f"  {_c(_C.RED, '*')} {f}")
        lines.append("")

    lines.append(_c(_C.DIM, "Metricas:"))
    for k, v in metrics.items():
        label = k.replace("_", " ").title()
        lines.append(f"  {label:<30} {v:.3f}")

    color = _C.GREEN if passed else _C.RED
    _safe_print(_box("VALIDACION", lines, color))


def _find_target(world: World) -> str:
    """Find the target node name dynamically."""
    from sreg.models.world import NodeType

    for n in world.nodes:
        if n.type == NodeType.TARGET:
            return n.name
    return "target_outcome"


def show_truth(world: World, true_state: dict[str, str]) -> None:
    """Pretty-print the sampled ground truth."""
    if _in_notebook():
        _show_truth_html(world, true_state)
        return

    _type_icon, _type_color = _node_styles()

    lines = [
        _c(_C.DIM, "Valores reales (el agente NO puede verlos):"),
        "",
    ]
    for n in world.nodes:
        icon = _type_icon.get(n.type, "?")
        clr = _type_color.get(n.type, "")
        val = true_state[n.name]
        lines.append(f"  {_c(clr, icon)} {n.name:<25} = {_c(_C.BOLD + _C.CYAN, val)}")

    target = _find_target(world)
    target_val = true_state.get(target, "?")
    lines.append("")
    lines.append(
        f"  Objetivo: predecir {_c(_C.BOLD + _C.YELLOW, f'{target} = {target_val}')}"
    )

    _safe_print(_box("VERDAD OCULTA", lines, _C.MAGENTA))


def show_prior(
    prior: dict[str, float],
    entropy: float,
    true_value: str,
) -> None:
    """Pretty-print prior distribution over target."""
    if _in_notebook():
        _show_prior_html(prior, entropy, true_value)
        return

    lines = [
        f"Entropia: {_c(_C.RED + _C.BOLD, f'{entropy:.2f}')} bits",
        "",
    ]
    for state, prob in prior.items():
        bar = _bar(prob)
        marker = _c(_C.RED, " << verdad") if state == true_value else ""
        lines.append(f"  {state:<12} {bar} {prob:>6.1%}{marker}")

    best = max(prior, key=prior.get)
    lines.append("")
    pct = f"{prior[best]:.1%}"
    if best == true_value:
        tag = _c(_C.GREEN, "[OK] acertaria")
        lines.append(f"  Diria '{best}' ({pct}) {tag}")
    else:
        tag = _c(_C.RED, "[X] se equivocaria")
        lines.append(f"  Diria '{best}' ({pct}) {tag}")

    _safe_print(_box("PRIOR P(target)", lines, _C.BLUE))


def show_step(
    step_num: int,
    node: str,
    observed_value: str,
    gains: dict[str, float],
    posterior: dict[str, float],
    entropy: float,
    true_value: str,
) -> None:
    """Pretty-print a single teacher step."""
    if _in_notebook():
        _show_step_html(
            step_num,
            node,
            observed_value,
            gains,
            posterior,
            entropy,
            true_value,
        )
        return

    map_state = max(posterior, key=posterior.get)
    correct = map_state == true_value
    icon = _c(_C.GREEN, "[OK]") if correct else _c(_C.RED, "[X]")

    obs_msg = f"{node} = {observed_value}"
    lines = [
        f"Observa: {_c(_C.BOLD + _C.CYAN, obs_msg)}",
        "",
        _c(_C.DIM, "Info gain por variable:"),
    ]
    for gn, gv in sorted(gains.items(), key=lambda x: -x[1]):
        marker = _c(_C.YELLOW, " <<") if gn == node else ""
        lines.append(f"  {gn:<20} {gv:.4f} bits{marker}")

    lines.append("")
    lines.append(_c(_C.DIM, "Posterior P(target):"))
    for state, prob in posterior.items():
        bar = _bar(prob, width=15)
        marker = _c(_C.RED, " <<") if state == true_value else ""
        lines.append(f"  {state:<12} {bar} {prob:>6.1%}{marker}")

    lines.append("")
    lines.append(f"  Prediccion: {_c(_C.BOLD, map_state)} {icon}  |  Entropia: {entropy:.3f} bits")

    color = _C.GREEN if correct else _C.RED
    _safe_print(_box(f"TURNO {step_num}", lines, color))


def show_result(prediction: str, true_value: str) -> None:
    """Pretty-print final episode result."""
    if _in_notebook():
        _show_result_html(prediction, true_value)
        return

    correct = prediction == true_value
    if correct:
        msg = _c(_C.GREEN + _C.BOLD, f"[OK] CORRECTO - {prediction}")
    else:
        msg = _c(
            _C.RED + _C.BOLD,
            f"[X] INCORRECTO - predijo {prediction}, verdad: {true_value}",
        )

    lines = [msg]
    color = _C.GREEN if correct else _C.RED
    _safe_print(_box("RESULTADO FINAL", lines, color))


def show_comparison(
    teacher_pred: str,
    random_pred: str,
    true_value: str,
    teacher_kl: float,
    random_kl: float,
    teacher_entropy: float,
    random_entropy: float,
) -> None:
    """Pretty-print teacher vs random comparison."""
    if _in_notebook():
        _show_comparison_html(
            teacher_pred,
            random_pred,
            true_value,
            teacher_kl,
            random_kl,
            teacher_entropy,
            random_entropy,
        )
        return

    t_ok = _c(_C.GREEN, "[OK]") if teacher_pred == true_value else _c(_C.RED, "[X]")
    r_ok = _c(_C.GREEN, "[OK]") if random_pred == true_value else _c(_C.RED, "[X]")

    lines = [
        f"{'':20} {'Teacher':>12}   {'Random':>12}",
        f"{'-' * 50}",
        f"{'Prediccion':<20} {teacher_pred:>12}   {random_pred:>12}",
        f"{'Verdad':<20} {true_value:>12}   {true_value:>12}",
        f"{'Correcto?':<20} {t_ok:>12}   {r_ok:>12}",
        f"{'KL div':<20} {teacher_kl:>12.4f}   {random_kl:>12.4f}",
        f"{'Entropia':<20} {teacher_entropy:>11.3f}   {random_entropy:>11.3f}",
        "",
        _c(_C.DIM, "KL mas bajo = mejor (0 = perfecto)"),
    ]

    _safe_print(_box("TEACHER vs RANDOM", lines, _C.MAGENTA))


def show_research_problem(problem: ResearchProblem) -> None:
    """Pretty-print a ResearchProblem — what the agent sees."""
    if _in_notebook():
        _show_research_problem_html(problem)
        return

    lines = [
        f"Titulo:    {_c(_C.BOLD + _C.CYAN, problem.title)}",
        f"Dominio:   {problem.domain}",
        f"Budget:    {_c(_C.BOLD, str(problem.budget))} observaciones",
        f"Target:    {_c(_C.YELLOW, problem.target_node)} ({', '.join(problem.target_states)})",
        "",
    ]

    # Description (wrap long text)
    lines.append(_c(_C.DIM, "Descripcion:"))
    desc = problem.description
    for i in range(0, len(desc), 80):
        lines.append(f"  {desc[i:i+80]}")
    lines.append("")

    # Theoretical context
    if problem.theoretical_context:
        lines.append(_c(_C.DIM, "Contexto teorico:"))
        ctx = problem.theoretical_context
        for i in range(0, len(ctx), 80):
            lines.append(f"  {ctx[i:i+80]}")
        lines.append("")

    # Research question
    lines.append(_c(_C.DIM, "Pregunta de investigacion:"))
    lines.append(f"  {_c(_C.BOLD, problem.research_question)}")
    lines.append("")

    # Data assets
    lines.append(_c(_C.DIM, f"Datos disponibles ({len(problem.data_assets)}):"))
    for asset in problem.data_assets:
        n_items = len(asset.data)
        rows_info = f"{n_items} filas" if asset.format == "tabular" else f"{n_items} obs"
        lines.append(f"  {_c(_C.GREEN, 'o')} {asset.name} ({asset.format}, {rows_info})")
    lines.append("")

    # Available actions
    lines.append(_c(_C.DIM, f"Acciones disponibles ({len(problem.available_actions)}):"))
    for action in problem.available_actions:
        lines.append(f"  {_c(_C.CYAN, '>')} {action.description} (costo: {action.cost})")

    _safe_print(_box("PROBLEMA DE INVESTIGACION", lines, _C.MAGENTA, width=90))


def show_score(score: Score) -> None:
    """Pretty-print a Score object."""
    if _in_notebook():
        _show_score_html(score)
        return

    lines = [
        f"KL divergence:   {_c(_C.BOLD, f'{score.functional_score:.4f}')}",
        f"Info efficiency: {_c(_C.BOLD, f'{score.information_efficiency:.1%}')}",
        f"Budget:          {score.budget_used} / {score.budget_total}",
    ]
    if score.per_step:
        lines.append("")
        lines.append(_c(_C.DIM, "Per-step:"))
        lines.append(f"  {'Step':>4} {'KL':>8} {'IG':>8} {'H':>8}")
        for s in score.per_step:
            kl = f"{s.posterior_kl:.4f}"
            ig = f"{s.cumulative_info_gain:.4f}"
            h = f"{s.entropy:.4f}"
            lines.append(f"  {s.step:>4} {kl:>8} {ig:>8} {h:>8}")

    _safe_print(_box("SCORE", lines, _C.CYAN))


# -------------------------------------------------------------------
# HTML renderers (notebook)
# -------------------------------------------------------------------

_CARD_CSS = (
    "border-left:4px solid {color};padding:12px 16px;margin:8px 0;"
    "background:linear-gradient(135deg,#f8f9fa,#fff);"
    "border-radius:6px;font-family:system-ui,-apple-system,sans-serif;"
)
_TITLE_CSS = "font-weight:700;font-size:14px;color:{color};margin-bottom:6px;"
_BODY_CSS = "font-size:13px;color:#343a40;line-height:1.6;"


def _nb_card(title: str, body: str, color: str = "#4263eb") -> None:
    from IPython.display import HTML, display

    card = _CARD_CSS.format(color=color)
    tcss = _TITLE_CSS.format(color=color)
    display(
        HTML(
            f'<div style="{card}">'
            f'<div style="{tcss}">{title}</div>'
            f'<div style="{_BODY_CSS}">{body}</div>'
            f"</div>"
        )
    )


_TH_CSS = (
    "padding:8px 14px;background:#4263eb;color:#fff;font-size:12px;text-align:center;border:none;"
)
_TABLE_CSS = (
    "border-collapse:collapse;border-radius:8px;overflow:hidden;"
    "box-shadow:0 1px 3px rgba(0,0,0,0.1);margin:10px 0;"
    "font-family:system-ui;"
)


def _nb_table(
    headers: list[str],
    rows: list[list[str]],
    highlight_col: int | None = None,
) -> None:
    from IPython.display import HTML, display

    th = "".join(f'<th style="{_TH_CSS}">{h}</th>' for h in headers)
    trs = ""
    for i, row in enumerate(rows):
        bg = "#f1f3f5" if i % 2 == 0 else "#fff"
        tds = ""
        for j, cell in enumerate(row):
            bld = "font-weight:700;" if j == highlight_col else ""
            style = f"padding:8px 14px;text-align:center;border:none;{bld}"
            tds += f'<td style="{style}">{cell}</td>'
        trs += f'<tr style="background:{bg};">{tds}</tr>'
    display(
        HTML(
            f'<table style="{_TABLE_CSS}"><thead><tr>{th}</tr></thead><tbody>{trs}</tbody></table>'
        )
    )


_HTML_NODE_COLORS = {"latent": "#fa5252", "observable": "#40c057", "target": "#fab005"}
_HTML_NODE_LABELS = {"latent": "Latente", "observable": "Observable", "target": "Target"}


def _show_world_html(world: World) -> None:
    tc = _HTML_NODE_COLORS
    tl = _HTML_NODE_LABELS

    _nb_card(
        "Mundo generado",
        (
            f"<code>{world.id}</code><br>"
            f"Dificultad: <b>{world.difficulty.level}</b> | "
            f"Template: <b>{world.template_family}</b> | "
            f"Nodos: <b>{len(world.nodes)}</b> | "
            f"Conexiones: <b>{len(world.edges)}</b>"
        ),
    )
    rows = []
    for n in world.nodes:
        badge_css = (
            f"background:{tc[n.type]};color:#fff;padding:2px 8px;border-radius:10px;font-size:11px;"
        )
        badge = f'<span style="{badge_css}">{tl[n.type]}</span>'
        rows.append([f"<b>{n.name}</b>", badge, ", ".join(n.states)])
    _nb_table(["Nodo", "Tipo", "Estados"], rows)


def _show_validation_html(
    passed: bool,
    failures: list[str],
    metrics: dict[str, float],
) -> None:
    if passed:
        _nb_card("Validacion exitosa", "El mundo paso todas las verificaciones.", color="#2b8a3e")
    else:
        items = "".join(f"<li>{f}</li>" for f in failures)
        _nb_card("Problemas", f"<ul>{items}</ul>", color="#e03131")
    rows = [[k.replace("_", " ").title(), f"{v:.3f}"] for k, v in metrics.items()]
    _nb_table(["Metrica", "Valor"], rows)


def _show_truth_html(world: World, true_state: dict[str, str]) -> None:
    tc = _HTML_NODE_COLORS
    rows = []
    for n in world.nodes:
        css = (
            f"background:{tc[n.type]};color:#fff;padding:1px 6px;border-radius:8px;font-size:11px;"
        )
        badge = f'<span style="{css}">{n.type}</span>'
        val = f'<b style="color:#364fc7;">{true_state[n.name]}</b>'
        rows.append([f"<b>{n.name}</b>", badge, val])
    _nb_card("Verdad oculta", "Valores reales", color="#7048e8")
    _nb_table(["Nodo", "Tipo", "Valor real"], rows, highlight_col=2)


def _bar_html(label: str, prob: float, color: str) -> str:
    w = max(prob * 100, 1)
    return (
        '<div style="display:flex;align-items:center;margin:2px 0;">'
        f'<span style="width:70px;font-size:12px;text-align:right;'
        f'margin-right:8px;">{label}</span>'
        f'<div style="background:{color};height:20px;'
        f'width:{w}%;border-radius:3px;"></div>'
        f'<span style="margin-left:6px;font-size:12px;'
        f'font-weight:600;">{prob:.1%}</span></div>'
    )


def _show_prior_html(
    prior: dict[str, float],
    entropy: float,
    true_value: str,
) -> None:
    bars = ""
    for s, p in prior.items():
        bg = "#e03131" if s == true_value else "#74C0FC"
        bars += _bar_html(s, p, bg)
    _nb_card(f"Prior P(target) - H = {entropy:.2f} bits", bars)


def _show_step_html(
    step_num: int,
    node: str,
    observed_value: str,
    gains: dict[str, float],
    posterior: dict[str, float],
    entropy: float,
    true_value: str,
) -> None:
    map_state = max(posterior, key=posterior.get)
    correct = map_state == true_value
    icon = "&#10003;" if correct else "&#10007;"

    gains_html = ""
    for gn, gv in sorted(gains.items(), key=lambda x: -x[1]):
        b = "<b>" if gn == node else ""
        be = "</b>" if gn == node else ""
        gains_html += f'<div style="font-size:12px;">{b}{gn}: {gv:.4f}{be}</div>'

    post_bars = ""
    for s, p in posterior.items():
        bg = "#e03131" if s == true_value else "#74C0FC"
        post_bars += _bar_html(s, p, bg)

    clr = "#2b8a3e" if correct else "#e03131"
    title = f"Turno {step_num} - <code>{node}</code> = <b>{observed_value}</b>"
    lbl = '<div style="font-size:11px;color:#868e96;margin-bottom:4px;">'
    body = (
        '<div style="display:flex;gap:30px;flex-wrap:wrap;">'
        f'<div style="flex:1;min-width:200px;">'
        f"{lbl}INFO GAIN</div>{gains_html}</div>"
        f'<div style="flex:2;min-width:250px;">'
        f"{lbl}POSTERIOR</div>{post_bars}"
        f'<div style="margin-top:6px;font-size:12px;">'
        f"Pred: <b>{map_state}</b> {icon} | "
        f"H={entropy:.3f} bits</div></div></div>"
    )
    _nb_card(title, body, color=clr)


def _show_result_html(prediction: str, true_value: str) -> None:
    correct = prediction == true_value
    if correct:
        _nb_card(
            "Resultado final",
            f"<b>{prediction}</b> - Correcto",
            color="#2b8a3e",
        )
    else:
        _nb_card(
            "Resultado final",
            f"Predijo <b>{prediction}</b>, verdad: <b>{true_value}</b> - Incorrecto",
            color="#e03131",
        )


def _show_comparison_html(
    teacher_pred: str,
    random_pred: str,
    true_value: str,
    teacher_kl: float,
    random_kl: float,
    teacher_entropy: float,
    random_entropy: float,
) -> None:
    t_ok = "&#10003;" if teacher_pred == true_value else "&#10007;"
    r_ok = "&#10003;" if random_pred == true_value else "&#10007;"
    _nb_card("Teacher vs Random", "Mismo mundo y episodio", color="#7048e8")
    _nb_table(
        ["", "Teacher", "Random"],
        [
            ["Prediccion", f"<b>{teacher_pred}</b>", f"<b>{random_pred}</b>"],
            ["Verdad", true_value, true_value],
            ["Correcto?", t_ok, r_ok],
            ["KL div", f"<b>{teacher_kl:.4f}</b>", f"{random_kl:.4f}"],
            ["Entropia", f"{teacher_entropy:.3f}", f"{random_entropy:.3f}"],
        ],
        highlight_col=1,
    )


def _show_research_problem_html(problem: ResearchProblem) -> None:
    body = f"<b>Dominio:</b> {problem.domain}<br>"
    body += f"<b>Budget:</b> {problem.budget} observaciones<br>"
    states_str = ", ".join(problem.target_states)
    body += f"<b>Target:</b> <code>{problem.target_node}</code> ({states_str})<br><br>"
    body += (
        f"<div style='font-size:12px;color:#495057;margin-bottom:8px;'>"
        f"{problem.description}</div>"
    )

    if problem.theoretical_context:
        body += (
            "<div style='font-size:11px;color:#868e96;font-style:italic;"
            f"margin-bottom:8px;'>{problem.theoretical_context}</div>"
        )

    body += f"<b>Pregunta:</b> {problem.research_question}<br><br>"

    body += "<b>Datos:</b><ul style='margin:4px 0;'>"
    for asset in problem.data_assets:
        body += f"<li>{asset.name} ({asset.format}, {len(asset.data)} items)</li>"
    body += "</ul>"

    body += "<b>Acciones:</b><ul style='margin:4px 0;'>"
    for action in problem.available_actions:
        body += f"<li>{action.description} (costo: {action.cost})</li>"
    body += "</ul>"

    _nb_card(problem.title, body, color="#7048e8")


def _show_score_html(score: Score) -> None:
    _nb_card(
        "Score",
        f"KL divergence: <b>{score.functional_score:.4f}</b><br>"
        f"Info efficiency: <b>{score.information_efficiency:.1%}</b><br>"
        f"Budget: {score.budget_used} / {score.budget_total}",
        color="#0b7285",
    )


__all__ = [
    "show_comparison",
    "show_prior",
    "show_research_problem",
    "show_result",
    "show_score",
    "show_step",
    "show_truth",
    "show_validation",
    "show_world",
]
