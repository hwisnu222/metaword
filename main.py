import sys
import os
from google import genai
from google.genai.errors import APIError
from PIL import Image
from dotenv import load_dotenv
from pathlib import Path
from tqdm import tqdm
from exiftool import ExifToolHelper
import json
import argparse

load_dotenv()

# colors
RED = "\033[31m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
DEFAULT = "\033[0m"


class Keyworder:
    api_key = os.getenv("GEMINI_API_KEY")
    MODEL_NAME = "gemini-2.5-flash"
    SYSTEM_INSTRUCTION = (
        "You are an expert SEO image caption writer for a stock photo platform like Shutterstock. "
        "Your task is to analyze an image and generate a Title, Description, two Categories, and Tags "
        "in English. The output must be highly relevant, engaging, and optimized with keywords "
        "that are frequently searched on Google Trends or stock photo platforms. "
        """
        Available categories:
        - abstract
        - animals/Wildlife
        - arts
        - backgrounds/Textures
        - beauty/Fashion
        - buildings/Landmarks
        - business/Finance
        - celebrities
        - education
        - food and drink
        - healthcare/Medical
        - holidays
        - industrial
        - interiors
        - miscellaneous
        - nature
        - objects
        - parks/Outdoor
        - people
        - religion
        - science
        - signs/Symbols
        - sports/Recreation
        - technology
        - transportation
        - vintage
        """
        "The output must follow this exact format:"
        "\n\n"
        "Title: Your SEO Title Here\n"
        "Description: Your detailed, keyword-rich description here\n"
        "Categories: category with lower case\n"
        "OUTPUT FORMAT (MUST BE VALID JSON) dont add any character invalid json:\n"
        "{\n"
        '  "title": "string",\n'
        '  "description": "string",\n'
        '  "categories": ["string", "string"],\n'
        '  "keywords": ["string", "string", "string"]\n'
        "}"
    )

    def has_exif(self, path):
        with ExifToolHelper() as et:
            metadata = et.get_metadata(path)

            if metadata[0].get("XMP:Title"):
                return True
            return False

    def add_metadata_to_eps(self, file_path, title, description, keywords, categories):

        try:
            with ExifToolHelper() as et:
                et.set_tags(
                    [file_path],
                    tags={
                        "Headline": title,
                        "Description": description,
                        "Caption-Abstract": description,
                        "Keywords": keywords,
                        "Categories": categories,
                        "XMP:Title": title,
                        "XMP:Description": description,
                        "XMP:Subject": keywords,
                    },
                    params=["-overwrite_original"],  # disable file backup .eps_original
                )
            print(f"{GREEN}[SUCCESS]{DEFAULT} added metadata to: {os.path.basename(file_path)}")
        except Exception as e:
            print(f"{RED}[ERROR]{DEFAULT} {file_path} file: {e}")

    def analyze_image_for_shutterstock(self, image_path):
        if not self.api_key:
            tqdm.write("{RED}[ERROR]{DEFAULT} 'GEMINI_API_KEY' not found")
            sys.exit(1)

        try:
            client = genai.Client(api_key=self.api_key)

            img = Image.open(image_path)
            tqdm.write(
                f"{YELLOW}[PROGRESS]{DEFAULT} Image is loaded: '{image_path}'. Send to Gemini server"
            )

            response = client.models.generate_content(
                model=self.MODEL_NAME,
                contents=img,
                config=genai.types.GenerateContentConfig(
                    system_instruction=self.SYSTEM_INSTRUCTION,
                    # change response to json format
                    response_mime_type="application/json",
                ),
            )

            if response.text:
                metadata = json.loads(response.text)

                self.add_metadata_to_eps(
                    image_path,
                    title=metadata.get("title"),
                    description=metadata.get("description"),
                    keywords=metadata.get("keywords"),
                    categories=metadata.get("categories"),
                )
                return

            tqdm.write(f"{RED}[ERROR]{DEFAULT} failed get response server")

        except FileNotFoundError:
            tqdm.write(f"{RED}[ERROR]{DEFAULT} image not found: {image_path}")
        except APIError as e:
            tqdm.write(f"{RED}[ERROR]{DEFAULT} failed to connect Gemini API. Error: ({e})")
        except Exception as e:
            tqdm.write(f"{RED}[ERROR]{DEFAULT} : {e}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()

    parser.add_argument('-l', '--limit', help="limit file check in newest")
    parser.add_argument('-p', '--path', help="EPS files of directory path")
    args = parser.parse_args()

    keyworder = Keyworder()

    workdir = "./stock/eps"
    if args.path and os.path.exists(workdir):
        workdir = args.path

    stock = Path(workdir)
    if not stock.exists():
        print(f"creating {workdir} directory")
        os.makedirs(stock, exist_ok=True)

    paths = list(stock.glob("*.eps"))

    if not len(paths) > 0:
        print(f"{RED}[ERROR]{DEFAULT} please add file *.eps in {workdir} folder")
        sys.exit(1)

    paths.sort(key=lambda x: x.stat().st_mtime, reverse=True)

    print(f"Checking exif data in {workdir} directory...")
    selected = []
    limit = 8
    if args.limit:
        limit = int(args.limit)
    for path in tqdm(paths[:limit]):
        # select file only don't have exif
        has_exif = keyworder.has_exif(path)
        if not has_exif:
            selected.append(path)
            tqdm.write(f"{RED}[X]{DEFAULT} {path}")
        else:
            tqdm.write("checking finished")

    try:
        if len(selected) < 1:
            print(f"{YELLOW}[INFO]{DEFAULT} all *.eps file in {workdir} directory has added exif metadata")
            sys.exit(1)

        print("Generate exif data to file...")
        selected_paths = selected
        for path in tqdm(selected_paths):
            keyworder.analyze_image_for_shutterstock(path)
    except KeyboardInterrupt as e:
        print(f"Process cancalled. Error: {e}")
