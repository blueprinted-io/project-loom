# Beginner Guide: Set Up a Linux System for a New Application

This guide walks you through preparing a Linux system so an application can run properly.  
You will:

1. Make sure the system is up to date  
2. Set up storage that survives reboots  
3. Install the software you need  
4. Confirm the correct version is installed  

---

## Before You Start

You should have:

- Access to the Linux machine  
- Permission to run commands with `sudo`  
- An internet connection  
- The name of the software package you want to install  
- A disk or partition you want to use for storage (if needed)

---

## Step 1 — Update the System's Software List

Linux keeps a list of available software versions.  
We refresh it so the system knows what the latest versions are.

Run:

    sudo apt update

Watch for errors. If repositories cannot be reached, fix network issues first.

---

## Step 2 — Upgrade Existing Software

Now bring the system up to date.

    sudo apt upgrade

Review the list of packages being upgraded, then allow the process to finish.

Why this matters: outdated libraries can cause application install or runtime failures.

---

## Step 3 — Set Up Storage That Mounts Automatically

If your application needs extra storage, configure Linux to attach it every time the system starts.

### 3a. Find the disk's unique ID

    sudo blkid

Copy the `UUID` of your target disk.

### 3b. Create a folder where it will appear

    sudo mkdir -p /mnt/data

### 3c. Back up the configuration file

    sudo cp /etc/fstab /etc/fstab.bak

### 3d. Add the disk to the startup list

Edit:

    sudo nano /etc/fstab

Add a line like:

    UUID=your-uuid-here   /mnt/data   ext4   defaults   0   2

Save and exit.

### 3e. Test the configuration

    sudo mount -a

Confirm it worked:

    findmnt /mnt/data

Do not reboot until this works.

---

## Step 4 — Mount the Storage Right Now

If the disk is not already mounted:

    sudo mount /dev/sdb1 /mnt/data

Confirm:

    df -h /mnt/data

---

## Step 5 — Install the Application

Install the software package:

    sudo apt install <package-name>

Wait for the installation to complete.

---

## Step 6 — Confirm the Installed Version

Check the version from the package manager:

    apt-cache policy <package-name>

Check the version from the program itself:

    <binary-name> --version

Make sure the installed version matches what you expected.

---

## You’re Done

Your system is now:

- Up to date  
- Configured with persistent storage  
- Running the required software  
- Verified to be on the correct version  

This system is ready for the application to run reliably.
