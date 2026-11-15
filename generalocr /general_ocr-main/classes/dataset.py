import os
import glob
from loguru import logger
import json
from classes.result import Result

class ImagesDataset:
    def __init__(self, data_path, output_dir, detector_type, skip_existing=True, sample_size=None):
        """
        Initialize a dataset from a path to an image file or a directory of images.
        
        Args:
            data_path (str): Path to an image file or directory containing images
        """
        self.dataset_name = data_path.split(os.sep)[-1] if os.path.isdir(data_path) else os.path.dirname(data_path).split(os.sep)[-1]
        self.data_path = data_path
        self.output_dir = output_dir
        self.skip_existing = skip_existing
        self.sample_size = sample_size

        # Check if the path exists
        if not os.path.exists(data_path):
            raise FileNotFoundError(f"Path does not exist: {data_path}")
        
        # Handle single image file
        if os.path.isfile(data_path):
            # Check if it's an image file (by extension)
            if data_path.lower().endswith(('.png', '.jpg', '.jpeg', '.tiff', '.bmp', '.gif')):
                self.data = [data_path]
            else:
                raise ValueError(f"File is not a supported image format: {data_path}")
        
        # Handle directory of images
        elif os.path.isdir(data_path):
            # Get all image files in the directory
            image_extensions = ['*.png', '*.jpg', '*.jpeg', '*.tiff', '*.bmp', '*.gif']
            self.data = []
            
            for ext in image_extensions:
                self.data.extend(glob.glob(os.path.join(data_path, ext)))
                # Also search in subdirectories
                self.data.extend(glob.glob(os.path.join(data_path, '**', ext), recursive=True))
            
            # Sort the files for consistency
            self.data = sorted(list(set(self.data)))
            
            if not self.data:
                print(f"Warning: No image files found in directory: {data_path}")
        
        else:
            raise ValueError(f"Path is neither a file nor a directory: {data_path}")
        
        if self.skip_existing:
            self.skip_existing_files(detector_type)
        
        if sample_size:
            self.get_sample(self.sample_size)

    def skip_existing_files(self, detector_type):
        """
        Skip existing files in the dataset based on the output directory.
        If the output directory exists, it will remove files that are already processed.
        """
        existing_files = [file for file in self.data if f'{os.path.splitext(os.path.basename(file))[0]}_{detector_type}.json' 
                          in set(os.listdir(self.output_dir))]
        if self.sample_size is not None:
            self.sample_size -= len(existing_files)
        self.data = [file for file in self.data if file not in existing_files]

        if not self.data:
            print("Warning: All files in the dataset have already been processed.")
    
    def get_sample(self, sample_size=None):
        """
        Get a sample of the dataset.

        Args:
            sample_size (int, optional): Number of samples to return. If None, returns the entire dataset.
        Returns:
            list: Sampled data.
        """
        if sample_size < 0 or sample_size > len(self.data):
            raise ValueError("Sample size must be a non-negative integer and less than or equal to the number of images in the dataset.")
        self.data = self.data[:sample_size]

    def get_data(self):
        return self.data

    def set_data(self, new_data):
        self.data = new_data

    def __repr__(self):
        return f"Dataset(data={self.data})"

    def __len__(self):
        return len(self.data)

    def __getitem__(self, index):
        return self.data[index] if 0 <= index < len(self.data) else None

class JsonsDataset:
    def __init__(self, input_dir, images_datapath):
        self.dataset_name = images_datapath.split(os.sep)[-1]
        data_path = os.path.join(input_dir, self.dataset_name)
        if not os.path.isdir(data_path):
            raise ValueError(f"Path is not a directory: {data_path}")
        if not os.path.exists(data_path):
            raise FileNotFoundError(f"Path does not exist: {data_path}")
        
        self.data_path = data_path
        # self.output_dir = os.path.join(data_path, 'labels')
        # os.makedirs(self.output_dir, exist_ok=True)

        # Get all JSON files in the directory
        lines_files = glob.glob(os.path.join(data_path, '*_lines.json'))
        layout_files = glob.glob(os.path.join(data_path, '*_layout.json'))
        
        # Create dictionaries mapping base filenames to full paths
        lines_dict = {os.path.splitext(os.path.basename(file))[0].replace('_lines', ''): file for file in lines_files}
        layout_dict = {os.path.splitext(os.path.basename(file))[0].replace('_layout', ''): file for file in layout_files}
        
        # Find common keys (intersection)
        common_keys = set(lines_dict.keys()).intersection(set(layout_dict.keys()))
        
        # Create merged dictionary with common keys
        self.data = {}
        for key in common_keys:
            self.data[key] = {
                'lines': lines_dict[key],
                'layout': layout_dict[key],
                'input_path': os.path.join(images_datapath, f'{key}.png')
            }
        
        if not self.data:
            print(f"Warning: No matching JSON pairs found in directory: {data_path}")

    def get_data(self):
        return self.data
    
    def set_data(self, new_data):
        self.data = new_data
    
    def __repr__(self):
        return f"JsonsDataset(data={self.data})"
    
    def __len__(self):
        return len(self.data)
    
    def __getitem__(self, key):
        return self.data.get(key)
    
    def items(self):
        return self.data.items()
    
    def keys(self):
        return self.data.keys()
    
    def values(self):
        return self.data.values()
    
    def merge_prediction(self, lines_path, layout_path, input_path):
        logger.info(f"Merging predictions for {input_path}")
        if not (os.path.exists(lines_path) or os.path.exists(layout_path)):
            logger.error(f"Prediction file {lines_path} or {layout_path} does not exist")
            raise ValueError(f"Prediction file {lines_path} or {layout_path} does not exist.")
        with open(lines_path, 'r', encoding='utf-8') as f:
            lines = json.load(f)
        with open(layout_path, 'r', encoding='utf-8') as f:
            layout = json.load(f)
            
        logger.debug(f"Found {len(lines.get('bboxes', []))} lines and {len(layout.get('boxes', []))} layout elements")
        
        merged_prediction = {'bboxes': [], 'input_path': input_path}
        for bbox in lines['bboxes']:
            merged_prediction['bboxes'].append({'label': 'text', 'bbox': bbox['bbox'], 'confidence': bbox['confidence']})
        for bbox in layout['boxes']:
            if bbox['label'] == 'text':
                continue
            merged_prediction['bboxes'].append({'label': bbox['label'], 'bbox': bbox['coordinate'], 'confidence': bbox['score']})
            
        logger.info(f"Merged prediction contains {len(merged_prediction['bboxes'])} bounding boxes")
        return merged_prediction

    def remove_overlapped_boxes(self, prediction):
        logger.info(f"Removing overlapped boxes from prediction with {len(prediction['bboxes'])} bounding boxes")
        filtered_bboxes = []
        text_bboxes = [bbox for bbox in prediction['bboxes'] if bbox['label'] == 'text']
        non_text_bboxes = [bbox for bbox in prediction['bboxes'] if bbox['label'] != 'text']
        
        logger.debug(f"Found {len(text_bboxes)} text bboxes and {len(non_text_bboxes)} non-text bboxes")
        
        # Keep all non-text bboxes
        filtered_bboxes.extend(non_text_bboxes)
        
        # Check non-text bboxes for overlaps with text bboxes
        for text_bbox in text_bboxes:
            text_box = text_bbox['bbox']
            overlaps_with_non_text = False
            
            for non_text_bbox in non_text_bboxes:
                non_text_box = non_text_bbox['bbox']
                
                # Calculate IoU (Intersection over Union)
                # Calculate intersection coordinates
                x_left = max(non_text_box[0], text_box[0])
                y_top = max(non_text_box[1], text_box[1])
                x_right = min(non_text_box[2], text_box[2])
                y_bottom = min(non_text_box[3], text_box[3])
                
                # Calculate areas
                if x_right > x_left and y_bottom > y_top:  # Check if there is an intersection
                    intersection_area = (x_right - x_left) * (y_bottom - y_top)
                    non_text_area = (non_text_box[2] - non_text_box[0]) * (non_text_box[3] - non_text_box[1])
                    text_area = (text_box[2] - text_box[0]) * (text_box[3] - text_box[1])
                    union_area = non_text_area + text_area - intersection_area
                    iou = intersection_area / text_area if text_area > 0 else 0
                    
                    # Consider boxes overlapping if IoU exceeds threshold
                    if iou > 0.7:  # You can adjust this threshold as needed
                        logger.debug(f"Text box {text_box} overlaps with non-text box {non_text_box} (IoU: {iou:.2f})")
                        overlaps_with_non_text = True
                        break
            
            # Only add text bbox if it doesn't overlap with any non-text bbox
            if not overlaps_with_non_text:
                filtered_bboxes.append(text_bbox)
        
        # Return a new prediction with filtered bboxes
        filtered_prediction = prediction.copy()
        filtered_prediction['bboxes'] = filtered_bboxes
        logger.info(f"After filtering overlaps, {len(filtered_prediction['bboxes'])} bounding boxes remain")
        return filtered_prediction

    def merge_predictions(self, visualize=False):
        logger.info(f"Merging predictions for {len(self)} results.")
        results = []
        for page, value in self.items():
            logger.info(f"Processing page: {page}")
            lines_path = value['lines']
            layout_path = value['layout']
            merged_prediction = self.merge_prediction(lines_path, layout_path, input_path=value['input_path'])
            filtered_prediction = self.remove_overlapped_boxes(merged_prediction)
            result = Result(filtered_prediction, type='merged', output_dir=self.data_path, to_save=True)
            if visualize:
                result.draw_bounding_boxes(plot=True, save=True)
            result.save_yolo_format()
            results.append(result)
        logger.success(f"Successfully processed page {page} from book {self.dataset_name}")
