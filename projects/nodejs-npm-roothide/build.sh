#!/bin/sh
# Build the .deb on a jailbroken device that already has node + npm deployed.
#
# Usage (run on the device, from the repo root):
#   VERSION=18.20.4-1 sh build.sh
#
# Output: $OUT/nodejs-npm_<VERSION>_iphoneos-arm64e.deb  (default OUT=/var/mobile)

set -e

VERSION="${VERSION:-18.20.4-1}"
ARCH="iphoneos-arm64e"
OUT="${OUT:-/var/mobile}"
WORK="${WORK:-/var/mobile/.build-nodejs-npm}"

[ -f debian/control.in ] || { echo "run this from the repo root" >&2; exit 1; }
[ -f /usr/local/lib/nodejs/node ] || { echo "node not deployed at /usr/local/lib/nodejs/node" >&2; exit 1; }

echo "==> staging into $WORK"
rm -rf "$WORK"
mkdir -p "$WORK/DEBIAN" "$WORK/usr/local/bin" "$WORK/usr/local/lib/nodejs" "$WORK/etc/profile.d"

cp -p /usr/local/bin/node /usr/local/bin/npm /usr/local/bin/npx "$WORK/usr/local/bin/"
cp -p /usr/local/lib/nodejs/node "$WORK/usr/local/lib/nodejs/"
cp -p /usr/local/lib/nodejs/entitlements.xml "$WORK/usr/local/lib/nodejs/"
cp -R /usr/local/lib/nodejs/npm "$WORK/usr/local/lib/nodejs/npm"

echo "==> control"
sed "s/@VERSION@/$VERSION/" debian/control.in > "$WORK/DEBIAN/control"
cp debian/postinst debian/postrm "$WORK/DEBIAN/"
chmod 755 "$WORK/DEBIAN/postinst" "$WORK/DEBIAN/postrm"

chown -R root:wheel "$WORK" 2>/dev/null || true

echo "==> packing"
DEB="$OUT/nodejs-npm_${VERSION}_${ARCH}.deb"
dpkg-deb -b -Zxz --root-owner-group "$WORK" "$DEB"

echo "==> done: $DEB"
ls -lh "$DEB"
rm -rf "$WORK"
