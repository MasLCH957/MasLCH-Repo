#!/usr/bin/env python3
"""Build the MasLCH-Repo APT repository (standard dists/ + pool/ layout).

Layout produced under --out (the GitHub Pages root):

    dists/stable/Release
    dists/stable/InRelease
    dists/stable/Release.gpg
    dists/stable/main/binary-<arch>/Packages[.gz]
    pool/main/<initial>/<package>/<package>_<version>_<arch>.deb
    key.gpg  key.asc

Clients add:

    deb [signed-by=...] https://<user>.github.io/MasLCH-Repo/ stable main

Usage:

    python tools/build-repo.py --debs dist/*.deb --out docs --key <private.asc>

Omit --key to build an unsigned repository.
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


def package_path(control, filename):
    pkg = field(control, "Package")
    return f"pool/main/{pkg[0].lower()}/{pkg}/{filename}"


def build(out, debs, key_path):
    dists = os.path.join(out, "dists", REPO_SUITE)
    shutil.rmtree(dists, ignore_errors=True)
    os.makedirs(dists, exist_ok=True)

    by_arch = {}
    for deb in debs:
        control = parse_ar_control(deb)
        arch = field(control, "Architecture")
        fname = os.path.basename(deb)
        rel = package_path(control, fname)

        dest = os.path.join(out, rel)
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        shutil.copy2(deb, dest)

        size = os.path.getsize(deb)
        data = open(deb, "rb").read()
        stanza = "\n".join([
            control,
            f"Filename: {rel}",
            f"Size: {size}",
            f"MD5sum: {digest_bytes(data, 'md5')}",
            f"SHA1: {digest_bytes(data, 'sha1')}",
            f"SHA256: {digest_bytes(data, 'sha256')}",
        ]) + "\n"
        by_arch.setdefault(arch, []).append((field(control, "Package"), stanza))
        print(f"  {field(control, 'Package'):<28} {field(control, 'Version'):<12} {arch}  -> {rel}")

    checksum_entries = []
    for arch, stanzas in sorted(by_arch.items()):
        stanzas.sort(key=lambda s: s[0])
        body = "\n".join(s for _, s in stanzas).encode()
        d = os.path.join(dists, "main", f"binary-{arch}")
        os.makedirs(d, exist_ok=True)
        open(os.path.join(d, "Packages"), "wb").write(body)
        gz = gzip.compress(body, 9, mtime=0)
        open(os.path.join(d, "Packages.gz"), "wb").write(gz)
        for name, data in (("Packages", body), ("Packages.gz", gz)):
            checksum_entries.append((f"main/binary-{arch}/{name}", data))
        print(f"  index {arch}: {len(stanzas)} package(s), {len(body)} bytes")

    now = format_datetime(datetime.now(timezone.utc), usegmt=True)
    lines = [
        f"Origin: {REPO_ORIGIN}",
        f"Label: {REPO_LABEL}",
        f"Suite: {REPO_SUITE}",
        f"Codename: {REPO_CODENAME}",
        "Version: 1.0",
        f"Architectures: {' '.join(sorted(by_arch))}",
        f"Components: {REPO_COMPONENTS}",
        f"Description: {REPO_DESC}",
        f"Date: {now}",
    ]
    for algo, label in (("md5", "MD5Sum"), ("sha1", "SHA1"), ("sha256", "SHA256")):
        lines.append(f"{label}:")
        for rel, data in checksum_entries:
            lines.append(f" {digest_bytes(data, algo)} {len(data):>16} {rel}")
    release = "\n".join(lines) + "\n"
    open(os.path.join(dists, "Release"), "w", newline="\n").write(release)
    print(f"  Release: {len(release)} bytes")

    if not key_path:
        print("  built UNSIGNED (clients need [trusted=yes])")
        return

    if PGPKey is None:
        raise SystemExit("pgpy required for signing: pip install pgpy")
    key, _ = PGPKey.from_file(key_path)

    msg = PGPMessage.new(release, cleartext=True)
    msg |= key.sign(msg)
    open(os.path.join(dists, "InRelease"), "w", newline="\n").write(str(msg))

    raw = PGPMessage.new(release.encode(), file=True)
    open(os.path.join(dists, "Release.gpg"), "wb").write(bytes(key.sign(raw)))

    open(os.path.join(out, "key.gpg"), "wb").write(bytes(key.pubkey))
    open(os.path.join(out, "key.asc"), "w", newline="\n").write(str(key.pubkey))
    print(f"  signed with {key.fingerprint}")


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
