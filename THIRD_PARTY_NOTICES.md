# Third-party notices

This package combines a new Research Hub orchestrator, RSS parser, and original evidence-led business/content analysis guidance with two MIT-licensed research engine snapshots. The upstream projects' names identify their origin and do not imply endorsement.

## Overseas runtime

- Project: https://github.com/mvanhorn/last30days-skill
- Author: Matt Van Horn and upstream contributors
- Version: 3.31.0, commit 7efc0ef764765ed9ceff5ce1204462b35b89d680
- Runtime location: skills/research-hub/engines/global/scripts/
- License: skills/research-hub/engines/global/LICENSE
- Changes: no changes to the copied runtime source; a minimal version manifest is included for its renderer.
- The vendored Bird search subset retains its own MIT notice and attribution to Peter Steinberger under skills/research-hub/engines/global/scripts/lib/vendor/bird-search/.

## Chinese runtime

- Project: https://github.com/Jesseovo/last30days-skill-cn
- Project name: last30days-cn, version 4.0.0-cn, installed snapshot dated 2026-10-29
- Original author: Matt Van Horn; Chinese localization author: Jesse (https://github.com/Jesseovo)
- Runtime location: skills/research-hub/engines/cn/scripts/
- License: skills/research-hub/engines/cn/LICENSE
- Integration change: a --research-only switch prevents topic text from invoking login, setup or hot-list subcommands.
- Snapshot corresponds to the installed localization version. Its exact source commit has not been established; this package does not claim a commit-level match.

## Business and content analysis methods

- `skills/research-hub/references/business-content-workflow.md` is original guidance written for this project, using the Research Hub evidence schema.
- Research included reading selected workflows in https://github.com/dontbesilent2025/dbskill and https://github.com/JimLiu/baoyu-skills. No dbskill text, code, knowledge atoms, or assets are redistributed. dbskill is licensed CC BY-NC 4.0; that non-commercial license is not included in this package. See `skills/research-hub/references/method-sources.md` for scope and evaluation notes.
- Baoyu's repository is MIT licensed. The new workflow does not copy its text or code; its source is recorded for attribution and review context. This package does not include Baoyu's image generation or publishing workflows.

Machine-specific configuration, credentials, login profiles, generated reports and browser data are not part of these snapshots. The feed configuration contains public source URLs; article text remains subject to the respective publishers' rights.
