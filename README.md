# GIR Rewrite
![GIR banner](data/images/banner.png)

GIR is a sophisticated moderation and miscellaneous utilities Discord bot created for the [r/Jailbreak Discord server](https://reddit.com/r/jailbreak). It features:

- Completely based on Discord's Slash Commands, written in the [Discord.py library](https://github.com/Rapptz/discord.py)
- Standard moderation commands such as warn, mute, kick, ban, ...
- XP and role-based permissions system
- An advanced filter and anti-raid system
- A logging and message mirroring system
- Self-assignable roles
- Miscellaneous utilities like `/canijailbreak`
- And much more!

GIR is custom made for the r/Jailbreak server and therefore there is no publicly running bot you can invite to your own server. However, you can self-host it as is or fork the code and modify it to your own requirements!

> See also: [Bloo](https://github.com/DiscordGIR/Bloo) and [GIR](https://github.com/DiscordGIR/GIR)

---

## Pre-setup instructions
These instructions *should* work on macOS, Windows and Linux.

### Antiraid content checks

The antiraid monitor deletes messages with hidden Discord invite links and applies a seven-day timeout. It strips Unicode format/control characters and normalizes compatibility characters before checking; ordinary invite links continue through the existing invite filter and Discord AutoMod.

For members without the configured Member Plus role, it also deletes and times out messages with four or more image attachments, an image named `1.*`, or a visual match to a stored scam image. Administrators and bots are exempt from these content checks. The image scanner uses both a 256-bit difference hash and a 16×16 RGB comparison; references live in `data/antiraid/scam_images.json` and require no startup downloads. Downloads are limited to 8 MiB and ten seconds, decoded images to 25 megapixels, and animated images are scanned using their first frame. Failed scans alone do not trigger moderation.

Reports use `channels.reports` and `roles.moderator` from `config.json`, ping online moderators (falling back to the moderator role), and include up to four preserved images. A five-minute cooldown per user limits reports while moderation still runs on subsequent messages. Reports show whether deletion and timeout succeeded. **Ban** uses GIR's ban helper, including its case history, notifications, ban cache, and moderation logs. **Dismiss** deletes the report and leaves the timeout in place.

Install the updated requirements or rebuild your deployment before running this version. The pinned `pyvips`/`pyvips-binary` dependencies supply the libvips image engine used by Sharp. The bot needs Manage Messages and Moderate Members for the automatic actions, Ban Members for the review button, and access to send embeds and files in the reports channel. Its role must be above members it moderates. The existing `Intents.all()` setup enables member and presence caching; enable the corresponding privileged intents in the Discord developer portal.

Run the isolated antiraid tests with `python -m unittest discover -s tests -v`; they do not connect to Discord or MongoDB.

### Setting up the `.env` file
1. Copy the `.env.example` to a file called `.env`
2. Start filling in the values as you want it set up. Follow the comments for hints.
3. For the `DB_HOST` variable:
    - If running the bot without Docker (not recommended), you can change `DB_HOST` to `localhost` instead. 
    - If running Mongo without Docker, `host.docker.internal` works on macOS and Windows, on Linux you can use `172.17.0.1`. 
    - If running Mongo in Docker, set `DB_HOST` to `mongo`

> **NOT RECOMMENDED FOR PRODUCTION DUE TO POOR PERFORMANCE**
Optionally, you can use [MongoDB Atlas](https://www.mongodb.com/atlas/database) instead of a local Mongo server, or you can ask SlimShadyIAm on Discord for access to the shared test database. In that case, you use:
`DB_CONNECTION_STRING=mongodb+srv://.....` instead of `DB_HOST` and `DB_PORT`.

## Setting up the bot

### Production setup
This setup uses Docker for deployment. You will need the following:
- Docker
- `docker-compose`
- Mongo installation (optional, but recommended because it makes the setup easier. Advanced uses can also run Mongo in Docker, follow the instructions in `docker-compose.yml`).

> Alternatively, you could set up the bot without Docker using PM2 but I won't provide instructions for that.

#### Steps
1. Set up the `.env`. file. Keep in mind whether or not you want to use Mongo in Docker or not. 
2. Set up the database.
3. Skip this step if running Mongo without Docker. If you want to run Mongo in Docker, you will need to edit `docker-compose.yml` slightly. Open it and follow the comments.
4. Run the bot using `docker-compose up -d --build`.

If everything is successful, the bot should be online in a few seconds. Otherwise, check the container's logs: `docker-compose logs gir`.

> **IMPORTANT**: slash commands are not synced automatically. Instead, the bot owner can DM the bot `!sync` to sync slash commands with Discord. This only needs to be done once when the bot is set up, or when you change any of the command data (such adding a new command, changing a command's name or description, etc.) 

The bot can be updated in the future by running: `git pull && docker-compose up -d --build --force-recreate`

---

### Development setup: with Docker (recommended!)
You will need the following installed:
- Docker
- Visual Studio Code to run the development container
- MongoDB running on the host machine or [MongoDB Atlas](https://www.mongodb.com/atlas/database).

#### Steps
1. Clone the repository and open the folder in Visual Studio Code
2. Install the [Microsoft Remote Development](https://marketplace.visualstudio.com/items?itemName=ms-vscode-remote.vscode-remote-extensionpack) plugin
3. Make sure that Docker is running
4. Open the Command Palette (`CMD+Shift+P` or `CTRL+Shift+P`) and run "Remote-Containers: Reopen In Container"
5. VSCode should build the Docker image and open it automatically; this may take a couple of minutes as it has to install some extensions as well.
6. Set up the `.env` file as shown [here](#env-file).
7. Make sure the database is set up (see below).
8. Open the integrated terminal in VSCode and run the `gir` command to start the bot with hot reload!

> Note that if you make changes to the `Dockerfile`, `.devcontainer.json`, or need to install a new requirement, you need to rebuild the Docker image. You can do this through the Command Palette again, run "Remote-Containers: Rebuild Container".

---

### Development setup: without Docker (not recommended)
You will need the following installed:
- `python3.9+`
- `venv` (Python's virtualenv module)
- MongoDB running on the host machine or [MongoDB Atlas](https://www.mongodb.com/atlas/database).

#### Steps
1. Inside the root folder of the project, run `python3 -m venv venv/`
2. `source venv/bin/activate`
3. `pip3 install -r requirements.txt`
4. Set up the .env file as shown [here](#env-file).
5. Make sure the database is set up (see below).
6. `python3 main.py`

---

### Database setup
If you have an existing dump of the database, make sure Mongo is running, then you can run `mongorestore <dump foldername>`. This can also be done if running Mongo in Docker by first copying the dump to the Mongo container with `docker cp`.

If setting up the database from scratch, follow these instructions:
1. Make sure you filled out the right values for the `.env` file as explained above.
2. Open up `setup.py` and fill in **ALL** the values. The bot's permissions, and as a result the bot itself, will not work without them.
3. Run `setup.py`:
    - If running the bot without Docker, follow the first few setup instructions until you need to set up the database, activate the `virtualenv` and then run `python3 setup.py`. Then you can proceed with the rest of the setup instructions.
    - If running the bot with Docker in production, start the container then run: `docker exec -it <GIR container name> python3 setup.py` (if you get an error about the container restarting, restart the container and try to run the command again immediately). You can find the container name by running `docker container ls` in the project folder. After it's setup, restart the container. **Note:** changes to `setup.py` won't be transferred until you rebuild the container. So build the container AFTER `setup.py` is set up how you want.
    - If running the bot with Docker in development, you can just run `python3 setup.py` in the integrated bash shell.

If you want to inspect or change database values:
- If running MongoDB locally, you can install Robo3T.
- If running MongoDB in Docker, you can use the web GUI at http://127.0.0.1:8081

---

## Contributors

<table>
  <tr>
    <td align="center"><a href="https://aamirfarooq.dev"><img src="https://avatars.githubusercontent.com/u/10660846?v=4" width="100px;" alt=""/><br /><sub><b>SlimShadyIAm</b></sub></a></td>
    <td align="center"><a href="https://stkc.win"><img src="https://stkc.win/assets/pfp.png" width="100px;" alt=""/><br /><sub><b>stkc</b></sub></a></td>
    <td align="center"><a href="https://github.com/Ultra03"><img src="https://avatars.githubusercontent.com/u/20672260?v=4" width="100px;" alt=""/><br /><sub><b>Ultra03</b></sub></a></td>
    <td align="center"><a href="https://github.com/ja1dan"><img src="https://avatars.githubusercontent.com/u/37126748?v=4" width="100px;" alt=""/><br /><sub><b>ja1dan</b></sub></a></td>
    <td align="center"><a href="https://github.com/donato-fiore"><img src="https://avatars.githubusercontent.com/u/50346119?v=4" width="100px;" alt=""/><br /><sub><b>donato-fiore</b></sub></a></td>
  </tr>
  <tr>
    <td align="center"><a href="https://m1sta.xyz/"><img src="https://avatars.githubusercontent.com/u/37033149?v=4" width="100px;" alt=""/><br /><sub><b>m1stadev</b></sub></a></td>
    <td align="center"><a href="https://saadat.dev/"><img src="https://avatars.githubusercontent.com/u/41216857?v=4" width="100px;" alt=""/><br /><sub><b>mass1ve-err0r</b></sub></a></td>
    <td align="center"><a href="https://github.com/sqlstatement"><img src="https://avatars.githubusercontent.com/u/27446425?v=4" width="100px;" alt=""/><br /><sub><b>sqlstatement</b></sub></a></td>
    <td align="center"><a href="https://github.com/beerpiss"><img src="https://avatars.githubusercontent.com/u/92439990?v=4" width="100px;" alt=""/><br /><sub><b>beerpsi</b></sub></a></td>
  </tr>
  </table>

### Special thanks
Special thanks to the following people for ideas, testing, or help:
- [Jack LaFond](https://www.jack.link/) --- creator of [tunes.ninja](https://tunes.ninja/), the bot that the Songs cog is inspired by
- Cameren from r/jb, who has given a lot of ideas and helped with testing on many occasions
- [Lillie](https://github.com/LillieWeeb001/) --- creator of the [fake jailbreak and iCloud bypass list](https://github.com/LillieWeeb001/Anti-Scam-Json-List) used by GIR's filter
- [Emma](https://github.com/emiyl) and the https://ios.cfw.guide team --- their API is used for miscellaneous commands such as `/canijailbreak`, `/deviceinfo`, `/devices add`, `/bypass` and more.
