"""Core quantization logic extracted from the GUI layer."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image
from sklearn.cluster import KMeans
from sklearn.metrics import pairwise_distances_argmin
from sklearn.utils import shuffle


DEFAULT_COLOR_COUNT = 64
DEFAULT_SAMPLE_SIZE = 1000
DEFAULT_RANDOM_STATE = 0

SUPPORTED_INPUT_EXTENSIONS = (".jpg", ".jpeg", ".png", ".bmp", ".gif")


@dataclass(frozen=True)
class QuantizationResult:
    """A single quantized image and the metadata needed for tests/debugging."""

    image: Image.Image
    palette: np.ndarray
    labels: np.ndarray
    sample_size_used: int
    original_shape: tuple[int, int, int]
    pixel_count: int


@dataclass(frozen=True)
class ComparisonResult:
    """Results for the K-Means path and the random baseline path."""

    original_image: Image.Image
    kmeans: QuantizationResult
    random: QuantizationResult
    n_colors: int
    random_state: int


def ensure_rgb(image: Image.Image) -> Image.Image:
    """Return an RGB copy of the given image."""

    if image.mode != "RGB":
        return image.convert("RGB")
    return image.copy()


def load_image(image_source: str | Path | Image.Image) -> Image.Image:
    """Load an image source into a detached RGB PIL image."""

    if isinstance(image_source, Image.Image):
        return ensure_rgb(image_source)

    with Image.open(image_source) as image:
        return ensure_rgb(image)


def image_to_array(image: Image.Image) -> tuple[np.ndarray, tuple[int, int, int]]:
    """Convert a PIL image into a flattened float array and its original shape."""

    rgb_image = ensure_rgb(image)
    array = np.array(rgb_image, dtype=np.float64) / 255.0
    original_shape = tuple(array.shape)
    if len(original_shape) != 3 or original_shape[2] != 3:
        raise ValueError("Expected an RGB image with three channels.")
    height, width, depth = original_shape
    return np.reshape(array, (height * width, depth)), original_shape


def recreate_image(codebook: np.ndarray, labels: np.ndarray, original_shape: tuple[int, int, int]) -> Image.Image:
    """Rebuild a PIL image from a palette, labels, and the original image shape."""

    height, width, depth = original_shape
    image = codebook[labels].reshape((height, width, depth))
    image = np.uint8(np.clip(image * 255.0, 0, 255))
    return Image.fromarray(image, mode="RGB")


def _normalize_parameters(image_array: np.ndarray, n_colors: int, sample_size: int) -> tuple[int, int]:
    if image_array.size == 0:
        raise ValueError("Image contains no pixels.")
    if n_colors < 2:
        raise ValueError("n_colors must be at least 2.")
    pixel_count = image_array.shape[0]
    if n_colors > pixel_count:
        raise ValueError("n_colors cannot exceed the number of pixels in the image.")
    if sample_size < 1:
        raise ValueError("sample_size must be at least 1.")
    return n_colors, min(sample_size, pixel_count)


def quantize_image(
    image_source: str | Path | Image.Image,
    n_colors: int = DEFAULT_COLOR_COUNT,
    sample_size: int = DEFAULT_SAMPLE_SIZE,
    random_state: int = DEFAULT_RANDOM_STATE,
) -> QuantizationResult:
    """Quantize an image with K-Means clustering."""

    image = load_image(image_source)
    image_array, original_shape = image_to_array(image)
    n_colors, sample_size_used = _normalize_parameters(image_array, n_colors, sample_size)
    image_array_sample = shuffle(image_array, random_state=random_state)[:sample_size_used]

    kmeans = KMeans(n_clusters=n_colors, random_state=random_state, n_init=10)
    kmeans.fit(image_array_sample)
    labels = kmeans.predict(image_array)

    return QuantizationResult(
        image=recreate_image(kmeans.cluster_centers_, labels, original_shape),
        palette=kmeans.cluster_centers_,
        labels=labels,
        sample_size_used=sample_size_used,
        original_shape=original_shape,
        pixel_count=image_array.shape[0],
    )


def random_quantize_image(
    image_source: str | Path | Image.Image,
    n_colors: int = DEFAULT_COLOR_COUNT,
    sample_size: int = DEFAULT_SAMPLE_SIZE,
    random_state: int = DEFAULT_RANDOM_STATE,
) -> QuantizationResult:
    """Quantize an image by sampling a random palette from the input."""

    image = load_image(image_source)
    image_array, original_shape = image_to_array(image)
    n_colors, sample_size_used = _normalize_parameters(image_array, n_colors, sample_size)
    codebook_random = shuffle(image_array, random_state=random_state)[:n_colors]
    labels_random = pairwise_distances_argmin(codebook_random, image_array, axis=0)

    return QuantizationResult(
        image=recreate_image(codebook_random, labels_random, original_shape),
        palette=codebook_random,
        labels=labels_random,
        sample_size_used=sample_size_used,
        original_shape=original_shape,
        pixel_count=image_array.shape[0],
    )


def compare_quantization(
    image_source: str | Path | Image.Image,
    n_colors: int = DEFAULT_COLOR_COUNT,
    sample_size: int = DEFAULT_SAMPLE_SIZE,
    random_state: int = DEFAULT_RANDOM_STATE,
) -> ComparisonResult:
    """Run both quantization paths and return their outputs together."""

    original_image = load_image(image_source)
    return ComparisonResult(
        original_image=original_image,
        kmeans=quantize_image(original_image, n_colors=n_colors, sample_size=sample_size, random_state=random_state),
        random=random_quantize_image(original_image, n_colors=n_colors, sample_size=sample_size, random_state=random_state),
        n_colors=n_colors,
        random_state=random_state,
    )


def save_image(image: Image.Image, destination: str | Path, **save_kwargs: Any) -> Path:
    """Save an image and return the resolved output path."""

    output_path = Path(destination).expanduser().resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(output_path, **save_kwargs)
    return output_path
