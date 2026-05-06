import sys
from pathlib import Path

from chess_variant import ai


def test_ai_data_path_supports_pyinstaller_meipass(tmp_path, monkeypatch) -> None:
    bundled_package_dir = tmp_path / "chess_variant"
    bundled_package_dir.mkdir()
    bundled_data = bundled_package_dir / "ai_data.json"
    bundled_data.write_text('{"material": {}}', encoding="utf-8")

    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path), raising=False)

    assert ai.ai_data_path() == bundled_data


def test_computer_label_replaced_in_ui_source() -> None:
    source = (Path(__file__).parents[1] / "chess_variant" / "ui.py").read_text(encoding="utf-8")

    assert "COMPUTER" in source
    assert "COMPU" + "TOR" not in source
