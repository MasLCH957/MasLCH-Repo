#!/usr/bin/env python3
"""Build an APT repository (flat layout) for the nodejs-npm .deb.

Produces, in the output directory:

    Packages, Packages.gz      index of the .deb
    Release                    repository metadata + checksums
    InRelease                  Release, clearsigned
    Release.gpg                Release, detached signature
    key.gpg / key.asc          public signing key
    *.deb                      the package itself

Usage:
    python tools/build-repo.py \
        --deb dist/nodejs-npm_18.20.4-1_iphoneos-arm64e.deb \
        --out docs \
        --key /path/to/private-key.asc

If --key is omitted, the repository is built unsigned (apt needs
`[trusted=yes]` in that case).
"""

import argparse
import gzip
import hashlib
import io
import os
import shutil
import sys
from datetime import datetime, timezone
from email.utils import format_datetime

try:
    from pgpy import PGPKey, PGPMessage
    from pgpy.constants import PubKeyAlgorithm
except ImportError:
    PGPKey = None

REPO_ORIGIN = "MasLCH957"
REPO_LABEL = "nodejs-npm-roothide"
REPO_SUITE = "stable"
REPO_CODENAME = "ios"
REPO_ARCHS = "iphoneos-arm64e iphoneos-arm64"
REPO_COMPONENTS = "main"
REPO_DESC = "Node.js + npm for Dopamine-roothide"


def digest(path, algo):
    h = hashlib.new(algo)
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def read_control(deb):
    """Extract the control file from a .deb using dpkg-deb if available,
    otherwise parse the ar archive directly."""
    import subprocess

    try:
        out = subprocess.run(
            ["dpkg-deb", "-f", deb], capture_output=True, text=True, check=True
        )
        return out.stdout.strip()
    except (FileNotFoundError, subprocess.CalledProcessError):
        return parse_ar_control(deb)


def parse_ar_control(deb):
    """Minimal ar reader: .deb = !<arch>\\n + members."""
    with open(deb, "rb") as fh:
        magic = fh.read(8)
        if magic != b"!<arch>\n":
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
                import tarfile

                with tarfile.open(fileobj=io.BytesIO(data)) as tf:
                    for member in tf.getmembers():
                        if member.name.lstrip("./") == "control":
                            return tf.extractfile(member).read().decode().strip()
    raise SystemExit(f"{deb}: control member not found")


def packages_stanza(control, deb, deb_name):
    size = os.path.getsize(deb)
    lines = [control, f"Filename: ./{deb_name}", f"Size: {size}"]
    lines.append(f"MD5sum: {digest(deb, 'md5')}")
    lines.append(f"SHA1: {digest(deb, 'sha1')}")
    lines.append(f"SHA256: {digest(deb, 'sha256')}")
    return "\n".join(lines) + "\n"


def release_file(pkg_indexes, packages_bytes, packages_gz):
    now = format_datetime(datetime.now(timezone.utc), usegmt=True)
    out = [
        f"Origin: {REPO_ORIGIN}",
        f"Label: {REPO_LABEL}",
        f"Suite: {REPO_SUITE}",
        f"Codename: {REPO_CODENAME}",
        f"Version: 1.0",
        f"Architectures: {REPO_ARCHS}",
        f"Components: {REPO_COMPONENTS}",
        f"Description: {REPO_DESC}",
        f"Date: {now}",
    ]
    for algo, label in (("md5", "MD5Sum"), ("sha1", "SHA1"), ("sha256", "SHA256")):
        out.append(f"{label}:")
        for name, data in (("Packages", packages_bytes), ("Packages.gz", packages_gz)):
            h = hashlib.new(algo, data).hexdigest()
            out.append(f" {h} {len(data):>16} {name}")
    return "\n".join(out) + "\n"


def sign_release(release_text, key_path):
    key, _ = PGPKey.from_file(key_path)

    # InRelease: clearsigned message
    msg = PGPMessage.new(release_text, cleartext=True)
    sig = key.sign(msg)
    msg |= sig
    inrelease = str(msg)

    # Release.gpg: detached signature over the exact Release bytes
    raw = PGPMessage.new(release_text.encode(), file=True)
    det = key.sign(raw)
    release_gpg = bytes(det)

    return inrelease, release_gpg, key.pubkey


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--deb", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--key", help="private key (.asc); omit to build unsigned")
    args = ap.parse_args()

    if not os.path.isfile(args.deb):
        raise SystemExit(f"no such deb: {args.deb}")

    os.makedirs(args.out, exist_ok=True)
    deb_name = os.path.basename(args.deb)
    shutil.copy2(args.deb, os.path.join(args.out, deb_name))

    control = read_control(args.deb)
    packages = packages_stanza(control, args.deb, deb_name).encode()

    packages_gz = gzip.compress(packages, 9, mtime=0)

    with open(os.path.join(args.out, "Packages"), "wb") as fh:
        fh.write(packages)
    with open(os.path.join(args.out, "Packages.gz"), "wb") as fh:
        fh.write(packages_gz)

    release_text = release_file(None, packages, packages_gz)
    with open(os.path.join(args.out, "Release"), "w", newline="\n") as fh:
        fh.write(release_text)

    print(f"Packages       {len(packages):>9} bytes")
    print(f"Packages.gz    {len(packages_gz):>9} bytes")

    if args.key:
        if PGPKey is None:
            raise SystemExit("pgpy is required for signing (pip install pgpy)")
        inrelease, release_gpg, pubkey = sign_release(release_text, args.key)
        with open(os.path.join(args.out, "InRelease"), "w", newline="\n") as fh:
            fh.write(inrelease)
        with open(os.path.join(args.out, "Release.gpg"), "wb") as fh:
            fh.write(release_gpg)
        with open(os.path.join(args.out, "key.gpg"), "wb") as fh:
            fh.write(bytes(pubkey))
        with open(os.path.join(args.out, "key.asc"), "w", newline="\n") as fh:
            fh.write(str(pubkey))
        print(f"InRelease      {len(inrelease):>9} bytes")
        print(f"Release.gpg    {len(release_gpg):>9} bytes")
        print(f"key fingerprint {pubkey.fingerprint}")
    else:
        print("built UNSIGNED (add [trusted=yes] on the client)")


if __name__ == "__main__":
    main()
