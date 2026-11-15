from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List
import os
from dotenv import load_dotenv

load_dotenv('.env', override=True)

class Settings(BaseSettings):
    # Font paths
    FONT_PATH_REGULAR: str
    FONT_PATH_BOLD: str
    FONT_PATH_MATH: str

    # Page settings
    PAGE_WIDTH: int
    PAGE_HEIGHT: int
    SIDE_MARGIN: int
    TOP_MARGIN: int
    LINE_SPACING: int
    QUESTIONS_PER_PAGE: int

    # Font settings
    FONT_SIZE: int
    MATH_FONT_SIZE: int

    # Output settings
    OUTPUT_DIR: str

    # Choice settings
    CHOICE_PREFIX_1: str
    CHOICE_PREFIX_2: str
    CHOICE_PREFIX_3: str
    CHOICE_PREFIX_4: str

    # Header settings
    DEFAULT_HEADER_TEXT: str

    IMAGE_RESCALE_FACTOR: float

    BBOX_MARGIN_X: int
    BBOX_MARGIN_Y: int

    QUESTION_TITLE_INDENTATION: int

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    @property
    def PAGE_SIZE(self):
        return (self.PAGE_WIDTH, self.PAGE_HEIGHT)

    @property
    def CHOICE_PREFIXES(self) -> List[str]:
        return [
            self.CHOICE_PREFIX_1,
            self.CHOICE_PREFIX_2,
            self.CHOICE_PREFIX_3,
            self.CHOICE_PREFIX_4,
        ]

settings = Settings()

# Ensure output directories exist
os.makedirs(settings.OUTPUT_DIR, exist_ok=True)
os.makedirs(os.path.join(settings.OUTPUT_DIR, "images"), exist_ok=True)
