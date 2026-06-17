from __future__ import annotations

from yggdrasil_sdk.ops_runtime.compose import _docker_compose_command, _port_from_values, _product_env_path, _read_env_file


def make_workspace(tmp_path):
    (tmp_path / "services").mkdir()
    (tmp_path / "modules").mkdir()
    infra = tmp_path / "infra"
    infra.mkdir()
    (infra / "docker-compose.product.yml").write_text("services: {}\n", encoding="utf-8")
    return infra


def test_product_compose_uses_local_product_env_when_present(tmp_path):
    infra = make_workspace(tmp_path)
    (infra / "product.env.template").write_text("YGGDRASIL_WEB_PORT=3000\n", encoding="utf-8")
    (infra / "product.env").write_text("YGGDRASIL_WEB_PORT=3300\n", encoding="utf-8")

    assert _product_env_path(tmp_path) == infra / "product.env"
    assert _read_env_file(_product_env_path(tmp_path))["YGGDRASIL_WEB_PORT"] == "3300"

    command = _docker_compose_command(tmp_path, product=True)

    assert str(infra / "product.env") in command
    assert str(infra / "product.env.template") not in command


def test_product_compose_falls_back_to_template_env(tmp_path):
    infra = make_workspace(tmp_path)
    (infra / "product.env.template").write_text("YGGDRASIL_WEB_PORT=3000\n", encoding="utf-8")

    assert _product_env_path(tmp_path) == infra / "product.env.template"

    command = _docker_compose_command(tmp_path, product=True)

    assert str(infra / "product.env.template") in command


def test_product_compose_port_values_allow_environment_override(monkeypatch):
    monkeypatch.setenv("YGGDRASIL_WEB_PORT", "3300")

    assert _port_from_values({"YGGDRASIL_WEB_PORT": "3000"}, "YGGDRASIL_WEB_PORT", 3000) == 3300
