import os
import json
from PIL import Image
from config import settings
from PIL import ImageDraw, ImageFont
from matplotlib import pyplot as plt
import shutil

class Result:
    def __init__(self, prediction, type, output_dir, to_save, image_path=None):
        if 'boxes' in prediction:
            self.bboxes = prediction['boxes']
        elif 'bboxes' in prediction:
            self.bboxes = prediction['bboxes']
        elif hasattr(prediction, 'bboxes'):
                self.bboxes = prediction.bboxes
        else:
            raise ValueError("Prediction does not contain bounding boxes.")
        if 'input_path' in prediction:
            self.image_path = prediction['input_path']
        else:
            self.image_path = image_path
        self.type = type
        self.prediction = prediction
        self.output_dir = output_dir
        self.to_save = to_save
        if self.to_save:
            self.save()

    def save(self):
        output_path = f'{self.output_dir}/{os.path.splitext(os.path.basename(self.image_path))[0]}'
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        if hasattr(self.prediction, 'model_dump_json'):
            with open(f'{output_path}_{self.type}.json', 'w', encoding='utf-8') as f:
                f.write(self.prediction.model_dump_json(indent=4))
        elif hasattr(self.prediction, 'save_to_json'):
            self.prediction.save_to_json(f'{output_path}_{self.type}.json')
        else:
            with open(f'{output_path}_{self.type}.json', 'w', encoding='utf-8') as f:
                json.dump(self.prediction, f, indent=4, ensure_ascii=False)

    
    def save_yolo_format(self):
        """
        Save the predictions in YOLO format: class_id x_center y_center width height
        Where:
        - class_id is an integer (0 for text, and other values for different labels)
        - x_center, y_center, width, height are normalized by image width and height
        """
        # Define class mapping (you can extend this as needed)
        class_map = settings.get_classes
        labels_dir = f'{os.path.dirname(os.path.dirname(self.output_dir))}/labels/'
        images_dir = f'{os.path.dirname(os.path.dirname(self.output_dir))}/images/'
        os.makedirs(labels_dir, exist_ok=True)
        os.makedirs(images_dir, exist_ok=True)
        # Copy the image to the images directory
        if self.image_path:
            shutil.copy2(self.image_path, os.path.join(images_dir, os.path.basename(self.image_path)))
        if not os.path.exists(os.path.join(labels_dir, 'labels.txt')):
            with open(os.path.join(labels_dir, 'labels.txt'), 'w', encoding='utf-8') as f:
                for cls_name, cls_id in class_map.items():
                    f.write(f"{cls_name}\n")
        with open(f'{labels_dir}{os.path.basename(self.image_path).split(".")[0]}.txt', 'w', encoding='utf-8') as f:
            if 'bboxes' in self.prediction:
                bboxes = self.prediction['bboxes']
            else:
                bboxes = self.bboxes
                
            for bbox in bboxes:
                # Get class id
                if isinstance(bbox, dict):
                    label = bbox.get('label', 'text')
                    coordinates = bbox.get('bbox', None)
                else:
                    label = getattr(bbox, 'label', 'text')
                    coordinates = getattr(bbox, 'bbox', None)
                    
                cls_id = class_map.get(label.lower(), 0)  # Default to 0 (text) if label not in map
                
                if coordinates:
                    # Convert from [x_min, y_min, x_max, y_max] to YOLO format [x_center, y_center, width, height]
                    x_min, y_min, x_max, y_max = coordinates
                    x_min, y_min, x_max, y_max = float(x_min), float(y_min), float(x_max), float(y_max)
                    
                    # Normalize coordinates
                    norm_coords = self.normalize_bbox([x_min, y_min, x_max, y_max])
                    x_min, y_min, x_max, y_max = norm_coords
                    
                    # Convert to center format
                    x_center = (x_min + x_max) / 2
                    y_center = (y_min + y_max) / 2
                    width = x_max - x_min
                    height = y_max - y_min
                    
                    # Write to file in YOLO format
                    f.write(f"{cls_id} {x_center:.6f} {y_center:.6f} {width:.6f} {height:.6f}\n")
    
    def normalize_bbox(self, bbox):
        with Image.open(self.image_path) as img:
            width, height = img.size
        x_min, y_min, x_max, y_max = bbox
        return(
            x_min / width,
            y_min / height,
            x_max / width,
            y_max / height
        )

    def draw_bounding_boxes(self, image_path=None, plot=True, save=False):
        if image_path is None:
            image_path = self.image_path
        image = Image.open(image_path)
        draw = ImageDraw.Draw(image)
        
        # Define color mapping for different labels
        color_map = {
            'text': "red",
            'paragraph_title': "blue",
            'image': "green",
            'table': "purple",
            'default': "yellow"  # Default color for any unrecognized label
        }
        
        for bbox in self.bboxes:
            if isinstance(bbox, dict):
                coordinates = bbox.get('bbox', None)
                label = bbox.get('label', 'text').lower()
            else:
                coordinates = getattr(bbox, 'bbox', None)
                label = getattr(bbox, 'label', 'text').lower()
            
            if coordinates:
                # Get color based on label (default to yellow if label not in map)
                color = color_map.get(label, color_map['default'])
                
                # Draw rectangle with the appropriate color
                draw.rectangle(coordinates, outline=color, width=4)
                
                # Optionally add label text above the bounding box
                # Try to load a font with larger size
                try:
                    font = ImageFont.truetype("arial.ttf", 60)  # Adjust size as needed
                except IOError:
                    # Fallback to default font if specific font not available
                    font = ImageFont.load_default()

                # Draw text with the larger font
                draw.text((coordinates[0], coordinates[1]-60), label, fill=color, font=font)
        
        # Save the image with bounding boxes
        if save:
            output_path = f'{self.output_dir}/{os.path.dirname(self.image_path).split("/")[-1]}/{os.path.basename(self.image_path).split(".")[0]}_boxes.png'
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            image.save(output_path)
        
        if plot:
            plt.figure(figsize=(12, 15))
            plt.tight_layout()
            plt.imshow(image)
            plt.axis('off')
            plt.show()
        
        return image