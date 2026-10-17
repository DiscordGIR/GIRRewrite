"""Detection helpers for the antiraid attachment filters."""

import base64
import json
import re
from pathlib import Path

import aiohttp
import pyvips


MAX_IMAGE_BYTES = 8 * 1024 * 1024
MAX_IMAGE_PIXELS = 25_000_000

# Committed fingerprints avoid downloads and expiring reference URLs at startup.
with (Path(__file__).resolve().parent.parent / "data/antiraid/scam_images.json").open() as file:
    KNOWN_SCAM_IMAGES = json.load(file)


def is_image(attachment):
    return (attachment.content_type and attachment.content_type.startswith("image/")) or (
        not attachment.content_type and re.search(
            r"\.(?:png|jpe?g|webp|gif|avif)$", attachment.filename, re.IGNORECASE
        ) is not None
    )


async def download_image(attachment, session):
    if attachment.size > MAX_IMAGE_BYTES:
        raise ValueError("Image exceeds 8 MiB scan limit")
    async with session.get(
        attachment.url, timeout=aiohttp.ClientTimeout(total=10), allow_redirects=False
    ) as response:
        if response.status != 200:
            raise ValueError(f"Image download HTTP {response.status}")
        buffer = bytearray()
        async for chunk in response.content.iter_chunked(64 * 1024):
            if len(buffer) + len(chunk) > MAX_IMAGE_BYTES:
                raise ValueError("Image exceeds 8 MiB scan limit")
            buffer.extend(chunk)
        return bytes(buffer)


def image_fingerprint(buffer):
    """Use libvips (as Sharp does) to retain compatibility with stored hashes.

    Called in a worker thread so decoding never blocks the Discord gateway.
    Only the first frame of animated images is scanned.
    """
    image = pyvips.Image.new_from_buffer(buffer, "", fail_on="error")
    if image.width * image.height > MAX_IMAGE_PIXELS:
        raise ValueError("Image exceeds 25 megapixel scan limit")
    orientation = image.get("orientation") if image.get_typeof("orientation") else 1

    def resize(width, height, greyscale=False):
        source = image
        # Sharp still uses JPEG decoder shrinking with fastShrinkOnLoad=false,
        # leaving at least a factor of two for the final Lanczos resize.
        if image.get("vips-loader").startswith("jpegload") and orientation == 1:
            shrink = min(image.width / width, image.height / height)
            factor = 8 if shrink >= 16 else 4 if shrink >= 8 else 2 if shrink >= 4 else 1
            if factor > 1:
                source = pyvips.Image.new_from_buffer(buffer, "", shrink=factor, fail_on="error")
        source = source.autorot()
        if source.get_typeof("icc-profile-data") and source.interpretation not in ("labs", "grey16"):
            try:
                source = source.icc_transform("srgb", embedded=True, intent="perceptual")
            except pyvips.Error:
                pass  # Sharp also ignores invalid embedded profiles.
        if source.hasalpha():
            white = 65535 if source.interpretation in ("rgb16", "grey16") else 255
            source = source.flatten(background=[white] * (source.bands - 1))
        if greyscale:
            source = source.colourspace("b-w")
        return source.resize(width / source.width, vscale=height / source.height,
                             kernel="lanczos3").colourspace("srgb").cast("uchar")

    pixels = bytes(resize(17, 16, greyscale=True)[0].write_to_memory())
    bits = "".join(
        "1" if pixels[y * 17 + x] > pixels[y * 17 + x + 1] else "0"
        for y in range(16) for x in range(16)
    )
    colors = bytes(resize(16, 16).write_to_memory())
    return {"bits": bits, "colors": base64.b64encode(colors).decode("ascii")}


def fingerprint_distance(a, b):
    ac, bc = base64.b64decode(a["colors"]), base64.b64decode(b["colors"])
    if len(a["bits"]) != 256 or len(b["bits"]) != 256 or len(ac) != 768 or len(bc) != 768:
        raise ValueError("Invalid image fingerprint")
    return (sum(x != y for x, y in zip(a["bits"], b["bits"])),
            sum(abs(x - y) for x, y in zip(ac, bc)) / len(ac))


def match_fingerprint(fingerprint):
    for reference in KNOWN_SCAM_IMAGES:
        bits, color = fingerprint_distance(fingerprint, reference)
        if bits <= 24 and color <= 8:
            return reference["name"]
    return None
