# Tracking reference — Project v2 IDs + GraphQL templates

## IDs estables (al 2026-04-17)

```bash
# Repo
REPO="lucaspecina/synthetic-research-envs"
PROJECT_NUM=4
PROJECT_OWNER="lucaspecina"

# Project v2
PROJECT_ID="PVT_kwHOAiGijs4BU2gW"

# Status field
STATUS_FIELD_ID="PVTSSF_lAHOAiGijs4BU2gWzhFxiPE"
  STATUS_TODO="f75ad846"
  STATUS_IN_PROGRESS="47fc9ee4"
  STATUS_DONE="98236657"

# Worktree field
WORKTREE_FIELD_ID="PVTSSF_lAHOAiGijs4BU2gWzhFxsaY"
  WT_EVAL_SUITE="33dda69b"
  WT_QWEN_BENCHMARKS="a3d8410f"
  WT_RL_TRAINING_INFRA="8ef0b6ab"
  WT_MAIN="d66cbbef"
  WT_COMPILER_FIX="4cfce8b8"
  WT_NONE="edeb5e36"
```

Si algun comando falla con "option not found" o similar, refrescar IDs (pueden haber cambiado si se agrego/quito opcion del field).

## Query de refresh (obtener todos los IDs actuales)

```bash
gh api graphql -f query='query {
  user(login:"lucaspecina") {
    projectV2(number:4) {
      id
      fields(first:20) {
        nodes {
          ... on ProjectV2SingleSelectField {
            id
            name
            options { id name color }
          }
        }
      }
    }
  }
}'
```

## Query del board (Status + Worktree por item)

```bash
gh api graphql -f query='query {
  user(login:"lucaspecina") {
    projectV2(number:4) {
      items(first:100) {
        nodes {
          id
          content {
            ... on Issue { number title state }
          }
          fieldValues(first:10) {
            nodes {
              ... on ProjectV2ItemFieldSingleSelectValue {
                field { ... on ProjectV2SingleSelectField { name } }
                name
              }
            }
          }
        }
      }
    }
  }
}'
```

Para parsear y ver tabla item/status/worktree, pipe a Python:
```bash
gh api graphql -f query='...' | python -c "
import json,sys
d=json.load(sys.stdin)
for n in d['data']['user']['projectV2']['items']['nodes']:
    if not n.get('content'): continue
    num = n['content']['number']
    title = n['content']['title'][:50]
    state = n['content']['state']
    fields = {f['field']['name']: f['name'] for f in n['fieldValues']['nodes'] if f.get('field')}
    status = fields.get('Status', 'MISSING')
    wt = fields.get('Worktree', 'MISSING')
    print(f'#{num:3} [{state}] Status={status:12} Worktree={wt:20} {title}')
"
```

## Sub-issue API

GitHub nativa — no "Part of #N" en body.

```bash
# Listar sub-issues de un epic
gh api /repos/lucaspecina/synthetic-research-envs/issues/<EPIC>/sub_issues \
  --jq '.[] | "#\(.number) [\(.state)] \(.title)"'

# Linkear sub-issue (sub_issue_id = databaseId entero, NO number)
CHILD_ID=$(gh issue view <NNN> --json id --jq '.databaseId')
gh api -X POST /repos/lucaspecina/synthetic-research-envs/issues/<EPIC>/sub_issues \
  -F sub_issue_id=$CHILD_ID

# Unlink (para re-parentear)
gh api -X DELETE /repos/lucaspecina/synthetic-research-envs/issues/<OLD_EPIC>/sub_issue \
  -F sub_issue_id=$CHILD_ID
```

## Auth

`gh` en PATH. Authenticated as `lucaspecina`. Scopes: `project, read:project`.
Si falla auth: `gh auth refresh -s project,read:project`.
