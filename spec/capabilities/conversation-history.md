# Capability: Conversation Threading

## What It Does
Remembers prior turns within a session so follow-up questions like “What about last month?” resolve against the previous context without re-uploading.

## Inputs

| Input | Type | Source | Required |
|-------|------|--------|----------|
| run_id | int | cookie / header | yes |
| question | str | UI | yes |

## Outputs

| Output | Type | Destination |
|--------|------|-------------|
| history | list[dict] | agent state |
| context_summary | str | prompt payload |

## External Calls
- DB read/write for `history` row.

## Business Rules
- History is summarized before inclusion in prompts to control token usage.
- Run timeout after 60 seconds of idle chat.

## Success Criteria
- [ ] Multi-turn test asks two questions; second answer references the first without repetition.
- [ ] 20-turn history keeps total prompt within model window without truncation error.
