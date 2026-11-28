"""Collected-file seeding: checksums enforced, real fetch time preserved, provenance reported."""
import os

import pytest

from hoops import rawcache


def _collect(tmp_path, year=2027):
    src = tmp_path / "src"
    src.mkdir()
    paths = {}
    for i, name in enumerate(rawcache.torvik_files(year)):
        p = src / name
        p.write_bytes(f"body {i}".encode())
        os.utime(p, (1_700_000_000 + i, 1_700_000_000 + i))
        paths[name] = p
    return rawcache.build_manifest(year, paths, "test"), paths


def test_install_preserves_bytes_and_fetch_time(tmp_path):
    manifest, paths = _collect(tmp_path)
    raw = tmp_path / "raw"
    rawcache.install(manifest, lambda n: paths[n].read_bytes(), raw)
    for name, p in paths.items():
        assert (raw / name).read_bytes() == p.read_bytes()
        assert (raw / name).stat().st_mtime == p.stat().st_mtime
    prov = rawcache.provenance(raw, list(paths))
    assert {v["via"] for v in prov.values()} == {"collector"}


def test_install_rejects_checksum_mismatch(tmp_path):
    manifest, paths = _collect(tmp_path)
    with pytest.raises(ValueError):
        rawcache.install(manifest, lambda n: b"tampered", tmp_path / "raw")


def test_newer_local_copy_is_kept_and_reported_direct(tmp_path):
    manifest, paths = _collect(tmp_path)
    raw = tmp_path / "raw"
    raw.mkdir()
    name = next(iter(paths))
    (raw / name).write_bytes(b"fresher direct download")
    rawcache.install(manifest, lambda n: paths[n].read_bytes(), raw)
    assert (raw / name).read_bytes() == b"fresher direct download"
    assert rawcache.provenance(raw, [name])[name]["via"] == "direct"
