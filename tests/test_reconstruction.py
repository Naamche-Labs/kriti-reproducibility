from __future__ import annotations

import sys
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS))

from reconstruction_common import (  # noqa: E402
    indicvoices_identity,
    normalize_reference,
    semantic_view_sha256,
    stable_sample_id,
)


class ReconstructionTests(unittest.TestCase):
    def test_stable_sample_id_matches_frozen_namespace(self) -> None:
        self.assertEqual(
            stable_sample_id("fixture", "utterance-001"),
            "kriti-bb78a72583f05d42a2205a7678a5abf9",
        )

    def test_indicvoices_identity_is_deterministic(self) -> None:
        self.assertEqual(
            indicvoices_identity(
                repository_relative_path="nepali/train-00000-of-00073.parquet",
                parquet_row_index=42,
                upstream_path="clip.flac",
                audio_sha256="a" * 64,
            ),
            (
                "train:a447a11f27c23a2168ce81008c8d78b4",
                "kriti-1548ad1ca9665c5b901f02f13e991da4",
            ),
        )

    def test_reference_normalization_matches_frozen_profile(self) -> None:
        self.assertEqual(normalize_reference("\ufeff  नेपाली\tपाठ\u200c  "), "नेपाली पाठ\u200c")
        self.assertEqual(normalize_reference("क\x00ख"), "कख")

    def test_semantic_commitment_is_ordered_by_ordinal(self) -> None:
        rows = [
            {
                "ordinal": 1,
                "sample_id": "b",
                "source_id": "s",
                "source_audio_sha256": "2" * 64,
                "pcm_sha256": "4" * 64,
                "num_frames": 2,
                "reference": "ख",
            },
            {
                "ordinal": 0,
                "sample_id": "a",
                "source_id": "s",
                "source_audio_sha256": "1" * 64,
                "pcm_sha256": "3" * 64,
                "num_frames": 1,
                "reference": "क",
            },
        ]
        self.assertEqual(
            semantic_view_sha256(rows),
            "faa7009991da04f86ed6e0df99769c24e08c431052f68874edc5b44cfc2772a1",
        )
        self.assertEqual(semantic_view_sha256(rows), semantic_view_sha256(list(reversed(rows))))


if __name__ == "__main__":
    unittest.main()
