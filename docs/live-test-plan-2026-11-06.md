# Discord regression test plan — 6 November 2026

Status: planning complete; no commands executed in this pass.

Server: **GIRCord 2.0** (`1203746555786432572`). Administrator: **habibitest2** (`705338290110332938`, Chrome profile GIRRewrite Target). Target: **habibitest** (`920662313399357460`, Chrome profile Your Chrome). Profile names are misleading; verify Discord identities before every moderation action. These assignments supersede the October report.

Source inventory: **113 slash-command leaves, 10 context-menu registrations, 2 prefix commands** (`!tag` with alias `!t`, and `!sync`). Reconcile these with the running bot's registered commands before execution; source presence does not establish runtime availability. The October report's 94 count is not the current source inventory.

## Execution and evidence

Each matrix row expands into separate cases. Record case ID, command and inputs, actor, precondition, expected result, actual result, Discord message link or screenshot, error reference, side effects, and cleanup. Use statuses NOT RUN, PASS, FAIL, BLOCKED, or PARTIAL. Record Discord client validation separately from handler execution. Browser observations cannot establish a numerical Python branch-coverage percentage.

Use `QA20261106` in reasons and disposable content; use alphanumeric names such as `qa20261106tag`. Save results in a separate dated report. Retest October failures from scratch: `/xptop`, `/editreason`, mixed-case `/casestats keyword`, mute timestamps, birthday role handling, and tags with missing sub-mod configuration.

Report progress at the start/end of each group and while longer workflows run: current command/case, outcomes, defects, cleanup, and next step. Do not label a command passed solely because it returned a success message. Check the target's UI, DMs, public log, cases, and persisted values exposed by read commands as applicable. Distinguish a failed operation from an operation that succeeded but failed to respond/log.

## 0. Establish prerequisites and restoration

1. Confirm both account IDs, server ID, bot identity, bot uptime, and actual permissions. Bot permissions use configured role IDs, not merely Discord's Administrator bit.
2. Check configured test-server channels/roles exist: bot commands, public logs, reports, rules, common issues, subreddit news, birthday, member tiers, moderator, administrator, sub-mod. Inspect configuration without exposing credentials. Missing fixtures block the relevant positive case; do not silently change the expected result.
3. Choose a disposable QA text channel and forum thread. Record initial channel overwrites, freezeable/ignored channel lists, switches, whitelist/filter entries, target nickname/roles, birthday/exclusion, timezone, XP/freeze state, warning points, command bans, and verification state. If a mutation has no command-based inverse, establish a narrowly scoped snapshot/restore method before running it.
4. Verify admin-to-target DMs work independent of server membership (friend connection if needed), prepare a usable invite, and send it over DM before removal tests. After every kick/ban: unban where needed, send the invite over DM again, use the target session to join, and verify membership, roles, and command access. Keep admin recovery access available throughout.
5. Inspect ban message-deletion behavior before execution. Save evidence before a ban and restrict deletion/purge tests to disposable QA messages. Any irreversible deletion of existing non-test content needs separate action-time confirmation.
6. Confirm the running process matches the checkout where possible. No second bot process. Do not restart the user-started bot until its launch method and safe restart procedure are known.

## 1. Shared checks applied across command groups

| Area | Cases and expected result |
| --- | --- |
| Authorization | Admin success; target denied for every privileged command available to it; hidden commands recorded as client restriction, not proof of backend enforcement. For intermediate Member+/Pro/Edition/Genius/sub-mod/mod tiers, test available roles or mark fixture-dependent. Guild-owner/bot-owner commands remain separately gated. |
| Target checks | Self, bot, equal/higher-role target rejected where the transformer requires it; ordinary lower-role target accepted. Test external-user paths using the same target while outside the server. Never target unrelated members. |
| Global checks | `/command_ban` prevents target execution, then removal restores it; cover a grouped subcommand too. A unique filtered phrase in an ordinary user's command argument is rejected; permitted/admin bypass remains functional. Guild-only commands unavailable in DMs. |
| Responses | Correct public versus ephemeral behavior in configured bot/general/support channels; expected DM received; no duplicate responses, unexplained interaction failures, or unintended mentions. |
| Inputs | Omitted optional fields versus explicit values; valid autocomplete selection versus arbitrary typed text; malformed IDs; case/whitespace variants; numeric boundaries; Unicode/markdown where relevant. Inputs blocked by Discord are not counted as server branches. |
| Components | First/next/previous/last page, single/empty/multiple pages; owner versus other user's click; selection menus; Yes/No/timeout; modal submit/cancel/validation. Check no writes on cancellation and no duplicate action on repeat clicks. |
| Attachments | Small PNG/JPEG/GIF/WebP; non-image rejected; missing optional image; replacement of an existing image; per-command 8,000,000-byte boundary where present, subject to account upload limits. Do not assume every image command has the same size rule. |
| State | Read before/after; reject duplicates without extra writes; verify cleanup; short concurrent operations checked for lost updates or duplicate cases. Deterministic race/failure claims require automated tests. |

## 2. Read-only baseline and lookups

| Commands | Cases |
| --- | --- |
| `/ping`, `/stats`, `/serverinfo`, `/roleinfo`, `/raidstats` | Both sessions; plausible latency/uptime; populated and empty role; server fields and raid totals render. Optional banner branch only if fixture exists. |
| `/help`, `/usage` | Full help DM for each account; existing command, grouped command/subcommand, unknown name; optional/required parameters; privileged help visibility; DM-disabled path if controllable and restorable. |
| `/userinfo`, `/xp`, `/warnpoints`, `/cases`, `/rundown`, `/xptop`, `/viewmuted` | Self default and explicit target; target denied access to others' restricted records; no cases versus multiple pages; WARN/MUTE/KICK/BAN/UNBAN/REMOVEPOINTS and lifted case display; empty/populated mute list; leaderboard navigation and top-three formatting. External target lookup during removal cycle. |
| `/casestats mod`, `/casestats keyword` | Default/current moderator, explicit moderator, no cases, matching/nonmatching keyword, mixed-case `QA20261106 MiXeD` reason; compare counts against created cases. Historical dates must not change after edit/lift. |
| `/avatar`, `/jumbo`, `/topic`, `/rule`, `/8ball`, `/dstatus` | Default/explicit avatar; static/default and animated/server avatar if available; Unicode/custom/invalid emoji and cooldown; topic absent/present/current/explicit channel; rule exact/autocomplete/number/fuzzy/no match as supported, with/without mention; normal 8ball response; status result or explicit upstream failure. |
| `/jailbreak`, `/firmware`, `/betafirmware`, `/deviceinfo`, `/canijailbreak`, `/bypass` | Known result and nonexistent input; autocomplete; device name versus identifier; supported and incompatible device/version; jailbreak available/unavailable and multiple results; stable/beta firmware; signed/unsigned/mixed firmware when data supports it; bypass exists/no bypass/unknown app; page and selection controls. Pick exact positive fixtures from current bot autocomplete rather than guessing catalog contents. |
| `/package`, `/repo` | Query shorter than two characters; normal match, no match, multiple results and selected result; repo autocomplete versus raw input/URL; links and buttons; general-channel privacy branch. External service failures recorded separately from bot regressions. |

## 3. Reversible personal state and scheduled jobs

| Commands | Cases |
| --- | --- |
| `/timezone set`, `/timezone view`, `/timezone list`, `/timezone remove` | Set Europe/Copenhagen, replace with UTC, invalid zone; view unset/set member; all zones, valid/invalid country code, page controls; remove and repeat removal. Restore original zone. |
| `/device add`, `/device remove` | Valid autocomplete device/version; invalid/incompatible pair; fresh nickname and replace existing device suffix; nickname length limit; remove absent/present suffix; bot role-hierarchy rejection where available. Restore original nickname. |
| `/remindme` | 20-second delivery exactly once; two overlapping reminders; malformed, zero and negative duration; verify recipient/text/time. Persistence across a controlled restart and quota failure are separate prerequisite-dependent cases. |
| `/freezexp` | Record XP, freeze target, send ordinary QA message, verify no increment, unfreeze and verify awards resume. Allow for unrelated traffic; restore original freeze state. |
| `/mybirthday`, `/setbirthday`, `/removebirthday`, `/birthdayexclude` | Permission/ineligible user; valid date, impossible date, Feb 29, zero/out-of-range day where accepted by UI; already-set birthday; exclusion denies self-set; moderator override clears exclusion as implemented; today triggers birthday role; non-today does not; role removal; bot target rejection. Missing-role branch gets isolated handling because earlier tests showed partial writes/no response. Restore original birthday/exclusion/role and jobs. |
| `/command_ban` | Ban `/ping`, target denial, unban and success; grouped `timezone view`; unknown command/subcommand; autocomplete. Restore prior restrictions. |
| `/giveaway start`, `/giveaway end`, `/giveaway reroll` | Explicit pretend/no-value QA prize; malformed duration, zero/negative winners; 1 winner, more winners than entrants; no entrants, one entrant, both accounts; normal expiry, early end, repeat end; unknown/nonnumeric ID; reroll active, ended-empty, eligible next winner, and exhausted winners. Verify scheduled end does not repeat after manual end. Departed-only remaining entrant path requires controlled automated testing because reroll can loop indefinitely. |

## 4. Content creation and interactive UI

| Commands | Cases |
| --- | --- |
| `/tags add`, `/tags edit`, `/tags delete`, `/tag`, `/taglist`, `!tag`, `!t` | Create text-only and image tags; duplicate/mixed-case name, nonalphanumeric/multiword name; missing tag; edit body/image/buttons, cancel/no change; delete then repeat delete; list/page; with/without user mention; prefix direct/reply behavior; target cooldown and admin bypass. Only delete test-created tags. |
| Tag/common-issue modals | Zero/one/two buttons; label without URL and URL without label; invalid URL scheme; leading emoji with text versus emoji-only/misplaced emoji; empty/whitespace body; field length limits; submit and cancel. Verify rendered links and persisted edits. |
| `/memes add`, `/memes edit`, `/memes delete`, `/meme`, `/memelist` | Text/image lifecycle; duplicate/invalid/missing names; image replacement; modal cancellation; mention/no mention; empty/populated list where naturally available; cooldown/bypass; cleanup only own fixtures. |
| `/commonissue new`, `/commonissue edit`, `/commonissue reindex`, `/issue` | Disposable issue with/without image/buttons; unknown title; cancel modal; refresh cache and read back; reindex includes new issue and avoids duplicate TOC; mentions and links. Reindex success requires a QA-only configured issues channel because it replaces existing index messages. |
| `/postembed`, `/rawembed`, `/subnews`, `/say`, `/poll` | Default and explicit QA destination; text-only/image; raw embed mobile-friendly true/false, invalid/nonnumeric/missing message ID, non-bot message, bot message without embed; poll reactions and target vote. Subnews positive case requires configured QA destination/role to avoid pinging unrelated users. |
| `/solved` | Reject text channel and non-forum thread; own QA forum post success; non-owner unauthorized rejection; authorized staff success; hierarchy branch if fixture exists. Verify archived/locked state. |
| `/snipe` | Empty channel; edit a disposable text message; delete disposable text/image/attachment-only message; verify correct prior content and channel isolation. Do not use unrelated users' content. |
| `/neuralnet`, `/memegen regular`, `/memegen motivate`, `/memegen aitext` | Enabled success or explicit disabled result; image validation/size; ASCII versus Unicode top/bottom text; allowed/disallowed channel; cooldown/admin bypass; response attachment. API error, confidence tiers, and generated filtered-output branches need deterministic mocks unless naturally observed. |

## 5. Moderation, run one action at a time

For successful actions verify target state, case type/unique ID, actor, reason, timestamp, DM and configured public log. No successful moderation case should be recorded for a Discord action that was rejected; case-number gaps alone are allowed.

| Commands | Cases and restoration |
| --- | --- |
| `/warn`, `/removepoints` | Normal 1/10-point warning; reason with markdown and mixed case; client boundaries 0/1/600/601; remove some/all points and reject negative resulting total. First preserve baseline and restore after each scenario. Later threshold cycle: total 399 (no kick), 400 (kick), return and 401 (no second kick when already warned-kicked), 599 (no ban), 600 (ban); unban/DM invite/rejoin; restore points and historical warning-kick flag using established recovery. |
| `/liftwarn` | Valid own QA warning; unknown ID, wrong user's ID, non-WARN case, already lifted, and lifting after points were removed would go negative. Verify both case flag and points, DM/log, unchanged original date. |
| `/editreason` | Valid QA case with matching public log; no matching log message using a purpose-built fixture; nonexistent/wrong user case; text escaping. Confirm saved reason and DM even if response fails. Compare `/cases` and both statistics commands. |
| `/mute`, `/unmute`, `/viewmuted` | 20-second native expiry; 2-minute timeout manually removed; repeat mute while muted; unmute when not muted; omitted reason; malformed/zero/negative duration; exactly 14 days then immediate cleanup, above 14 days rejected. Verify timestamps in both UIs. New timeout must survive older timeout's original expiry. |
| `/kick`, `/roblox` | Lower-role target removed with expected reason; self/bot/hierarchy denial; each followed by DM invitation and verified return. Blocked-DM variant only after independent recovery route verified. |
| `/ban`, `/unban` | Member ban, already-banned target rejection; unban, repeat unban while still outside; external target ban by ID while absent; current-member unban rejection; cache correctness and no duplicated cases; DM invitation and verified return after each cycle. |
| `/staffban` | Initiator cannot approve own request; ordinary target cannot approve; timeout leaves target untouched. A different authorized moderator is required for both accepted Yes and accepted No branches; mark blocked with present two-account setup. |
| `/purge` | 1, several, and 100 disposable messages if practical; reject 0/101 at UI boundary; requested amount greater than existing QA message count; confirm actual count and no deletion outside QA channel. |
| `/transferprofile` | Permission/self/hierarchy rejection now. Success needs two lower-role disposable targets plus admin and snapshots of both profiles/cases. Test populated source/empty destination, populated destination per intended merge semantics, source=destination guard, and restoration only in that isolated fixture. Never use the admin's real profile as destination. |
| `/clem` | Owner-only rejection for ordinary admin/target; self/bot rejection when owner available. Success needs guild/bot owner and restorable target snapshot; verify actual XP/level against advertised reset as well as 599 points, freeze flag, clem flag and case. No ordinary message/warn until restoration. |

## 6. Filters, raid controls and report actions

| Commands | Cases |
| --- | --- |
| `/filter add`, `/filter list`, `/filter remove`, `/silent_filter`, `/piracy`, `/falsepositive` | Unique harmless QA phrase; duplicate add; notify on/off; bypass thresholds; list/readback; matching target message versus permitted admin; silent report without deletion; piracy marker behavior; enhanced-check toggle; remove missing/existing and prove filter ceases. Test normalized/case/obfuscation matches and benign near-miss. Restore configuration immediately. |
| `/whitelist`, `/blacklist` | Valid QA guild ID, malformed ID, add twice, remove twice; prove whitelist affects invite filter using controlled invite fixtures. Do not alter unrelated guild entries. |
| `/ignorechannel`, `/unignorechannel`, `/ignorechannellogs`, `/unignorechannellogs` | Add/repeat/remove/repeat; verify actual filtering/logging behavior before/during/after. Restore original membership, not an assumed default. |
| `/offlineping`, `/spammode`, `/verify` | Explicit true/false and omitted toggle; readback/report effects; restore original values. Verify target state influences antiraid exemptions. Today's-new-account branch cannot be simulated with these old accounts. |
| `/raid add`, `/raid list`, `/raid remove`, `/batchraid` | Unique harmless phrase, duplicate, missing removal; mixed-case/normalization; batch modal blank/cancel, new phrases, duplicates-only, mixed duplicates/new, Yes/No/20-second timeout; list and cleanup. Large confirmation truncation tested only with disposable bounded fixtures. |
| `/lock`, `/unlock`, `/freezeable`, `/unfreezeable`, `/freeze`, `/unfreeze` | Current/explicit QA channel; repeated transitions; verify target send permission while admin recovery stays available; zero/multiple freezeable channels only after original list is recorded and isolated; already frozen/unfrozen; restore exact original overwrites/list. |
| `/nameban` | Preview matching set; wrong-user click, cancel, timeout. Confirm success only if preview is exclusively the disposable target. Verify membership/cases and restore via unban/invite. Multiple matching users needs additional disposable fixtures. |
| Report buttons | Create a controlled filter/invite report; authorized/unauthorized action, Dismiss/Ban, repeat clicks and expiration. Dismiss own timeout restores access; create newer timeout then dismiss old report: newer timeout must survive. Failed/no/expired timeout must not cause unmute. Ban routes through the same recovery cycle. |

## 7. Context menus and owner utilities

Run each of **Support tag**, **View avatar**, **Warn 50 points**, **Generate report**, and **Userinfo** from both a member and that member's message (10 registrations). Verify correct target resolution, role checks, response visibility, menus/buttons, support-tag missing/cooldown branches, and cleanup of 50 warning points. Generated report must refer to the selected message author, not the invoker.

`/setpfp`: unauthorized target rejection, invalid attachment, valid image only with original bot avatar saved for restoration; account-wide effect means run last and restore immediately. `/sabbath`: ordinary admin denied unless also owner; explicit on/off/toggle for owner only, restore prior setting. `!sync`: non-owner denied; actual sync only if command registration is stale and bot owner available. Verify resulting inventory without creating duplicate globals/guild commands. These are real permission constraints, not reasons to promote the test target to owner.

## 8. Refactor-specific verification beyond UI commands

Run the existing regression suite separately and report its actual outcome. Relevant files cover boot, database boundary, case numbers, XP, jobs, birthdays, timeout ownership, ban outcomes, image queue, HTTP fetchers, worker pools, and log queue. Real-Mongo tests require an explicitly disposable test database; never use the running bot database for destructive integration tests.

Controlled restart cases (after process ownership is established): pending reminder; active timeout; pending giveaway; check exactly-once delivery/end and no early unmute. Confirm scheduled callbacks complete and error cleanly. Persistent report views are documented as unsupported after restart; record that limitation instead of counting it as new passing coverage.

Injected Discord Forbidden/NotFound, database failure after successful moderation, malformed upstream responses, queue saturation/deadlines, real atomic concurrency, absent member birthday jobs, slow I/O and reconnects belong in deterministic automated/isolated tests. Do not deliberately disconnect the user's running database or flood Discord to force these branches. Browser coverage and backend coverage are reported separately.

## Completion criteria

Every source command has a recorded outcome, with separate positive and negative cases where reachable. Every mutation has verified cleanup or an explicit unresolved item. Target is in GIRCord 2.0, unbanned and not timed out, with baseline roles/settings restored; QA channel locks, filters, toggles and jobs restored/finished; bot avatar restored if changed. Moderation case history remains labeled QA evidence. Report remaining fixture/owner/integration limitations and defects with reproducible inputs; no claim of full branch coverage from manual testing alone.
