import argparse

import pytest
from PIL import Image

from photoscan.cli.main import main, parse_corners_string


def test_parse_corners_string():
    corners_str = "0.1,0.1;0.9,0.1;0.9,0.9;0.1,0.9"
    corners = parse_corners_string(corners_str)
    assert corners.top_left.x == 0.1
    assert corners.bottom_right.y == 0.9

    with pytest.raises(argparse.ArgumentTypeError):
        parse_corners_string("invalid")

def test_cli_help():
    # Calling with --help should return 0 (SystemExit caught internally)
    ret = main(["--help"])
    assert ret == 0

def test_cli_single_file_scan(tmp_path):
    # Create source image
    src_file = tmp_path / "document.png"
    img = Image.new("RGB", (300, 300), color=(128, 128, 128))
    img.save(src_file)

    out_file = tmp_path / "output.png"

    # Run CLI
    ret = main([str(src_file), "--output", str(out_file), "--mode", "color"])

    assert ret == 0
    assert out_file.exists()
    assert out_file.stat().st_size > 0

def test_cli_multipage_pdf_scan(tmp_path):
    src1 = tmp_path / "page1.png"
    src2 = tmp_path / "page2.png"

    Image.new("RGB", (200, 200), color=(120, 120, 120)).save(src1)
    Image.new("RGB", (200, 200), color=(100, 100, 100)).save(src2)

    out_pdf = tmp_path / "scanned_doc.pdf"

    ret = main([str(src1), str(src2), "--output", str(out_pdf), "--dpi", "150"])

    assert ret == 0
    assert out_pdf.exists()
    assert out_pdf.stat().st_size > 0

def test_cli_dry_run_and_json(tmp_path, capsys):
    src_file = tmp_path / "input.png"
    Image.new("RGB", (100, 100), color=(255, 255, 255)).save(src_file)

    out_file = tmp_path / "output.png"

    # Run dry run with --json
    ret = main([str(src_file), "--output", str(out_file), "--dry-run", "--json"])

    assert ret == 0
    assert not out_file.exists()

    # Verify JSON output
    captured = capsys.readouterr()
    import json
    data = json.loads(captured.out)
    assert len(data) == 1
    assert data[0]["status"] == "dry_run"
