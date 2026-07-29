from pathlib import Path

import onnxruntime as ort
from rapidocr import RapidOCR
from rapidocr.utils.typings import LangDet, LangRec, ModelType, OCRVersion


PARAMS = {
    "Global.use_cls": False,
    "Global.log_level": "error",
    "Det.ocr_version": OCRVersion.PPOCRV5,
    "Det.lang_type": LangDet.CH,
    "Det.model_type": ModelType.MOBILE,
    "Rec.ocr_version": OCRVersion.PPOCRV5,
    "Rec.lang_type": LangRec.KOREAN,
    "Rec.model_type": ModelType.MOBILE,
}


RapidOCR(params=PARAMS)

model_directory = Path(__import__("rapidocr").__file__).resolve().parent / "models"
required_models = (
    "ch_PP-OCRv5_det_mobile.onnx",
    "korean_PP-OCRv5_rec_mobile.onnx",
)
missing = [name for name in required_models if not (model_directory / name).is_file()]
if missing:
    raise RuntimeError(f"RapidOCR model prefetch failed: {', '.join(missing)}")

recognition_model = model_directory / "korean_PP-OCRv5_rec_mobile.onnx"
metadata = ort.InferenceSession(str(recognition_model), providers=["CPUExecutionProvider"]).get_modelmeta().custom_metadata_map
characters = metadata.get("character", "")
if not any("가" <= character <= "힣" for character in characters):
    raise RuntimeError("RapidOCR Korean model contains no Korean character metadata")

print(f"Prefetched Korean PP-OCRv5 models in {model_directory}")
