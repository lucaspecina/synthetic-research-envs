# Tracking commands — recipes por situacion

Cargar IDs desde `reference.md` antes de correr cualquier comando que toque el Project.

## 1. Crear issue nueva (flujo completo)

```bash
# (1) Escribir el body con el template de 3 secciones
cat > /tmp/body.md <<'EOF'
## Contexto (para humanos)
<...>

## Detalle tecnico (para Claude / sesiones)
<...>

## Criterio de cierre
<...>
EOF

# (2) Crear la issue (devuelve URL)
URL=$(gh issue create --title "..." --body-file /tmp/body.md | tail -1)
N=$(echo "$URL" | grep -oE '[0-9]+$')

# (3) Agregar al Project board y capturar item ID
ITEM_ID=$(gh project item-add 4 --owner lucaspecina --url "$URL" --format json --jq '.id')

# (4) Setear Worktree (obligatorio; Status queda en Todo por default)
gh project item-edit --project-id $PROJECT_ID --id $ITEM_ID \
  --field-id $WORKTREE_FIELD_ID --single-select-option-id $WT_EVAL_SUITE

# (5) Si es sub-issue de un epic: linkear
CHILD_ID=$(gh issue view $N --json id --jq '.databaseId')
gh api -X POST /repos/lucaspecina/synthetic-research-envs/issues/<EPIC>/sub_issues \
  -F sub_issue_id=$CHILD_ID
```

## 2. Empezar a trabajar un issue (Status -> In Progress)

```bash
# Obtener item_id por numero de issue
ITEM_ID=$(gh api graphql -f query='
  query { user(login:"lucaspecina") { projectV2(number:4) {
    items(first:100) { nodes { id content { ... on Issue { number } } } }
  } } }' --jq ".data.user.projectV2.items.nodes[] | select(.content.number==<N>) | .id")

gh project item-edit --project-id $PROJECT_ID --id $ITEM_ID \
  --field-id $STATUS_FIELD_ID --single-select-option-id $STATUS_IN_PROGRESS
```

## 3. Cerrar issue (completar)

```bash
gh issue close <N> --reason completed \
  --comment "Se completo: <que se hizo>. PR mergeado: <url>"
# Project mueve item a Done automaticamente.
```

## 4. Cerrar como "not planned" (descartar)

```bash
gh issue close <N> --reason "not planned" \
  --comment "Scope change: <explicar>"

# Ademas, remover del Project para que no poluye Done:
gh api graphql -f query="mutation {
  deleteProjectV2Item(input: {projectId: \"$PROJECT_ID\", itemId: \"$ITEM_ID\"}) { deletedItemId }
}"
```

## 5. Reabrir issue (volver a Todo)

```bash
gh issue reopen <N>
gh project item-edit --project-id $PROJECT_ID --id $ITEM_ID \
  --field-id $STATUS_FIELD_ID --single-select-option-id $STATUS_TODO
```

## 6. Promover sub-issue a epic

Usar cuando un sub-issue crece a necesitar 3+ sub-sub-items.

```bash
# (1) Renombrar titulo al formato Epic
gh issue edit <N> --title "Epic · <worktree> · <meta concreta>"

# (2) Reescribir body para reflejar criterio de cierre del epic
gh issue edit <N> --body-file /tmp/new_body.md

# (3) Unlink del epic padre anterior (si existia)
gh api -X DELETE /repos/lucaspecina/synthetic-research-envs/issues/<OLD_PARENT>/sub_issue \
  -F sub_issue_id=$CHILD_ID_DE_N

# (4) Crear los nuevos sub-issues y linkearlos al epic <N>
# (loop usando flujo #1 para cada uno)

# (5) Actualizar la tabla "Epics activos" en CLAUDE.md
```

## 7. Agregar opcion al campo Worktree (al crear worktree nueva)

**TRAMPA CRITICA**: la mutation `updateProjectV2Field` con `singleSelectOptions` REEMPLAZA TODAS las opciones existentes. **Hay que pasar la lista completa** (existentes + nueva). Si solo pasas la nueva, se borran las demas y todos los items quedan `Worktree=MISSING`.

```bash
# (1) Crear worktree fisico
git worktree add .claude/worktrees/<nombre> -b <branch>

# (2) Query de opciones ACTUALES
gh api graphql -f query='query { user(login:"lucaspecina") { projectV2(number:4) {
  fields(first:20) { nodes { ... on ProjectV2SingleSelectField {
    name options { name color description }
  } } }
} } }' --jq '.data.user.projectV2.fields.nodes[] | select(.name=="Worktree") | .options'

# (3) Llamar updateProjectV2Field con TODAS las opciones (existentes + nueva)
gh api graphql -f query='mutation {
  updateProjectV2Field(input: {
    fieldId: "PVTSSF_lAHOAiGijs4BU2gWzhFxsaY",
    singleSelectOptions: [
      {name: "eval-suite",        color: GRAY, description: ""},
      {name: "qwen-benchmarks",   color: GRAY, description: ""},
      {name: "rl-training-infra", color: GRAY, description: ""},
      {name: "main",              color: GRAY, description: ""},
      {name: "compiler-fix",      color: GRAY, description: ""},
      {name: "none",              color: GRAY, description: ""},
      {name: "<NUEVA>",           color: GRAY, description: ""}
    ]
  }) { projectV2Field { ... on ProjectV2SingleSelectField { options { id name } } } }
}'

# (4) Verificar que las opciones viejas siguen y capturar el ID de la nueva
# (5) Actualizar reference.md con el nuevo option ID
# (6) Actualizar la lista de opciones Worktree en SKILL.md y CLAUDE.md
```

Si por error pasas solo la nueva y se pierden asignaciones: re-setear Worktree en cada item afectado con los NUEVOS option IDs (cambian al recrear).

## 8. Listar sub-issues de un epic

```bash
gh api /repos/lucaspecina/synthetic-research-envs/issues/<EPIC>/sub_issues \
  --jq '.[] | "#\(.number) [\(.state)] \(.title)"'
```

## 9. Auditar razones de cierre (busca items mal cerrados)

```bash
gh issue list --state closed --limit 50 --json number,title,stateReason | \
  python -c "import json,sys; [print(f\"#{i['number']:3} {i['stateReason']:13} {i['title'][:60]}\") for i in json.load(sys.stdin)]"
```

Si ves `not_planned` en items que deberian ser `completed` (o viceversa), reabrir y cerrar con la razon correcta.

## 10. Limpiar el board de items "not planned"

```bash
# Para cada item cerrado con not_planned que aun aparece en Done:
gh api graphql -f query="mutation {
  deleteProjectV2Item(input: {projectId: \"$PROJECT_ID\", itemId: \"$ITEM_ID\"}) { deletedItemId }
}"
# El issue sigue cerrado; solo se remueve del board.
```
