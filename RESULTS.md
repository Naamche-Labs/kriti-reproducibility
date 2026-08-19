# Per-source results

All values below are punctuation-insensitive WER percentages recomputed with
the exact metric code in [`tools/metrics.py`](tools/metrics.py). Rank uses the
overall score; exact numerator/denominator counts, raw WER/CER, revisions,
decoders, and both replicate hashes are in
[`per-source.json`](evidence/predictions-20260819/metrics/per-source.json).

| Rank | System | Overall | FLEURS | IndicVoices | OpenSLR54 |
|---:|---|---:|---:|---:|---:|
| 1 | Kriti | 24.0773 | 24.9133 | 25.0312 | 5.1433 |
| 1 | AI4Bharat Nepali hybrid RNNT | 24.0773 | 24.9133 | 25.0312 | 5.1433 |
| 3 | AI4Bharat Nepali hybrid CTC | 25.3109 | 25.6455 | 26.2513 | 7.7150 |
| 4 | Qwen3-ASR Nepali public | 52.4043 | 30.0385 | 57.3222 | 13.1535 |
| 5 | Whisper large-v3 Nepali (Kiran Pantha) | 55.7059 | 35.5299 | 59.7720 | 26.9393 |
| 6 | Whisper large-v3 Nepali (OpenSLR) | 55.7678 | 35.7033 | 59.9342 | 24.9578 |
| 7 | Nepali ASR Whisper medium (Paudel et al.) | 58.4027 | 34.1040 | 63.8298 | 14.2496 |
| 8 | MMS-1B-all NPI | 60.1274 | 31.3102 | 63.6629 | 59.7808 |
| 9 | Nepali ASR MMS-1B | 60.7661 | 34.4316 | 65.4543 | 34.3170 |
| 10 | wav2vec2 XLS-R 300M Nepali (Shniranjan) | 62.8900 | 40.9441 | 68.2802 | 14.2496 |
| 11 | IndicConformer Nepali hybrid | 70.3655 | 42.5241 | 75.9328 | 31.4503 |
| 12 | SeamlessM4T-v2-large NPI | 70.4234 | 25.9538 | 78.7916 | 17.6644 |
| 13 | Nepali ASR XLS-R-53 (Paudel et al.) | 74.9945 | 55.6069 | 79.7414 | 32.2934 |
| 14 | wav2vec2 XLS-R 300M Nepali (Spktsagar) | 88.2688 | 84.0270 | 92.3498 | 24.3676 |
| 15 | Whisper large-v3 | 97.0218 | 92.9480 | 97.0001 | 106.3238 |
| 16 | Vakyansh wav2vec2 Nepali NEM-130 | 101.5749 | 101.6956 | 100.4890 | 120.7841 |
| 17 | Whisper large-v3-turbo | 111.2362 | 92.6975 | 113.0739 | 118.8449 |
| 18 | Qwen3-ASR 0.6B base | 112.0207 | 112.0617 | 111.8444 | 115.0927 |
| 19 | Whisper large-v3-turbo Nepali (Kiran Pantha) | 137.2437 | 111.8690 | 129.0819 | 339.1231 |

WER may exceed 100% when insertions outnumber reference words. The two rank-1
systems have identical aggregate error counts but different decoded text and
different prediction-file hashes.
