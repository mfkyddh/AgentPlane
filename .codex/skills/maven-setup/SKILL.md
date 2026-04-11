---
name: maven-setup
description: Install or upgrade Apache Maven in Ubuntu or WSL, ensure a compatible Java runtime exists first, and switch Maven dependency resolution to the Aliyun mirror. Use when Codex is asked to set up Maven, replace an old or missing Maven installation, fix mixed Windows and WSL Maven paths, or configure `~/.m2/settings.xml` for China-friendly package downloads.
---

# Maven Setup

Verify the current official Maven release first, note that Maven does not use an LTS release model, then install the target version in the intended Linux user environment, configure an Aliyun mirror in `~/.m2/settings.xml`, and verify that a fresh interactive shell resolves the Linux Maven binary instead of a Windows-hosted fallback.

## Workflow

1. Check the latest official stable Maven release on `maven.apache.org` because the answer changes over time.
2. State explicitly that Maven does not publish separate LTS releases; use the latest stable release unless the user requests a specific version.
3. Detect `java -version`, `mvn -v`, effective user, and home directory inside the target Ubuntu or WSL environment.
4. Install a supported JDK first if Java is missing. Prefer a current LTS JDK for stability.
5. Install Maven from the official Apache binary distribution when the exact current version matters more than distro package convenience.
6. Expose Maven through the target user's shell profile, typically with `MAVEN_HOME` and a prepended `PATH` entry.
7. Write `~/.m2/settings.xml` with the requested mirror. For Aliyun, use `https://maven.aliyun.com/repository/public`.
8. Verify `java -version`, `which -a mvn`, `mvn -v`, and the mirror settings in a fresh interactive shell.
9. Confirm that `Maven home` points to the Linux installation path, not a Windows path inherited through WSL interop.

## Command Pattern

Prefer running commands as the target Linux user explicitly:

```bash
wsl -d Ubuntu -u <user> bash -lc '...'
```

Install a JDK first when needed:

```bash
sudo apt-get update
sudo apt-get install -y openjdk-21-jdk curl tar
```

Install the verified Maven release from Apache archives or downloads:

```bash
mkdir -p /home/<user>/.local
cd /home/<user>/.local
curl -fsSLO https://archive.apache.org/dist/maven/maven-3/<version>/binaries/apache-maven-<version>-bin.tar.gz
tar -xzf apache-maven-<version>-bin.tar.gz
ln -sfn apache-maven-<version> current-maven
```

Configure the user's shell:

```bash
export MAVEN_HOME=/home/<user>/.local/current-maven
export PATH="$MAVEN_HOME/bin:$PATH"
```

Configure the Aliyun mirror:

```xml
<settings>
  <mirrors>
    <mirror>
      <id>aliyunmaven</id>
      <mirrorOf>*</mirrorOf>
      <name>Aliyun Maven</name>
      <url>https://maven.aliyun.com/repository/public</url>
    </mirror>
  </mirrors>
</settings>
```

Verify in a fresh interactive shell:

```bash
bash -ic 'java -version 2>&1; which -a mvn; mvn -v'
```

## Notes

- Do not describe Maven as LTS without clarification. Maven uses stable releases, not a separate LTS line.
- If WSL inherits Windows `PATH`, `mvn` may resolve to a Windows installation first. Check `which -a mvn` and fix shell ordering so the Linux Maven path comes first.
- When appending shell exports from PowerShell, avoid host-side expansion of `$PATH`; otherwise a Windows path snapshot may be written into `.bashrc`.
- Keep the mirror configuration in `~/.m2/settings.xml` unless the user explicitly wants a project-local `.mvn` setup.
- Report the exact Maven version, JDK version, and mirror URL that were verified.
