from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_distribution_manifest_defines_release_package_contract() -> None:
    manifest = json.loads((ROOT / "packaging/distributions/local-preview.json").read_text(encoding="utf-8"))

    assert manifest["distributionId"] == "local-preview"
    assert manifest["releaseChannel"] == "github-releases-preview"
    assert manifest["updatePolicy"] == "manual-check-manual-apply"
    assert manifest["docker"]["strategy"] == "detect-and-guide"
    assert manifest["signing"]["status"] == "reserved"
    assert manifest["defaultAppId"] == "yggdrasil.app.deep-research"

    for app_path in manifest["includedApplications"]:
        assert (ROOT / app_path / "yggdrasil.app.yaml").exists()

    assert {target["openPath"] for target in manifest["shortcutTargets"]} >= {
        "/applications/yggdrasil.app.deep-research",
        "/applications/yggdrasil.app.graduate-researcher",
    }


def test_desktop_scripts_support_distribution_shortcuts_and_open_path() -> None:
    desktop_script = (ROOT / "packaging/desktop/windows/Yggdrasil.Desktop.ps1").read_text(encoding="utf-8")
    install_script = (ROOT / "packaging/desktop/windows/Yggdrasil.Install.ps1").read_text(encoding="utf-8")
    build_script = (ROOT / "packaging/desktop/windows/Build-Yggdrasil.ReleasePackage.ps1").read_text(encoding="utf-8")

    assert '"start-app"' in desktop_script
    assert "[string]$OpenPath" in desktop_script
    assert "distributionShortcuts" in desktop_script
    assert "[string]$AppPackagePath" in install_script
    assert "[string]$DefaultAppId" in install_script
    assert "release-manifest.json" in build_script
    assert "GitHub Releases" in build_script


def test_product_release_smoke_includes_upgrade_and_explicit_rollback_snapshot() -> None:
    script = (ROOT / "scripts/product-release-smoke.mjs").read_text(encoding="utf-8")

    assert "product-compose-smoke" in script
    assert 'payload.status !== "ok"' in script
    assert "backup before upgrade" in script
    assert "rollbackSnapshot" in script
    assert '"rollback", "--", "--snapshot", rollbackSnapshot' in script
