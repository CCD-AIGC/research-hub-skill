# Third-party notices

This package combines a new Research Hub orchestrator and RSS parser with two MIT-licensed research engine snapshots. The upstream projects' names identify their origin and do not imply endorsement.

## Overseas runtime

- Project: https://github.com/mvanhorn/last30days-skill
- Author: Matt Van Horn and upstream contributors
- Version: 3.31.0, commit 7efc0ef764765ed9ceff5ce1204462b35b89d680
- Runtime location: engines/global/scripts/
- License: engines/global/LICENSE
- Changes: no changes to the copied runtime source; a minimal version manifest is included for its renderer.
- The vendored Bird search subset retains its own MIT notice and attribution to Peter Steinberger under engines/global/scripts/lib/vendor/bird-search/.

## Chinese runtime

- Project: last30days-cn, version 4.0.0-cn, snapshot dated 2026-10-29
- Original author: Matt Van Horn; Chinese localization author: Jesse (https://github.com/Jesseovo)
- Runtime location: engines/cn/scripts/
- License: engines/cn/LICENSE
- Integration change: a --research-only switch prevents topic text from invoking login, setup or hot-list subcommands.
- This snapshot is described as the installed localization version; no unverified upstream repository URL or release is claimed.

Machine-specific configuration, credentials, login profiles, generated reports and browser data are not part of these snapshots. The feed configuration contains public source URLs; article text remains subject to the respective publishers' rights.
