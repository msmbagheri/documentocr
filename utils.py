import matplotlib.pyplot as plt
import matplotlib as mpl
from PIL import Image, ImageDraw, ImageFont
from config import settings
import os
import io
from matplotlib.backends.backend_agg import FigureCanvasAgg as FigureCanvas
import re
import tempfile
import subprocess
import pdf2image
import numpy as np
import glob
import subprocess

def parse_response_coordinates(json_filename):
    """Parse response txt file and match images to questions."""
    # Find matching txt file
    base_name = os.path.basename(json_filename).split('.')[0]
    txt_files = glob.glob(os.path.join(os.path.dirname(json_filename), f"{base_name}.txt"))
    
    if not txt_files:
        return {}
    
    txt_file = txt_files[0]
    
    questions = []
    images = []
    
    with open(txt_file, 'r') as f:
        for line in f:
            parts = line.strip().split()
            if len(parts) >= 5:
                type_id = int(float(parts[0]))
                x = float(parts[1])
                y = float(parts[2])
                w = float(parts[3])
                h = float(parts[4])
                
                if type_id == 0:  # Question
                    questions.append({'x': x, 'y': y, 'w': w, 'h': h, 'matched_image': None})
                elif type_id == 1:  # Image
                    images.append({'x': x, 'y': y, 'w': w, 'h': h})
    
    # Sort questions by y-coordinate (top to bottom)
    questions.sort(key=lambda q: q['y'])
    
    # Match each image to the closest question
    for image in images:
        closest_dist = float('inf')
        closest_question = None
        
        for i, question in enumerate(questions):
            # Calculate distance between image and question centers
            img_center_y = image['y'] + image['h']/2
            q_center_y = question['y'] + question['h']/2
            dist = abs(img_center_y - q_center_y)
            
            if dist < closest_dist:
                closest_dist = dist
                closest_question = i
        
        if closest_question is not None:
            questions[closest_question]['matched_image'] = image
    
    return questions

def to_farsi_digits(s):
    persian_digits = str.maketrans('0123456789', '۰۱۲۳۴۵۶۷۸۹')
    
    # Replace digit sequences with \text{farsi-digits}
    def replace_digits(match):
        digits = match.group()
        return r'\text{' + digits.translate(persian_digits) + '}'

    # Only replace numbers in math mode, not inside commands or variables
    return re.sub(r'(?<!\\)[0-9]+', replace_digits, s)


# def render_math(formula):
#     # Use tight LaTeX rendering settings
#     # formula = to_farsi_digits(formula)
#     mpl.rcParams.update({
#         'text.usetex': True,
#         'text.latex.preamble': r'\usepackage{amsmath}',
#         'font.size': settings.MATH_FONT_SIZE,
#         'figure.dpi': 300,
#         'savefig.pad_inches': 0,
#         'figure.constrained_layout.use': True
#     })

#     fig = plt.figure(figsize=(0.01, 0.01))
#     canvas = FigureCanvas(fig)
#     ax = fig.add_subplot(111)
#     ax.axis('off')

#     # Render the math formula
#     text_obj = ax.text(0.5, 0.5, f"${formula}$", ha='center', va='center', fontsize=settings.MATH_FONT_SIZE)

#     # Autoscale figure to fit text
#     fig.canvas.draw()
#     bbox = text_obj.get_window_extent()
#     bbox = bbox.transformed(fig.dpi_scale_trans.inverted())
#     fig.set_size_inches(bbox.width, bbox.height)

#     buffer = io.BytesIO()
#     fig.savefig(buffer, format='png', dpi=300, bbox_inches='tight', transparent=True, pad_inches=0.0)
#     plt.close(fig)
#     buffer.seek(0)

#     return Image.open(buffer)

def preprocess_latex_formula(formula):
    """Preprocess LaTeX formula to fix common issues."""
    # Fix cases environment: replace single backslashes with double backslashes between cases
    if r'\begin{cases}' in formula:
        # Split the content between \begin{cases} and \end{cases}
        parts = formula.split(r'\begin{cases}')
        if len(parts) > 1:
            before = parts[0]
            rest = parts[1].split(r'\end{cases}')
            if len(rest) > 1:
                cases_content = rest[0]
                after = rest[1]
                
                # Fix the cases content
                # 1. Split by single backslash that's not followed by another backslash
                lines = re.split(r'(?<!\\)\\(?!\\)\s*', cases_content)
                # 2. Join with proper line breaks
                fixed_cases = ' \\\\ '.join(line.strip() for line in lines if line.strip())
                
                # Reassemble the formula
                formula = before + r'\begin{cases} ' + fixed_cases + r' \end{cases}' + after
    
    return formula

def render_math(formula):
    # Preprocess the formula
    formula = preprocess_latex_formula(formula)
    # LaTeX document template with Persian font and math
    latex_template = r'''
    \documentclass[varwidth, border=2pt]{standalone}
    \usepackage{amsmath}
    \usepackage{amssymb}
    \usepackage{fontspec}
    \usepackage{xepersian}
    \settextfont[Path=/home/ariyadis-ai/Desktop/Amir/konkoor_synth/fonts/, Extension=.ttf]{merged_reg}
    \setmathdigitfont[Path=/home/ariyadis-ai/Desktop/Amir/konkoor_synth/fonts/, Extension=.ttf]{XBNiloofar}
    \begin{document}
        $%s$
    \end{document}
    '''

    with tempfile.TemporaryDirectory() as tmpdir:
        tex_path = os.path.join(tmpdir, 'formula.tex')
        with open(tex_path, 'w', encoding='utf-8') as f:
            f.write(latex_template % formula)
        
        # Run xelatex to generate PDF (suppress output)
        proc = subprocess.run(
            ['xelatex', '-interaction=nonstopmode', tex_path],
            cwd=tmpdir,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )

        if proc.returncode != 0:
            print("XeLaTeX compilation failed:")
            print("STDOUT:\n", proc.stdout)
            print("STDERR:\n", proc.stderr)
            print("Temporary files are in:", tmpdir)
            raise RuntimeError("XeLaTeX compilation error")

        
        pdf_path = os.path.join(tmpdir, 'formula.pdf')
        
        # Convert PDF to image (needs poppler installed)
        images = pdf2image.convert_from_path(pdf_path, dpi=300)
        img = images[0]
        
        return img



# def render_math(formula):
#     # Create a LaTeX document
#     doc = Document()
#     # Add the formula to the document
#     doc.append(f"${formula}$")
#     # Render the document to an image
#     img = doc.create_png()
#     return img

def draw_header(draw, font, page_number, header_text=None):
    header_font = ImageFont.truetype(settings.FONT_PATH_BOLD, settings.FONT_SIZE - 4)
    x = settings.PAGE_SIZE[0] - settings.SIDE_MARGIN
    if header_text is None:
        header_text = settings.DEFAULT_HEADER_TEXT
    
    # Draw the header text
    draw.text((x, settings.TOP_MARGIN - 120), header_text, font=header_font, anchor="ra", fill="black")
    draw.text((x-2000, settings.TOP_MARGIN - 120), f"صفحه {page_number}", font=header_font, anchor="ra", fill="black")
    
    # Draw a filled line under the header, respecting side margins
    line_y = settings.TOP_MARGIN - 50  # Adjust this value based on your header height
    draw.rectangle([(settings.SIDE_MARGIN, line_y), (settings.PAGE_SIZE[0] - settings.SIDE_MARGIN, line_y + 5)], fill="black")  # 5 pixels height for the line

def handle_lines(draw, text, x, y, font, draw_bbox, is_choice=False):
    word_bboxes, y = draw_rtl_words(draw, text, x, y, font, draw_bbox, is_choice)
    return word_bboxes, y

def draw_question(draw, question, y, number, font_regular, font_bold, image_draw, image_path, draw_bbox=False, question_coords=None):
    x = settings.PAGE_SIZE[0] - settings.SIDE_MARGIN
    title_indent = settings.QUESTION_TITLE_INDENTATION
    start_y = y
    bboxes = []

    # Read margin settings
    margin_x = settings.BBOX_MARGIN_X
    margin_y = settings.BBOX_MARGIN_Y

    # -------- Title --------
    try:
        title_ops_original = question['title']['body']['ops']
        processed_title_ops = [{'insert': f'-{number} '}] + title_ops_original
        word_bboxes, y = draw_rtl_words(draw, processed_title_ops, x, y, font_bold, image_draw, draw_bbox)
        bboxes.extend([{"type": "word", "bbox": wb["bbox"], "text": wb["word"]} for wb in word_bboxes])
        if word_bboxes:
            line_bbox = (
                min(wb["bbox"][0] for wb in word_bboxes),# - margin_x,
                min(wb["bbox"][1] for wb in word_bboxes),# - margin_y,
                max(wb["bbox"][2] for wb in word_bboxes),# + margin_x,
                max(wb["bbox"][3] for wb in word_bboxes),# + margin_y,
            )
            if draw_bbox:
                draw.rectangle(line_bbox, outline="blue", width=2)
            bboxes.append({"type": "title", "bbox": line_bbox})
    except (IndexError, KeyError, AttributeError):
        error_message_ops = [{'insert': f"❌ [خطا در بارگذاری سوال]"}]
        word_bboxes, y = draw_rtl_words(draw, error_message_ops, x, y, font_bold, image_draw, draw_bbox)

    y += settings.LINE_SPACING

    # -------- Choices --------
    for i, choice in enumerate(question.get("choices", [])):
        choice_ops_original = choice['ops']
        processed_choice_ops = [{'insert': f'{settings.CHOICE_PREFIXES[i]} '}] + choice_ops_original
        word_bboxes, y = draw_rtl_words(draw, processed_choice_ops, x, y, font_regular, image_draw, draw_bbox, is_choice=True)
        bboxes.extend([{"type": f"choice_{i}_word", "bbox": wb["bbox"], "text": wb["word"]} for wb in word_bboxes])
        if word_bboxes:
            line_bbox = (
                min(wb["bbox"][0] for wb in word_bboxes),# - margin_x,
                min(wb["bbox"][1] for wb in word_bboxes),# - margin_y,
                max(wb["bbox"][2] for wb in word_bboxes),# + margin_x,
                max(wb["bbox"][3] for wb in word_bboxes),# + margin_y,
            )
            if draw_bbox:
                draw.rectangle(line_bbox, outline="green", width=2)
            bboxes.append({"type": f"choice_{i}_title", "bbox": line_bbox})
        y += settings.LINE_SPACING

    # -------- Question Block --------
    question_bbox = (settings.SIDE_MARGIN - margin_x, start_y - margin_y, settings.PAGE_SIZE[0] - settings.SIDE_MARGIN + margin_x, y + margin_y)
    if draw_bbox:
        draw.rectangle(question_bbox, outline="red", width=3)
    bboxes.append({"type": "question_block", "bbox": question_bbox})

    return (y + settings.LINE_SPACING + font_regular.size, bboxes)

def draw_rtl_words(draw, ops, x, y, font, image_draw, draw_bbox=False, is_choice=False, max_width=None):
    lines = []
    current_line = []
    current_width = 0
    space_width = font.getbbox(" ")[2]
    max_width = max_width or (x - settings.SIDE_MARGIN)
    special_labels = {"الف", "ب", "ج", "د"}

    # Read margin settings
    margin_x = settings.BBOX_MARGIN_X
    margin_y = settings.BBOX_MARGIN_Y

    # First pass: calculate widths and group into lines
    for op in ops:
        if isinstance(op.get('insert'), str):
            words = op['insert'].split()
            for word in words:
                word_width = font.getbbox(word)[2]
                if (current_width + word_width > max_width and current_line) or (not is_choice and word.strip(":() ").strip() in special_labels):
                    lines.append(current_line)
                    current_line = []
                    current_width = 0
                current_line.append(('text', word, word_width, None))
                current_width += word_width + space_width
        elif isinstance(op.get('insert'), dict) and 'formula' in op['insert']:
            formula_img = render_math(op['insert']['formula'])
            formula_width = formula_img.width
            if current_width + formula_width > max_width and current_line:
                lines.append(current_line)
                current_line = []
                current_width = 0
            current_line.append(('formula', formula_img, formula_width, op['insert']['formula']))
            current_width += formula_width + space_width
        # Skip image inserts
        elif isinstance(op.get('insert'), dict) and 'image' in op['insert']:
            continue

    if current_line:
        lines.append(current_line)

    # Second pass: render everything
    current_y = y
    word_bboxes = []
    max_height_in_line = font.size

    for line in lines:
        current_x = x
        max_height_in_line = font.size  # Reset for each line
        
        # First calculate max height in this line
        for item_type, item, width, latex in line:
            if item_type == 'formula':
                max_height_in_line = max(max_height_in_line, item.height)

        # Then render items in the line
        for item_type, item, width, latex in line:
            if item_type == 'text':
                word_x = current_x - width
                # Vertically center the text if there's a tall formula in the line
                text_y = current_y + (max_height_in_line - font.size) // 2
                bbox = (word_x - margin_x, text_y - margin_y, current_x + margin_x, text_y + font.size + margin_y)
                draw.text((current_x, text_y), item, font=font, anchor="ra", fill="black")
                if draw_bbox:
                    draw.rectangle(bbox, outline="orange", width=3)
                word_bboxes.append({"word": item, "bbox": bbox})
                current_x -= width + space_width
            else:  # formula
                formula_x = current_x - width
                # Vertically center the formula
                formula_y = current_y + (max_height_in_line - item.height) // 2
                image_draw.paste(item, (formula_x, formula_y))
                bbox = (formula_x - margin_x, formula_y - margin_y, formula_x + width + margin_x, formula_y + item.height + margin_y)
                if draw_bbox:
                    draw.rectangle(bbox, outline="purple", width=3)
                word_bboxes.append({"word": latex, "bbox": bbox})
                current_x -= width + space_width

        current_y += max_height_in_line + settings.LINE_SPACING

    return word_bboxes, current_y