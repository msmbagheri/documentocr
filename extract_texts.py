import os
import json
from collections import defaultdict

def extract_text_from_bboxes(bboxes_json_path, output_dir=None):
    """
    Extract text from bboxes.json file with the structure:
    {
      "page_1": [
        {
          "question_number": 1,
          "bboxes": [
            {
              "type": "word",
              "bbox": [x1, y1, x2, y2],
              "text": "word text"
            },
            ...
          ]
        },
        ...
      ],
      "page_2": [...],
      ...
    }
    
    Args:
        bboxes_json_path (str): Path to the bboxes.json file
        output_dir (str, optional): Directory to save text files. Defaults to same directory as input.
    
    Returns:
        list: Paths to the saved text files
    """
    # Set output directory
    if output_dir is None:
        output_dir = os.path.dirname(bboxes_json_path)
    os.makedirs(output_dir, exist_ok=True)
    
    # Load the bboxes JSON file
    with open(bboxes_json_path, 'r', encoding='utf-8') as f:
        bboxes_data = json.load(f)
    
    saved_files = []
    
    # Process each page
    for page_key, questions in bboxes_data.items():
        page_num = page_key.split('_')[1]  # Extract page number from "page_1"
        
        page_text = ""
        
        for question in questions:
            question_number = question.get("question_number", "")
            # if question_number:
            #     page_text += f"Question {question_number}:\n"
            
            # Process all words in the question
            if "bboxes" in question:
                # Group words by lines based on y-coordinate
                words_by_line = defaultdict(list)
                
                for word_data in question["bboxes"]:
                    if "text" in word_data and "bbox" in word_data:
                        bbox = word_data["bbox"]
                        text = word_data["text"]
                        
                        # Use the y-coordinate (vertical position) to group into lines
                        # Using both top and bottom of the bbox for better line detection
                        y_mid = (bbox[1] + bbox[3]) / 2  # Average of top and bottom
                        line_key = int(y_mid // 20) * 20  # Group nearby y values
                        
                        words_by_line[line_key].append({
                            "text": text,
                            "x1": bbox[0],
                            "x2": bbox[2],
                        })
                
                # Process each line (RTL text)
                for y_key in sorted(words_by_line.keys()):
                    words = words_by_line[y_key]
                    # Sort words right-to-left (for RTL languages)
                    rtl_sorted_words = sorted(words, key=lambda w: -w["x1"])
                    line_text = " ".join(word["text"] for word in rtl_sorted_words)
                    page_text += line_text + "\n"
                
                page_text += "\n"  # Add extra space between questions
        
        # Save to file
        output_file = os.path.join(output_dir, f"page_{page_num}.txt")
        
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(page_text)
        
        saved_files.append(output_file)
        print(f"Page {page_num} text saved to {output_file}")
    
    return saved_files

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Extract text from bboxes.json files with proper newlines")
    parser.add_argument("--input", default="output_pages/bboxes.json", 
                        help="Path to bboxes.json file")
    parser.add_argument("--output-dir", default="texts", 
                        help="Directory to save text files")
    
    args = parser.parse_args()
    extract_text_from_bboxes(args.input, args.output_dir)