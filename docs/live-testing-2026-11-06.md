# Live tests — 6 November 2026

In progress. Server GIRCord 2.0. Intended admin habibitest2; target habibitest. Moderation lifecycle tests are in progress; see results below.

| Case | Result | Evidence |
| --- | --- | --- |
| Admin /ping | PASS | 20:52 Copenhagen: message latency 568ms, API 172ms. Message 1568352353805930517 in bot-cmds 1536450411911975013. |
| Admin /stats | PASS | 20:52: Python 3.9.6, 37 MB, uptime about 8 minutes. Message 1568352455769718898. |
| Admin /viewmuted | BLOCKED | 20:57: habibitest2 received ephemeral “You do not have permission to use this command.” Intended admin is not recognized by running bot permission mapping. User notified. |
| Admin /viewmuted retry | PASS | 20:58 after user role correction: “No one is muted.” Prior permission blocker resolved. |
| Target /viewmuted | PASS rejection | 20:58 habibitest denied with expected permission error. |
| Admin /serverinfo | PASS | 20:59: 12 users, 23 channels, 17 roles, 0 bans, 1 emoji. |
| Admin /xptop | FAIL | 20:59 generic error reference 423c4e29653d. Reproduces earlier leaderboard failure. |
| Admin /raidstats | PASS | 21:00 all categories and total zero. |
| Admin /userinfo default | PASS | habibitest2, level 2, XP 4; roles aaron/admin/mod rendered. |
| Target /warnpoints default | PASS | Target ID 920662313399357460, baseline 0 points. |
| /taglist, /memelist | PASS empty branches | Expected no-tags/no-memes responses. Populated paths untested. |
| /filter list, /raid list | PASS empty branches | Expected empty-list validation. |
| /tags add name:qa20261106tag | FAIL / config blocker | 21:02 error 109751bf4d32 before modal. Source permission guard returns no success when configured sub_mod role is missing. Runtime traceback not inspected. |

Recovery preparation: admin sent a 30-day GIRCord 2.0 invite to target by DM; target session visibly received the valid server invite card. Admin sent friend request and target accepted; pending-request controls disappeared. Invite acceptance after actual removal remains untested.

## After configuration repair and agent-managed restart

All placeholder channel/role IDs replaced with verified GIRCord 2.0 IDs. Bot started in exec session 62811; log /private/tmp/gir-live-testing-20261106.log. Database, gateway and scheduler startup succeeded.

| Case | Result | Evidence |
| --- | --- | --- |
| /xptop | FAIL confirmed | 21:07 cbe5282626ea. Traceback: utils/views/menus/menu.py:48 indexes self.pages[self.current_page - 1] when pages is empty. |
| /tags add qa20261106tag | PARTIAL / response defect | Permission gate now passes and modal opens. Submitted body “QA20261106 disposable regression tag.” with no buttons/image. Modal reports Something went wrong, but tag persisted. No new traceback in captured log at inspection. |
| /taglist populated | PASS | Lists qa20261106tag, author habibitest2, usage 0, page 1/1. |
| /tag qa20261106tag | PASS | Correct body returned, usage incremented to 1. |
| /tags delete qa20261106tag | PASS | Deletion acknowledged; subsequent /taglist confirms no tags defined. QA fixture cleaned up. |

Automated suite: `.venv/bin/python -m unittest discover -s tests -v` completed with 47 tests discovered, 44 passed, 3 skipped (real MongoDB concurrency required). No failures. This does not establish live command coverage.

Configuration placeholders were repaired before the agent-managed restart; see configuration section above.

Unlisted cases remain NOT RUN; see live-test-plan-2026-11-06.md. This report is updated during execution.

### Continued live run — 21:10–21:15
- `/timezone list`: all-zone result rendered page 1/29; controls automatically disabled on timeout. Active navigation still pending.
- `/timezone view member:habibitest2`: correctly reported unset baseline.
- `/timezone set Europe/Copenhagen`: success; `/timezone remove`: success, restoring original unset state. Set readback/invalid variants pending.
- `/help`: mailbox acknowledgement returned; DM content verification pending.
- `/warn user:920662313399357460 points:1 reason:QA20261106 MiXeD warning lifecycle`: case #19 created, target `/warnpoints` independently showed 1.
- `/editreason` case #19 to `QA20261106 MiXeD edited reason`: success, reported public-log edit and preserved original 21:13 timestamp in response.
- `/liftwarn` case #19: reported decrease of 1; independent zero-point readback pending.
- `/mute` target for 20s, omitted reason: case #20 created with default `No reason.` Target UI explicitly showed Timed Out with 14 seconds remaining, confirming enforcement. Expiry verification next.

### Timeout and kick recovery — 21:15–21:17
- 20-second timeout expired; target successfully posted `QA20261106 timeout expired; target can send again.`
- Two-minute timeout case #22 applied; `/unmute` case #23 succeeded with QA cleanup reason.
- `/kick` case #24 removed target; target UI returned to Friends. Admin sent the invite again through their existing DM; target clicked Join and returned to bot-cmds with an enabled composer. Recovery verified.

### Cases, lookups, reminder, ban — 21:18–21:23
- Target `/warnpoints`: independently confirms zero restored after lifting. `/cases` shows case #19 lifted with edited reason and original 21:13 timestamp.
- FAIL: `/cases` renders new mute cases #20/#22 at 20:15 despite execution at 21:15 (one-hour timezone error). Kick timestamp correct.
- FAIL: `/casestats keyword QA20261106 MiXeD` returns zero despite matching persisted warning. `/casestats mod` lists five moderator cases including that exact lowercased reason.
- `/cases` default works for both accounts (populated histories); `/xp` target returns level 3, XP58/135, rank634/5622.
- `/help` full DM content verified. `/usage warn` displays all required arguments and descriptions.
- `/remindme` 20s: DM received once with exact QA content; captured scheduler log confirms callback completed successfully.
- `/avatar` default renders avatar and png/jpeg/webp links. `/topic` current empty-topic channel returns expected validation.
- `/dstatus` returns upstream status and incident details. `/8ball` returns question and answer.
- `/deviceinfo` autocomplete for iPhone failed to load; raw `iPhone` returns no-device validation. Exact positive fixture pending.
- `/package a` correctly rejects short query.
- `/jailbreak palera1n`: autocomplete and result with version, compatibility, image and three links PASS.
- User confirmed all target messages in preceding day disposable. `/ban` case #25 removed target; `/unban` case #26 succeeded. Admin sent post-ban recovery invite through DM; target clicked Join and returned to bot-cmds with enabled composer. Ban recovery PASS.

### External lookups and filters — 21:23–21:28
- `/repo a`: handled unregistered-repository response.
- `/firmware` autocomplete iOS16.0 (20A362): valid metadata, 27 devices, unsigned, link.
- `/betafirmware` iOS16.0 beta8 (20A5358a): valid metadata, 23 devices, unknown signing status.
- `/bypass qa20261106nonexistent`: handled no-app/no-bypass response.
- `/canijailbreak` iPhone X + iOS16.0.3: successful 4-result carousel. Pagination click inconclusive because composer autocomplete was open; do not count navigation as passed.
- `/raid add qa20261106raidphrase`: success; `/raid remove`: success.
- `/filter add` notify=False, bypass=Moderators, phrase=qa20261106filterphrase: success; target matching message disappeared.
- `/silent_filter` toggled fixture; target matching message persisted visibly. `/piracy` and `/falsepositive` acknowledged flags. `/filter list` readback showed expected phrase, bypass, silent status. `/filter remove` acknowledged deletion.
- `/batchraid` two QA phrases: modal incorrectly titled `New sub news post`; preview correctly listed 2 phrases. No confirmation branch returned Cancelled. No additions intended; raid-list verification in progress.

### Content and settings — 21:29–21:38
- `/memes add`, `/meme`, `/memes edit`, `/memelist`, `/memes delete`: text-only lifecycle PASS. Edited text persisted and fixture deleted.
- `/jumbo 😀`: image attachment returned. `/solved` in text channel: expected rejection.
- Missing `/rule`, `/issue`, `/commonissue edit`, `/tags edit`: handled not-found responses.
- `/memegen aitext`: clean disabled response.
- `/rawembed` valid reports channel + nonnumeric message ID + False: expected Invalid message ID.
- `/say`: exact QA message posted. `/poll`: reactions seeded; target clicked upvote, count increased from 1 to 2.
- `/postembed`: form submitted; rendered title, body and bold markdown verified.
- `/command_ban` target ping: deny confirmed; toggled off; target ping succeeded (416ms/134ms).
- `/rundown` target shows zero points and correct recent kick/ban/unban cases.
- `/freezexp`: target frozen, QA message sent, XP remained58; restored unfrozen.
- `/birthdayexclude` and `/removebirthday` bot-target guard reject; they emit duplicate error responses (send_error then raise).
- `/offlineping`: on/off acknowledged, original False restored.
- `/spammode`: enabled; explicitly False restored after interruption. `/verify`: verified/unverified target, False restored.
- Narrow DB baseline read saved `/private/tmp/gir-qa-state-baseline.json` (two test users and test guild settings only). Both birthdays empty, exclusionFalse; verificationFalse; guild channel/whitelist lists empty, spamFalse, sabbathFalse.
- `/whitelist`: invalid ID rejected; test guild added; `/blacklist` removed it.
- `/ignorechannel` + `/unignorechannel`, `/ignorechannellogs` + `/unignorechannellogs`: acknowledged changes and restoration for bot-cmds. Behavior beyond acknowledgements pending.
- `/lock` blocks target composer; `/unlock` restores it. `/freeze` empty list rejects; `/freezeable` added only bot-cmds; `/freeze` blocked target; `/unfreeze` restored access; `/unfreezeable` cleanup submitted.

### Birthday, giveaway, and context commands — 21:38–21:42
- `/setbirthday` target November6: success; `/userinfo` verified @bday role. `/removebirthday` success; `/roleinfo` bday showed zero members. Scheduler log confirms birthday job removed.
- Target `/mybirthday`: expected Member+/booster eligibility denial.
- FAIL `/giveaway end not-an-id` (5008ece18c9e) and `/giveaway reroll not-an-id` (0389bfd24653): unhandled ValueError at int(message_id), source lines114/79.
- `/giveaway start`: no-value pretend prize, admin sponsor,30s,1winner,bot-cmds. Target entered via 🎉; normal expiry selected target and posted congratulations. No real prize/transaction.
- `/removepoints`1 at zero: correctly rejects negative total. `/transferprofile` self-source: rejected.
- Target `/clem` denied; admin `/sabbath` denied (owner permissions unavailable).
- `/nameban` preview matched exactly1 disposable target; No cancelled.
- `/staffban`: initiator/target Yes clicks did not ban; request timed out and displayed Timed out. Accepted approval branches require another moderator fixture.
- Message context `Userinfo` and `View avatar`: correctly resolve message author habibitest; roles None confirms birthday-role cleanup.
- Message context `Support tag`: handled empty list.
- Message context `Warn 50 points`: reason buttons, Other custom modal, QA reason -> case27 +50. `/removepoints`50 cleanup -> case28. Generated report independently showed zero points afterward.
- Message context `Generate report`: chose No moderator ping; report in configured reports channel had target ID920662313399357460, exact selected QA message and link. Post ID returned correct target ID. Dismiss removed controlled report; target was not timed out.

### Continued coverage — 21:43–21:54
- Member context Userinfo, View avatar, Support tag invoked with expected target/empty-list results; member Warn50 cancelled; member Generate report submitted No-ping (report cleanup pending).
- `/snipe` returned our disposable filter-deleted phrase.
- `/device add` target iPhoneX/iOS16.7.16 changed nickname to `habibi test [A11, 16.7.16]`; `/device remove` restored `habibi test`.
- `/deviceinfo iPhone X`: complete device details and link PASS.
- FAIL `/subnews` b4be9e89ea5d: AttributeError cfg.channels.subnews; configured field is sub_news.
- FAIL avatar view timeout: utils/views/misc.py:15 PFPView default embed is class discord.Embed, causing to_dict missing self. This was the avatar view, not a context selector.
- `/commonissue new` text+one Reference button, `/issue` readback, `/commonissue edit`: PASS. Deleted own source fixture through UI; `/commonissue reindex` cleaned cache/index. Source channel verified only original `joe` remains. Cosmetic off-by-one count: reindex says2 when one issue exists (count starts1).
- `!tag` and `!t`: both return correct disposable tag and increment use count1/2. Fixture deleted through `/tags delete`.
- `/roblox`: target removed (target Friends UI). Recovery DM sent. Rejoin now requires CAPTCHA; direct invite retry confirms valid server invite, then CAPTCHA recurs. User asked to complete challenge. Target presently OUTSIDE server; recovery unresolved, no further removal tests until restored.
- Attachment access enabled by user. Disposable PNG `/private/tmp/gir-qa-image.png` uploaded successfully.
- FAIL `/memegen regular` ASCII text + PNG: handled `An error occurred generating that meme.` Runtime cause pending.
- `/memegen motivate` Unicode café + PNG: expected non-ASCII validation (`Bottom text can't have weird characters.`). ASCII positive still pending.

### Scope change and final PR smoke pass
User narrowed scope to PR smoke testing. Summary/mapping: `pr-smoke-2026-11-06.md`.
Target returned (user joined another tab); independently verified membership, no roles and enabled composer. ASCII motivational generation also failed. Isolated purge3 left one of3 seeded messages. Own forum solved returned archiving response; final archive state not independently inspected before cleanup. QA text/forum channels deleted.
Timezone pagination verified next2/29, last29/29 with correct boundary disabling, previous28/29, first1/29 and Stop disabling all buttons. Invalid timezone and malformed timeout rejected; unmute of clear target rejected.
GridFS PNG meme create/read/delete PASS. Pending90s reminder survived controlled bot restart, DM delivered once at22:11, scheduler callback completed. Bot now session70927, postrestart ping432ms/154ms. Final DB restoration confirmed zero points, no timeout, no birthday/timeout jobs, XP unfrozen, no QA tags/memes, restored guild settings. Member-context report retained as QA evidence after restart; other controlled report dismissed earlier. Full smoke limitations are in summary report.
