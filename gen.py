import json
from PIL import Image, ImageDraw, ImageFont
import argparse
from config import settings
from utils import draw_header, draw_question, parse_response_coordinates
from loguru import logger
import os
import signal
import sys


def read_questions(json_path, n):
    logger.info(f"Reading the first {n} questions from {json_path}")
    with open(json_path, "r", encoding="utf-8") as f:
        questions = json.load(f)
    
    logger.info(f"Read {len(questions)} questions from {json_path}")
    return dict(list(questions.items())[:n])

def get_last_generated_question(bbox_path):
    """Read the last generated question from bboxes.json."""
    if not os.path.exists(bbox_path):
        logger.warning(f"No existing file found at {bbox_path}.")
        return None, None, None  # No existing file

    with open(bbox_path, "r", encoding="utf-8") as f:
        bboxes_data = json.load(f)

    last_page = list(bboxes_data.keys())[-1]  # Get the last page
    last_questions = bboxes_data[last_page]
    last_question_number = len(last_questions)  # Number of questions in the last page

    logger.info(f"Last generated page: {last_page}, with {last_question_number} questions.")
    return last_page, last_question_number, bboxes_data

def main(json_path, n, image_path, draw_bbox=False, export_bbox=False, overwrite=False):
    logger.info(f"Starting main process with {n} questions from {json_path}")
    
    if overwrite:
        logger.info("Overwrite flag is set. Starting fresh.")
        last_page, last_question_number, bboxes_data = None, None, None
    else:
        last_page, last_question_number, bboxes_data = get_last_generated_question(os.path.join(settings.OUTPUT_DIR, "bboxes.json"))
    
    questions = read_questions(json_path, n)
    question_coords = parse_response_coordinates(json_path)

    font_regular = ImageFont.truetype(settings.FONT_PATH_REGULAR, settings.FONT_SIZE)
    font_bold = ImageFont.truetype(settings.FONT_PATH_BOLD, settings.FONT_SIZE)
    question_items = list(questions.items())
    all_bboxes = {}

    page_number = 1
    q_index = 0

    if last_page and not overwrite:
        page_number = int(last_page.split('_')[-1])  # Assuming page names are like "page_1"
        q_index = sum(len(bboxes_data[page]) for page in list(bboxes_data.keys())[:-1])  # Count all questions in previous pages

    bbox_path = f"{settings.OUTPUT_DIR}/bboxes.json"

    if os.path.exists(bbox_path) and not overwrite:
        with open(bbox_path, "r", encoding="utf-8") as f:
            existing_data = json.load(f)
    else:
        existing_data = {}

    def save_bboxes():
        with open(bbox_path, "w", encoding="utf-8") as f:
            json.dump(existing_data, f, ensure_ascii=False, indent=2)
        logger.info(f"Saved bounding boxes to {bbox_path}")

    def handle_interrupt(signum, frame):
        logger.warning("Interrupted! Saving progress before exit...")
        save_bboxes()
        sys.exit(0)

    signal.signal(signal.SIGINT, handle_interrupt)
    signal.signal(signal.SIGTERM, handle_interrupt)

    try:
        while q_index < len(question_items):
            image = Image.new("RGB", settings.PAGE_SIZE, "white")
            draw = ImageDraw.Draw(image)

            draw_header(draw, font_regular, page_number)
            y = settings.TOP_MARGIN
            page_bboxes = []

            while q_index < len(question_items):
                temp_img = Image.new("RGB", settings.PAGE_SIZE, "white")
                temp_draw = ImageDraw.Draw(temp_img)
                temp_y = y

                q_key, q_data = question_items[q_index]
                q_number = q_index + 1
                
                q_coord = question_coords[q_index] if q_index < len(question_coords) else None

                final_y, _ = draw_question(temp_draw, q_data, temp_y, q_number, font_regular, font_bold, temp_img, image_path, draw_bbox=False, question_coords=q_coord)
                question_height = final_y - y

                if final_y > settings.PAGE_SIZE[1] - settings.SIDE_MARGIN:
                    logger.info(f"Not enough space for question {q_number}, moving to the next page.")
                    break

                y, bboxes = draw_question(draw, q_data, y, q_number, font_regular, font_bold, image, image_path, draw_bbox, question_coords=q_coord)
                if export_bbox:
                    page_bboxes.append({"question_number": q_number, "bboxes": bboxes})

                logger.info(f"Processed question {q_number}.")
                q_index += 1

            image_path_out = f"{settings.OUTPUT_DIR}/images/page_{page_number}.png"
            image.save(image_path_out)
            logger.info(f"Saved image: {image_path_out}")
            
            if export_bbox:
                page_key = f"page_{page_number}"
                existing_data[page_key] = page_bboxes
                save_bboxes()  # Save after each page

            page_number += 1

    except Exception as e:
        logger.error(f"Exception occurred: {e}")
        save_bboxes()
        raise

    if export_bbox:
        save_bboxes()
        logger.info("Final bounding boxes saved.")


if __name__ == "__main__":
    image_file = "/data/Screenshot from 2025-05-19 10-53-02.png"
    json_file = "/data/result.json"
    parser = argparse.ArgumentParser()
    parser.add_argument("--json_path", default=json_file, help="Path to the questions JSON file")
    parser.add_argument("--image_path", default=None, help="Path to the questions image file")
    parser.add_argument("--draw-bbox", action="store_true", default=False, help="Draw bounding boxes on the output image")
    parser.add_argument("--export-bbox", action="store_true", default=True, help="Export bounding box data to JSON")
    parser.add_argument("--n", type=int, default=10, help="Number of questions to generate")
    parser.add_argument("--overwrite", action="store_true", default=False, help="Overwrite existing data and start from scratch")
    args = parser.parse_args()

    main(args.json_path, args.n, args.image_path, draw_bbox=args.draw_bbox, export_bbox=args.export_bbox, overwrite=args.overwrite)