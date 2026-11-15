import json
from config import settings
from PIL import Image
import os
import shutil
import argparse

IDENTIFIER_MAP = {
    'word': 'words',
    'title': 'sep'
}

def prepare_question_blocks_data(json_data, image_width, image_height, class_id=0):
    """
    Prepares data for question blocks detection
    """
    if os.path.exists(f"{settings.OUTPUT_DIR}/labels"):
        shutil.rmtree(f"{settings.OUTPUT_DIR}/labels")
    os.makedirs(f"{settings.OUTPUT_DIR}/labels", exist_ok=True)

    for page_id, page in json_data.items():
        yolo_annotations = []
        for question in page:
            for item in question['bboxes']:
                if item['type'] == 'question_block':
                    x_min, y_min, x_max, y_max = item['bbox']
                    x_center = ((x_min + x_max) / 2) / image_width
                    y_center = ((y_min + y_max) / 2) / image_height
                    width = (x_max - x_min) / image_width
                    height = (y_max - y_min) / image_height

                    # Round for readability or use full precision for actual files
                    yolo_line = f"{class_id} {x_center:.6f} {y_center:.6f} {width:.6f} {height:.6f}"
                    yolo_annotations.append(yolo_line)

            with open(f"{settings.OUTPUT_DIR}/labels/{page_id}.txt", "w", encoding="utf-8") as f:
                for line in yolo_annotations:
                    f.write(line + "\n")

def prepare_crops_dataset(json_data, identifier):
    """
    Prepares data for question_title/choices if identifier is 'title' 
    and word/latex detection if identifier is 'word'.
    """
    if os.path.exists(f"{settings.OUTPUT_DIR}/crops/{IDENTIFIER_MAP[identifier]}/labels"):
        shutil.rmtree(f"{settings.OUTPUT_DIR}/crops/{IDENTIFIER_MAP[identifier]}/labels")
    if os.path.exists(f"{settings.OUTPUT_DIR}/crops/{IDENTIFIER_MAP[identifier]}/images"):
        shutil.rmtree(f"{settings.OUTPUT_DIR}/crops/{IDENTIFIER_MAP[identifier]}/images")

    os.makedirs(f"{settings.OUTPUT_DIR}/crops/{IDENTIFIER_MAP[identifier]}/images", exist_ok=True)
    os.makedirs(f"{settings.OUTPUT_DIR}/crops/{IDENTIFIER_MAP[identifier]}/labels", exist_ok=True)

    filtered_data = {}
    for page_id, page in json_data.items():
        filtered_data[page_id] = []
        for question in page:
            for item in question['bboxes']:
                if item['type'] == 'question_block':
                    # Find all words inside this question block
                    x_min, y_min, x_max, y_max = item['bbox']
                    words_in_block = []
                    for word_item in question['bboxes']:
                        if word_item['type'].split('_')[-1] == identifier:
                            wx_min, wy_min, wx_max, wy_max = word_item['bbox']
                            # Check if word bbox is fully inside question block bbox
                            if (wx_min >= x_min and wy_min >= y_min and
                                wx_max <= x_max and wy_max <= y_max):
                                # Transpose bbox to crop frame
                                rel_bbox = [wx_min - x_min, wy_min - y_min, wx_max - x_min, wy_max - y_min]
                                word_copy = word_item.copy()
                                word_copy['rel_bbox'] = rel_bbox
                                words_in_block.append(word_copy)
                            else:
                                print(f"Word {word_item['text']} is not in the question block")
                    # Add words to the item dict
                    item = item.copy()  # avoid mutating original
                    item['words'] = words_in_block
                    filtered_data[page_id].append(item)

    sorted_data = sorted(filtered_data.items(), key=lambda x: x[0])

    for page_id, page in sorted_data:
        image = Image.open(f"{settings.OUTPUT_DIR}/images/{page_id}.png")
        for q_idx, question in enumerate(page):
            x_min, y_min, x_max, y_max = question['bbox']
            question_crop = image.crop((x_min, y_min, x_max, y_max))
            question_crop.save(f"{settings.OUTPUT_DIR}/crops/{IDENTIFIER_MAP[identifier]}/images/{page_id}_{q_idx+1}.png")
            x_center = ((x_min + x_max) / 2) / question_crop.width
            y_center = ((y_min + y_max) / 2) / question_crop.height
            width = (x_max - x_min) / question_crop.width
            height = (y_max - y_min) / question_crop.height
            with open(f"{settings.OUTPUT_DIR}/crops/{IDENTIFIER_MAP[identifier]}/labels/{page_id}_{q_idx+1}.txt", "w", encoding="utf-8") as f:
                for word in question['words']:
                    x_min, y_min, x_max, y_max = word['rel_bbox']
                    x_center = ((x_min + x_max) / 2) / question_crop.width
                    y_center = ((y_min + y_max) / 2) / question_crop.height
                    width = (x_max - x_min) / question_crop.width
                    height = (y_max - y_min) / question_crop.height
                    if identifier == 'word' and word['text'].strip()[0] == "\\":
                        f.write(f"{1} {x_center:.6f} {y_center:.6f} {width:.6f} {height:.6f}\n")
                    elif identifier == 'title' and word['type'].split('_')[0] == "choice":
                        f.write(f"{1} {x_center:.6f} {y_center:.6f} {width:.6f} {height:.6f}\n")
                    else:
                        f.write(f"{0} {x_center:.6f} {y_center:.6f} {width:.6f} {height:.6f}\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--identifier", type=str, default='word', choices=['word', 'title'])
    parser.add_argument("--task", type=str, choices=['blocks', 'crops'], required=True)
    args = parser.parse_args()
    image_w, image_h = settings.PAGE_WIDTH, settings.PAGE_HEIGHT
    data = json.load(open(f"{settings.OUTPUT_DIR}/bboxes.json", "r", encoding="utf-8"))
    if args.task == 'blocks':
        prepare_question_blocks_data(data, image_w, image_h)
    elif args.task == 'crops':
        prepare_crops_dataset(data, args.identifier)
