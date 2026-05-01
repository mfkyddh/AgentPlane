## Change Summary

- 

## Change Layer

- [ ] **Strategy** — Vision, principles, roadmap, decision records
- [ ] **Project** — Project charter, roles, communication, risks
- [ ] **Engineering** — Code style, Git conventions, testing, release
- [ ] **Technical** — Architecture, specifications, operations

## Verification

- [ ] `agentplane repo health-check --repo-root .`
- [ ] Focused tests for touched behavior:

## Risk Notes

- Production or live-gate impact:
- Unverified items:

## Agent Checklist

- [ ] I used current formal entrypoints, not retired scripts or ad hoc SSH/Docker.
- [ ] I did not add real secrets, credentials, tokens, private keys, or local-only paths.
- [ ] I kept unrelated formatting and behavior changes out of the same logical change.
- [ ] I updated reference docs or runbooks when changing contracts, commands, or workflows.
- [ ] **Skill Sync**: If I added or changed CLI commands, I updated the matching `.agents/skills/*/SKILL.md` file with the new commands and capability details.
