# VPS deployment

GitHub Actions builds and checks the production image, publishes it to
`ghcr.io/discordgir/girrewrite`, then asks the VPS to deploy its immutable digest.
Pull requests only build/check images. They do not publish or receive VPS secrets.
Production deployment is disabled until the repository variable
`VPS_DEPLOY_ENABLED` is set to `true`.

The VPS uses a dedicated SSH account with a forced command. That account has no
Docker access and can only request a digest from this fixed image repository.
A root-owned script controls a root-owned Compose file, waits for Discord
readiness, and restores the previous successful image if startup fails.

## 1. Prepare the VPS once

These instructions assume an x86-64 Linux VPS with Docker Engine, Docker Compose
**2.30 or newer**, Bash, sudo, and util-linux (`flock`). The hosted build currently
targets x86-64; do not use it on an ARM VPS without adding an ARM image build.
Run the administrative commands from a trusted checkout of the reviewed commit.
Do not place deployment scripts/configuration in a directory the deploy user can
write. This setup does not provision or migrate MongoDB.

```bash
sudo useradd --create-home --shell /bin/bash gir-deploy
sudo install -d -o root -g root -m 755 /etc/gir
sudo install -d -o root -g root -m 700 /etc/gir/docker /var/lib/gir-deploy
sudo install -o root -g root -m 755 deploy/gir-deploy /usr/local/sbin/gir-deploy
sudo install -o root -g root -m 755 deploy/gir-deploy-ssh /usr/local/bin/gir-deploy-ssh
sudo install -o root -g root -m 644 deploy/compose.yml /etc/gir/compose.yml
sudo install -o root -g root -m 600 /path/to/production/.env /etc/gir/bot.env
sudo install -o root -g 10001 -m 640 /path/to/production/config.json /etc/gir/config.json
```

Compose reads `bot.env` as root and passes it at runtime. Use standard Compose
`.env` syntax; single-quote values containing literal dollar signs to prevent
interpolation. The non-root container
reads the JSON bind mount through group 10001. Production `.env` and `config.json`
are excluded from images. Keep them on the VPS; no bot token belongs in Actions.
The image now uses Python 3.12 and runs as UID/GID 10001.

The secure Compose service retains the existing host networking so a MongoDB
address such as `localhost` keeps working on Linux. Network access is therefore
shared with the host; the container has no host filesystem or Docker socket
access. Keep MongoDB bound to appropriate interfaces and retain its firewall and
authentication. Runtime application files are read-only; `/tmp` is writable.

Create `/etc/sudoers.d/gir-deploy` with `sudo visudo -f /etc/sudoers.d/gir-deploy`:

```sudoers
gir-deploy ALL=(root) NOPASSWD: /usr/local/sbin/gir-deploy *
```

The script validates its single argument before invoking Docker. Do not grant
the user broader sudo rights or membership in the `docker` group.

Generate a dedicated, passphrase-free Ed25519 key on your administrative machine:

```bash
ssh-keygen -t ed25519 -f gir-actions -C gir-actions-deploy
```

Install its public key on the VPS in `/home/gir-deploy/.ssh/authorized_keys` as
**one line** (replace the example key):

```text
restrict,command="/usr/local/bin/gir-deploy-ssh" ssh-ed25519 AAAA... gir-actions-deploy
```

Make that account's home and SSH authorization root-owned so it cannot replace
the forced-command restriction. Do not grant password authentication to it.

```bash
sudo chown -R root:root /home/gir-deploy
sudo chmod 755 /home/gir-deploy
sudo chown -R root:root /home/gir-deploy/.ssh
sudo chmod 755 /home/gir-deploy/.ssh
sudo chmod 644 /home/gir-deploy/.ssh/authorized_keys
```

The public key is not secret. Keep the private key only in your password manager
and GitHub's production environment secret, and rotate it if exposed. The SSH
account needs a working Bash login shell for forced commands. Check your distro's
SSH account-lock/PAM rules and allow public-key login without enabling passwords.
The public SSH endpoint must be reachable by GitHub-hosted runners; do not expose
the Docker daemon API.

If the GHCR package is private, authenticate Docker **on the VPS** once with a
dedicated account's token scoped to `read:packages` and authorized for that package:

```bash
read -rsp 'Read-only GHCR token: ' GHCR_TOKEN; echo
printf '%s' "$GHCR_TOKEN" | sudo docker --config /etc/gir/docker login ghcr.io \
  --username YOUR_GITHUB_LOGIN --password-stdin
unset GHCR_TOKEN
```

Do not use a `write:packages` token on the VPS. A public package needs no registry
credential. Actions publishes with its own short-lived `GITHUB_TOKEN`.

## 2. Configure GitHub

Create a `production` environment in repository Settings → Environments. Restrict
its deployment branches to `main`; optionally require a reviewer for deployment.
Add these **environment secrets**:

| Secret | Value |
| --- | --- |
| `VPS_HOST` | VPS hostname or IP |
| `VPS_USER` | `gir-deploy` |
| `VPS_SSH_KEY` | Entire private `gir-actions` key |
| `VPS_KNOWN_HOSTS` | Verified OpenSSH `known_hosts` line(s) for that hostname/port |

Obtain the VPS host-key fingerprint through its trusted console, for example
`ssh-keygen -lf /etc/ssh/ssh_host_ed25519_key.pub`. Compare it with the key collected
on your administrative machine before storing the known-hosts entry. For a
nonstandard port, the entry must use `[hostname]:port`. The workflow deliberately
does not trust `ssh-keyscan` output obtained during a deployment.

Repository Actions variables:

| Variable | Value |
| --- | --- |
| `VPS_SSH_PORT` | Optional; defaults to `22` |
| `VPS_DEPLOY_ENABLED` | Keep unset until the VPS is ready; set to `true` to enable |

Allow Actions to publish GHCR packages. If a package of this name already exists,
grant this repository Actions write access to it. Protect `main`, review changes
to `.github/workflows/` and `deploy/`, and limit who can change production secrets.

## 3. First deployment and migration

After merging the PR, Actions can build/publish while deployment remains disabled.
Use the digest printed in the workflow summary to bootstrap a manual deployment:

```bash
ssh -i gir-actions gir-deploy@YOUR_VPS 'deploy sha256:THE_64_CHARACTER_DIGEST'
```

Before the **first** secure deployment, stop the existing bot using its original
Compose project (`docker compose stop gir` from that checkout). Do not run two
instances of the same bot token. The new service uses the `gir-production` project
and does not touch the existing database. The first deployment has no recorded
rollback image: if it fails, the script stops the new bot; restart the original
service manually while investigating. Do not remove the original setup until
you have verified the new bot.

Once successful, set `VPS_DEPLOY_ENABLED=true` and run the workflow manually on
`main`, or merge your next change. Each release deploys its specific digest.
Workflow concurrency serializes releases, and a server lock rejects concurrent
manual deployments. There is brief downtime during replacement; this is not a
zero-downtime deployment.

Readiness requires the Discord connection plus completed startup cache loading;
the bot refreshes a heartbeat every five seconds. Docker rejects stale heartbeats.
A failed candidate gets up to 240 seconds, then the saved release gets the same
readiness check. A failed rollback leaves the workflow red and requires an admin.
The heartbeat is not a full functional test of every command or external service.

## Rollback, logs, and maintenance

The root-only files `/var/lib/gir-deploy/current` and `previous` store successful
image references. An administrator can redeploy a previous digest using the same
SSH command or `sudo /usr/local/sbin/gir-deploy 'deploy sha256:...'`. This does not
roll back database changes. Do not prune images referenced by these files or
delete their GHCR manifests while rollback is required.

To inspect logs, as an administrator:

```bash
IMAGE=$(sudo cat /var/lib/gir-deploy/current)
sudo env GIR_IMAGE="$IMAGE" docker --config /etc/gir/docker compose \
  --env-file /dev/null -p gir-production -f /etc/gir/compose.yml logs --tail 100 gir
```

For a failed first deployment, use the candidate image reference from the Actions
summary instead. Logs stay on the VPS rather than being copied automatically to
GitHub, because application logs may contain sensitive information.

If a deployment is interrupted or the server loses power, inspect the actual
container and saved digest before redeploying; rollback cannot be guaranteed
after a hard process/host failure. Monitor the bot after rollout: Docker marks
later health failures but does not automatically roll back or restart an unhealthy
running process. The restart policy handles processes that exit.

Changes to the server scripts and Compose file require a reviewed manual reinstall
as root; the deployment key cannot update those files. Update base images and
dependency pins regularly. To disable automatic deployment, unset
`VPS_DEPLOY_ENABLED`; revoke the authorized key to revoke SSH deployment access.

The legacy `docker-compose.yml` remains usable for local builds. It now injects
`.env` and mounts `config.json` at runtime because both are excluded from the build
context. Ensure the mounted JSON is readable by UID/GID 10001. Run interactive
`setup.py` from a trusted local checkout before installing that config; production
configuration mounts are deliberately read-only.
