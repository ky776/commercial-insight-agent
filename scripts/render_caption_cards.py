#!/usr/bin/env python3
"""Render transparent caption cards with Pillow for FFmpeg composition."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


def fit_font(draw: ImageDraw.ImageDraw, lines: list[str], font_path: str, max_size: int, max_width: int) -> ImageFont.FreeTypeFont:
    for size in range(max_size, 27, -2):
        font = ImageFont.truetype(font_path, size)
        if all(draw.textbbox((0, 0), line, font=font, stroke_width=3)[2] <= max_width for line in lines):
            return font
    return ImageFont.truetype(font_path, 28)


def render(config_path: Path) -> None:
    config = json.loads(config_path.read_text(encoding="utf-8"))
    width = int(config["width"])
    height = int(config["height"])
    output_dir = Path(config["output_dir"])
    output_dir.mkdir(parents=True, exist_ok=True)
    font_path = config.get("font_path") or "/System/Library/Fonts/STHeiti Medium.ttc"
    for index, cue in enumerate(config["cues"], 1):
        image = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)
        lines = cue["lines"]
        font = fit_font(draw, lines, font_path, max(34, int(width * 0.052)), int(width * 0.84))
        spacing = max(8, int(font.size * 0.25))
        boxes = [draw.textbbox((0, 0), line, font=font, stroke_width=4) for line in lines]
        text_height = sum(box[3] - box[1] for box in boxes) + spacing * (len(lines) - 1)
        y = int(height * 0.76) - text_height // 2
        padding_x = int(width * 0.035)
        padding_y = int(height * 0.012)
        max_line_width = max(box[2] - box[0] for box in boxes)
        background = (0, 0, 0, 150)
        draw.rounded_rectangle(
            ((width - max_line_width) // 2 - padding_x, y - padding_y,
             (width + max_line_width) // 2 + padding_x, y + text_height + padding_y),
            radius=max(8, int(width * 0.012)), fill=background,
        )
        cursor_y = y
        for line, box in zip(lines, boxes):
            line_width = box[2] - box[0]
            draw.text(
                ((width - line_width) // 2, cursor_y), line, font=font,
                fill=(255, 255, 255, 255), stroke_width=4, stroke_fill=(20, 20, 20, 255),
            )
            cursor_y += box[3] - box[1] + spacing
        image.save(output_dir / f"caption-{index:03d}.png")


if __name__ == "__main__":
    render(Path(sys.argv[1]))
