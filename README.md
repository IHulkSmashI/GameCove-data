# GameCove-data

The data [GameCove](https://github.com/IHulkSmashI/GameCove) downloads: the game database, the firmware list, the
upscaler files and their signed list, and the device photos. The app fetches these files itself. They're **not meant
for direct use**: there's nothing to install here. To get GameCove, go to
[GameCove's releases](https://github.com/IHulkSmashI/GameCove/releases).

They live in their own repo so GameCove's Releases page lists only real app versions.

## The releases

| Release | Files | Rebuilt | Signed |
| --- | --- | --- | --- |
| [`gamedb`](https://github.com/IHulkSmashI/GameCove-data/releases/tag/gamedb) | `gamedb.json.gz` (game database), `upcoming.json.gz` (Discover's release calendar), `NOTICE.md` (sources and credits, also the release notes) | Nightly (`gamedb.yml`) | No (fetched over HTTPS, size-capped) |
| [`firmware`](https://github.com/IHulkSmashI/GameCove-data/releases/tag/firmware) | `firmware.json.gz` (newest BIOS / EC / controller firmware each maker lists per handheld, plus Linux driver versions: versions, dates and links only, no firmware), `.sha256`, `.sigstore.json` | Nightly (`firmware.yml`) | Yes |
| [`upscalers`](https://github.com/IHulkSmashI/GameCove-data/releases/tag/upscalers) (and `upscalers-2`, ... once one nears GitHub's 1000-file limit) | Unmodified copies of OptiScaler (stable and v10 nightly, each with the source archive of the exact commit it was built from), OptiPatcher, fakenvapi, xess-xmx-linux (the XeSS XMX driver), REFramework and the FSR 4 files (Intel XMX build and AMD's own DLL with its licence notice), each named `<component>-<version>-<sha256[:8]>-<upstream name>`; `upscalers.json` (newest version of each, upstream URL, mirror URL, sha256, size, date), `.sha256`, `.sigstore.json` | Nightly (`upscalers.yml`); files are never deleted or replaced, so every pinned hash keeps resolving | Yes (`upscalers.json`) |
| [`device-photos`](https://github.com/IHulkSmashI/GameCove-data/releases/tag/device-photos) | One WebP per handheld (about 1200 px wide), `manifest.json` (sha256, size, author, licence and source page of every photo) | Weekly (`device-photos.yml`) | No; the app checks each photo's size and sha256 against the manifest and re-applies the free-licence allowlist |

## How GameCove checks them

`firmware.json.gz` and `upscalers.json` are signed with [cosign](https://github.com/sigstore/cosign) keyless
(Sigstore). GameCove accepts them only when the signature was made by exactly this repo's workflow on `main`:

- `https://github.com/IHulkSmashI/GameCove-data/.github/workflows/firmware.yml@refs/heads/main`
- `https://github.com/IHulkSmashI/GameCove-data/.github/workflows/upscalers.yml@refs/heads/main`

with the issuer `https://token.actions.githubusercontent.com` (GitHub Actions). The pins are in GameCove's
`app/scripts/system/data_repo.gd` and `packaging/helpers/gamecove_upscale/mirror.py`. Without a valid signature the
app falls back to its own tested pins; every downloaded upscaler file is checked against its sha256 either way, and
maker firmware downloads are offered only from a list whose signature checked out.

## How they're built

Each workflow runs GameCove's own builders (`gamedb/`, `tools/upscalers/`, `tools/device_photos/`, with their
tests), checked out read-only at the GameCove commit `gamecove-source.env` pins. Every workflow has two jobs:
`build` runs the tests, the scrapers and the builder with a read-only token and no signing identity; only `publish`,
which runs nothing but pinned cosign, `gh` and standard-library checks of the files, can sign and write the release.
The signing `publish` jobs run in the `nightly` environment, which only `main` can deploy to; their build job stops
the run if that environment is missing or lets another branch deploy. Upscaler builds are promoted only from each
component's official repository and only once they've been out 72 hours. Actions are pinned by commit; pip installs
by hash. `tests/check_workflows.py` (run by `checks.yml` on every push) checks all of that.

### Updating

After a GameCove change to a builder or its data (`gamedb/`, `tools/upscalers/`, `tools/device_photos/`,
`app/data/devices.json`, `app/data/device_photos.json`, `packaging/helpers/`, a new tested pin in `versions.json`, or
the cosign pins in `packaging/get-gamecove.sh`) is on GameCove's `main`, set `GAMECOVE_COMMIT` in
`gamecove-source.env` to that commit and run the workflow by hand, for example
`gh workflow run upscalers.yml -R IHulkSmashI/GameCove-data`. A new tested pin must be on the mirror before an app
release ships it.

### Owner settings

- **Settings > Environments > New environment `nightly`**: no required reviewers; Deployment branches and tags:
  "Selected branches and tags", one rule, branch `main`. GitHub would create a missing environment without any
  protection on the first run that names it, so the signing workflows refuse to run until it's set up this way.
- **Settings > Actions > General**: Actions allowed. Workflow permissions can stay "Read repository contents"
  (each job asks for only what it needs: `contents: write` to publish, `id-token: write` to sign).
- **Settings > Secrets and variables > Actions**: `TWITCH_CLIENT_ID` and `TWITCH_CLIENT_SECRET` (IGDB, for
  `gamedb.yml`; without them IGDB's fields keep their previous values).
- Protect `main` (pull requests, no force pushes): it's the signing identity.

## Credits and licences

The files here aren't GameCove's code and aren't under GameCove's GPL unless they say so: each keeps its own
licence. From GameCove's [CREDITS.md](https://github.com/IHulkSmashI/GameCove/blob/main/CREDITS.md):

### Upscaler files

- **OptiScaler** (GPL-3.0), **OptiPatcher**, **fakenvapi** (FakeMichau), **REFramework** (onehoon's fork, MIT) and **AMD FSR SDK** (GPUOpen FidelityFX-SDK, AMD binary licence: redistribution allowed with its notice): not in GameCove's app or packages. GameCove downloads them when the user installs or updates them, the newest from GameCove's signed upscalers list or else the tested pins (`packaging/helpers/gamecove_upscale/data/versions.json`), every file sha256 checked. Unmodified copies are kept on the `upscalers` release of GameCove's data repo ([GameCove-data](https://github.com/IHulkSmashI/GameCove-data), its `.github/workflows/upscalers.yml`, nightly), under their own licences, so a file moved upstream never breaks an install; the helper tries that copy first, then upstream. every mirrored OptiScaler build has GitHub's source archive at the exact commit it was built from next to it (`source` in `upscalers.json`; a build whose commit can't be determined isn't mirrored), and AMD's licence notice next to each AMD DLL (no notice, no copy). `upscalers.json` names each file's upstream URL and release.
- **FSR 4 on Intel XMX** (`fsr4_xmx` in versions.json): nitec's FSR 4.1.2 build for the XMX cores (OptiScaler community), made from AMD's FidelityFX SDK upscaler DLL; hosted on ClawDeck's `fsr4-xmx-files` branch, pinned by commit and sha256, and copied unmodified to the same `upscalers` release; downloaded only when the user asks. AMD's own DLL (`fsr4_amd`) comes from GPUOpen's FidelityFX-SDK repository under AMD's binary licence, mirrored with its notice.
- **xess-xmx-linux** (HHHHanasak1): its GitHub release, mirrored unmodified on GameCove-data's `upscalers` release; installed when the user installs XeSS on XMX, sha256 checked.

`upscalers.json` names every file's upstream URL, release and (for OptiScaler) source archive.

### Game database

`NOTICE.md` on the `gamedb` release is the full notice (it's also the release notes). In short:

- **Game data from [IGDB](https://www.igdb.com)**: time to beat, game details and critic averages in
  `gamedb.json.gz`, upcoming release dates in `upcoming.json.gz`, used under the
  [Twitch Developer Service Agreement](https://www.twitch.tv/p/legal/developer-agreement/) with credit to IGDB.
  Anyone reusing these fields must credit IGDB the same way.
- **Compatibility tiers**: GameCove's own summary of [ProtonDB](https://www.protondb.com) community reports
  ([bdefore/protondb-data](https://github.com/bdefore/protondb-data)), not ProtonDB's official tier. ProtonDB's data
  is under the [ODbL 1.0](https://opendatacommons.org/licenses/odbl/1-0/) (contents DbCL 1.0); the derived tiers in
  `gamedb.json.gz` are shared under the ODbL 1.0 too.
- **Wikidata** (CC0): titles, dates, cross-store ids, genres, developers, publishers, upcoming release dates.
- **AreWeAntiCheatYet** (MIT): anti-cheat status.
- **Steam store** (Valve, [Steam Web API Terms of Use](https://steamcommunity.com/dev/apiterms)): popularity,
  game details, release dates and coming-soon state, and Metacritic scores exactly as Valve publishes them (never
  fetched from Metacritic; Metacritic is a registered trademark of Fandom, Inc.).
- **Exchange rates** in `upcoming.json.gz`: Source: ECB statistics (European Central Bank, reused unmodified).
- OpenCritic data is not in these files.

Not affiliated with or endorsed by IGDB, Twitch, ProtonDB, Valve, Metacritic, Fandom or Wikimedia.

### Device photos

Freely licensed photos from [Wikimedia Commons](https://commons.wikimedia.org/) and Flickr (found through
[Openverse](https://openverse.org/)), each under its own licence (CC0, public domain, CC BY or CC BY-SA), not
GameCove's GPL. Every licence is re-checked at its source on each run; scaling to 1200 px and converting to WebP is
the only change made. Author, licence and source page for every file are in `manifest.json` on the release, and the
app shows that credit under the photo.

### Firmware list

Versions, dates and links read from each maker's public support listings (ASUS, Lenovo, MSI, Valve's
jupiter-hw-support) and upstream release pages. No firmware is hosted here.

## Licence

The workflows and scripts in this repo are GPL-3.0, like GameCove. The released files keep the licences above.
