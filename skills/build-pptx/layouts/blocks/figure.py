"""figure block — image with optional caption.

Aspect-aware: scales image to fit bbox preserving aspect ratio.
Caption sits below at 9pt mono dim.

params:
    image_path  str   — path to image file
    caption     str   — optional caption text
    alt         str   — alt text (used if image fails to load)
"""
from __future__ import annotations

from pathlib import Path

from pptx.dml.color import RGBColor
from pptx.util import Inches

from ._base import (
    _add_text, _get_image_aspect,
    DIM_RGB, MUTED_RGB,
    branding,
)


def render(slide, *, left: float, top: float, width: float, height: float,
           params: dict, accent_rgb: RGBColor) -> None:
    image_path_str = params.get("image_path", "")
    caption = params.get("caption", "")
    alt = params.get("alt", "")

    caption_h = 0.28 if caption else 0.0
    img_h = max(0.3, height - caption_h - (0.08 if caption else 0.0))

    img_path = Path(image_path_str) if image_path_str else None

    if img_path is None or not img_path.exists():
        # Placeholder with alt text
        placeholder = alt or image_path_str or "[figure]"
        _add_text(slide, f"[{placeholder}]",
                  left=left, top=top, width=width, height=img_h,
                  size=10, color_rgb=DIM_RGB, font=branding.MONO_FONT)
    else:
        try:
            aspect = _get_image_aspect(img_path)
            # Fit into bbox preserving aspect
            bbox_aspect = width / img_h
            if aspect >= bbox_aspect:
                # Image is wider — fit to width
                actual_w = width
                actual_h = width / aspect
            else:
                # Image is taller — fit to height
                actual_h = img_h
                actual_w = img_h * aspect

            actual_w = max(0.1, actual_w)
            actual_h = max(0.1, actual_h)

            # Center in bbox
            img_left = left + (width - actual_w) / 2
            img_top = top + (img_h - actual_h) / 2

            slide.shapes.add_picture(
                str(img_path),
                Inches(img_left), Inches(img_top),
                width=Inches(actual_w), height=Inches(actual_h),
            )
        except Exception as e:
            _add_text(slide, f"[image error: {e}]",
                      left=left, top=top, width=width, height=img_h,
                      size=9, color_rgb=DIM_RGB, font=branding.MONO_FONT)

    if caption:
        caption_top = top + img_h + 0.04
        _add_text(slide, caption,
                  left=left, top=caption_top, width=width, height=caption_h,
                  size=9, color_rgb=MUTED_RGB, font=branding.MONO_FONT,
                  italic=True)
