#!/usr/bin/env python3
"""Build the MasLCH-Repo APT repository.

Two layouts are emitted from the same pool, so that both Sileo (which assumes
a flat repository when you paste a bare URL) and standard apt clients work:

  flat (repo root, what Sileo expects)

      Release, InRelease, Release.gpg
      Packages, Packages.gz            all architectures in one index
      pool/main/<initial>/<package>/<deb>

  dists (standard Debian layout)

      dists/stable/Release, InRelease, Release.gpg
      dists/stable/main/binary-<arch>/Packages[.gz]

Clients may use either:

    deb [signed-by=...] https://<user>.github.io/MasLCH-Repo/ ./
    deb [signed-by=...] https://<user>.github.io/MasLCH-Repo/ stable main

Usage:

    python tools/build-repo.py --debs dist/*.deb --out docs --key <private.asc>
"""

import argparse
import glob
import gzip
import hashlib
import io
import os
import shutil
import sys
import tarfile
from datetime import datetime, timezone
from email.utils import format_datetime

try:
    from pgpy import PGPKey, PGPMessage
except ImportError:
    PGPKey = None

REPO_ORIGIN = "MasLCH957"
REPO_LABEL = "MasLCH Repo"
REPO_SUITE = "stable"
REPO_CODENAME = "ios"
REPO_COMPONENTS = "main"
REPO_DESC = "MasLCH957's personal jailbreak packages"


def digest_bytes(data, algo):
    return hashlib.new(algo, data).hexdigest()


def parse_ar_control(deb):
    """Extract the control stanza from a .deb without dpkg-deb."""
    with open(deb, "rb") as fh:
        if fh.read(8) != b"!<arch>\n":
            raise SystemExit(f"{deb}: not a deb (bad ar magic)")
        while True:
            hdr = fh.read(60)
            if len(hdr) < 60:
                break
            name = hdr[0:16].decode("ascii", "replace").strip().rstrip("/")
            size = int(hdr[48:58].decode("ascii").strip())
            data = fh.read(size)
            if size % 2:
                fh.read(1)
            if name.startswith("control.tar"):
                with tarfile.open(fileobj=io.BytesIO(data)) as tf:
                    for member in tf.getmembers():
                        if member.name.lstrip("./") == "control":
                            return tf.extractfile(member).read().decode().strip()
    raise SystemExit(f"{deb}: control member not found")


def field(control, name):
    for line in control.splitlines():
        if line.startswith(name + ":"):
            return line.split(":", 1)[1].strip()
    return ""


def write_packages(directory, stanzas):
    """Write Packages / Packages.gz into directory; return their bytes."""
    os.makedirs(directory, exist_ok=True)
    body = "\n".join(stanzas).encode()
    gz = gzip.compress(body, 9, mtime=0)
    open(os.path.join(directory, "Packages"), "wb").write(body)
    open(os.path.join(directory, "Packages.gz"), "wb").write(gz)
    return body, gz


def write_release(directory, entries, archs, key):
    """Write Release + signature into directory.

    entries: list of (path_relative_to_directory, bytes)
    """
    now = format_datetime(datetime.now(timezone.utc), usegmt=True)
    lines = [
        f"Origin: {REPO_ORIGIN}",
        f"Label: {REPO_LABEL}",
        f"Suite: {REPO_SUITE}",
        f"Codename: {REPO_CODENAME}",
        "Version: 1.0",
        f"Architectures: {' '.join(sorted(archs))}",
        f"Components: {REPO_COMPONENTS}",
        f"Description: {REPO_DESC}",
        f"Date: {now}",
    ]
    for algo, label in (("md5", "MD5Sum"), ("sha1", "SHA1"), ("sha256", "SHA256")):
        lines.append(f"{label}:")
        for rel, data in entries:
            lines.append(f" {digest_bytes(data, algo)} {len(data):>16} {rel}")
    release = "\n".join(lines) + "\n"

    open(os.path.join(directory, "Release"), "w", newline="\n").write(release)

    if not key:
        return len(release)

    msg = PGPMessage.new(release, cleartext=True)
    msg |= key.sign(msg)
    open(os.path.join(directory, "InRelease"), "w", newline="\n").write(str(msg))

    raw = PGPMessage.new(release.encode(), file=True)
    open(os.path.join(directory, "Release.gpg"), "wb").write(bytes(key.sign(raw)))
    return len(release)


def build(out, debs, key_path):
    dists = os.path.join(out, "dists", REPO_SUITE)
    for stale in ("dists", "pool"):
        shutil.rmtree(os.path.join(out, stale), ignore_errors=True)
    for stale in ("Packages", "Packages.gz", "Release", "InRelease", "Release.gpg"):
        p = os.path.join(out, stale)
        if os.path.exists(p):
            os.remove(p)

    all_stanzas = []
    by_arch = {}
    for deb in debs:
        control = parse_ar_control(deb)
        arch = field(control, "Architecture")
        pkg = field(control, "Package")
        rel = f"pool/main/{pkg[0].lower()}/{pkg}/{os.path.basename(deb)}"

        dest = os.path.join(out, rel)
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        shutil.copy2(deb, dest)

        data = open(deb, "rb").read()
        stanza = "\n".join([
            control,
            f"Filename: {rel}",
            f"Size: {len(data)}",
            f"MD5sum: {digest_bytes(data, 'md5')}",
            f"SHA1: {digest_bytes(data, 'sha1')}",
            f"SHA256: {digest_bytes(data, 'sha256')}",
        ]) + "\n"
        all_stanzas.append((pkg, stanza))
        by_arch.setdefault(arch, []).append((pkg, stanza))
        print(f"  {pkg:<28} {field(control, 'Version'):<12} {arch}  -> {rel}")

    key = None
    if key_path:
        if PGPKey is None:
            raise SystemExit("pgpy required for signing: pip install pgpy")
        key, _ = PGPKey.from_file(key_path)

    # ---- flat layout at the repo root (Sileo pastes a bare URL) ----
    all_stanzas.sort(key=lambda s: s[0])
    flat_body, flat_gz = write_packages(out, [s for _, s in all_stanzas])
    size = write_release(
        out,
        [("Packages", flat_body), ("Packages.gz", flat_gz)],
        by_arch.keys(),
        key,
    )
    print(f"  flat  : {len(all_stanzas)} package(s), Release {size} bytes")

    # ---- dists layout ----
    entries = []
    for arch, stanzas in sorted(by_arch.items()):
        stanzas.sort(key=lambda s: s[0])
        body, gz = write_packages(
            os.path.join(dists, "main", f"binary-{arch}"), [s for _, s in stanzas]
        )
        entries.append((f"main/binary-{arch}/Packages", body))
        entries.append((f"main/binary-{arch}/Packages.gz", gz))
        print(f"  dists : binary-{arch}, {len(stanzas)} package(s)")
    write_release(dists, entries, by_arch.keys(), key)

    if key:
        open(os.path.join(out, "key.gpg"), "wb").write(bytes(key.pubkey))
        open(os.path.join(out, "key.asc"), "w", newline="\n").write(str(key.pubkey))
        print(f"  signed with {key.fingerprint}")
    else:
        print("  built UNSIGNED (clients need [trusted=yes])")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--debs", nargs="+", required=True, help="deb files or globs")
    ap.add_argument("--out", required=True, help="output dir (GitHub Pages root)")
    ap.add_argument("--key", help="private key .asc; omit to build unsigned")
    args = ap.parse_args()

    debs = []
    for pattern in args.debs:
        hits = sorted(glob.glob(pattern))
        if not hits:
            sys.exit(f"no match: {pattern}")
        debs.extend(hits)

    os.makedirs(args.out, exist_ok=True)
    print(f"building repo with {len(debs)} package(s) -> {args.out}")
    build(args.out, debs, args.key)


if __name__ == "__main__":
    main()
