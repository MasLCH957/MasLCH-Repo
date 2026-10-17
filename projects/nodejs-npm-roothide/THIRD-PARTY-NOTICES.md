# Third-party notices

The `.deb` published in this repository's Releases **redistributes** the
following third-party software. The packaging in this repo is original work
(MIT, see `LICENSE`); the payload is not.

---

## Node.js 18.20.4

- Upstream: https://github.com/nodejs/node (tag `v18.20.4`)
- License: MIT (plus the licenses of bundled dependencies)
- Copyright: Node.js contributors, and the respective authors of bundled
  components (V8, OpenSSL, ICU, zlib, c-ares, llhttp, nghttp2, …)
- Full text, including every bundled component: [`licenses/node-LICENSE.txt`](licenses/node-LICENSE.txt)

**Provenance of the binary.** The `node` Mach-O in the release asset is the
`iphoneos-arm64` build produced by **imcynic** and distributed through the
jailbreak package `io.github.imcynic.nodejs` (18.20.4-1), whose project page is
<https://github.com/imcynic/nodejs-ios>. This repository does **not** rebuild
Node.js from source; it repackages that binary, adds npm, replaces the
launcher, and retargets the package architecture from `iphoneos-arm64` to
`iphoneos-arm64e`. All credit for the iOS build belongs to imcynic.

## npm 10.9.2

- Upstream: https://github.com/npm/cli (tag `v10.9.2`)
- License: Artistic License 2.0
- Copyright: npm, Inc. and Contributors
- Full text: [`licenses/npm-LICENSE.txt`](licenses/npm-LICENSE.txt)

The npm tree is taken verbatim from the official
`https://registry.npmjs.org/npm/-/npm-10.9.2.tgz` tarball. No source changes
were made; only the `bin/*.js` entry points are wrapped by the launchers in
`files/`.

---

## Notes on redistribution

- Node.js is MIT-licensed, which permits redistribution in binary form
  provided the copyright notice and permission notice are included. They are,
  in `licenses/node-LICENSE.txt`.
- npm is under the Artistic License 2.0, which permits redistribution of the
  unmodified package provided the license text accompanies it. It does, in
  `licenses/npm-LICENSE.txt`.
- If you are a rights holder and believe something here is attributed
  incorrectly, open an issue and it will be corrected promptly.
