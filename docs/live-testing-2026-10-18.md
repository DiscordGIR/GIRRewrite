# Live command testing — 18 October 2026

Server: GIRCord 2.0 (`1203746555786432572`). Bot application: GIRR Test (`777282444931104769`), displayed as Botty McBotface Test.

Admin: `habibitest` (`920662313399357460`); target: `habibitest2` (`705338290110332938`), verified with no roles. Test channel: `bot-cmds` (`1536450411911975013`).

Registered current branch definitions: 94 guild slash commands plus 10 context commands; zero globals, no duplicate name/type pairs. User restarted the local bot around 02:34 CEST during testing. Uptime subsequently verified at 39 seconds. Earlier results are provisional until repeated; post-restart checks are labeled below.

Local config has placeholder role/channel IDs (`123`), including public logs and birthday role. Runtime config may differ; record actual outcomes.

| Command | Result | Evidence |
| --- | --- | --- |
| /device add | Not run |  |
| /device remove | Not run |  |
| /ping | PASS after restart | 522 ms message, 140 ms API latency. |
| /roleinfo | Not run |  |
| /stats | PASS after restart | Uptime39 seconds; Python3.9.6;57MB. |
| /serverinfo | PASS | 12 users, 22 channels, 17 roles, 0 bans. |
| /raidstats | PASS | All raid categories and total returned 0. |
| /casestats mod | PASS after restart | Returns 6 cases and includes QA kick, manual unmute, edited warning. |
| /casestats keyword | FAIL after restart | GIR QA search reports 0; moderator statistics show matching case reasons. Repository compares lowercased keyword with unchanged reason. |
| /help | PARTIAL | Acknowledged with mailbox emoji; DM delivery still to verify. |
| /usage | PASS | Returned mute parameters and optional reason. |
| /tag | Not run |  |
| /taglist | PASS (empty) | Expected no-tags error. |
| /tags add | BLOCKED by config | Both valid and invalid-name attempts failed generic checks (b52eb9b13170 /6344a58da3f2). genius_or_submod_and_up returns None when configured sub_mod role123 is absent, before admin level check. |
| /tags edit | Not run |  |
| /tags delete | Not run |  |
| /userinfo | PASS | Target profile returned; roles None. |
| /xp | PASS | Target profile/leaderboard rank returned: level 0, XP 0, rank 5618/5618. |
| /warnpoints | PASS after restart | Target verified0 after cleanup. |
| /xptop | FAIL after restart | Error 2232964612df; before restart 66a7fe543b61. |
| /cases | PARTIAL after restart | Cases12 kick,13mute and lifted8 persisted; mute timestamps remain two hours early. Target0points. |
| /setpfp | Not run |  |
| /sabbath | Not run |  |
| /package | PASS (initial result) | Filza search returned result card, package details and selector; selector not exercised. |
| /repo | PARTIAL | Raw BigBoss query returned not registered; successful autocomplete selection still untested. |
| /commonissue new | Not run |  |
| /commonissue edit | Not run |  |
| /commonissue reindex | Not run |  |
| /postembed | Not run |  |
| /rawembed | Not run |  |
| /issue | Not run |  |
| /subnews | Not run |  |
| /solved | Not run |  |
| /giveaway start | Not run |  |
| /giveaway reroll | Not run |  |
| /giveaway end | Not run |  |
| /jailbreak | Not run |  |
| /firmware | Not run |  |
| /betafirmware | Not run |  |
| /deviceinfo | PASS | Selected iPhone13 via iPhone14,5 autocomplete; returned details and AppleDB link. |
| /canijailbreak | Not run |  |
| /bypass | Not run |  |
| /meme | Not run |  |
| /memelist | PASS (empty) | Expected no-memes error. |
| /memes add | Not run |  |
| /memes edit | Not run |  |
| /memes delete | Not run |  |
| /8ball | PASS | Returned Outlook good for QA question. |
| /neuralnet | Not run |  |
| /memegen regular | Not run |  |
| /memegen motivate | Not run |  |
| /memegen aitext | Not run |  |
| /snipe | Not run |  |
| /remindme | PASS after restart | 20-second reminder delivered to target DM. Automatic-unmute DM also delivered as case14. |
| /jumbo | PASS | Unicode grinning emoji rendered image attachment. |
| /mybirthday | Not run |  |
| /avatar | PASS | Target default avatar with format links returned. |
| /rule | Not run |  |
| /topic | PASS (empty) | Correctly reports bot-cmds has no topic. |
| /poll | Not run |  |
| /dstatus | PASS | Discord status and last incident returned. |
| /timezone set | Not run |  |
| /timezone remove | Not run |  |
| /timezone view | Not run |  |
| /timezone list | PASS | Timezone menu rendered, page 1/29; pagination not yet exercised. |
| /raid add | PASS | Unique QA phrase added. |
| /raid list | PASS | Verified empty, populated and cleaned states. |
| /raid remove | PASS | QA phrase removed; list verified empty. |
| /batchraid | Not run |  |
| /spammode | Not run |  |
| /verify | Not run |  |
| /lock | Not run |  |
| /unlock | Not run |  |
| /freezeable | Not run |  |
| /unfreezeable | Not run |  |
| /freeze | Not run |  |
| /unfreeze | Not run |  |
| /nameban | Not run |  |
| /offlineping | Not run |  |
| /filter add | Not run |  |
| /filter list | PASS (empty) | Expected empty-list validation. |
| /filter remove | Not run |  |
| /silent_filter | Not run |  |
| /piracy | Not run |  |
| /whitelist | Not run |  |
| /blacklist | Not run |  |
| /ignorechannel | Not run |  |
| /unignorechannel | Not run |  |
| /ignorechannellogs | Not run |  |
| /unignorechannellogs | Not run |  |
| /falsepositive | Not run |  |
| /warn | PASS after restart | Case15 applied10 points; removepoints case16 restored0. |
| /kick | PASS after restart | Target removed and rejoined via test-server invite. Moderator statistics persist kick reason. Initial attempt interrupted by restart. |
| /roblox | Not run |  |
| /mute | PASS after restart | 20-second timeout applied; target UI countdown observed. Earlier 30sec automatic expiry and 5min/manual unmute also passed. |
| /unmute | PASS | Case 10; target composer restored and viewmuted empty. |
| /ban | Not run |  |
| /staffban | Not run |  |
| /unban | Not run |  |
| /purge | Not run |  |
| /liftwarn | PASS | Case 8 lifted; warnpoints verified back to 0; target received DM. |
| /editreason | FAIL after restart | Error 32fd69910ced; saved updated reason visible in moderator statistics. Before restart 199c75cd7f57 also saved and DMed before failure. |
| /removepoints | PASS after restart | Removed10 QA points; target warnpoints independently returned0. |
| /rundown | Not run |  |
| /transferprofile | Not run |  |
| /clem | Not run |  |
| /freezexp | PASS after restart | Frozen then unfrozen; database confirms false. |
| /birthdayexclude | FAIL (partial write) | Application did not respond. Database exclusion became true; placeholder birthday role causes early return. QA exclusion cleared directly for target; birthday empty. |
| /removebirthday | Not run |  |
| /setbirthday | Not run |  |
| /command_ban | PASS after restart | Ping ban enforced for target; toggled off and target ping succeeded. |
| /say | Not run |  |
| /viewmuted | PASS | Admin sees timeout/empty states; role-free user correctly denied, repeated after restart. |

## Outstanding work and cleanup

This is an incomplete live pass, not release sign-off. Not-run rows remain unverified. Context commands, attachment workflows, most external lookups and remaining moderation commands still need testing.

Ban/unban testing awaits the user's answer about the current ban implementation deleting recent target messages. Staffban also needs a second authorized staff account. Fix test-server placeholder configuration before testing features that require those channels/roles.

Target rejoined the test server with no roles. Warning points are0; XP was unfrozen; birthday exclusion applied by QA was cleared; ping command restriction was toggled off. The disposable raid phrase was removed. Moderation case records remain as test evidence. No other server was used.

Confirmed post-restart defects: leaderboard crashes; reason edit saves then errors; keyword search misses mixed-case matching reasons; mute case timestamps are two hours early; missing birthday role leaves a database mutation without an interaction response. Missing sub_mod role blocks tag creation even for an administrator.
