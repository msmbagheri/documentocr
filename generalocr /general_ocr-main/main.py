import os
# Disable PaddlePaddle 3.x PIR mode (causes NotImplementedError with older models like PP-DocLayout_plus-L)
os.environ["FLAGS_enable_pir_api"] = "0"
os.environ["FLAGS_enable_pir_in_executor"] = "0"

from loguru import logger

# --- PaddlePaddle API compatibility patch ---
# paddlepaddle 2.6+ renamed set_optimization_level -> tensorrt_optimization_level
# but tensorrt_optimization_level() is now a getter-only (returns int), not a setter.
# The method is used for IR optimization only; making it a no-op allows inference to proceed.
import paddle.base.libpaddle as _lp
if not hasattr(_lp.AnalysisConfig, 'set_optimization_level'):
    def _set_optimization_level(self, level):
        pass  # No-op: optimization level setting was removed in paddlepaddle 2.6+
    _lp.AnalysisConfig.set_optimization_level = _set_optimization_level
# ------------------------------------------------

from config import settings
from classes.dataset import ImagesDataset, JsonsDataset
from classes.detection import Detection


logger.add(
    os.path.join(settings.OUTPUT_DIR, "logs/detection_{time}.log"), 
    rotation="10 MB", 
    level="INFO",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}"
)

if __name__ == "__main__":
    logger.info("Starting detection script")
    detector = Detection(output_dir=settings.JSONS_PATH, save=settings.SAVE, detector_type=settings.DETECTION)

    detector_types = ['lines', 'layout'] if settings.ENABLE_PADDLE else ['lines']
    if not settings.ENABLE_PADDLE:
        logger.info("ENABLE_PADDLE=false -> Paddle layout stage is skipped (not called)")

    for detector_type in detector_types:
        images_dataset = ImagesDataset(settings.DATA_PATH, output_dir=settings.JSONS_PATH, 
                                       detector_type=detector_type)
        logger.info(f"Created dataset with {len(images_dataset)} images")
        logger.info(f"Running detection with detector_type={detector_type}")
        detector(detector_type=detector_type)
        detector.model.detect(images_dataset)

    if settings.ENABLE_PADDLE:
        jsons_dataset = JsonsDataset(input_dir=settings.JSONS_PATH, images_datapath=settings.DATA_PATH)    
        jsons_dataset.merge_predictions(visualize=settings.VISUALIZE)
    else:
        logger.info("Skipping layout merge / YOLO export: requires *_layout.json (Paddle disabled)")

    logger.success("Detection completed successfully")