"""Seed a Debian/Linux operations corpus into the local SQLite DB.

This aligns with the example in tests/Linux(deb)WorkingExample.md, but scales it.

Creates (default):
  - 50 Tasks
  - 12 Workflows

Status mix (default):
  - Tasks: 30 draft, 20 submitted
  - Workflows: 7 draft, 5 submitted

Run:
  cd lcs_mvp
  source .venv/bin/activate
  python3 seed/seed_debian_corpus.py

To reseed:
  python3 seed/seed_debian_corpus.py --force

Notes:
- This is demo data; it is structurally correct (atomic steps + completion checks),
  but it is not environment-specific and must be SME-reviewed before confirmation.
"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
import uuid
from datetime import datetime, timezone


SEED_NOTE = "seed_debian_corpus_v1"
ACTOR = "seed"


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def j(v) -> str:
    return json.dumps(v, ensure_ascii=False)


def step(text: str, completion: str) -> dict[str, str]:
    return {"text": text, "completion": completion}


def task(
    title: str,
    outcome: str,
    procedure_name: str,
    steps: list[dict[str, str]],
    deps: list[str],
    facts: list[str] | None = None,
    concepts: list[str] | None = None,
    tags: list[str] | None = None,
    meta: dict[str, str] | None = None,
    irreversible: int = 0,
) -> dict:
    return {
        "title": title,
        "outcome": outcome,
        "facts": facts or [],
        "concepts": concepts or [],
        "procedure_name": procedure_name,
        "steps": steps,
        "deps": deps,
        "tags": tags or ["linux", "debian"],
        "meta": meta or {"domain": "Linux", "owner_team": "IT Operations", "risk_level": "medium"},
        "irreversible": irreversible,
    }


def build_tasks() -> list[dict]:
    """Build a Debian/Linux admin task corpus.

    Focus: repeatable sysadmin work with explicit completion checks.
    Avoid troubleshooting; keep tasks atomic.
    """

    tasks: list[dict] = []

    # --- Storage / fstab / mounts (expand the example) ---
    tasks += [
        task(
            "Identify a block device and filesystem type",
            "Target block device is identified and its filesystem type is recorded.",
            "Identify block device",
            [
                step("List block devices using an approved command (e.g. lsblk).", "Target device path is identified and recorded."),
                step("Retrieve filesystem type and UUID using blkid.", "UUID and filesystem type are recorded for the target device."),
            ],
            deps=["Sudo access."],
            facts=["UUIDs are stable identifiers for filesystems.", "Filesystem type is required for fstab entries."],
            concepts=["Stable device identification reduces boot-time mount failures."],
            tags=["linux", "debian", "storage"],
        ),
        task(
            "Create a mount point directory",
            "Mount point directory exists with expected path.",
            "Create mount point",
            [
                step("Create the mount point directory with mkdir -p.", "Directory exists at the mount point path."),
                step("Set ownership/permissions for the mount point.", "Permissions and ownership match the defined requirement."),
            ],
            deps=["Sudo access.", "Mount point path defined."],
            facts=["Mount points must exist before mounting."],
            concepts=["Mount point is where a filesystem is attached to the directory tree."],
            tags=["linux", "debian", "storage"],
        ),
        task(
            "Back up /etc/fstab",
            "A backup copy of /etc/fstab exists for rollback.",
            "Backup fstab",
            [
                step("Copy /etc/fstab to a timestamped backup file.", "Backup file exists and is readable."),
                step("Verify the backup is non-empty.", "Backup file size is greater than zero."),
            ],
            deps=["Sudo access."],
            facts=["/etc/fstab controls persistent mounts."],
            concepts=["Backup reduces risk before configuration changes."],
            tags=["linux", "debian", "storage", "change-management"],
        ),
        task(
            "Add a persistent filesystem mount entry",
            "A filesystem is configured to mount at boot via /etc/fstab.",
            "Add fstab entry",
            [
                step("Open /etc/fstab in a text editor with elevated permissions.", "/etc/fstab is opened for editing."),
                step("Insert a new fstab line using UUID, mount point, filesystem type, and options.", "A new line exists and matches the required fields."),
                step("Save the file.", "/etc/fstab contains the new entry after save."),
            ],
            deps=["Device UUID and filesystem type known.", "Mount point exists.", "Sudo access."],
            facts=["fstab lines require source, mount point, fs type, options, dump, fsck order."],
            concepts=["Persistent config should be validated before reboot."],
            tags=["linux", "debian", "storage"],
            irreversible=0,
        ),
        task(
            "Validate fstab configuration",
            "fstab entries are validated without reboot.",
            "Validate fstab",
            [
                step("Run mount -a to apply unmounted fstab entries.", "Command exits with status 0."),
                step("Confirm the mount is present with findmnt.", "findmnt shows the target mount point with expected source."),
            ],
            deps=["fstab entry exists.", "Sudo access."],
            facts=["mount -a mounts all unmounted fstab entries."],
            concepts=["Validation prevents boot failures due to incorrect fstab."],
            tags=["linux", "debian", "storage"],
        ),
        task(
            "Mount a filesystem immediately",
            "Filesystem is mounted in the current session.",
            "Mount filesystem now",
            [
                step("Run mount with the device and mount point.", "findmnt shows the mount point is mounted."),
                step("Confirm visible capacity using df -h for the mount point.", "df output includes the mount point and shows size/used."),
            ],
            deps=["Device exists.", "Mount point exists.", "Sudo access."],
            facts=["Mount attaches filesystem to a directory."],
            concepts=["Session mount does not imply persistence across reboot."],
            tags=["linux", "debian", "storage"],
        ),
        task(
            "Create an ext4 filesystem on a block device",
            "Block device contains a new ext4 filesystem.",
            "Format device as ext4",
            [
                step("Verify the target device is correct and not mounted.", "findmnt does not show the target device mounted."),
                step("Create an ext4 filesystem using mkfs.ext4.", "mkfs completes successfully and outputs filesystem creation summary."),
                step("Verify filesystem UUID using blkid.", "blkid shows TYPE=\"ext4\" and a UUID."),
            ],
            deps=["Target block device exists.", "Sudo access."],
            facts=["Formatting destroys existing data on the target device."],
            concepts=["Filesystems must exist before mounting."],
            tags=["linux", "debian", "storage"],
            irreversible=1,
        ),
    ]

    # --- APT / package management ---
    tasks += [
        task(
            "Update APT package metadata",
            "Local APT package index reflects current repository state.",
            "apt update",
            [
                step("Run apt update with sudo.", "Command completes successfully without repository errors."),
                step("Review output for failed repository lines.", "Any errors are recorded or output is clean."),
            ],
            deps=["Network access.", "Sudo access."],
            facts=["APT uses local metadata to resolve packages."],
            concepts=["Update before install/upgrade for predictable dependency resolution."],
            tags=["linux", "debian", "apt"],
        ),
        task(
            "Upgrade installed packages",
            "Installed packages are upgraded to latest available versions.",
            "apt upgrade",
            [
                step("Run apt upgrade and review the proposed changes.", "Upgrade completes successfully."),
                step("Confirm there are no packages left in a broken state.", "apt reports no broken packages."),
            ],
            deps=["APT metadata is current.", "Sudo access.", "Sufficient disk space."],
            facts=["Upgrades can change system behavior."],
            concepts=["Controlled upgrades reduce security exposure but carry change risk."],
            tags=["linux", "debian", "apt", "change-management"],
        ),
        task(
            "Install a package with APT",
            "A specified package is installed and usable.",
            "apt install",
            [
                step("Install the package using apt install <package>.", "APT reports the package was installed."),
                step("Confirm the package is installed using dpkg -l.", "dpkg -l shows the package in installed state."),
                step("Confirm the primary binary is available on PATH.", "Running the binary returns exit code 0 or version output."),
            ],
            deps=["APT metadata is current.", "Sudo access."],
            facts=["APT installs dependencies automatically."],
            concepts=["Package manager provides reproducible installs."],
            tags=["linux", "debian", "apt"],
        ),
        task(
            "Add a third-party APT repository with signed-by keyring",
            "A new APT repository is configured with a dedicated keyring and can be queried.",
            "Add APT repo",
            [
                step("Create /etc/apt/keyrings if it does not exist.", "Directory exists at /etc/apt/keyrings."),
                step("Store the repository signing key in /etc/apt/keyrings as a .gpg file.", "Keyring file exists and is readable."),
                step("Create a new .list file in /etc/apt/sources.list.d.", "List file exists with expected name."),
                step("Add the repository line including signed-by= to the list file.", "List file contains a repo line with signed-by pointing to the keyring."),
                step("Run apt update.", "APT update completes successfully and includes the new repo."),
            ],
            deps=["Repo URL known.", "Signing key available.", "Network access.", "Sudo access."],
            facts=["Per-repo keyrings reduce trust sprawl."],
            concepts=["Repo trust is a supply-chain boundary."],
            tags=["linux", "debian", "apt", "security"],
        ),
        task(
            "Verify a package version",
            "Installed package version is recorded and meets requirement.",
            "Verify package version",
            [
                step("Retrieve installed version using dpkg-query.", "A version string is recorded."),
                step("Retrieve runtime version using the program's --version output.", "Runtime version output is recorded."),
                step("Compare recorded version against requirement.", "Comparison result is recorded as pass/fail."),
            ],
            deps=["Package installed."],
            facts=["Runtime and package versions can differ for wrappers."],
            concepts=["Verification ensures the environment matches expectation."],
            tags=["linux", "debian", "apt", "assurance"],
        ),
    ]

    # --- Users, groups, permissions ---
    tasks += [
        task(
            "Create a system user account",
            "A user account exists with expected UID/GID and home directory.",
            "Create user",
            [
                step("Create the user with useradd (or adduser) using the approved parameters.", "id <user> returns the new user and group."),
                step("Set or lock the password according to policy.", "passwd status indicates set/locked as required."),
                step("Verify the home directory exists.", "Home directory exists and is owned by the user."),
            ],
            deps=["Sudo access."],
            facts=["User accounts should be least-privilege."],
            concepts=["Separate identities improve traceability."],
            tags=["linux", "debian", "identity"],
        ),
        task(
            "Add a user to a group",
            "User is a member of the specified group.",
            "Modify group membership",
            [
                step("Add the user to the group using usermod -aG.", "id <user> output includes the group."),
                step("Start a new session for the user to apply group membership.", "A new session shows the updated groups."),
            ],
            deps=["User and group exist.", "Sudo access."],
            facts=["Group membership may require re-login to take effect."],
            concepts=["Groups are the main mechanism for shared permissions."],
            tags=["linux", "debian", "identity"],
        ),
        task(
            "Set directory ownership and permissions",
            "Directory ownership and permissions match the defined requirement.",
            "Apply chmod/chown",
            [
                step("Set ownership with chown.", "ls -ld shows expected owner and group."),
                step("Set permissions with chmod.", "ls -ld shows expected permission bits."),
            ],
            deps=["Target path exists.", "Sudo access (if required)."],
            facts=["Permissions control read/write/execute for user/group/other."],
            concepts=["File permissions enforce least privilege."],
            tags=["linux", "debian", "permissions", "security"],
        ),
    ]

    # --- systemd services ---
    tasks += [
        task(
            "Create a systemd service unit",
            "A systemd unit file exists and is syntactically valid.",
            "Create systemd unit",
            [
                step("Create a .service file in /etc/systemd/system.", "Unit file exists at the expected path."),
                step("Reload systemd manager configuration.", "systemctl daemon-reload completes successfully."),
                step("Check unit status for parse errors.", "systemctl status shows the unit loaded without errors."),
            ],
            deps=["Sudo access.", "Service parameters defined."],
            facts=["systemd reads unit files from /etc/systemd/system."],
            concepts=["Services are managed declaratively via unit files."],
            tags=["linux", "debian", "systemd"],
        ),
        task(
            "Enable a systemd service at boot",
            "A systemd service is enabled to start at boot.",
            "Enable systemd service",
            [
                step("Enable the unit using systemctl enable.", "systemctl is-enabled reports enabled."),
                step("Verify the enablement creates expected symlinks.", "systemctl status shows enabled preset state."),
            ],
            deps=["Unit file exists.", "Sudo access."],
            facts=["Enabled services start automatically based on targets."],
            concepts=["Enablement is separate from starting a service now."],
            tags=["linux", "debian", "systemd"],
        ),
        task(
            "Start and verify a systemd service",
            "A systemd service is running and reports healthy status.",
            "Start systemd service",
            [
                step("Start the unit using systemctl start.", "systemctl status shows Active: active (running)."),
                step("Check recent logs for startup errors.", "journalctl shows no error-level messages for the unit since start."),
            ],
            deps=["Unit exists.", "Sudo access."],
            facts=["systemctl status reports runtime state."],
            concepts=["Logs validate service behavior beyond 'running'."],
            tags=["linux", "debian", "systemd", "assurance"],
        ),
    ]

    # --- Networking / SSH ---
    tasks += [
        task(
            "Install OpenSSH server",
            "OpenSSH server package is installed.",
            "Install sshd",
            [
                step("Install openssh-server using apt.", "dpkg -l shows openssh-server installed."),
                step("Confirm sshd unit exists.", "systemctl status ssh shows unit loaded."),
            ],
            deps=["APT metadata is current.", "Sudo access."],
            tags=["linux", "debian", "ssh", "security"],
        ),
        task(
            "Configure SSH to disable password authentication",
            "sshd is configured to disallow password authentication.",
            "Harden SSH auth",
            [
                step("Back up /etc/ssh/sshd_config.", "Backup file exists."),
                step("Set PasswordAuthentication to no.", "sshd_config contains PasswordAuthentication no."),
                step("Validate sshd configuration syntax.", "sshd -t exits with status 0."),
                step("Reload or restart ssh service.", "systemctl status ssh shows active."),
            ],
            deps=["OpenSSH server installed.", "Key-based access confirmed for at least one admin.", "Sudo access."],
            facts=["Disabling password auth reduces brute-force risk."],
            concepts=["Safe changes require verifying alternate access path."],
            tags=["linux", "debian", "ssh", "security"],
            irreversible=0,
        ),
        task(
            "Allow SSH through the firewall (UFW)",
            "Firewall permits inbound SSH and firewall status is active.",
            "Configure UFW for SSH",
            [
                step("Install ufw using apt.", "dpkg -l shows ufw installed."),
                step("Allow the OpenSSH profile.", "ufw status shows OpenSSH ALLOW."),
                step("Enable ufw.", "ufw status reports Status: active."),
            ],
            deps=["Sudo access."],
            facts=["Firewall rules can lock you out if misconfigured."],
            concepts=["Apply allow rule before enabling firewall."],
            tags=["linux", "debian", "network", "security"],
        ),
    ]

    # --- Logs / audit ---
    tasks += [
        task(
            "Query system logs for a service",
            "Relevant systemd journal entries for a service are retrieved and recorded.",
            "Query journalctl",
            [
                step("Query logs for the unit using journalctl -u <unit>.", "Log output is produced for the requested time range."),
                step("Filter for error-level entries.", "Error-level entries are identified or none are present."),
                step("Record the findings in the ticket or run log.", "A record exists with timestamp and summary."),
            ],
            deps=["Systemd unit name known."],
            facts=["journalctl provides centralized service logs."],
            concepts=["Operational evidence should be recorded outside the terminal."],
            tags=["linux", "debian", "assurance"],
        ),
    ]

    # --- More Debian tasks (templated, but still concrete and command-driven) ---

    # Common Debian utilities (install + verify)
    pkg_pairs = [
        ("curl", "curl"),
        ("git", "git"),
        ("jq", "jq"),
        ("unzip", "unzip"),
        ("htop", "htop"),
        ("ca-certificates", "update-ca-certificates"),
        ("gnupg", "gpg"),
        ("dnsutils", "dig"),
        ("lsof", "lsof"),
        ("net-tools", "ifconfig"),
        ("rsyslog", "rsyslogd"),
        ("logrotate", "logrotate"),
        ("cron", "cron"),
        ("ufw", "ufw"),
        ("fail2ban", "fail2ban-client"),
    ]

    for pkg, binname in pkg_pairs:
        tasks.append(
            task(
                f"Install and verify package: {pkg}",
                f"Package '{pkg}' is installed and the '{binname}' command is available.",
                f"Install {pkg}",
                [
                    step(f"Install {pkg} using apt install {pkg}.", "APT reports installation completed successfully."),
                    step(f"Confirm {pkg} is installed using dpkg -l {pkg}.", "dpkg -l shows the package in installed state."),
                    step(f"Confirm the binary is callable: run {binname} --version.", "Command returns version output or exits with status 0."),
                ],
                deps=["APT metadata is current.", "Sudo access."],
                facts=["APT installs dependencies automatically."],
                concepts=["Installing via APT creates traceable, reproducible state."],
                tags=["linux", "debian", "apt"],
            )
        )

    # systemd actions for common services
    svc_units = ["ssh", "cron", "rsyslog", "ufw", "fail2ban"]
    for unit in svc_units:
        tasks.append(
            task(
                f"Enable and start systemd unit: {unit}",
                f"The {unit} unit is enabled and running.",
                f"Enable+start {unit}",
                [
                    step(f"Enable {unit} using systemctl enable {unit}.", "systemctl is-enabled reports enabled."),
                    step(f"Start {unit} using systemctl start {unit}.", "systemctl status shows Active: active (running)."),
                    step(f"Check recent logs for {unit}.", "journalctl output contains no error-level messages since start."),
                ],
                deps=["Unit is installed.", "Sudo access."],
                facts=["Enablement and runtime state are separate concerns."],
                concepts=["Service management must be auditable and repeatable."],
                tags=["linux", "debian", "systemd"],
            )
        )

    # misc operational tasks
    tasks += [
        task(
            "Create an SSH authorized_keys file for a user",
            "User can authenticate using a configured SSH public key.",
            "Configure authorized_keys",
            [
                step("Create the ~/.ssh directory with correct permissions.", "~/.ssh exists with mode 700."),
                step("Add the public key to ~/.ssh/authorized_keys.", "authorized_keys contains the public key line."),
                step("Set permissions on authorized_keys.", "authorized_keys has mode 600 and is owned by the user."),
            ],
            deps=["User account exists.", "SSH public key available."],
            facts=["SSH key auth relies on strict file permissions."],
            concepts=["Key-based auth is stronger than passwords when managed properly."],
            tags=["linux", "debian", "ssh", "security"],
        ),
        task(
            "Test SSH login using key authentication",
            "SSH key authentication is validated for the target user.",
            "Validate SSH key auth",
            [
                step("Initiate an SSH connection using the configured key.", "SSH session is established without password prompt."),
                step("Record the successful authentication evidence.", "A record exists noting user, host, and timestamp."),
            ],
            deps=["SSH server installed.", "Key-based auth configured for the user.", "Network reachability to SSH port."],
            facts=["Password auth may be disabled in hardened configurations."],
            concepts=["Validate access paths before locking down authentication methods."],
            tags=["linux", "debian", "ssh", "assurance"],
        ),
        task(
            "Set the system hostname",
            "System hostname is set and persists across reboot.",
            "Set hostname",
            [
                step("Set the hostname using hostnamectl.", "hostnamectl status shows the expected Static hostname."),
                step("Confirm /etc/hostname matches the configured hostname.", "/etc/hostname contains the expected hostname."),
            ],
            deps=["Sudo access."],
            facts=["Hostname affects prompts, logs, and some service discovery."],
            concepts=["Persistent hostname is managed by system tools and config files."],
            tags=["linux", "debian", "network"],
        ),
        task(
            "Configure system timezone",
            "System timezone is configured and reported correctly.",
            "Set timezone",
            [
                step("Set the timezone using timedatectl set-timezone.", "timedatectl shows the expected Time zone."),
                step("Confirm local time displays in the configured timezone.", "date output matches expected timezone offset."),
            ],
            deps=["Sudo access."],
            facts=["Timezone impacts log timestamps and scheduled jobs."],
            concepts=["Correct time settings support auditing and incident response."],
            tags=["linux", "debian", "assurance"],
        ),
        task(
            "Enable system time synchronization",
            "Time synchronization is enabled and clock reports synchronized.",
            "Enable time sync",
            [
                step("Enable NTP synchronization using timedatectl set-ntp true.", "timedatectl shows NTP service active."),
                step("Confirm system clock is synchronized.", "timedatectl shows System clock synchronized: yes."),
            ],
            deps=["Network access.", "Sudo access."],
            facts=["Accurate time is required for reliable auditing."],
            concepts=["Time sync reduces drift that breaks security assumptions."],
            tags=["linux", "debian", "assurance"],
        ),
        task(
            "Enable unattended security updates",
            "Unattended upgrades are enabled and configured to apply security updates.",
            "Configure unattended-upgrades",
            [
                step("Install unattended-upgrades using apt.", "dpkg -l shows unattended-upgrades installed."),
                step("Enable unattended upgrades via configuration.", "unattended-upgrades is enabled in configuration."),
                step("Verify unattended-upgrades timer exists.", "systemctl list-timers shows unattended-upgrades timer."),
            ],
            deps=["APT metadata is current.", "Sudo access."],
            facts=["Automatic updates change system state."],
            concepts=["Security patch latency is a measurable risk."],
            tags=["linux", "debian", "apt", "security"],
        ),
        task(
            "Clean APT package cache",
            "APT cache is cleaned to reclaim disk space.",
            "apt clean",
            [
                step("Run apt clean.", "Command exits with status 0."),
                step("Confirm cache directory is cleared.", "/var/cache/apt/archives contains no .deb files or is reduced."),
            ],
            deps=["Sudo access."],
            facts=["APT caches downloaded package files."],
            concepts=["Disk pressure can cause upgrades and installs to fail."],
            tags=["linux", "debian", "apt"],
        ),
        task(
            "Remove unused packages",
            "Unused packages are removed.",
            "apt autoremove",
            [
                step("Run apt autoremove and review the proposed removals.", "Command completes successfully."),
                step("Confirm apt reports no broken packages.", "apt reports no broken packages."),
            ],
            deps=["Sudo access."],
            facts=["Autoremove removes packages installed as dependencies that are no longer needed."],
            concepts=["Removing unused packages reduces attack surface and disk usage."],
            tags=["linux", "debian", "apt"],
        ),
        task(
            "Create a sudoers drop-in for an admin group",
            "A sudoers drop-in grants admin group sudo access and passes validation.",
            "Configure sudoers drop-in",
            [
                step("Create a file in /etc/sudoers.d with the required rule.", "File exists in /etc/sudoers.d with expected contents."),
                step("Validate sudoers syntax using visudo -cf.", "visudo validation exits with status 0."),
            ],
            deps=["Sudo access.", "Admin group name defined."],
            facts=["Invalid sudoers syntax can break sudo."],
            concepts=["Use drop-ins to avoid editing the main sudoers file."],
            tags=["linux", "debian", "security", "identity"],
        ),
        task(
            "Create a swap file",
            "A swap file exists and is activated.",
            "Create swapfile",
            [
                step("Allocate a swap file of the required size.", "Swap file exists at the expected path and size."),
                step("Set swap file permissions to 600.", "ls -l shows mode 600 on the swap file."),
                step("Initialize the swap area using mkswap.", "mkswap completes successfully."),
                step("Enable swap using swapon.", "swapon --show lists the new swap file."),
            ],
            deps=["Sudo access.", "Sufficient disk space."],
            facts=["Swap files extend virtual memory."],
            concepts=["Swap reduces OOM risk but may impact performance."],
            tags=["linux", "debian", "storage"],
            irreversible=0,
        ),
    ]

    # Keep corpus size stable for demos
    return tasks[:50]


def build_workflows(task_ids: list[tuple[str, int, dict]]) -> list[dict]:
    def pick_tag(tag: str, n: int) -> list[tuple[str, int]]:
        out: list[tuple[str, int]] = []
        for rid, ver, t in task_ids:
            if tag in t.get("tags", []):
                out.append((rid, ver))
        return out[:n]

    storage = pick_tag("storage", 6)
    apt = pick_tag("apt", 6)
    systemd = pick_tag("systemd", 5)
    ssh = pick_tag("ssh", 4)
    assurance = pick_tag("assurance", 6)

    workflows = [
        {
            "title": "Prepare Debian host for software deployment",
            "objective": "Host package state is current and required software is installed and verified.",
            "refs": [apt[0], apt[1], apt[2], apt[4]],
            "tags": ["linux", "debian", "apt"],
            "meta": {"domain": "Linux", "owner_team": "IT Operations", "risk_level": "medium"},
        },
        {
            "title": "Configure persistent storage for an application",
            "objective": "Storage is formatted (if needed), mounted, and configured to persist across reboot.",
            "refs": [storage[0], storage[1], storage[2], storage[3], storage[4], storage[5]],
            "tags": ["linux", "debian", "storage"],
            "meta": {"domain": "Linux", "owner_team": "IT Operations", "risk_level": "high"},
        },
        {
            "title": "Deploy and enable a systemd-managed service",
            "objective": "A service is defined, enabled at boot, and running with validated logs.",
            "refs": [systemd[0], systemd[1], systemd[2]],
            "tags": ["linux", "debian", "systemd"],
            "meta": {"domain": "Linux", "owner_team": "Platform", "risk_level": "medium"},
        },
        {
            "title": "Harden SSH access",
            "objective": "SSH is installed and configured with key-based access and firewall allowance.",
            "refs": [ssh[0], ssh[2], ssh[1]],
            "tags": ["linux", "debian", "ssh", "security"],
            "meta": {"domain": "Linux", "owner_team": "Security Operations", "risk_level": "high"},
        },
        {
            "title": "Linux evidence pack (service + system assurance)",
            "objective": "A set of Debian system assurance checks is executed and evidence is recorded.",
            "refs": assurance[:5],
            "tags": ["linux", "debian", "assurance"],
            "meta": {"domain": "Linux", "owner_team": "IT Operations", "risk_level": "medium"},
        },
    ]

    # pad to 12 workflows with generic assurance bundles
    all_refs = [(rid, ver) for rid, ver, _ in task_ids]
    cursor = 0
    idx = 1
    while len(workflows) < 12:
        refs = all_refs[cursor:cursor + 4]
        if len(refs) < 2:
            cursor = 0
            continue
        workflows.append(
            {
                "title": f"Debian operations workflow #{idx}",
                "objective": "A set of Debian operational tasks is executed in sequence.",
                "refs": refs,
                "tags": ["linux", "debian"],
                "meta": {"domain": "Linux", "owner_team": "IT Operations", "risk_level": "medium"},
            }
        )
        idx += 1
        cursor += 4

    return workflows


def main() -> None:
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    if base_dir not in sys.path:
        sys.path.insert(0, base_dir)

    from app.main import DB_PATH, init_db

    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true", help="Allow reseeding even if seed marker exists")
    parser.add_argument(
        "--reset-db",
        action="store_true",
        help="Delete ALL existing records (tasks/workflows/refs/audit) before seeding the Debian corpus",
    )
    args = parser.parse_args()

    init_db()

    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.row_factory = sqlite3.Row

    if args.reset_db:
        # Wipe ALL records so the DB contains only this corpus.
        # Order matters due to FK constraints.
        conn.execute("DELETE FROM workflow_task_refs")
        conn.execute("DELETE FROM workflows")
        conn.execute("DELETE FROM tasks")
        conn.execute("DELETE FROM audit_log")
        conn.commit()

    existing = conn.execute(
        "SELECT 1 FROM tasks WHERE change_note=? LIMIT 1",
        (SEED_NOTE,),
    ).fetchone()
    if existing and not args.force and not args.reset_db:
        raise SystemExit(f"Refusing to seed: marker '{SEED_NOTE}' already present. Run with --force or --reset-db.")

    now = utc_now_iso()

    tasks = build_tasks()
    # 50 tasks: 30 draft, 20 submitted
    for idx, t in enumerate(tasks):
        t["status"] = "draft" if idx < 30 else "submitted"

    inserted: list[tuple[str, int, dict]] = []

    for t in tasks:
        rid = str(uuid.uuid4())
        ver = 1
        conn.execute(
            """
            INSERT INTO tasks(
              record_id, version, status,
              title, outcome, facts_json, concepts_json, procedure_name, steps_json, dependencies_json,
              irreversible_flag, task_assets_json,
              tags_json, meta_json,
              created_at, updated_at, created_by, updated_by,
              reviewed_at, reviewed_by, change_note,
              needs_review_flag, needs_review_note
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                rid,
                ver,
                t["status"],
                t["title"],
                t["outcome"],
                j(t.get("facts", [])),
                j(t.get("concepts", [])),
                t["procedure_name"],
                j(t.get("steps", [])),
                j(t.get("deps", [])),
                int(t.get("irreversible", 0)),
                j([]),
                j(t.get("tags", [])),
                j(t.get("meta", {})),
                now,
                now,
                ACTOR,
                ACTOR,
                None,
                None,
                SEED_NOTE,
                1,
                "Seeded Debian corpus (structure demo); requires SME review",
            ),
        )
        inserted.append((rid, ver, t))

    workflows = build_workflows(inserted)
    for idx, wf in enumerate(workflows):
        wf["status"] = "draft" if idx < 7 else "submitted"

    for wf in workflows:
        wid = str(uuid.uuid4())
        wv = 1
        conn.execute(
            """
            INSERT INTO workflows(
              record_id, version, status,
              title, objective,
              tags_json, meta_json,
              created_at, updated_at, created_by, updated_by,
              reviewed_at, reviewed_by, change_note,
              needs_review_flag, needs_review_note
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                wid,
                wv,
                wf["status"],
                wf["title"],
                wf["objective"],
                j(wf.get("tags", [])),
                j(wf.get("meta", {})),
                now,
                now,
                ACTOR,
                ACTOR,
                None,
                None,
                SEED_NOTE,
                1,
                "Seeded Debian corpus (structure demo); requires SME review",
            ),
        )
        for order_index, (trid, tver) in enumerate(wf["refs"], start=1):
            conn.execute(
                """
                INSERT INTO workflow_task_refs(workflow_record_id, workflow_version, order_index, task_record_id, task_version)
                VALUES (?,?,?,?,?)
                """,
                (wid, wv, order_index, trid, int(tver)),
            )

    conn.commit()
    conn.close()

    print(f"Seeded Debian corpus: {len(tasks)} tasks and {len(workflows)} workflows into {DB_PATH}")


if __name__ == "__main__":
    main()
