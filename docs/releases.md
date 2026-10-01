# Ragnar Releases

A per-PR log of everything merged into `main`. **Newest release is always on top** — add new entries directly under the "Releases" heading (inside the newest date section), above the previous one.

Each entry is a pull request merged to `main`: the PR link and title, merge date, branch and diff size, a short summary of what changed, and links to the documentation it added or updated. The backfilled history starts at PR #737 (2026-09-11). For the older feature-by-feature narrative see [RELEASE_NOTES.md](RELEASE_NOTES.md).

## Adding an entry (every PR)

Before opening a PR, add an entry at the top of the newest date section (create a new `### YYYY-MM-DD` section above the others if the date is new):

```markdown
#### [#NNN](https://github.com/PierreGode/Ragnar/pull/NNN) — type(scope): PR title
*Merged YYYY-MM-DD · branch `feature/x` · N file(s), +A / −D*

- One-line summary of each notable change
- **Docs:** [feature.md](feature.md), [README (root)](../README.md)
```

Link every `.md` file the PR adds or changes (paths are relative to `docs/`). If the PR number is not known yet, open the PR first and then push the entry to the same branch.

## Releases

### 2026-10-01

#### [#893](https://github.com/PierreGode/Ragnar/pull/893) — docs: per-PR release log (docs/releases.md)
*Merged 2026-10-01 · branch `docs/releases-log` · 3 file(s)*

- New `docs/releases.md`: one entry per PR merged to `main`, newest on top, with summary and doc links
- Backfilled the last 150 merged PRs (#737–#892) from the merge history
- Linked from the root README and the docs index
- **Docs:** [releases.md](releases.md), [README (root)](../README.md), [docs index](README.md)

### 2026-09-30

#### [#892](https://github.com/PierreGode/Ragnar/pull/892) — fix(apc-guard): run the module self-test tier in its own interpreter
*Merged 2026-09-30 · branch `fix/apc-selftest-thread` · 1 file(s), +10 / −11*

#### [#891](https://github.com/PierreGode/Ragnar/pull/891) — fix(ui): move APC Guard card to the Diagnostics sub-tab
*Merged 2026-09-30 · branch `fix/apc-guard-diagnostics` · 18 file(s), +1350 / −1141*

- feat(ui): sort Network > Diagnostics by OSI layer
- feat(ui): visibility matrix as a reference guide in Diagnostics
- **Docs:** [README (root)](../README.md), [docs index](README.md), [certwatch.md](certwatch.md), [nettools.md](nettools.md)

#### [#890](https://github.com/PierreGode/Ragnar/pull/890) — feat(net): APC Guard — passive APC/Schneider NMC Ripple20 guard
*Merged 2026-09-30 · branch `feature/apc-guard` · 17 file(s), +3773 / −43*

- **Docs:** [README (root)](../README.md), [CREDITS.md](CREDITS.md), [CVE.md](CVE.md), [nettools.md](nettools.md), [watchtower.md](watchtower.md)

#### [#889](https://github.com/PierreGode/Ragnar/pull/889) — feat(gps): set the clock from GPS offline and repair sessions on clock steps
*Merged 2026-09-30 · branch `feature/gps-clock-set` · 9 file(s), +304 / −6*

- **Docs:** [wardriving.md](wardriving.md)

#### [#888](https://github.com/PierreGode/Ragnar/pull/888) — fix(wardriving): stop reopening a session from overwriting its start time
*Merged 2026-09-30 · branch `fix/wardriving-session-start-time` · 2 file(s), +78 / −3*

### 2026-09-29

#### [#887](https://github.com/PierreGode/Ragnar/pull/887) — docs(cellular): heartbeat states, test procedure, IFACE order and push details
*Merged 2026-09-29 · branch `feature/cellular-heartbeat-failover` · 9 file(s), +125 / −35*

- docs(device-console): complete the guide; fix script id handling
- **Docs:** [DISPLAY_CONTROLS.md](DISPLAY_CONTROLS.md), [docs index](README.md), [cellular-uplink.md](cellular-uplink.md), [nettools.md](nettools.md), [push-notifications.md](push-notifications.md), [serial-console.md](serial-console.md)

#### [#886](https://github.com/PierreGode/Ragnar/pull/886) — feat(network): heartbeat failover + failback hysteresis for cellular uplink
*Merged 2026-09-29 · branch `feature/cellular-heartbeat-failover` · 8 file(s), +505 / −35*

- **Docs:** [README (root)](../README.md), [docs index](README.md), [cellular-uplink.md](cellular-uplink.md)

#### [#885](https://github.com/PierreGode/Ragnar/pull/885) — feat(gps): inject saved almanac/ephemeris on offline boots too
*Merged 2026-09-29 · branch `fix/gps-assist-offline-orbits` · 3 file(s), +58 / −27*

- **Docs:** [wardriving.md](wardriving.md)

#### [#884](https://github.com/PierreGode/Ragnar/pull/884) — fix(gps): orbit-data saves run from first fix and merge per satellite
*Merged 2026-09-29 · branch `fix/gps-aid-save-schedule-merge` · 4 file(s), +103 / −52*

- **Docs:** [wardriving.md](wardriving.md)

#### [#883](https://github.com/PierreGode/Ragnar/pull/883) — fix(wifi): reconnect key falls back to saved NetworkManager profiles
*Merged 2026-09-29 · branch `fix/key2-reconnect-nm-profiles` · 3 file(s), +295 / −10*

- **Docs:** [DISPLAY_CONTROLS.md](DISPLAY_CONTROLS.md)

#### [#882](https://github.com/PierreGode/Ragnar/pull/882) — fix(gps): save orbit data 15 s after a fix, not 60 s
*Merged 2026-09-29 · branch `fix/gps-assist-early-save` · 3 file(s), +28 / −7*

- fix(gps): save orbit data 5 s after a fix, then at 1 min, then every 5 min
- **Docs:** [wardriving.md](wardriving.md)

#### [#881](https://github.com/PierreGode/Ragnar/pull/881) — feat(gps): assisted start — pre-load position, NTP time and saved orbit data
*Merged 2026-09-29 · branch `feature/gps-assist-preload` · 11 file(s), +733 / −6*

- docs(gps): assist store lives in data/, next to last_gps.json
- **Docs:** [README (root)](../README.md), [wardriving.md](wardriving.md)

### 2026-09-28

#### [#880](https://github.com/PierreGode/Ragnar/pull/880) — feat(ui): group Settings into sub-tabs
*Merged 2026-09-28 · branch `feature/settings-subtabs` · 3 file(s), +69 / −3*

- **Docs:** [spec.md](spec.md)

#### [#878](https://github.com/PierreGode/Ragnar/pull/878) — feat(network): cellular uplink fallback via USB-tethered hotspot
*Merged 2026-09-28 · branch `feature/cellular-uplink-fallback` · 19 file(s), +952 / −15*

- **Docs:** [README (root)](../README.md), [docs index](README.md), [cell.md](cell.md), [cellular-uplink.md](cellular-uplink.md), [nettools.md](nettools.md), [push-notifications.md](push-notifications.md)

#### [#877](https://github.com/PierreGode/Ragnar/pull/877) — feat(system): cooling fan status and control in the System tab
*Merged 2026-09-28 · branch `feature/pi-fan-status` · 9 file(s), +1052 / −4*

- **Docs:** [README (root)](../README.md), [docs index](README.md), [fan.md](fan.md), [power.md](power.md)

#### [#876](https://github.com/PierreGode/Ragnar/pull/876) — fix(wardriving): parse iw's decimal channel frequencies
*Merged 2026-09-28 · branch `fix/iw-decimal-freqs` · 2 file(s), +38 / −2*

#### [#875](https://github.com/PierreGode/Ragnar/pull/875) — Delete .github/codeql/codeql-config.yml
*Merged 2026-09-28 · branch `PierreGode-patch-5` · 1 file(s), +0 / −81*

#### [#874](https://github.com/PierreGode/Ragnar/pull/874) — perf(actions): lazy-import pandas in connectors to cut startup RAM
*Merged 2026-09-28 · branch `perf/lazy-pandas-imports` · 8 file(s), +55 / −74*

#### [#846](https://github.com/PierreGode/Ragnar/pull/846) — fix(system-tab): make the System tab work on phones
*Merged 2026-09-28 · branch `system-tab-mobile` · 2 file(s), +52 / −29*

#### [#873](https://github.com/PierreGode/Ragnar/pull/873) — fix(serial-console): script picker no longer resets on every poll tick
*Merged 2026-09-28 · branch `fix/console-script-select` · 2 file(s), +12 / −3*

#### [#872](https://github.com/PierreGode/Ragnar/pull/872) — fix(files): dark editor textarea (pruned Tailwind has no bg-black/80)
*Merged 2026-09-28 · branch `fix/files-editor-dark` · 2 file(s), +2 / −2*

#### [#871](https://github.com/PierreGode/Ragnar/pull/871) — fix(console-scripts): seed defaults at runtime, never overwrite user edits
*Merged 2026-09-28 · branch `fix/console-scripts-seed` · 7 file(s), +88 / −150*

#### [#870](https://github.com/PierreGode/Ragnar/pull/870) — feat(files): in-browser text file editor with save
*Merged 2026-09-28 · branch `feature/files-editor` · 5 file(s), +134 / −7*

- **Docs:** [README (root)](../README.md), [serial-console.md](serial-console.md)

#### [#869](https://github.com/PierreGode/Ragnar/pull/869) — feat(serial-console): add console scripts — run pre-made command sequences
*Merged 2026-09-28 · branch `feature/console-scripts` · 11 file(s), +388 / −4*

- **Docs:** [README (root)](../README.md), [serial-console.md](serial-console.md)

#### [#868](https://github.com/PierreGode/Ragnar/pull/868) — refactor(serial-console): simplify mesh write — no separate checkbox
*Merged 2026-09-28 · branch `fix/console-mesh-write-simplify` · 5 file(s), +25 / −68*

- **Docs:** [serial-console.md](serial-console.md)

#### [#867](https://github.com/PierreGode/Ragnar/pull/867) — fix(cyd): stop orphaned rtl_sdr subprocess from blocking CYD waterfall
*Merged 2026-09-28 · branch `fix/cyd-display` · 4 file(s), +32 / −11*

- **Docs:** [cyd-firmware.md](cyd-firmware.md), [rf-waterfall.md](rf-waterfall.md)

### 2026-09-27

#### [#865](https://github.com/PierreGode/Ragnar/pull/865) — fix(wardrift): interpolate export times along the GPS track
*Merged 2026-09-27 · branch `fix/wardrift-trail-jumps` · 5 file(s), +60 / −11*

- **Docs:** [wardriving.md](wardriving.md)

#### [#866](https://github.com/PierreGode/Ragnar/pull/866) — Implement gated write functionality in serial_console.py
*Merged 2026-09-27 · branch `Consoleupdate` · 6 file(s), +413 / −97*

- fix(serial-console): wire up write-gate UI, routes and strip broken prose
- fix(serial-console): allow_write state consistent across all endpoints
- feat(serial-console): mesh write — send commands to a remote Ragnar's console
- **Docs:** [README (root)](../README.md), [serial-console.md](serial-console.md)

#### [#864](https://github.com/PierreGode/Ragnar/pull/864) — feat(install): installhead.sh — add/switch a screen on a headless install
*Merged 2026-09-27 · branch `feature/installhead` · 4 file(s), +320 / −1*

- **Docs:** [README (root)](../README.md), [DISPLAY_CONTROLS.md](DISPLAY_CONTROLS.md), [INSTALL.md](INSTALL.md)

#### [#863](https://github.com/PierreGode/Ragnar/pull/863) — feat(mikrotik-guard): v2 — MikroTrick SSH exposure (MTK-021)
*Merged 2026-09-27 · branch `feature/mikrotik-guard-v2` · 7 file(s), +197 / −16*

- **Docs:** [README (root)](../README.md), [CREDITS.md](CREDITS.md), [CVE.md](CVE.md), [nettools.md](nettools.md)

### 2026-09-26

#### [#862](https://github.com/PierreGode/Ragnar/pull/862) — fix(rf-waterfall): SDR-spike hatch only on the trace, not over the waterfall
*Merged 2026-09-26 · branch `adjust` · 2 file(s), +3 / −4*

- **Docs:** [rf-waterfall.md](rf-waterfall.md)

#### [#861](https://github.com/PierreGode/Ragnar/pull/861) — fix
*Merged 2026-09-26 · branch `adjust` · 11 file(s), +1010 / −92*

- water
- feat(sdr): self-healing RTL-SDR USB recovery
- feat(rf-waterfall): 3D view peaks 30% taller
- Revert "feat(rf-waterfall): 3D view peaks 30% taller"
- feat(rf-waterfall): 3D panel 30% taller on screen
- feat(rf-waterfall): "Hide the SDR centre spike" setting
- …and 1 more commit(s)
- **Docs:** [README (root)](../README.md), [rf-api.md](rf-api.md), [rf-waterfall.md](rf-waterfall.md), [sdr-subghz.md](sdr-subghz.md)

#### [#860](https://github.com/PierreGode/Ragnar/pull/860) — feat(notifications): rename Pushover Notifications to Push Notifications, add Slack
*Merged 2026-09-26 · branch `feature/push-notifications-slack` · 11 file(s), +268 / −38*

- **Docs:** [README (root)](../README.md), [docs index](README.md), [push-notifications.md](push-notifications.md), [rusense.md](rusense.md)

#### [#859](https://github.com/PierreGode/Ragnar/pull/859) — feat(rf-waterfall): Zigbee Suzi (sub-GHz Zigbee 4.0) presets in the Mesh dropdown
*Merged 2026-09-26 · branch `feature/rf-zigbee-suzi-presets` · 5 file(s), +75 / −23*

- **Docs:** [README (root)](../README.md), [rf-waterfall.md](rf-waterfall.md), [sdr-subghz.md](sdr-subghz.md)

#### [#856](https://github.com/PierreGode/Ragnar/pull/856) — fix(analyzer): stop the Signal Analyzer running Ragnar out of memory; explain every control
*Merged 2026-09-26 · branch `fix/rf-analyzer-crashes` · 4 file(s), +369 / −47*

- **Docs:** [rf-waterfall.md](rf-waterfall.md)

#### [#855](https://github.com/PierreGode/Ragnar/pull/855) — feat(serial-console): per-unit 'Share with mesh' view-only console sharing
*Merged 2026-09-26 · branch `feature/serial-console-mesh-share` · 6 file(s), +162 / −23*

- **Docs:** [mesh.md](mesh.md), [serial-console.md](serial-console.md)

#### [#852](https://github.com/PierreGode/Ragnar/pull/852) — feat(rf-waterfall): Wi-Fi HaLow (802.11ah) presets in the Mesh dropdown
*Merged 2026-09-26 · branch `feature/rf-halow-presets` · 5 file(s), +142 / −13*

- **Docs:** [README (root)](../README.md), [rf-waterfall.md](rf-waterfall.md), [sdr-subghz.md](sdr-subghz.md)

#### [#851](https://github.com/PierreGode/Ragnar/pull/851) — feat(wardriving): pause orchestrator active scans while driving
*Merged 2026-09-26 · branch `wardrive-pause-scans` · 6 file(s), +193 / −8*

- feat(wardriving): also pause the nmap scanner when triggered manually
- **Docs:** [wardriving.md](wardriving.md)

#### [#850](https://github.com/PierreGode/Ragnar/pull/850) — feat(serial-console): read-only device console on the dashboard, mesh-wide
*Merged 2026-09-26 · branch `feature/serial-console` · 11 file(s), +1208 / −6*

- fix(cyd): identify-before-write on auto-detected ports; console coexistence
- **Docs:** [README (root)](../README.md), [mesh.md](mesh.md), [serial-console.md](serial-console.md)

#### [#847](https://github.com/PierreGode/Ragnar/pull/847) — feat(rpc-watch): v3 — IRemoteWinSpool relay level + PetitPotam attribution
*Merged 2026-09-26 · branch `feature/rpc-watch-v3` · 25 file(s), +208 / −20*

- chore: commit the exec bit on 16 top-level modules + the TFT kiosk script
- **Docs:** [README (root)](../README.md), [CREDITS.md](CREDITS.md), [CVE.md](CVE.md), [nettools.md](nettools.md)

#### [#849](https://github.com/PierreGode/Ragnar/pull/849) — Update nettools.md
*Merged 2026-09-26 · branch `PierreGode-patch-4` · 1 file(s), +1 / −8*

- **Docs:** [nettools.md](nettools.md)

#### [#848](https://github.com/PierreGode/Ragnar/pull/848) — feat(telnet-watch): v5 — r-services, CVE-2011-4862, CVE-2022-39028
*Merged 2026-09-26 · branch `feature/telnet-watch-v5` · 11 file(s), +2509 / −144*

- **Docs:** [README (root)](../README.md), [CREDITS.md](CREDITS.md), [CVE.md](CVE.md), [nettools.md](nettools.md), [watchtower.md](watchtower.md)

### 2026-09-25

#### [#845](https://github.com/PierreGode/Ragnar/pull/845) — feat(power-test): watch a USB GPS through the power test
*Merged 2026-09-25 · branch `power-test-gps` · 6 file(s), +235 / −26*

- **Docs:** [power.md](power.md)

#### [#844](https://github.com/PierreGode/Ragnar/pull/844) — feat(power): Pi 5 USB current limit fix, power test and cleaner System tab
*Merged 2026-09-25 · branch `pi5-usb-power` · 11 file(s), +1231 / −445*

- **Docs:** [README (root)](../README.md), [docs index](README.md), [power.md](power.md)

#### [#843](https://github.com/PierreGode/Ragnar/pull/843) — Update nettools.md
*Merged 2026-09-25 · branch `PierreGode-patch-3` · 1 file(s), +1 / −3*

- **Docs:** [nettools.md](nettools.md)

### 2026-09-24

#### [#842](https://github.com/PierreGode/Ragnar/pull/842) — feat(smtp-watch): add CVE-2019-16928 overlong EHLO detection
*Merged 2026-09-24 · branch `feature/smtp-watch-update` · 8 file(s), +87 / −15*

- **Docs:** [README (root)](../README.md), [CREDITS.md](CREDITS.md), [CVE.md](CVE.md), [nettools.md](nettools.md), [watchtower.md](watchtower.md)

#### [#841](https://github.com/PierreGode/Ragnar/pull/841) — feat(smtp-watch): passive Exim CVE detector on the SMTP conversation
*Merged 2026-09-24 · branch `feature/smtp-watch` · 12 file(s), +1346 / −15*

- **Docs:** [README (root)](../README.md), [CREDITS.md](CREDITS.md), [CVE.md](CVE.md), [nettools.md](nettools.md), [watchtower.md](watchtower.md)

#### [#840](https://github.com/PierreGode/Ragnar/pull/840) — feat(ftp-watch): passive ProFTPD CVE detector on the FTP control channel
*Merged 2026-09-24 · branch `feature/ftp-watch` · 12 file(s), +1700 / −14*

- **Docs:** [README (root)](../README.md), [CREDITS.md](CREDITS.md), [CVE.md](CVE.md), [nettools.md](nettools.md), [watchtower.md](watchtower.md)

#### [#839](https://github.com/PierreGode/Ragnar/pull/839) — feat(wardriving): Pushover summary after each auto-uploaded drive
*Merged 2026-09-24 · branch `feature/wardrive-upload-pushover` · 6 file(s), +182 / −11*

- **Docs:** [wardriving.md](wardriving.md)

#### [#838](https://github.com/PierreGode/Ragnar/pull/838) — feat(wardriving): upload sessions to Wardrift
*Merged 2026-09-24 · branch `feature/wardrift-upload` · 16 file(s), +2533 / −231*

- fix(cyd): stop the CYD serial bridge from claiming the USB GPS
- feat(wardriving): Wardrift logo on the upload card
- feat(wardrift): report a Meshtastic node to Wardrift (USB or WiFi)
- fix(wardrift): explain and stop retrying rejected mesh reports
- fix(wardrift): reject masked/garbled API keys on save
- wardriving: GPS backfill setting tweaks
- …and 7 more commit(s)
- **Docs:** [README (root)](../README.md), [cyd-hybrid-node.md](cyd-hybrid-node.md), [sdr-subghz.md](sdr-subghz.md), [wardriving.md](wardriving.md)

#### [#837](https://github.com/PierreGode/Ragnar/pull/837) — docs: RTL8812AU monitor-mode driver setup & troubleshooting
*Merged 2026-09-24 · branch `docs/rtl8812au-driver-troubleshooting` · 2 file(s), +149 / −1*

- **Docs:** [PWNAGOTCHI.md](PWNAGOTCHI.md), [wifi-rtl8812au.md](wifi-rtl8812au.md)

### 2026-09-23

#### [#836](https://github.com/PierreGode/Ragnar/pull/836) — feat(rf-waterfall): detectors, front-end overload warning, image verification
*Merged 2026-09-23 · branch `feature/rf-instrument-grade` · 11 file(s), +3288 / −94*

- feat(rf-waterfall): armed trigger with pre-trigger IQ capture
- feat(rf-waterfall): band-power and noise markers, ACPR, spurs, harmonics, reference trace
- feat(analyzer): FM deviation and AM modulation depth
- feat(rf): geotagged captures and field-strength measurements
- feat(rf-waterfall): memory channels, instrument setups, measurement report, API reference
- feat(analyzer): CTCSS and DCS squelch-tag decoding
- …and 11 more commit(s)
- **Docs:** [README (root)](../README.md), [rf-api.md](rf-api.md), [rf-waterfall-guide.md](rf-waterfall-guide.md), [rf-waterfall.md](rf-waterfall.md)

### 2026-09-22

#### [#835](https://github.com/PierreGode/Ragnar/pull/835) — feat(rf-waterfall): display range, row history, settings drawer
*Merged 2026-09-22 · branch `fix/rf-waterfall-retune-storm` · 10 file(s), +3259 / −356*

- feat(rf-waterfall): hover readout, time axis, history scroll-back, colour bar
- feat(rf-waterfall): wheel zoom, drag pan, pinch, precise ruler
- feat(rf-waterfall): markers M1-M4 with delta, peak search, next peak, centre
- feat(sdr): resolution + hardware settings; fix dead columns on narrow zoom; radio SSB/CW/squelch
- feat(rf-waterfall): Resolution + Hardware settings UI, RBW readout
- feat(rf-waterfall): radio USB/LSB/CW, squelch slider, audio recording
- …and 10 more commit(s)
- **Docs:** [README (root)](../README.md), [rf-waterfall-guide.md](rf-waterfall-guide.md), [rf-waterfall.md](rf-waterfall.md), [sdr-subghz.md](sdr-subghz.md)

#### [#834](https://github.com/PierreGode/Ragnar/pull/834) — feat(rf-waterfall): noise print, record the background and subtract it
*Merged 2026-09-22 · branch `feature/rf-waterfall-noise-print` · 2 file(s), +132 / −5*

- **Docs:** [rf-waterfall.md](rf-waterfall.md)

#### [#833](https://github.com/PierreGode/Ragnar/pull/833) — fix(rf-waterfall): steady live scroll, no speed-up/slow-down surges
*Merged 2026-09-22 · branch `fix/rf-waterfall-steady-flow` · 2 file(s), +44 / −18*

- **Docs:** [rf-waterfall.md](rf-waterfall.md)

#### [#832](https://github.com/PierreGode/Ragnar/pull/832) — style(rf-waterfall): double waterfall height on desktop (210 -> 420 px)
*Merged 2026-09-22 · branch `fix/rf-waterfall-desktop-height` · 1 file(s), +2 / −2*

#### [#831](https://github.com/PierreGode/Ragnar/pull/831) — fix(smb-watch): stop mDNS DNS-SD PTRs raising spoof-conflict
*Merged 2026-09-22 · branch `fix/smb-mdns-spoof-conflict-fp` · 3 file(s), +143 / −25*

- fix(smb-watch): close the evasions the DNS-SD fix opened
- **Docs:** [nettools.md](nettools.md)

### 2026-09-21

#### [#830](https://github.com/PierreGode/Ragnar/pull/830) — fixes
*Merged 2026-09-21 · branch `data` · 3 file(s), +164 / −21*

#### [#829](https://github.com/PierreGode/Ragnar/pull/829) — docs: add unified CVE index (docs/CVE.md) + generator
*Merged 2026-09-21 · branch `docs/unified-cve-list` · 4 file(s), +669 / −9*

- **Docs:** [README (root)](../README.md), [CREDITS.md](CREDITS.md), [CVE.md](CVE.md)

#### [#828](https://github.com/PierreGode/Ragnar/pull/828) — feat(dns-watch): port DNS Poison Checker v5 passive detectors
*Merged 2026-09-21 · branch `feature/dns-poison-v5` · 11 file(s), +847 / −37*

- **Docs:** [README (root)](../README.md), [CREDITS.md](CREDITS.md), [nettools.md](nettools.md)

#### [#827](https://github.com/PierreGode/Ragnar/pull/827) — fix(network): stop dual-homed boxes degrading every host each scan (#818)
*Merged 2026-09-21 · branch `fix/818-dual-homed-degraded-flap` · 6 file(s), +488 / −29*

- fix(wifi): identify the network by SSID, not the NM profile name (#818)
- **Docs:** [asset-inventory.md](asset-inventory.md)

#### [#826](https://github.com/PierreGode/Ragnar/pull/826) — docs(ui): name D(HE)at in the TLS and SSH Watch cards
*Merged 2026-09-21 · branch `feature/tls-ssh-dheat-card-wording` · 1 file(s), +2 / −2*

#### [#825](https://github.com/PierreGode/Ragnar/pull/825) — docs(ui): note OSPFv3-SR in the SR-MPLS Watch card
*Merged 2026-09-21 · branch `feature/srmpls-card-ospfv3sr-wording` · 1 file(s), +3 / −3*

#### [#824](https://github.com/PierreGode/Ragnar/pull/824) — feat(watchers): SR-MPLS Watch v3 (OSPFv3-SR) + OSPF Watch v5 (OSPFv3 instance anomaly)
*Merged 2026-09-21 · branch `feature/srmpls-v3-ospfv3sr` · 4 file(s), +558 / −20*

- Update nettools.md
- **Docs:** [CREDITS.md](CREDITS.md), [nettools.md](nettools.md)

### 2026-09-20

#### [#823](https://github.com/PierreGode/Ragnar/pull/823) — Update nettools.md
*Merged 2026-09-20 · branch `PierreGode-patch-2` · 1 file(s), +2 / −1*

- **Docs:** [nettools.md](nettools.md)

#### [#822](https://github.com/PierreGode/Ragnar/pull/822) — fix(config): only restart the service for settings that actually need it
*Merged 2026-09-20 · branch `fix/restart-only-when-needed` · 7 file(s), +277 / −15*

- **Docs:** [ble_provisioning.md](ble_provisioning.md), [spec.md](spec.md)

#### [#821](https://github.com/PierreGode/Ragnar/pull/821) — fix(network): stop every target flapping Offline/Degraded between scans
*Merged 2026-09-20 · branch `fix/host-liveness-flapping` · 5 file(s), +399 / −17*

- **Docs:** [README (root)](../README.md), [asset-inventory.md](asset-inventory.md)

#### [#820](https://github.com/PierreGode/Ragnar/pull/820) — feat(watchers): BGP v4 + OSPF v4 + EIGRP v5 + IS-IS v5 CVE coverage
*Merged 2026-09-20 · branch `feature/bgp4-ospf4-eigrp5-isis5` · 6 file(s), +205 / −36*

- **Docs:** [README (root)](../README.md), [CREDITS.md](CREDITS.md), [nettools.md](nettools.md)

#### [#819](https://github.com/PierreGode/Ragnar/pull/819) — feat(watchers): LACP v2 + LDAP v4 + DHCP Guardian v3 + IPv6 RA Guard v2
*Merged 2026-09-20 · branch `feature/lacp2-dhcp3-raguard2-ldap4` · 6 file(s), +457 / −28*

- **Docs:** [README (root)](../README.md), [CREDITS.md](CREDITS.md), [nettools.md](nettools.md)

#### [#817](https://github.com/PierreGode/Ragnar/pull/817) — feat(watchers): SR-MPLS Watch v2 (SR-TLV overrun) + BFD Watch v3 (auth-bypass / micro-flap)
*Merged 2026-09-20 · branch `feature/srmpls-v2-bfd-v3` · 6 file(s), +643 / −47*

- **Docs:** [README (root)](../README.md), [CREDITS.md](CREDITS.md), [nettools.md](nettools.md)

### 2026-09-19

#### [#816](https://github.com/PierreGode/Ragnar/pull/816) — feat(watchers): ARP v4 frame capture + SMB/Kerberos v3 CVEs + RPC/NetLogon v2
*Merged 2026-09-19 · branch `feature/arp-v4-smb-kerb-v3-rpc-v2` · 8 file(s), +1074 / −45*

- **Docs:** [README (root)](../README.md), [CREDITS.md](CREDITS.md), [nettools.md](nettools.md)

#### [#815](https://github.com/PierreGode/Ragnar/pull/815) — feat(mesh): hub gateway — relay app requests to fleet peers over Tailscale
*Merged 2026-09-19 · branch `feat/mesh-gateway` · 2 file(s), +123 / −1*

- docs(mesh): document the hub gateway (relay app requests to fleet peers)
- fix(mesh): import requests in the gateway (NameError crashed every relay)
- **Docs:** [mesh.md](mesh.md)

#### [#814](https://github.com/PierreGode/Ragnar/pull/814) — fix(ble): private D-Bus bus so provisioning works inside the webapp
*Merged 2026-09-19 · branch `feat/ble-ip-handover` · 3 file(s), +67 / −13*

- feat(ble): expose 'Bluetooth handover' — app finds box + reads LAN IP over BLE
- **Docs:** [bluetooth-pan.md](bluetooth-pan.md)

#### [#813](https://github.com/PierreGode/Ragnar/pull/813) — fix(cyd): stop Watchtower new-AP warnings from the ESP32 CYD sensor
*Merged 2026-09-19 · branch `vik` · 1 file(s), +3 / −1*

#### [#812](https://github.com/PierreGode/Ragnar/pull/812) — feat(tls-watch): Heartbleed + oversized-DH-prime passive detection (TLS Watch v7)
*Merged 2026-09-19 · branch `feature/tls-v7-ptp-v3` · 5 file(s), +350 / −15*

- feat(ptp-watch): Class V CVE-attributed signatures (PTP Watch v3)
- docs(credits): +6 CVEs (TLS v7 Heartbleed/oversized-DH, PTP v3 Class V) -> ~165
- **Docs:** [README (root)](../README.md), [CREDITS.md](CREDITS.md), [nettools.md](nettools.md)

#### [#811](https://github.com/PierreGode/Ragnar/pull/811) — feat(watch): passive SNMP/IGMP/NTP CVE detection (SNMP v4, IGMP v4, NTP v6)
*Merged 2026-09-19 · branch `feature/snmp-igmp-ntp-v4` · 7 file(s), +1016 / −55*

- chore(web): cache-bust ragnar_modern.js for the SNMP 'exploit' verdict style
- **Docs:** [README (root)](../README.md), [CREDITS.md](CREDITS.md), [nettools.md](nettools.md)

#### [#810](https://github.com/PierreGode/Ragnar/pull/810) — feat(bt-pan): 'Clear all Bluetooth pairings' button
*Merged 2026-09-19 · branch `feat/bt-pan-client-mode` · 5 file(s), +302 / −4*

- feat(bt-pan): box-as-client mode (connect to phone's BT tethering)
- **Docs:** [bluetooth-pan.md](bluetooth-pan.md)

### 2026-09-18

#### [#809](https://github.com/PierreGode/Ragnar/pull/809) — fix(bt-pan): self-heal discoverability + class on the poll loop
*Merged 2026-09-18 · branch `fix/bt-pan-keepalive-discoverable` · 2 file(s), +19 / −2*

- **Docs:** [bluetooth-pan.md](bluetooth-pan.md)

#### [#808](https://github.com/PierreGode/Ragnar/pull/808) — feat(bt-pan): list + forget paired Bluetooth devices in the Config card
*Merged 2026-09-18 · branch `feat/bt-pan-device-list` · 5 file(s), +141 / −0*

- **Docs:** [bluetooth-pan.md](bluetooth-pan.md)

#### [#807](https://github.com/PierreGode/Ragnar/pull/807) — fix(bt-pan): advertise a network Class-of-Device so phones offer tethering
*Merged 2026-09-18 · branch `fix/bt-pan-network-class` · 2 file(s), +27 / −0*

- **Docs:** [bluetooth-pan.md](bluetooth-pan.md)

### 2026-09-17

#### [#801](https://github.com/PierreGode/Ragnar/pull/801) — fix(advscan): serialize ZAP scans, delete from all network DBs, stop ghost resurrection
*Merged 2026-09-17 · branch `fix/advscan-ghost-scans` · 3 file(s), +274 / −18*

- fix(advscan): serialize ZAP scans, delete scans from all network DBs, stop ghost resurrection

#### [#806](https://github.com/PierreGode/Ragnar/pull/806) — feat(icmp-watch): CVE-2020-16898 "Bad Neighbor" (ICMPv6 RA RDNSS overflow)
*Merged 2026-09-17 · branch `feature/icmp-watch-v4` · 5 file(s), +191 / −6*

- **Docs:** [README (root)](../README.md), [CREDITS.md](CREDITS.md), [nettools.md](nettools.md)

#### [#805](https://github.com/PierreGode/Ragnar/pull/805) — feat(dns): DNS Doctor v4 — passive DNS-response watcher + DNSSEC-CVE posture
*Merged 2026-09-17 · branch `feature/dns-doctor-v4` · 16 file(s), +2461 / −9*

- **Docs:** [README (root)](../README.md), [CREDITS.md](CREDITS.md), [nettools.md](nettools.md), [watchtower.md](watchtower.md)

#### [#804](https://github.com/PierreGode/Ragnar/pull/804) — feat(bt-pan): on-demand dependency install for the Bluetooth access point
*Merged 2026-09-17 · branch `feat/bt-pan-install-deps` · 5 file(s), +325 / −16*

- fix(bt-pan): box now shows up as 'Ragnar' and is actually discoverable
- fix(bt-pan): trust paired devices so the PAN actually connects (Android)
- **Docs:** [bluetooth-pan.md](bluetooth-pan.md)

#### [#803](https://github.com/PierreGode/Ragnar/pull/803) — feat(cyd): Settings toggles for Invert colors + Flip 180 (persisted)
*Merged 2026-09-17 · branch `vik` · 8 file(s), +399 / −66*

- feat(cyd): compact 4x6 font — ~25% smaller UI text everywhere
- revert(cyd): drop compact 4x6 font — restore readable built-in font
- feat(cyd): compact HOME menu — size-1 tile labels + tighter tiles
- fix(cyd): restore HOME tile size + size-2 labels
- feat(cyd): small proportional font for HOME tile labels only
- feat(cyd): action progress — spinner, elapsed clock, countdown + progress bar
- …and 2 more commit(s)
- **Docs:** [cyd-hybrid-node.md](cyd-hybrid-node.md)

#### [#802](https://github.com/PierreGode/Ragnar/pull/802) — feat(bt-pan): Bluetooth PAN (NAP) as a direct link for the mobile app
*Merged 2026-09-17 · branch `feat/bluetooth-pan` · 5 file(s), +505 / −0*

- **Docs:** [bluetooth-pan.md](bluetooth-pan.md)

#### [#800](https://github.com/PierreGode/Ragnar/pull/800) — feat(dheat): D(HE)at (CVE-2002-20001) across TLS + SSH + a new IPsec/IKE watcher
*Merged 2026-09-17 · branch `feature/dheater-cross-protocol` · 16 file(s), +1985 / −20*

- fix(ipsec): wire IPsec Watch into Watchtower + background rotation + docs
- docs(credits): update CVE corpus count for the D(HE)at / IPsec wave
- **Docs:** [README (root)](../README.md), [CREDITS.md](CREDITS.md), [nettools.md](nettools.md), [watchtower.md](watchtower.md)

### 2026-09-16

#### [#799](https://github.com/PierreGode/Ragnar/pull/799) — feat(ssh-watch): SWEET32 (CVE-2016-2183) attribution for DES/3DES-CBC
*Merged 2026-09-16 · branch `feature/ssh-watch-v4-sweet32` · 3 file(s), +119 / −10*

- **Docs:** [nettools.md](nettools.md)

#### [#798](https://github.com/PierreGode/Ragnar/pull/798) — test(relay-watch): add IPv6 self-test parity for Relay/Coercion Watch
*Merged 2026-09-16 · branch `feature/relay-watch-ipv6-parity` · 2 file(s), +54 / −4*

- **Docs:** [nettools.md](nettools.md)

#### [#797](https://github.com/PierreGode/Ragnar/pull/797) — Update CREDITS.md
*Merged 2026-09-16 · branch `PierreGode-patch-1` · 0 file(s), +0 / −0*

#### [#796](https://github.com/PierreGode/Ragnar/pull/796) — Update CREDITS.md
*Merged 2026-09-16 · branch `PierreGode-patch-1-1` · 1 file(s), +2 / −4*

- **Docs:** [CREDITS.md](CREDITS.md)

#### [#787](https://github.com/PierreGode/Ragnar/pull/787) — Display fix so that when on pi5's webui, ragnar's display updates correctly
*Merged 2026-09-16 · branch `fix/display-null-epd-guard` · 1 file(s), +28 / −0*

- fix(display): don't crash-loop when an EPD panel's helper is None

#### [#795](https://github.com/PierreGode/Ragnar/pull/795) — docs: add docs/CREDITS.md crediting Solarflere for the CVE research
*Merged 2026-09-16 · branch `docs/consolidate-md-into-docs` · 10 file(s), +65 / −71*

- docs: move remaining loose .md files under docs/
- docs: merge the two Home Assistant docs into one
- **Docs:** [README (root)](../README.md), [CREDITS.md](CREDITS.md), [docs index](README.md), [cyd-firmware.md](cyd-firmware.md), [cyd-hybrid-node.md](cyd-hybrid-node.md), [lab.md](lab.md), [legacywatch.md](legacywatch.md), [wpswatch.md](wpswatch.md)

#### [#794](https://github.com/PierreGode/Ragnar/pull/794) — tune(cyd): raise deauth-flood alert threshold 8 -> 15 frames
*Merged 2026-09-16 · branch `vik` · 2 file(s), +7 / −3*

- feat(cyd): CYD WiFi-Defense button runs a DEEP WIDS scan

### 2026-09-15

#### [#793](https://github.com/PierreGode/Ragnar/pull/793) — fix(cyd): revive 2.4GHz sniff + centred wardrive layout + snappier mesh/wifi streams
*Merged 2026-09-15 · branch `vik` · 6 file(s), +50 / −33*

- **Docs:** [cyd-hybrid-node.md](cyd-hybrid-node.md)

#### [#792](https://github.com/PierreGode/Ragnar/pull/792) — feat(arista-guard): port aristaguard v3 BlastRADIUS engine in-app
*Merged 2026-09-15 · branch `feature/arista-guard-v3-blastradius` · 3 file(s), +264 / −35*

- **Docs:** [nettools.md](nettools.md)

#### [#791](https://github.com/PierreGode/Ragnar/pull/791) — Add files via upload
*Merged 2026-09-15 · branch `vik` · 8 file(s), +51725 / −24001*

- feat(cyd): new full-screen 240x320 boot animation
- feat(cyd): boot animation plays at natural 15s, loops until Ragnar is up
- **Docs:** [cyd-hybrid-node.md](cyd-hybrid-node.md)

#### [#790](https://github.com/PierreGode/Ragnar/pull/790) — fix(cyd): keep the serial link responsive over the GPIO UART
*Merged 2026-09-15 · branch `vik` · 5 file(s), +58 / −12*

#### [#789](https://github.com/PierreGode/Ragnar/pull/789) — feat(cyd): rich live Wardrive page (nets/BLE/cell/zigbee/companions/GPS)
*Merged 2026-09-15 · branch `vik` · 7 file(s), +166 / −36*

- fix(cyd): stop wardriving from grabbing the CYD serial port
- feat(cyd): grey out wardrive Start/Stop while the action is in flight
- **Docs:** [cyd-hybrid-node.md](cyd-hybrid-node.md)

#### [#788](https://github.com/PierreGode/Ragnar/pull/788) — feat(cyd): Wardrive is its own page with live status
*Merged 2026-09-15 · branch `vik` · 5 file(s), +86 / −23*

- **Docs:** [cyd-hybrid-node.md](cyd-hybrid-node.md)

### 2026-09-14

#### [#786](https://github.com/PierreGode/Ragnar/pull/786) — feat(cyd): action result subpage — no more fire-and-forget taps
*Merged 2026-09-14 · branch `vik` · 6 file(s), +223 / −66*

- fix(cyd): stop the every-cycle reboot — reclaim ~53KB DRAM for WiFi
- fix(cyd): Traffic 'TOTAL PKTS' value green (was gray)
- feat(cyd): waterfall matches web inferno + adds spectrum strip & freq axis
- fix(cyd): brighter waterfall — gamma lift on the quantised row
- fix(cyd): brighter waterfall — raise black level + stronger gamma
- **Docs:** [cyd-hybrid-node.md](cyd-hybrid-node.md)

#### [#785](https://github.com/PierreGode/Ragnar/pull/785) — feat(selftest): surface Dell/MikroTik/Aruba + BFD/PTP/SR-MPLS/LACP/RPC in the Detector Self-Test
*Merged 2026-09-14 · branch `feature/detector-selftest-coverage` · 4 file(s), +64 / −5*

- **Docs:** [nettools.md](nettools.md)

#### [#784](https://github.com/PierreGode/Ragnar/pull/784) — Add files via upload
*Merged 2026-09-14 · branch `vik` · 8 file(s), +24168 / −74*

- feat(cyd): 5s glitch boot animation splash
- fix(cyd): header brand renders 'Ragnar' with a big R
- docs(cyd): refresh for the cabled console — de-emphasise WiFi, drop 'Bjorn'
- **Docs:** [cyd-hybrid-node.md](cyd-hybrid-node.md)

#### [#783](https://github.com/PierreGode/Ragnar/pull/783) — docs(aruba-guard): trim skip prose, drop non-PAPI CVEs, drop InstantOS from titles
*Merged 2026-09-14 · branch `feature/aruba-guard-text-cleanup` · 4 file(s), +12 / −25*

- Update nettools.md
- **Docs:** [nettools.md](nettools.md)

#### [#782](https://github.com/PierreGode/Ragnar/pull/782) — feat(cyd): honest bridge counters + fixed waterfall gain
*Merged 2026-09-14 · branch `feature/cyd-console-menu` · 2 file(s), +18 / −9*

#### [#781](https://github.com/PierreGode/Ragnar/pull/781) — feat(cyd): network actions, alerts view, expanded status fields
*Merged 2026-09-14 · branch `feature/cyd-console-menu` · 10 file(s), +1411 / −185*

- feat(cyd): touch-test / orientation validator screen
- fix(cyd): correct touch Y axis — validated on real hardware
- fix(cyd): bigger, easier back-button target
- fix(cyd): stop the every-2s graphics twitch (redraw only on change)
- feat(cyd): compact NET tile, short unit name, dense network grid
- fix(cyd): waterfall works with RTL-SDR; drop name from Dashboard
- …and 9 more commit(s)
- **Docs:** [cyd-hybrid-node.md](cyd-hybrid-node.md)

#### [#780](https://github.com/PierreGode/Ragnar/pull/780) — feat(cyd): dense data-driven launcher + Network & Settings screens
*Merged 2026-09-14 · branch `feature/cyd-console-menu` · 3 file(s), +149 / −40*

#### [#779](https://github.com/PierreGode/Ragnar/pull/779) — fix(cyd): touch axis orientation (was mirrored vs display)
*Merged 2026-09-14 · branch `fix/cyd-ui-responsive` · 5 file(s), +25 / −3*

- chore(cyd-flasher): drop the boar glyph from the flasher header

#### [#778](https://github.com/PierreGode/Ragnar/pull/778) — feat(aruba-guard): passive HPE Aruba PAPI CVE guard
*Merged 2026-09-14 · branch `feature/aruba-guard` · 5 file(s), +593 / −5*

- **Docs:** [nettools.md](nettools.md)

#### [#777](https://github.com/PierreGode/Ragnar/pull/777) — fix(cyd): responsive console — no twitch, steady LED, live touch
*Merged 2026-09-14 · branch `fix/cyd-ui-responsive` · 4 file(s), +90 / −67*

- **Docs:** [cyd-hybrid-node.md](cyd-hybrid-node.md)

### 2026-09-13

#### [#776](https://github.com/PierreGode/Ragnar/pull/776) — fix(rf-waterfall): smooth, even fall instead of stepping
*Merged 2026-09-13 · branch `fix/rtl-waterfall-smooth` · 2 file(s), +121 / −43*

#### [#775](https://github.com/PierreGode/Ragnar/pull/775) — feat(cyd): selectable serial port (GPIO/P1 UART, not just USB)
*Merged 2026-09-13 · branch `feature/cyd-hybrid-node` · 12 file(s), +913 / −111*

- feat(cyd): 2.4 GHz WiFi-Defense sensor -> Watchtower
- feat(cyd): app-launcher console + SigInt radar + streamed RF waterfall
- **Docs:** [cyd-hybrid-node.md](cyd-hybrid-node.md)

#### [#774](https://github.com/PierreGode/Ragnar/pull/774) — feat(cyd): ESP32-2432S028R hybrid companion node (firmware + ingest)
*Merged 2026-09-13 · branch `feature/cyd-hybrid-node` · 19 file(s), +2204 / −14*

- feat(cyd): live action dispatch + operator UI (Mesh → CYD Nodes)
- feat(cyd): status nets_24/nets_5 from cached iw scan dump
- feat(cyd): captive-portal provisioning + browser flasher (bins)
- feat(cyd): USB-serial transport — one cabled unit (no WiFi)
- ci(cyd): publish the CYD flasher on GitHub Pages
- **Docs:** [docs index](README.md), [cyd-hybrid-node.md](cyd-hybrid-node.md)

#### [#773](https://github.com/PierreGode/Ragnar/pull/773) — feat(ui): informational Dell Guard card (standalone daemon, no scan)
*Merged 2026-09-13 · branch `feature/dell-guard-info-card` · 3 file(s), +218 / −1*

- feat(dell-guard): enable/disable switch on the card (drives systemd)
- fix(dell-guard): --no-block systemctl so the switch doesn't time out

#### [#772](https://github.com/PierreGode/Ragnar/pull/772) — feat(mikrotik-guard): passive RouterOS (CCR/CRS) CVE guard
*Merged 2026-09-13 · branch `feature/mikrotik-guard` · 5 file(s), +752 / −5*

- **Docs:** [nettools.md](nettools.md)

#### [#770](https://github.com/PierreGode/Ragnar/pull/770) — Wdgwars Wardrive Upload Feature
*Merged 2026-09-13 · branch `feature/wdgwars-wardrive-upload` · 4 file(s), +409 / −0*

- wardriving: add WiGLE/WDGWars session upload endpoint
- wardriving UI: branded WDGWars/WiGLE upload card + per-session buttons
- wardriving UI: WDGWars card standalone; WiGLE creds move under Import WiGLE CSV
- wardriving: auto-upload finished wardrives (queued, offline-safe)
- wardriving: exclude WDGWars/WiGLE keys from config export
- wardriving: add WDGWars logo asset + render it as a badge

#### [#771](https://github.com/PierreGode/Ragnar/pull/771) — feat(dellguard): vendor Dell SmartFabric OS10 SSRF-egress sensor (CVE-2025-22474)
*Merged 2026-09-13 · branch `feature/dell-guard` · 9 file(s), +3875 / −2*

- **Docs:** [nettools.md](nettools.md)

#### [#767](https://github.com/PierreGode/Ragnar/pull/767) — tft kiosk: debounce mode detection to survive boot-time flapping
*Merged 2026-09-13 · branch `fix/tft35-kiosk-debounce` · 1 file(s), +19 / −7*

#### [#769](https://github.com/PierreGode/Ragnar/pull/769) — feat(tls-watch,ssh-watch): IPv6 extension-header capture (TLS v5 / SSH v3)
*Merged 2026-09-13 · branch `feature/watch-batch-tls-ssl-ntp-juniper` · 4 file(s), +86 / −11*

- **Docs:** [nettools.md](nettools.md)

### 2026-09-12

#### [#768](https://github.com/PierreGode/Ragnar/pull/768) — feat(ntp-watch): crypto-NAK auth-bypass + zero-origin injection (v4)
*Merged 2026-09-12 · branch `feature/ntp-watch-v4` · 4 file(s), +154 / −11*

- **Docs:** [nettools.md](nettools.md)

#### [#766](https://github.com/PierreGode/Ragnar/pull/766) — Make the SPI TFT kiosk mode-aware (Ragnar + Pwnagotchi)
*Merged 2026-09-12 · branch `feature/tft35-mode-aware-kiosk` · 4 file(s), +208 / −21*

- **Docs:** [PWNAGOTCHI.md](PWNAGOTCHI.md)

#### [#760](https://github.com/PierreGode/Ragnar/pull/760) — feat(rf-analyzer): multi-signal survey — find + track every carrier (Segment 10)
*Merged 2026-09-12 · branch `feature/analyzer-multisignal` · 5 file(s), +224 / −6*

- **Docs:** [rf-analyzer-roadmap.md](rf-analyzer-roadmap.md), [rf-waterfall.md](rf-waterfall.md)

#### [#765](https://github.com/PierreGode/Ragnar/pull/765) — Fix Pwnagotchi mode: make live capture, counting, and wpa-sec upload work
*Merged 2026-09-12 · branch `fix/pwnagotchi-pwn-mode` · 2 file(s), +120 / −0*

#### [#764](https://github.com/PierreGode/Ragnar/pull/764) — feat(tls-watch): RC4 + record-layer CVEs (v4)
*Merged 2026-09-12 · branch `feature/tls-watch-v4` · 3 file(s), +329 / −21*

- **Docs:** [nettools.md](nettools.md)

#### [#763](https://github.com/PierreGode/Ragnar/pull/763) — feat(rf-analyzer): PWM/PPM pulse symbol decoder (Segment 12)
*Merged 2026-09-12 · branch `feature/analyzer-pulse` · 4 file(s), +240 / −10*

- **Docs:** [rf-analyzer-roadmap.md](rf-analyzer-roadmap.md)

#### [#762](https://github.com/PierreGode/Ragnar/pull/762) — feat(rf-analyzer): device fingerprint + bit workbench (Segment 11)
*Merged 2026-09-12 · branch `feature/analyzer-fingerprint` · 4 file(s), +589 / −21*

- **Docs:** [rf-analyzer-roadmap.md](rf-analyzer-roadmap.md)

### 2026-09-11

#### [#761](https://github.com/PierreGode/Ragnar/pull/761) — feat(ssh-watch): duplicate host key detection (v2, CVE-2025-38741 family)
*Merged 2026-09-11 · branch `feature/ssh-watch-v2` · 3 file(s), +332 / −12*

- **Docs:** [nettools.md](nettools.md)

#### [#759](https://github.com/PierreGode/Ragnar/pull/759) — feat(cisco-guard): CAPWAP malformed-header detection (v5, CVE-2025-20315)
*Merged 2026-09-11 · branch `feature/cisco-guard-v5` · 3 file(s), +97 / −4*

- **Docs:** [nettools.md](nettools.md)

#### [#758](https://github.com/PierreGode/Ragnar/pull/758) — feat(rf-analyzer): upload/import recordings (Flipper .sub, raw IQ, SigMF)
*Merged 2026-09-11 · branch `feature/analyzer-upload` · 5 file(s), +382 / −3*

- **Docs:** [rf-analyzer-roadmap.md](rf-analyzer-roadmap.md), [rf-waterfall.md](rf-waterfall.md)

#### [#757](https://github.com/PierreGode/Ragnar/pull/757) — feat(rf-waterfall): optional 3D terrain waterfall view (2D | 3D toggle)
*Merged 2026-09-11 · branch `feature/waterfall-3d` · 2 file(s), +99 / −6*

- fix(rf-waterfall): smooth the 3D surface (rounded crests, finer, anti-aliased)
- **Docs:** [rf-waterfall.md](rf-waterfall.md)

#### [#756](https://github.com/PierreGode/Ragnar/pull/756) — feat(rf-analyzer): PSK constellation demod (Segment 9)
*Merged 2026-09-11 · branch `feature/analyzer-constellation` · 5 file(s), +267 / −9*

- style(rf-analyzer): lay Cyclostationary + LoRa + Constellation side by side
- style(rf-analyzer): swap the Constellation demod and Filter card slots
- **Docs:** [rf-analyzer-roadmap.md](rf-analyzer-roadmap.md), [rf-waterfall.md](rf-waterfall.md)

#### [#755](https://github.com/PierreGode/Ragnar/pull/755) — refactor(signal-intel): tidy the toolbar into two logical rows
*Merged 2026-09-11 · branch `feature/signal-intel-toolbar-tidy` · 3 file(s), +26 / −11*

- fix(signal-intel): analyzer back-link, dead wifi-status id, button spacing
- style(signal-intel): more horizontal spacing between toolbar controls
- fix(signal-intel): use gap classes that exist in the compiled Tailwind
- style(signal-intel): tighten toolbar spacing to gap-4 (24px -> 16px)

#### [#754](https://github.com/PierreGode/Ragnar/pull/754) — feat(rf-analyzer): shareable deep-links + keyboard shortcuts (Segment 8)
*Merged 2026-09-11 · branch `feature/analyzer-ux` · 5 file(s), +106 / −15*

- feat(signal-intel): add a Signal Analyzer button to the SI tool row
- **Docs:** [rf-analyzer-roadmap.md](rf-analyzer-roadmap.md), [rf-waterfall.md](rf-waterfall.md)

#### [#753](https://github.com/PierreGode/Ragnar/pull/753) — feat(rf-analyzer): cyclostationary symbol-rate detector (Segment 7)
*Merged 2026-09-11 · branch `feature/analyzer-cyclo` · 4 file(s), +192 / −3*

- **Docs:** [rf-analyzer-roadmap.md](rf-analyzer-roadmap.md)

#### [#752](https://github.com/PierreGode/Ragnar/pull/752) — feat(rf-analyzer): LoRa de-chirp view (Segment 7)
*Merged 2026-09-11 · branch `feature/analyzer-lora` · 4 file(s), +244 / −31*

- feat(rf-analyzer): move Modulation card under Time envelope; upgrade the symbol tool
- fix(rf-analyzer): LoRa de-chirp card — inset the BW/SF controls and plot from the edge
- **Docs:** [rf-analyzer-roadmap.md](rf-analyzer-roadmap.md)

#### [#751](https://github.com/PierreGode/Ragnar/pull/751) — feat(rf-analyzer): Segment 7 (start) — band-pass / notch filter with before/after spectrum
*Merged 2026-09-11 · branch `feature/analyzer-dsp` · 4 file(s), +125 / −5*

- **Docs:** [rf-analyzer-roadmap.md](rf-analyzer-roadmap.md)

#### [#750](https://github.com/PierreGode/Ragnar/pull/750) — feat(rf-analyzer): symbol-period cursor on the derived plots (inspectrum parity)
*Merged 2026-09-11 · branch `feature/analyzer-symcursor` · 2 file(s), +82 / −12*

- feat(rf-analyzer): stack the derived plots (inspectrum multi-plot model)
- **Docs:** [rf-analyzer-roadmap.md](rf-analyzer-roadmap.md)

#### [#749](https://github.com/PierreGode/Ragnar/pull/749) — feat(rf-analyzer): I/Q sample plot (inspectrum's "Add sample plot")
*Merged 2026-09-11 · branch `feature/analyzer-sampleplot` · 3 file(s), +26 / −5*

- **Docs:** [rf-analyzer-roadmap.md](rf-analyzer-roadmap.md)

#### [#748](https://github.com/PierreGode/Ragnar/pull/748) — feat(rf-analyzer): Segment 6 — SigMF annotations (label signals, round-trip to the file)
*Merged 2026-09-11 · branch `feature/analyzer-annotations` · 4 file(s), +216 / −9*

- **Docs:** [rf-analyzer-roadmap.md](rf-analyzer-roadmap.md)

#### [#747](https://github.com/PierreGode/Ragnar/pull/747) — feat(rf-analyzer): candidate frame lengths + per-candidate CRC scan
*Merged 2026-09-11 · branch `feature/analyzer-frame-candidates` · 4 file(s), +188 / −44*

- **Docs:** [rf-analyzer-roadmap.md](rf-analyzer-roadmap.md)

#### [#746](https://github.com/PierreGode/Ragnar/pull/746) — feat(rf-analyzer): AI assistant can take actions (agentic — drives the analyzer)
*Merged 2026-09-11 · branch `feature/analyzer-ai-actions` · 5 file(s), +190 / −5*

- **Docs:** [rf-waterfall.md](rf-waterfall.md)

#### [#745](https://github.com/PierreGode/Ragnar/pull/745) — feat(rf-analyzer): AI RF-analyst assistant on the Signal Analyzer page
*Merged 2026-09-11 · branch `feature/analyzer-ai` · 4 file(s), +157 / −1*

- **Docs:** [rf-waterfall.md](rf-waterfall.md)

#### [#744](https://github.com/PierreGode/Ragnar/pull/744) — feat(rf-analyzer): loading spinner while the spectrogram computes
*Merged 2026-09-11 · branch `fix/analyzer-spinner` · 1 file(s), +14 / −1*

#### [#743](https://github.com/PierreGode/Ragnar/pull/743) — feat(rf-analyzer): Segment 4 — protocol framework (line coding, frame alignment, CRC scan)
*Merged 2026-09-11 · branch `feature/analyzer-protocol` · 4 file(s), +296 / −6*

- **Docs:** [rf-analyzer-roadmap.md](rf-analyzer-roadmap.md)

#### [#742](https://github.com/PierreGode/Ragnar/pull/742) — feat(rf-analyzer): Segment 3 — modulation analysis (classify + constellation + instantaneous)
*Merged 2026-09-11 · branch `feature/analyzer-modclass` · 4 file(s), +237 / −9*

- **Docs:** [rf-analyzer-roadmap.md](rf-analyzer-roadmap.md)

#### [#741](https://github.com/PierreGode/Ragnar/pull/741) — feat(rf-analyzer): Segment 2 — measurement (cursors/Δ, box power, zoom history, max-hold) + follow-ups
*Merged 2026-09-11 · branch `feature/analyzer-measure` · 4 file(s), +157 / −48*

- **Docs:** [rf-analyzer-roadmap.md](rf-analyzer-roadmap.md)

#### [#740](https://github.com/PierreGode/Ragnar/pull/740) — feat(rf-analyzer): Segment 1 — decode-from-capture (rtl_433) + bit views; add roadmap
*Merged 2026-09-11 · branch `feature/analyzer-decode` · 5 file(s), +310 / −35*

- fix(rf-analyzer): robust burst detection — gap-merge + duty (handles held & pulse-train signals)
- **Docs:** [rf-analyzer-roadmap.md](rf-analyzer-roadmap.md), [rf-waterfall.md](rf-waterfall.md)

#### [#739](https://github.com/PierreGode/Ragnar/pull/739) — feat(rf-analyzer): on-box SigMF IQ analyzer page + "Open in Analyzer" button
*Merged 2026-09-11 · branch `feature/sigmf-analyzer` · 8 file(s), +1050 / −1*

- feat(rf-waterfall): Sessions dropdown — open any recorded SigMF capture in the Analyzer
- feat(rf-waterfall): ⓘ info popup on IQ capture — size/memory guidance
- feat(rf-waterfall): rename + delete for SigMF sessions
- **Docs:** [rf-waterfall-guide.md](rf-waterfall-guide.md), [rf-waterfall.md](rf-waterfall.md)

#### [#738](https://github.com/PierreGode/Ragnar/pull/738) — fix(radio): stream Local Radio as MP3 so it plays on iOS / mobile
*Merged 2026-09-11 · branch `fix/radio-ios-mp3` · 5 file(s), +90 / −15*

- **Docs:** [sdr-subghz.md](sdr-subghz.md)

#### [#737](https://github.com/PierreGode/Ragnar/pull/737) — docs: add RF Waterfall capability guide
*Merged 2026-09-11 · branch `docs/rf-waterfall-guide` · 2 file(s), +131 / −1*

- **Docs:** [docs index](README.md), [rf-waterfall-guide.md](rf-waterfall-guide.md)

