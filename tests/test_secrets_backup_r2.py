import json
import os
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path


class FakeR2Client:
    def __init__(self, existing: dict[str, bytes] | None = None, *, fail_put: bool = False) -> None:
        self.objects = dict(existing or {})
        self.fail_put = fail_put
        self.put_calls: list[str] = []
        self.delete_calls: list[str] = []

    def put_object(self, *, bucket: str, key: str, file_path: Path) -> dict[str, str]:
        self.put_calls.append(key)
        if self.fail_put:
            raise RuntimeError("put failed")
        self.objects[key] = file_path.read_bytes()
        return {"etag": "fake-etag", "bucket": bucket, "key": key}

    def list_objects(self, *, bucket: str, prefix: str) -> list[dict[str, object]]:
        return [
            {"key": key, "size": len(value)}
            for key, value in sorted(self.objects.items())
            if key.startswith(prefix)
        ]

    def delete_object(self, *, bucket: str, key: str) -> None:
        self.delete_calls.append(key)
        self.objects.pop(key, None)


def fake_encrypt_file(input_path: Path, output_path: Path, password: str) -> None:
    output_path.write_bytes(input_path.read_bytes() + f":{password}".encode("utf-8"))


class SecretsBackupR2Tests(unittest.TestCase):
    def _make_config(self, root: Path):
        from agentplane.scripts.automation.backup_secrets_r2 import BackupConfig

        return BackupConfig(
            source_dir=root / "secrets" / "hosts" / "wsl",
            state_file=root / "state" / "state.json",
            tmp_dir=root / "tmp",
            bucket="AgentPlane_Backups",
            endpoint="https://example.r2.cloudflarestorage.com",
            prefix="backups/agentplane/secrets-main",
            access_key_id="access",
            secret_access_key="secret",
            password="qf19940930",
            keep_count=5,
        )

    def test_backup_skips_upload_when_scan_fingerprint_matches_state(self) -> None:
        from agentplane.scripts.automation.backup_secrets_r2 import run_backup

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            secrets_dir = root / "secrets" / "hosts" / "wsl"
            secrets_dir.mkdir(parents=True)
            (secrets_dir / "alpha.txt").write_text("alpha\n", encoding="utf-8")

            config = self._make_config(root)
            client = FakeR2Client()

            first = run_backup(
                config,
                client=client,
                now=datetime(2026, 3, 27, 1, 0, tzinfo=timezone.utc),
                encrypt_file=fake_encrypt_file,
            )
            second = run_backup(
                config,
                client=client,
                now=datetime(2026, 3, 27, 2, 0, tzinfo=timezone.utc),
                encrypt_file=fake_encrypt_file,
            )

            self.assertEqual("ok_uploaded", first["status"])
            self.assertEqual("ok_no_changes", second["status"])
            self.assertEqual(1, len(client.put_calls))
            self.assertEqual(first["content_fingerprint"], second["content_fingerprint"])
            self.assertEqual(first["object_key"], second["last_uploaded_key"])

    def test_backup_updates_scan_state_without_upload_when_only_mtime_changes(self) -> None:
        from agentplane.scripts.automation.backup_secrets_r2 import run_backup

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            secrets_dir = root / "secrets" / "hosts" / "wsl"
            secrets_dir.mkdir(parents=True)
            target = secrets_dir / "alpha.txt"
            target.write_text("alpha\n", encoding="utf-8")

            config = self._make_config(root)
            client = FakeR2Client()

            first = run_backup(
                config,
                client=client,
                now=datetime(2026, 3, 27, 1, 0, tzinfo=timezone.utc),
                encrypt_file=fake_encrypt_file,
            )
            stat = target.stat()
            os.utime(target, ns=(stat.st_atime_ns, stat.st_mtime_ns + 1_000_000_000))

            second = run_backup(
                config,
                client=client,
                now=datetime(2026, 3, 27, 2, 0, tzinfo=timezone.utc),
                encrypt_file=fake_encrypt_file,
            )

            state = json.loads(config.state_file.read_text(encoding="utf-8"))
            self.assertEqual("ok_no_changes", second["status"])
            self.assertEqual(1, len(client.put_calls))
            self.assertNotEqual(first["scan_fingerprint"], second["scan_fingerprint"])
            self.assertEqual(first["content_fingerprint"], second["content_fingerprint"])
            self.assertEqual(second["scan_fingerprint"], state["scan_fingerprint"])
            self.assertEqual(second["content_fingerprint"], state["content_fingerprint"])

    def test_backup_uploads_new_archive_and_prunes_old_remote_objects(self) -> None:
        from agentplane.scripts.automation.backup_secrets_r2 import run_backup

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            secrets_dir = root / "secrets" / "hosts" / "wsl"
            secrets_dir.mkdir(parents=True)
            (secrets_dir / "alpha.txt").write_text("alpha\n", encoding="utf-8")

            existing = {
                "backups/agentplane/secrets-main/agentplane-secrets-20260320T000000Z-old000000001.tar.gz.enc": b"1",
                "backups/agentplane/secrets-main/agentplane-secrets-20260321T000000Z-old000000002.tar.gz.enc": b"2",
                "backups/agentplane/secrets-main/agentplane-secrets-20260322T000000Z-old000000003.tar.gz.enc": b"3",
                "backups/agentplane/secrets-main/agentplane-secrets-20260323T000000Z-old000000004.tar.gz.enc": b"4",
                "backups/agentplane/secrets-main/agentplane-secrets-20260324T000000Z-old000000005.tar.gz.enc": b"5",
            }
            config = self._make_config(root)
            client = FakeR2Client(existing=existing)

            payload = run_backup(
                config,
                client=client,
                now=datetime(2026, 3, 27, 3, 0, tzinfo=timezone.utc),
                encrypt_file=fake_encrypt_file,
            )

            self.assertEqual("ok_uploaded", payload["status"])
            self.assertEqual(1, len(client.put_calls))
            self.assertEqual(1, payload["deleted_old_backups"])
            self.assertEqual(
                [
                    "backups/agentplane/secrets-main/agentplane-secrets-20260320T000000Z-old000000001.tar.gz.enc"
                ],
                client.delete_calls,
            )
            self.assertEqual(5, len(client.objects))

    def test_backup_returns_failed_runtime_and_cleans_tmp_files_when_upload_fails(self) -> None:
        from agentplane.scripts.automation.backup_secrets_r2 import run_backup

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            secrets_dir = root / "secrets" / "hosts" / "wsl"
            secrets_dir.mkdir(parents=True)
            (secrets_dir / "alpha.txt").write_text("alpha\n", encoding="utf-8")

            config = self._make_config(root)
            client = FakeR2Client(fail_put=True)

            payload = run_backup(
                config,
                client=client,
                now=datetime(2026, 3, 27, 4, 0, tzinfo=timezone.utc),
                encrypt_file=fake_encrypt_file,
            )

            self.assertEqual("failed_runtime", payload["status"])
            self.assertEqual([], list(config.tmp_dir.glob("*")))
            self.assertFalse(config.state_file.exists())


if __name__ == "__main__":
    unittest.main()
