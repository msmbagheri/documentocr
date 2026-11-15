import os
import pdf2image
from tqdm import tqdm

def pdf_to_images(pdf_path, output_folder, dpi=300):
    """
    Convert a PDF file to images, one image per page.

    :param pdf_path: Path to the PDF file.
    :param output_folder: Directory where the images will be saved.
    :param dpi: Resolution of the output images.
    :return: List of file paths to the generated images.
    """
    # Ensure the output directory exists
    os.makedirs(output_folder, exist_ok=True)

    # Convert PDF to images
    images = pdf2image.convert_from_path(pdf_path, dpi=dpi)

    image_paths = []
    for i, image in tqdm(enumerate(images)):
        image_path = os.path.join(output_folder, f"page_{i + 1}.png")
        image.save(image_path, "PNG")
        image_paths.append(image_path)

    return image_paths

if __name__ == "__main__":
    # Example usage
    # pdf_path = "/home/amir/Ariyadis/bonyan/general_ocr/books/C110202.pdf"  # Replace with your PDF file path
    # output_folder = "/home/amir/Ariyadis/bonyan/general_ocr/data/images/C110202"  # Replace with your desired output folder
    pdf_path = "/home/amir/Ariyadis/bonyan/emtehan/test.pdf"
    output_folder = "/home/amir/Ariyadis/bonyan/emtehan/test"
    image_paths = pdf_to_images(pdf_path, output_folder)