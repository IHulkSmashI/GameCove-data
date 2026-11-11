## Test fixture: only the lines of GameCove's app/scripts/system/data_repo.gd that tests/check_workflows.py reads.
const REPO := "IHulkSmashI/GameCove-data"
const RELEASES := "https://github.com/IHulkSmashI/GameCove-data/releases/download/"
const FIRMWARE_SIGNER := "(?i)^https://github\\.com/IHulkSmashI/GameCove-data/\\.github/workflows/firmware\\.yml@refs/heads/main$"
const UPSCALERS_SIGNER := "(?i)^https://github\\.com/IHulkSmashI/GameCove-data/\\.github/workflows/upscalers\\.yml@refs/heads/main$"
## The nightly fix definitions (docs/FIXES.md), signed by that repo's fixes.yml on main.
const FIXES_SIGNER := "(?i)^https://github\\.com/IHulkSmashI/GameCove-data/\\.github/workflows/fixes\\.yml@refs/heads/main$"
const FIXES_URL := RELEASES + "fixes/fixes.json"
