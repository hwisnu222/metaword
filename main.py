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
import logging
from platformdirs import PlatformDirs


def config_dir():
    dirs = PlatformDirs(appname="metaword")
    config_path = dirs.user_config_dir
    os.makedirs(config_path, exist_ok=True)

    return config_path

env_path = os.path.join(config_dir(), ".env")
load_dotenv(dotenv_path=env_path)

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
            logging.info(f"Added metadata to: {os.path.basename(file_path)}")
        except Exception as e:
            print(f"Error {file_path} file: {e}")

    def analyze_image_for_shutterstock(self, image_path):
        if not self.api_key:
            tqdm.write("GEMINI_API_KEY not found")
            sys.exit(1)

        try:
            client = genai.Client(api_key=self.api_key)

            img = Image.open(image_path)
            tqdm.write(
                f"Image is loaded: '{image_path}'. Send to Gemini server"
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
                logging.info("Success add metadata to file")
                return metadata

            tqdm.write("Failed get response server")

        except FileNotFoundError:
            tqdm.write(f"Image not found: {image_path}")
        except APIError as e:
            tqdm.write(f"Failed to connect Gemini API. Error: ({e})")
        except Exception as e:
            tqdm.write(f"Error: {e}")


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument('-l', '--limit', help="limit file check in newest")
    parser.add_argument('-i', "--include", help="specific files")
    parser.add_argument("-d", "--directory", help="source directory")
    parser.add_argument("-e", "--ext", help="extension target")
    parser.add_argument("-g", "--json", action="store_true", help="json result")

    args = parser.parse_args()

    keyworder = Keyworder()

    config = config_dir()
    env_file = Path(os.path.join(config, ".env"))
    if not env_file.exists():
        logging.info("environment variable doesn't exists")
        api_key = input("Gemini api key: ")

        with open(env_file, "a") as file:
            file.write(f"GEMINI_API_KEY={api_key}")

        logging.info("Success added api key")


    if args.directory:
        source_dir = Path(args.directory)
        paths = list(source_dir.glob(args.ext))

        if not len(paths) > 0:
            logging.error(f"please add file in {args.directory} folder")
            sys.exit(1)

        paths.sort(key=lambda x: x.stat().st_mtime, reverse=True)

        try:
            logging.info("Generate exif data to file...")
            for path in tqdm(paths):
                keyworder.analyze_image_for_shutterstock(path)
        except KeyboardInterrupt as e:
            print(f"Process cancalled. Error: {e}")

    if args.include:
        try:
            logging.info("Generate exif data to file...")
            res = keyworder.analyze_image_for_shutterstock(args.include)

            if args.json:
                print(json.dumps(res, indent=2))
        except KeyboardInterrupt as e:
            logging.error(f"Process cancalled. Error: {e}")
