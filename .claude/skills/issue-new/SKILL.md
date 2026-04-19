---
name: issue-new
description: Crear una issue en GitHub + agregarla al project "SREG Roadmap" + setear Worktree/Status + linkearla como sub-issue de un epic. Hace TODO el flujo en un solo paso para evitar el bug recurrente de issues sueltas que no aparecen en el board del epic.
---

Crear una issue completa en GitHub que quede correctamente vinculada al
project board y al epic correspondiente.

## Cuando usar

- Cuando descubres un bug, refactor pendiente o sub-task durante el trabajo
  en un epic.
- Cuando el usuario pide "creemos una issue para esto".
- Antes de empezar trabajo nuevo que no tiene issue propia.

NO usar para:
- Crear el body de PRs (eso es `gh pr create`).
- Comentarios en issues existentes (eso es `gh issue comment`).

## Inputs requeridos

El user debe proveer (preguntar si falta algo):

- **`title`**: titulo de la issue (corto, ASCII-safe).
- **`body`**: cuerpo completo de la issue (markdown). Tipicamente:
  - `## Contexto (para humanos)` — el porque
  - `## Detalle tecnico (para Claude / sesiones)` — el como tecnico
  - `## Criterio de cierre` — bullets verificables
  - Linkear research notes relevantes en `research/notes/`.
- **`worktree`**: uno de
  `eval-suite | qwen-benchmarks | rl-training-infra | main | compiler-fix | none | science-coverage`.
  Si la issue no tiene un worktree obvio, preguntar al user.
- **`epic`** (opcional pero recomendado): numero del epic padre (ej. `31`).
  Si la issue es estandalone (no tiene epic), saltar el `addSubIssue`.
- **`status`** (default `Todo`): `Todo | In Progress | Done`.

## IDs cacheados (re-querear si cambian)

```
Project ID:        PVT_kwHOAiGijs4BU2gW
Project number:    4
Project owner:     lucaspecina
Repo:              lucaspecina/synthetic-research-envs

Worktree field ID: PVTSSF_lAHOAiGijs4BU2gWzhFxsaY
  eval-suite:        9594c291
  qwen-benchmarks:   13a6f96e
  rl-training-infra: 6e49a1a7
  main:              152ea29e
  compiler-fix:      d9abcc2c
  none:              a1100fc4
  science-coverage:  ca6c4b8a

Status field ID:   PVTSSF_lAHOAiGijs4BU2gWzhFxiPE
  Todo:        f75ad846
  In Progress: 47fc9ee4
  Done:        98236657
```

Si algun option ID falla con error de GraphQL, re-querear:
`gh project field-list 4 --owner lucaspecina --format json`

## Pasos a ejecutar (en orden)

### 1. Escribir el body a archivo temporal

```bash
# El body suele tener caracteres especiales/comillas. Escribir a archivo
# evita problemas de shell escaping en --body "..."
cat > .tmp_issue_body.md <<'EOF'
<el body completo aqui>
EOF
```

(Borrar el archivo al final con `rm .tmp_issue_body.md`.)

### 2. Crear la issue

```bash
"/c/Program Files/GitHub CLI/gh.exe" issue create \
  --title "<TITLE>" \
  --body-file .tmp_issue_body.md
# → devuelve URL https://github.com/lucaspecina/synthetic-research-envs/issues/NN
# Capturar NN.
```

### 3. Agregar al project

```bash
"/c/Program Files/GitHub CLI/gh.exe" project item-add 4 \
  --owner lucaspecina \
  --url https://github.com/lucaspecina/synthetic-research-envs/issues/NN
```

### 4. Obtener el itemId del item recien agregado

```bash
"/c/Program Files/GitHub CLI/gh.exe" project item-list 4 \
  --owner lucaspecina --format json --limit 100 \
  | python -c "import json,sys; d=json.load(sys.stdin);
[print(i['id']) for i in d['items']
 if i.get('content',{}).get('number')==NN]"
# → ITEM_ID (PVTI_...)
```

### 5. Setear Worktree

```bash
"/c/Program Files/GitHub CLI/gh.exe" project item-edit \
  --id <ITEM_ID> \
  --field-id PVTSSF_lAHOAiGijs4BU2gWzhFxsaY \
  --single-select-option-id <WORKTREE_OPTION_ID> \
  --project-id PVT_kwHOAiGijs4BU2gW
```

### 6. Setear Status (default Todo)

```bash
"/c/Program Files/GitHub CLI/gh.exe" project item-edit \
  --id <ITEM_ID> \
  --field-id PVTSSF_lAHOAiGijs4BU2gWzhFxiPE \
  --single-select-option-id <STATUS_OPTION_ID> \
  --project-id PVT_kwHOAiGijs4BU2gW
```

### 7. Linkear como sub-issue del epic (si hay epic)

```bash
# Obtener node IDs de epic + child
"/c/Program Files/GitHub CLI/gh.exe" api graphql -f query='query {
  repository(owner:"lucaspecina", name:"synthetic-research-envs") {
    parent: issue(number: <EPIC>) { id }
    child:  issue(number: <NN>)   { id }
  }
}'
# → parent_id (I_...), child_id (I_...)

# Crear la relacion
"/c/Program Files/GitHub CLI/gh.exe" api graphql -f query='mutation {
  addSubIssue(input: {issueId: "<PARENT_ID>", subIssueId: "<CHILD_ID>"}) {
    issue    { number }
    subIssue { number }
  }
}'
```

### 8. Cleanup

```bash
rm .tmp_issue_body.md
```

### 9. Reportar al user

Reportar conciso:
- Numero y URL de la nueva issue
- Que campos quedaron seteados
- Si quedo linkeada al epic

## Errores comunes

- **"single-select-option-id is required"**: pasaste `--text` en vez de
  `--single-select-option-id`, o el option ID no existe (re-queriar field-list).
- **"unknown field id"**: el field-id es del project equivocado, o se renombro.
- **`addSubIssue` falla**: el issueId tiene que ser un node ID `I_...`, no
  el numero ni un project itemId `PVTI_...`.
- **Issue creada pero no aparece en board del epic**: te olvidaste el
  `addSubIssue`. La mention textual `#NN` en el body NO crea la relacion.

## Anti-patrones que esta skill resuelve

Antes de esta skill, era comun:
- Crear issue con `gh issue create` y olvidar agregar al project →
  invisible en el board.
- Mencionar `#NN` en el body del epic en vez de hacer `addSubIssue` →
  contador "Sub-issues progress" del epic queda mal.
- No setear `Worktree` → issue queda flotando sin home en el board.
