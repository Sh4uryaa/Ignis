"""Archive extraction and inspection tests using synthetic fixtures only."""
import zipfile
from pathlib import Path

import pandas as pd
import pytest

import processing.extract_archives as ex
from config.settings import SOURCE_COLUMNS, SourceArchive
from processing.inspect_data import compare_with_expected, inspect_dataframe
from processing.read_source import SchemaError, read_raw_strings

HEADER = ",".join(SOURCE_COLUMNS)
MODIS_ROWS = [
    "31.29,75.84,308,3,1.7,2000-11-01,0637,Terra,MODIS,48,6.03,294.9,19.9,D,0",
    "30.54,74.36,314.9,2.5,1.5,2002-07-18,0638,Aqua,MODIS,10,6.03,300.5,23.4,D,2",
    "30.54,74.36,314.9,2.5,1.5,2026-08-27,0638,Aqua,MODIS,85,61.03,300.5,23.4,N,0",
]


def _make_zip(tmp_path: Path, archive_csv: str, nrt_csv: str) -> Path:
    z = tmp_path / "test.zip"
    with zipfile.ZipFile(z, "w") as zf:
        zf.writestr(archive_csv, HEADER + "\n" + "\n".join(MODIS_ROWS) + "\n")
        zf.writestr(nrt_csv, HEADER + "\nNRT,SHOULD,NOT,BE,USED\n")
        zf.writestr("Readme.txt", "readme")
    return z


@pytest.fixture
def archive(tmp_path, monkeypatch):
    _make_zip(tmp_path, "fire_archive_TEST.csv", "fire_nrt_TEST.csv")
    monkeypatch.setattr(ex, "EXTRACTED_DIR", tmp_path / "extracted")
    a = SourceArchive(key="MODIS", zip_name="test.zip", archive_csv="fire_archive_TEST.csv",
                      ignored_csvs=("fire_nrt_TEST.csv",), collection="test")
    monkeypatch.setattr(SourceArchive, "zip_path", property(lambda self: tmp_path / self.zip_name))
    return a


def test_classify_members_ignores_nrt(archive):
    groups = ex.classify_members(archive, ex.list_archive_members(archive))
    assert groups["archive"] == ["fire_archive_TEST.csv"]
    assert groups["ignored_nrt"] == ["fire_nrt_TEST.csv"]
    assert groups["other"] == ["Readme.txt"]


def test_extract_only_historical_csv(archive, tmp_path):
    out = ex.extract_historical_csv(archive, dest_dir=tmp_path / "extracted")
    assert out.name == "fire_archive_TEST.csv"
    assert not (tmp_path / "extracted" / "fire_nrt_TEST.csv").exists()
    df = read_raw_strings(out)
    assert list(df.columns) == list(SOURCE_COLUMNS)
    assert len(df) == 3


def test_missing_archive_message(tmp_path, monkeypatch):
    a = SourceArchive(key="VIIRS", zip_name="nope.zip", archive_csv="x.csv",
                      ignored_csvs=(), collection="test")
    monkeypatch.setattr(SourceArchive, "zip_path", property(lambda self: tmp_path / self.zip_name))
    with pytest.raises(ex.ArchiveError, match="Expected filename : nope.zip"):
        ex.list_archive_members(a)


def test_schema_error_on_missing_columns(tmp_path):
    p = tmp_path / "bad.csv"
    p.write_text("latitude,longitude\n1,2\n")
    with pytest.raises(SchemaError):
        read_raw_strings(p)


def test_inspect_dataframe_statistics(tmp_path):
    p = tmp_path / "m.csv"
    p.write_text(HEADER + "\n" + "\n".join(MODIS_ROWS + [MODIS_ROWS[0]]) + "\n")
    s = inspect_dataframe(read_raw_strings(p), "MODIS")
    assert s["total_rows"] == 4
    assert s["exact_duplicates"] == 1
    assert s["missing_values"] == 0
    assert s["first_date"] == "2000-11-01" and s["last_date"] == "2026-08-27"
    assert s["satellite_counts"] == {"Aqua": 2, "Terra": 2}
    assert s["satellite_coverage"]["Aqua"] == ["2002-07-18", "2026-08-27"]
    assert s["confidence_class_counts"] == {"nominal": 2, "low": 1, "high": 1}
    assert s["nominal_plus_high"] == 3 and s["low_confidence_excluded"] == 1
    assert s["type_counts"] == {"0": 3, "2": 1}
    assert s["version_counts"] == {"6.03": 3, "61.03": 1}
    assert s["unknown_types"] == []


def test_unknown_type_is_reported(tmp_path):
    p = tmp_path / "m.csv"
    p.write_text(HEADER + "\n" + MODIS_ROWS[0][:-1] + "9\n")
    s = inspect_dataframe(read_raw_strings(p), "MODIS")
    assert s["unknown_types"] == ["9"]


def test_compare_with_expected_flags_discrepancy():
    checks = compare_with_expected({"total_rows": 10, "type_counts": {"0": 5}},
                                   {"total_rows": 11, "type_counts": {"0": 5}})
    assert {c["check"]: c["match"] for c in checks} == {"total_rows": False, "type_counts": True}
