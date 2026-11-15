from dotenv import load_dotenv
import os
from pydantic_settings import BaseSettings

load_dotenv(override=True)

class Settings(BaseSettings):
    DATA_PATH: str
    OUTPUT_DIR: str
    JSONS_PATH: str
    
    SAVE: bool
    DETECTION: str
    VISUALIZE: bool = False

    IMAGE_CLS_ID: str
    TABLE_CLS_ID: str
    PARAGRAPH_TITLE_CLS_ID: str
    TEXT_CLS_ID: str
    HEADER_CLS_ID: str
    FOOTER_CLS_ID: str

    PADDLE_LAYOUT_MODEL_NAME: str

    # Pipeline switches (defaults keep the pipeline runnable without .env changes)
    ENABLE_PADDLE: bool = False       # Paddle layout stage is optional (runtime incompatible)
    ENABLE_RECOGNITION: bool = True   # run Surya recognition and save *_ocr.json

    @property
    def get_classes(self):
        return {
            'image': self.IMAGE_CLS_ID,
            'table': self.TABLE_CLS_ID,
            'paragraph_title': self.PARAGRAPH_TITLE_CLS_ID,
            'text': self.TEXT_CLS_ID,
            'header': self.HEADER_CLS_ID,
            'footer': self.FOOTER_CLS_ID
        }

settings = Settings()