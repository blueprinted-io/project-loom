# Linux Operations Example — Task and Workflow Model

This example demonstrates atomic Tasks and composable Workflows using common Linux administration activities.

---

# Reusable Tasks (Atomic Performance Units)

---

## T1 — Add a Persistent Filesystem Mount
**Outcome**  
A filesystem is configured to mount automatically at boot via `/etc/fstab`.

**Facts**
- `/etc/fstab` defines filesystems to mount automatically.
- Entries require source (UUID/device), mount point, filesystem type, options, dump, fsck order.
- UUIDs are stable identifiers.
- `mount -a` mounts all unmounted fstab entries.

**Concepts**
- Persistence vs session state  
- Stable device identification (UUID)  
- Safe validation before reboot  

**Dependencies**
- Target block device exists and has a filesystem  
- Filesystem type known  
- Mount point path known  
- Sudo access available  

**Procedure (Steps)**
1. Identify the block device.  
2. Retrieve UUID and filesystem type using `blkid`.  
3. Create the mount point directory.  
4. Backup `/etc/fstab`.  
5. Edit `/etc/fstab`.  
6. Add the new mount entry.  
7. Save the file.  
8. Run `mount -a` to validate.  
9. Confirm the filesystem is mounted.  

---

## T2 — Mount a Filesystem Immediately
**Outcome**  
A filesystem is mounted in the current session.

**Facts**
- `mount` attaches a filesystem to the directory tree.  
- Mount point must exist.  

**Concepts**
- Immediate operational state vs persistent configuration  
- Mount point as attachment location  

**Dependencies**
- Block device exists  
- Mount point exists  
- Sudo access available  

**Procedure**
1. Create mount point if needed.  
2. Run `mount` with device and mount point.  
3. Confirm mount with `findmnt`.  
4. Confirm storage visibility with `df -h`.  

---

## T3 — Update Package Repository Metadata
**Outcome**  
Local APT package index reflects latest repository state.

**Facts**
- APT uses local metadata to resolve packages.  
- `apt update` refreshes the index.  

**Concepts**
- Repository metadata as decision base  
- Safe sequencing before installs/upgrades  

**Dependencies**
- APT present  
- Network access  
- Sudo access  

**Procedure**
1. Run `apt update`.  
2. Review output for errors.  
3. Confirm command completes successfully.  

---

## T4 — Upgrade Installed Packages
**Outcome**  
Installed packages are upgraded to latest available versions.

**Facts**
- `apt upgrade` applies newer versions.  
- Upgrades can change system behavior.  

**Concepts**
- System state change risk  
- Dependency on current metadata  

**Dependencies**
- T3 completed  
- Sudo access  
- Sufficient disk space  

**Procedure**
1. Run `apt upgrade`.  
2. Review proposed changes.  
3. Confirm completion.  
4. Confirm no packages are broken.  

---

## T5 — Install a Software Package
**Outcome**  
A specified package is installed and usable.

**Facts**
- APT installs packages by name.  
- Dependencies install automatically.  

**Concepts**
- Package manager as source of truth  
- Reproducible installs  

**Dependencies**
- T3 completed  
- Package exists in repos  
- Sudo access  

**Procedure**
1. Run `apt install <package>`.  
2. Confirm install completes.  
3. Confirm package is listed as installed.  
4. Confirm binary is on PATH.  

---

## T6 — Verify Installed Software Version
**Outcome**  
Installed version of a package is confirmed.

**Facts**
- Tools expose version output.  
- Package manager tracks installed version.  

**Concepts**
- Verification as control  
- Runtime vs package version  

**Dependencies**
- T5 completed  
- Command name known  

**Procedure**
1. Retrieve package manager version info.  
2. Retrieve runtime version.  
3. Record version.  
4. Confirm version meets requirement.  

---

## T7 — Add a Software Repository
**Outcome**  
A new APT repository is registered and usable.

**Facts**
- Repos defined in `/etc/apt/sources.list*`  
- Repos should be signed.  
- Modern APT supports per-repo keyrings.  

**Concepts**
- Trust chain  
- Separation of sources  

**Dependencies**
- Repo URL known  
- Signing key available  
- Sudo access  
- Network access  

**Procedure**
1. Create keyring directory if needed.  
2. Store repository signing key.  
3. Create a new `.list` file.  
4. Add repo entry with `signed-by=`.  
5. Save file.  
6. Run Task T3.  

---

# Workflows (Compositions)

---

## W1 — Prepare System for New Software Deployment
**Objective**  
System is updated and ready for installs.

**Tasks**
- **T3 — Update package repository metadata**  
- **T4 — Upgrade installed packages**

---

## W2 — Install Software from Default Repositories
**Objective**  
Software is installed and verified.

**Tasks**
- **T3 — Update package repository metadata**  
- **T5 — Install a software package**  
- **T6 — Verify installed software version**

---

## W3 — Install Software from Third-Party Repository
**Objective**  
Software from external repo is installed and verified.

**Tasks**
- **T7 — Add a software repository**  
- **T3 — Update package repository metadata**  
- **T5 — Install a software package**  
- **T6 — Verify installed software version**

---

## W4 — Configure Persistent Storage
**Objective**  
Storage mounts and persists across reboots.

**Tasks**
- **T1 — Add a persistent filesystem mount**  
- **T2 — Mount a filesystem immediately**

---

## W5 — Provision Application Environment
**Objective**  
System updated, storage configured, software installed and verified.

**Tasks**
- **T3 — Update package repository metadata**  
- **T4 — Upgrade installed packages**  
- **T1 — Add a persistent filesystem mount**  
- **T2 — Mount a filesystem immediately**  
- **T5 — Install a software package**  
- **T6 — Verify installed software version**

> Workflows reuse Tasks directly. No workflow nesting.
