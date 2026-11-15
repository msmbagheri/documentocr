from PIL import Image, ImageDraw

# Load project .env BEFORE importing surya so SURYA_INFERENCE_* env vars are visible
from dotenv import load_dotenv
load_dotenv(override=True)

from surya.detection import DetectionPredictor
from surya.recognition import RecognitionPredictor
from paddleocr import LayoutDetection, TextDetection
import json
import os
import re
from config import settings
from classes.result import Result
from loguru import logger
from tqdm import tqdm


class Detection:
    def __init__(self, output_dir, save, detector_type='lines'):
        self.output_dir = output_dir
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir, exist_ok=True)
            logger.info(f"Created output directory: {self.output_dir}")
        self.save = save
        self.detector_type = detector_type
        logger.info(f"Initializing Detection with detector_type={detector_type}")
        self.select_model(detector_type)
    
    def __call__(self, detector_type):
        if self.detector_type == detector_type:
            logger.debug(f"Detector type {detector_type} already selected")
            return
        logger.info(f"Changing detector type from {self.detector_type} to {detector_type}")
        self.detector_type = detector_type
        self.select_model(detector_type)

    def select_model(self, detector_type):
        logger.info(f"Selecting model for detector_type: {detector_type}")
        if detector_type == "lines":
            self.model = SuryaDetection(self.output_dir, self.save, self.detector_type)
        elif detector_type == "layout":
            self.model = PaddleDetection(self.output_dir, self.save, self.detector_type)
        else:
            logger.error(f"Unsupported detection type: {detector_type}")
            raise ValueError(f"Unsupported detection type: {detector_type}")

    def draw_bounding_boxes(self, image_path, predictions):
        logger.debug(f"Drawing bounding boxes for {image_path}")
        image = Image.open(image_path)
        draw = ImageDraw.Draw(image)
        for prediction in predictions:
            draw.rectangle(prediction.bbox, outline="red", width=2)
        return image


class PaddleDetection:
    def __init__(self, output_dir, save, detector_type):
        logger.info(f"Initializing PaddleDetection with model: {settings.PADDLE_LAYOUT_MODEL_NAME} (CPU mode)")
        self.detection_predictor = LayoutDetection(
            model_name=settings.PADDLE_LAYOUT_MODEL_NAME,
            device='cpu'
        )
        self.type = detector_type
        self.output_dir = output_dir
        self.save = save
    
    def detect(self, dataset):
        logger.info(f"Running PaddleDetection on dataset with {len(dataset)} images")
        logger.debug(f"Processing {len(dataset)} images")
        for image_path in tqdm(dataset.get_data()):
            prediction = self.detection_predictor.predict(image_path, batch_size=1, layout_nms=True)[0]
            Result(prediction, image_path=image_path, type=self.type, output_dir=self.output_dir, to_save=self.save)
        logger.success(f"PaddleDetection completed for {len(dataset)} images")


class SuryaDetection():
    def __init__(self, output_dir, save, detector_type):
        logger.info("Initializing SuryaDetection")
        self.output_dir = output_dir
        self.save = save
        self.type = detector_type
        self.detection_predictor = DetectionPredictor()
        self.recognition_predictor = RecognitionPredictor() if settings.ENABLE_RECOGNITION else None
        if self.recognition_predictor is not None:
            logger.info("Surya recognition enabled (backend attaches via SURYA_INFERENCE_URL)")
        logger.debug("SuryaDetection initialized successfully")

    def _save_ocr(self, page_result, image_path):
        """Persist recognition output as <stem>_ocr.json (additive; *_lines.json untouched)."""
        blocks = []
        for block in page_result.blocks:
            html = getattr(block, "html", "") or ""
            text = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html)).strip()
            blocks.append({
                "label": block.label,
                "bbox": block.bbox,
                "confidence": block.confidence,
                "reading_order": block.reading_order,
                "text": text,
                "html": html,
            })
        blocks.sort(key=lambda b: b["reading_order"])
        payload = {
            "input_path": image_path,
            "image_bbox": page_result.image_bbox,
            "text": "\n".join(b["text"] for b in blocks if b["text"]),
            "blocks": blocks,
        }
        stem = os.path.splitext(os.path.basename(image_path))[0]
        out_path = os.path.join(self.output_dir, f"{stem}_ocr.json")
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        logger.info(f"Saved OCR text -> {out_path} ({len(payload['text'])} chars)")
        return payload

    def detect(self, dataset):
        logger.info(f"Running SuryaDetection on dataset with {len(dataset)} images")
        logger.debug(f"Processing {len(dataset)} images")
        for image_path in tqdm(dataset.get_data()):
            image = Image.open(image_path)
            predictions = self.detection_predictor([image])
            if self.recognition_predictor is not None:
                try:
                    ocr_result = self.recognition_predictor([image])
                    self._save_ocr(ocr_result[0], image_path)
                except Exception as e:
                    logger.error(f"Recognition failed for {image_path}: {type(e).__name__}: {e}")
            Result(predictions[0], image_path=image_path, type=self.type, output_dir=self.output_dir, to_save=self.save)
        logger.success(f"SuryaDetection completed for {len(dataset)} images")