These synthetic images exercise RGB, transparency, grayscale, JPEG decoder
shrinking, and EXIF rotation. They are not scam-image references.

`fingerprints.json` contains results from the user-supplied JavaScript
`imageFingerprint` function, using Sharp 0.33.5 with libvips 8.15.3. The test
requires the Python port to produce the same hashes and RGB samples. Keep the
libvips binary pinned, or regenerate and review these fixtures when upgrading.
