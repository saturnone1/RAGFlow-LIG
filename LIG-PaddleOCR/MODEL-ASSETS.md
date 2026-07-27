# Model assets

The Docker build uses RapidOCR 3.8.1 to download and verify the following Apache-2.0 PaddleOCR-derived ONNX assets. They are stored in the final image so runtime operation does not require internet access.

| Asset | Source | Bytes | SHA-256 |
| --- | --- | ---: | --- |
| `ch_PP-OCRv5_det_mobile.onnx` | `RapidAI/RapidOCR` v3.8.0 model registry, derived from PaddleOCR PP-OCRv5 | 4,819,576 | `4d97c44a20d30a81aad087d6a396b08f786c4635742afc391f6621f5c6ae78ae` |
| `korean_PP-OCRv5_rec_mobile.onnx` | `RapidAI/RapidOCR` v3.8.0 model registry, derived from `PaddlePaddle/korean_PP-OCRv5_mobile_rec` | 13,488,748 | `cd6e2ea50f6943ca7271eb8c56a877a5a90720b7047fe9c41a2e541a25773c9b` |

Upstream references:

- https://github.com/RapidAI/RapidOCR
- https://huggingface.co/PaddlePaddle/korean_PP-OCRv5_mobile_rec_onnx
- https://github.com/PaddlePaddle/PaddleOCR/blob/main/docs/version3.x/algorithm/PP-OCRv5/PP-OCRv5_multi_languages.en.md

Verified locally on 2026-07-28 after the image build.
