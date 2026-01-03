#!/usr/bin/venv python3

# /// script
# dependencies = [
#   "requests",
#   "gallery_dl",
#   "googletrans",
#   "pykakasi"
# ]
# ///

import asyncio
import datetime
import io
import json
import re
import shutil
import os
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, NoReturn, TypedDict, cast

import pykakasi
import requests
from gallery_dl import config, job
from gallery_dl.extractor.message import Message
from googletrans import Translator

RED = "\033[0;31m"
L_RED = "\033[1;31m"
PURPLE = "\033[0;35m"
L_PURPLE = "\033[1;35m"
NC = "\033[0m"
L_GREEN = "\033[1;32m"
YELLOW = "\033[0;33m"
L_YELLOW = "\033[1;33m"
L_CYAN = "\033[1;36m"
L_BLUE = "\033[1;34m"
BLUE = "\033[0;34m"
CYAN = "\033[0;36m"
GREEN = "\033[0;32m"
GRAY = "\033[38;5;240m"
LIGHT_GRAY = "\033[38;5;242m"
LIGHTER_GRAY = "\033[38;5;246m"


class AuthorInfo(TypedDict):
    human_readable_name: str
    pixiv_id: int
    pixiv_username: str
    pixiv_name: str
    pixiv_link: str
    artstation_username: str
    artstation_id: int
    artstation_name: str
    artstation_link: str


class ImageInfo(TypedDict):
    image_title: str
    image_index: int
    original_image_filename: str
    image_id: str  # Hash id for artstation, id for pixiv
    image_slug: str  # Slug for artstation, syncthetic slug for pixiv from title
    image_url: str
    image_url_core: str
    image_tags: list[str]
    image_width: int
    image_height: int

BASE_DIR = Path(__file__).parent

PENDING_ARTSTATION_IMAGES_FILE_LOCATION = Path(os.environ.get("PENDING_ARTSTATION_IMAGES_FILE_LOCATION", "./pending.txt"))
PIXIV_IMAGES_SOURCE_DIR = Path(os.environ.get("PIXIV_IMAGES_SOURCE_DIR", "./pixiv"))

BASE_PERSONAL_DIR = Path(os.environ.get("BASE_PERSONAL_DIR", "/home/kloud/Documents/shared/_Personal"))
BASE_PICTURES_DIR = Path(BASE_PERSONAL_DIR, "Pictures")

TARGET_DIRECTORY_PATH = Path(BASE_PICTURES_DIR, "backgrounds")

# Fill creation datetime in these directories
DATETIME_UPDATE_DIRS = [
    TARGET_DIRECTORY_PATH,
    Path(BASE_PICTURES_DIR, "memez"),
    Path(BASE_PICTURES_DIR, "cutouts_collages"),
    Path(BASE_PICTURES_DIR, "Icons and fonts"),
    Path(BASE_PICTURES_DIR, "neko_ark"),
    Path(BASE_PICTURES_DIR, "avatars"),
]
MTIME_CACHE_FILE = Path(BASE_DIR, "dt_cache.json")

TEMPORARY_DIRECTORY_PATH = Path(BASE_DIR, "./temp")
AUTHOR_INFO_FILENAME = "author_info.json"

FEEDER_EXPORTS_PATH = Path(BASE_PERSONAL_DIR, "exports/feeder")
ARTSTATION_OPML_EXPORT_FILENAME = "artstation-export.opml"

AUTHOR_INFOS: list[AuthorInfo] = []

direct_artstation_url_cores: set[str] = set()
artstation_urls: set[str] = set()

grouped_urls: list[tuple[AuthorInfo, ImageInfo]] = []

directory_update_time_cache: dict[
    str, float
] = {}  # Last recorded time a certain directory was updated, used for skipping changing modification datetime


def err_exit(msg: str) -> NoReturn:
    print(f"{L_RED}ERROR: {msg}{NC}")
    exit(1)


def getYN(default: bool):
    return "[Y/n]" if default else "[y/N]"


def wait_for_YN(msg: str, default: bool):
    while True:
        ret = input(f"{msg} {getYN(default)}: ").lower().strip()
        if ret in ["y", "Y"]:
            return True
        if ret in ["n", "N"]:
            return False

        if len(ret.strip()) == 0 and len(ret) > 0:
            return default

        print(getYN(default))


def second_if_first_empty[T](value1: T, value2: T) -> T:
    is_val1_empty = len(str(value1).strip()) == 0 or value1 == 0 or value1 == -1
    return value2 if is_val1_empty else value1


# "{name}-{id}_{service}-{id2}_{service2}" or
def get_folder_name_for_author(info: AuthorInfo) -> str:
    if len(info["human_readable_name"]) == 0:
        err_exit("Can't construct folder name, human_readable_name is missing")

    if info["pixiv_id"] == 0 and info["artstation_id"] == 0:
        err_exit(f"Can't construct folder name, pixiv or artstation id is missing for {info['human_readable_name']}")

    name = info["human_readable_name"]
    if info["pixiv_id"] > 0:
        name = f"{name}-{info['pixiv_id']}_pixiv"

    if info["artstation_id"] > 0:
        name = f"{name}-{info['artstation_id']}_artstation"

    return name


# {title}-{slug}-{id}_p{num}
def get_file_name_for_image(info: ImageInfo, extension: str):
    name = info["image_id"]

    if len(info["image_slug"]) > 0:
        name += f"+{info['image_slug']}"

    if info["image_index"] >= 0:
        name += f"_p{info['image_index']}"

    return f"{name}.{extension}"


def generate_permutations(str__: str, symbol: str):
    return [str__] + ["".join([str__[0:n], symbol, str__[n:]]) for n in range(len(str__))]


# Example
# Search: maxvhay
# Directory: max_v_hay_artstation
def fuzzy_match(str1: str, str2: str):
    if len(str1) == 0 or len(str2) == 0:
        return False

    if len(str1) == len(str2):
        return str1 == str2

    shorter_str = str1 if len(str1) < len(str2) else str2
    longer_str = str1 if len(str1) > len(str2) else str2

    shorter_str = shorter_str.replace("_", "")
    shorter_str = shorter_str.replace("-", "")

    potential_permutations = generate_permutations(shorter_str, "_") + generate_permutations(shorter_str, "-")

    return any(True for permut in potential_permutations if permut in longer_str)


def find_author_info(search_str: str, key_: str, fuzzy: bool):
    found_infos = [
        info
        for info in AUTHOR_INFOS
        if (fuzzy_match(search_str, str(info[key_])) if fuzzy else search_str == str(info[key_]))
    ]
    if len(found_infos) > 1:
        err_exit(f"Found more than one author info by '{search_str}' ({key_}): {found_infos}")

    return None if len(found_infos) == 0 else found_infos[0]


def load_author_map():
    print(f"\n╭─{L_PURPLE}Loading author information from {TARGET_DIRECTORY_PATH}{NC}")

    AUTHOR_INFOS.clear()

    for dir_ in TARGET_DIRECTORY_PATH.iterdir():
        json_files = list(dir_.glob("*.json"))
        current_author_dir_name = dir_.parts[-1]

        if len(json_files) == 0:
            continue

        if len(json_files) > 1:
            err_exit(f"More than one json file in {current_author_dir_name}")

        author_info_file = json_files[0]
        if author_info_file.name != AUTHOR_INFO_FILENAME:
            err_exit(f"Wrong file for author info file in {current_author_dir_name}")

        parsed_info: AuthorInfo = json.loads(author_info_file.read_text(encoding="utf-8-sig"))
        AUTHOR_INFOS.append(parsed_info)

        print(f"├╼{GREEN} Loaded author info from {current_author_dir_name}{NC}")
        wanted_author_dir_name = get_folder_name_for_author(parsed_info)

        if wanted_author_dir_name is None:
            err_exit(f"Missing author data for {current_author_dir_name}")

        if current_author_dir_name != wanted_author_dir_name:
            dir_.rename(Path(dir_.parent, wanted_author_dir_name))
            print(f"├─╡{BLUE}Renamed {current_author_dir_name} to {wanted_author_dir_name}{NC}")

    print(f"╰─{L_GREEN}OK{NC}\n")


def remove_url_params(url___: str):
    return url___.split("?")[0]  # Remove any extra params


# Urls are in this format:
# https://cdnb.artstation.com/p/assets/images/images/080/330/209/large/marcel-deneuve-pfc-1.jpg?1748769056&4a6e=30921857fe35
def extract_image_url_core(url_: str):
    url_ = remove_url_params(url_)
    stripped_url = url_.partition("/p/")[-1]  # assets/images/images/080/330/209/large/marcel-deneuve-pfc-1.jpg
    stripped_url = str(Path(stripped_url).parent.parent)  # assets/images/images/080/330/209
    return stripped_url


load_author_map()

print(f"\n{L_PURPLE}Classifying urls{NC}\n")

for url in PENDING_ARTSTATION_IMAGES_FILE_LOCATION.read_text(encoding="utf-8-sig").splitlines():
    yrl = url.strip()
    if len(url) == 0:
        print(f"{GRAY} - - - Skipping empty line{NC}")
        continue

    if url.startswith("https://www.artstation.com/"):
        print(f"{LIGHTER_GRAY}Adding artstation url: {url}{NC}")
        artstation_urls.add(url)
        continue

    if url.startswith("https://cdna.artstation.com/") or url.startswith("https://cdnb.artstation.com/"):
        core = extract_image_url_core(url)
        print(f"{LIGHT_GRAY}Adding direct artwork url: {url} (core: {core}){NC}")
        direct_artstation_url_cores.add(core)
        continue

    print(f"{L_YELLOW}Unknown url: {url}{NC}")


print(
    f"{L_PURPLE}{len(direct_artstation_url_cores)}{CYAN} direct links, {L_PURPLE}{len(artstation_urls)}{CYAN} artstation links{NC}\n"
)


def user_data_from_artstation(data: dict[str, Any]) -> AuthorInfo:
    return {
        "artstation_id": cast(int, data.get("id")),
        "artstation_link": cast(str, data.get("permalink")),
        "artstation_name": cast(str, data.get("full_name")),
        "artstation_username": cast(str, data.get("username")),
        "human_readable_name": cast(str, data.get("username")).lower(),
        "pixiv_id": -1,
        "pixiv_link": "",
        "pixiv_name": "",
        "pixiv_username": "",
    }


def user_data_from_pixiv(author_name_raw: str, author_name_translated: str, pixiv_user_id: int) -> AuthorInfo:
    return {
        "artstation_id": -1,
        "artstation_link": "",
        "artstation_name": "",
        "artstation_username": "",
        "human_readable_name": author_name_translated.lower(),
        "pixiv_id": pixiv_user_id,
        "pixiv_link": f"https://www.pixiv.net/en/users/{pixiv_user_id}",
        "pixiv_name": author_name_raw,
        "pixiv_username": author_name_translated,
    }


def image_info_from_artstation(data: dict[str, Any]) -> ImageInfo:
    image_data = cast(dict[str, Any], data.get("asset"))
    return {
        "original_image_filename": cast(str, data.get("filename")),
        "image_id": cast(str, data.get("hash_id")),
        "image_index": cast(int, data.get("num")) - 1,  # Artstation nums start from 1, not good
        "image_slug": cast(str, data.get("slug")),
        "image_tags": cast(list[str], data.get("tags")),
        "image_title": cast(str, data.get("title")),
        "image_width": cast(int, image_data.get("width")),
        "image_height": cast(int, image_data.get("height")),
        "image_url": "",
        "image_url_core": "",
    }


def image_info_from_pixiv(image_name_raw: str, image_slug: str, pixiv_image_id: int, image_index: int) -> ImageInfo:
    return {
        "original_image_filename": "",
        "image_id": f"{pixiv_image_id}",
        "image_index": image_index,  # Pixiv nums start from 0, good
        "image_slug": image_slug,
        "image_tags": [],
        "image_title": image_name_raw,
        "image_width": -1,  # Not used
        "image_height": -1,  # Not used
        "image_url": f"https://www.pixiv.net/en/artworks/{pixiv_image_id}",
        "image_url_core": "",
    }


def merge_user_data(base: AuthorInfo, additional: AuthorInfo):
    # Update ids if unset in base
    base["artstation_id"] = second_if_first_empty(additional["artstation_id"], base["artstation_id"])
    base["pixiv_id"] = second_if_first_empty(additional["pixiv_id"], base["pixiv_id"])

    if (
        base["artstation_id"] != additional["artstation_id"]
        and base["artstation_id"] > 0
        and additional["artstation_id"] > 0
    ):
        err_exit("Can't merge unrelated user infos, artstation ids are different")

    if base["pixiv_id"] != additional["pixiv_id"] and base["pixiv_id"] > 0 and additional["pixiv_id"] > 0:
        err_exit("Can't merge unrelated user infos, pixiv ids are different")

    # Don't override human_readable_name if set
    base["human_readable_name"] = second_if_first_empty(base["human_readable_name"], additional["human_readable_name"])

    # Set to artstation username if not set in 'additional'
    base["human_readable_name"] = second_if_first_empty(base["human_readable_name"], additional["artstation_username"])

    # Take the rest from 'additional' if set
    base["artstation_name"] = second_if_first_empty(additional["artstation_name"], base["artstation_name"])
    base["artstation_username"] = second_if_first_empty(additional["artstation_username"], base["artstation_username"])
    base["artstation_link"] = second_if_first_empty(additional["artstation_link"], base["artstation_link"])

    # Same for pixiv
    base["pixiv_name"] = second_if_first_empty(additional["pixiv_name"], base["pixiv_name"])
    base["pixiv_username"] = second_if_first_empty(additional["pixiv_username"], base["pixiv_username"])
    base["pixiv_link"] = second_if_first_empty(additional["pixiv_link"], base["pixiv_link"])


def get_merged_existing_author_info(extracted_info: AuthorInfo, is_artstation: bool):
    id_lookup = "artstation_id" if is_artstation else "pixiv_id"
    name_lookup = "artstation_username" if is_artstation else "pixiv_username"

    found_userdata: AuthorInfo | None = None
    existing_userdata_by_id = find_author_info(str(extracted_info[id_lookup]), id_lookup, False)

    if existing_userdata_by_id is not None:
        print(f"├╼ {PURPLE}Found existing user data by id, merging{NC}")
        merge_user_data(existing_userdata_by_id, extracted_info)
        found_userdata = existing_userdata_by_id
    else:
        existing_userdata_by_name = find_author_info(str(extracted_info[name_lookup]), name_lookup, True)
        if existing_userdata_by_name is not None:
            print(f"├╼ {PURPLE}Found existing user data by username, merging{NC}")
            merge_user_data(existing_userdata_by_name, extracted_info)
            found_userdata = existing_userdata_by_name

    return found_userdata


def save_author_info(info: AuthorInfo, author_dir_: Path):
    author_dir_.mkdir(exist_ok=True)

    target_path_ = Path(author_dir_, AUTHOR_INFO_FILENAME)
    target_content = json.dumps(info, indent=4, ensure_ascii=False)

    if target_path_.exists() and target_path_.read_text(encoding="utf-8-sig") == target_content:
        return

    target_path_.write_text(target_content, encoding="utf-8")

    print(f"├╼ {CYAN}Updating author info in {author_dir_}{NC}")
    load_author_map()


def find_or_create_author_info(extracted_info: AuthorInfo, is_artstation: bool):
    extracted_author_name = extracted_info["human_readable_name"]
    merged_userdata = get_merged_existing_author_info(extracted_info, is_artstation)

    if merged_userdata is None:
        print(f"├┈ {L_YELLOW}Could't find an existing user file for {extracted_info}{NC}")
        print(f"├┈ {CYAN}Searching the directory tree{NC}")
        for dir_ in TARGET_DIRECTORY_PATH.iterdir():
            dirname = dir_.name.lower()

            does_match = False

            if extracted_info["pixiv_id"] > 0:
                does_match = str(extracted_info["pixiv_id"]) in dirname

            if extracted_info["artstation_id"] > 0:
                does_match = does_match or (
                    fuzzy_match(extracted_author_name.lower(), dirname)
                    or str(extracted_info["artstation_id"]) in dirname
                )

            if does_match:
                if wait_for_YN(f"Found directory: {dir_.name}, is this correct?", False):
                    save_author_info(extracted_info, dir_)
                    merged_userdata = get_merged_existing_author_info(extracted_info, is_artstation)
                    break

    if merged_userdata is None:
        print(f"├┈ {L_YELLOW}Could't match an existing user in the directory tree for {extracted_author_name}{NC}")
        target_author_directory_name = get_folder_name_for_author(extracted_info)
        if wait_for_YN(f"Create new directory? ({target_author_directory_name})", False):
            save_author_info(extracted_info, Path(TARGET_DIRECTORY_PATH, target_author_directory_name))
            merged_userdata = get_merged_existing_author_info(extracted_info, is_artstation)

    if merged_userdata is None:
        err_exit(f"Don't know the target directory for {extracted_author_name}")

    save_author_info(merged_userdata, Path(TARGET_DIRECTORY_PATH, get_folder_name_for_author(merged_userdata)))

    return merged_userdata


def convert_to_jpg_if_needed(image_path: Path):
    if image_path.suffix in [".jpeg", ".jpg"]:
        return image_path

    target_converted_image_path = image_path.with_suffix(".jpg")
    print(f"├╼ {BLUE}Converting to jpg{NC} ({image_path} --> {target_converted_image_path})")
    subprocess.check_call(
        [
            "magick",
            "-quality",
            "95",
            image_path.absolute().as_posix(),
            target_converted_image_path.absolute().as_posix(),
        ],
        stderr=subprocess.STDOUT,
    )
    image_path.unlink()
    return target_converted_image_path


def post_process_image(
    source_image_path: Path, source_image_data: ImageInfo, source_author_data: AuthorInfo, is_artstation: bool
):
    target_image_path = convert_to_jpg_if_needed(source_image_path)

    print("├╼ Cleaning metadata")
    subprocess.check_call(
        [
            "exiftool",
            "-overwrite_original",
            "-HistoryParameters=",
            "-HistoryWhen=",
            "-HistorySoftwareAgent=",
            "-HistoryInstanceID=",
            "-HistoryChanged=",
            "-HistoryAction=",
            "-DocumentID=",
            "-DerivedFromInstanceID=",
            "-DerivedFromDocumentID=",
            "-DerivedFromOriginalDocumentID=",
            "-InstanceID=",
            "-OriginalDocumentID=",
            "-DocumentAncestors=",
            "-photoshop:all=",
            target_image_path.absolute().as_posix(),
        ],
        stderr=subprocess.STDOUT,
    )

    print("├╼ Adding metadata")
    subprocess.check_call(
        [
            "exiftool",
            "-overwrite_original",
            *(f"-Subject={tag}" for tag in source_image_data["image_tags"]),
            f"-BaseURL={source_image_data['image_url']}",
            f"-ImageTitle={source_image_data['image_title']}",
            f"-OriginalFileName={source_image_data['original_image_filename']}",
            f"-ImageUniqueID={source_image_data['image_id']}",
            f"-SeriesNumber={source_image_data['image_index']}",
            f"-AssetID={source_image_data['image_slug']}",
            f"-Nickname={source_author_data['artstation_username'] if is_artstation else source_author_data['pixiv_username']}",
            f"-CreatorTool={'artstation' if is_artstation else 'pixiv'}",
            target_image_path.absolute().as_posix(),
        ],
        stderr=subprocess.STDOUT,
    )

    return target_image_path


config.load()

print(f"{L_PURPLE}Fetching artist data using gallery-dl{NC}\n")

for url__ in artstation_urls:
    print(f"\n╭─{CYAN} Processing {url__}{NC}")

    with io.StringIO() as in_memory_file:
        job.DataJob(url__, resolve=True, file=in_memory_file, ensure_ascii=False).run()
        loaded_json: list[list[int | dict[str, Any]]] = json.loads(in_memory_file.getvalue())

    extracted_author_info: AuthorInfo | None = None
    extracted_images: list[ImageInfo] = []

    for result_array in loaded_json:
        if result_array[0] != Message.Url:
            # Only parse 'Url' packets
            continue

        print(f"├╍ Found {result_array[1]}")

        raw_data = cast(dict[str, Any], result_array[2])

        asset_type = cast(dict[str, Any], raw_data.get("asset"))["asset_type"]
        if asset_type != "image":
            print(f"├╌{L_YELLOW} Skipping asset because it's not an image ({asset_type}){NC}")
            continue

        if extracted_author_info is None:
            extracted_author_info = user_data_from_artstation(cast(dict[str, Any], raw_data.get("user")))

        extracted_image_info: ImageInfo = image_info_from_artstation(raw_data)
        extracted_image_info["image_url"] = cast(str, result_array[1])
        extracted_image_info["image_url_core"] = extract_image_url_core(extracted_image_info["image_url"])
        extracted_images.append(extracted_image_info)

    if extracted_author_info is None:
        if wait_for_YN(f"Could not extract user info for {url__}, ignore?", False):
            continue
        err_exit("exit")

    merged_userdata = find_or_create_author_info(extracted_author_info, True)

    print(f"├╼{CYAN} Filtering images for {url__}{NC}")

    has_matches_in_direct_links = False  # pylint: disable=invalid-name
    filtered_extracted_images = []
    directly_matched_images = []
    for image_info in extracted_images:
        has_direct_match = image_info["image_url_core"] in direct_artstation_url_cores

        has_matches_in_direct_links = has_matches_in_direct_links or has_direct_match
        direct_artstation_url_cores.discard(image_info["image_url_core"])

        w = image_info["image_width"]
        h = image_info["image_height"]

        if (w < 1920) or (h < 1080):
            print(
                f"├╌{L_YELLOW} Skipping image because it's too small (w: {L_RED if w < 1920 else L_YELLOW}{w}{L_YELLOW}, h: {L_RED if h < 1080 else L_YELLOW}{h}{L_YELLOW}){NC}"
            )
            continue

        if has_direct_match:
            directly_matched_images.append(image_info)

        if not has_matches_in_direct_links:
            # We don't care about all the filtered images if there is a direct match
            filtered_extracted_images.append(image_info)

    if has_matches_in_direct_links:
        if len(directly_matched_images) == 0:
            print(f"╰╴{YELLOW} Nothing left after filtering small images (has direct matches){NC}")
        else:
            print(f"├╼ Adding {len(directly_matched_images)} url(s) to download queue (direct matches)")
            grouped_urls += ((merged_userdata, image_data) for image_data in directly_matched_images)
            print(f"╰─{L_GREEN}OK{NC}")
    else:
        if len(filtered_extracted_images) == 0:
            print(f"╰╴{YELLOW} Nothing left after filtering small images (all){NC}")
        else:
            print(f"├╼ Adding {len(filtered_extracted_images)} url(s) to download queue (all)")
            grouped_urls += ((merged_userdata, image_data) for image_data in filtered_extracted_images)
            print(f"╰─{L_GREEN}OK{NC}")

if len(direct_artstation_url_cores) > 0:
    print(direct_artstation_url_cores)
    err_exit("Some direct urls left after processing")

print(f"{L_PURPLE}Downloading {len(grouped_urls)} images{NC}\n")

for user_info, image_info in grouped_urls:
    download_dir = Path(TEMPORARY_DIRECTORY_PATH, get_folder_name_for_author(user_info))
    download_dir.mkdir(parents=True, exist_ok=True)

    url = image_info["image_url"]

    downloaded_file_extension = remove_url_params(url).split(".")[-1]
    target_temp_download_filepath = Path(download_dir, get_file_name_for_image(image_info, downloaded_file_extension))

    print(f"\n{BLUE}┌ Downloading {url} to {target_temp_download_filepath}{NC}")

    r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=60 * 1000)
    if not r.ok:
        err_exit(f"Error downloading {url}")

    target_temp_download_filepath.write_bytes(r.content)

    post_process_image(target_temp_download_filepath, image_info, user_info, True)

    print(f"╰─{L_GREEN}OK{NC}")

PENDING_ARTSTATION_IMAGES_FILE_LOCATION.write_text("", encoding="utf-8")

print(f"\n{L_PURPLE}Moving images{NC}")

for downloaded_author_dir in TEMPORARY_DIRECTORY_PATH.iterdir():
    author_dir_name = downloaded_author_dir.name
    target_author_dir = Path(TARGET_DIRECTORY_PATH, author_dir_name)

    print(f"\n╭{BLUE} Moving images for {author_dir_name}{NC}")

    moved_images = 0  # pylint: disable=invalid-name
    for image_path in downloaded_author_dir.iterdir():
        target_path = Path(target_author_dir, image_path.name)
        if target_path.exists():
            print(f"├╼ {L_YELLOW}Target image ({target_path}) already exists, please check manually{NC}")
            continue

        shutil.move(image_path.absolute().as_posix(), target_path.absolute().as_posix())
        moved_images += 1

    print(f"╰{L_GREEN} Moved {moved_images} images for {author_dir_name}{NC}")
    downloaded_author_dir.rmdir()

print(f"\n{L_GREEN}============ Artstation DONE!{NC}")

kks = pykakasi.kakasi()


async def google_translate(input_: str):
    async with Translator() as translator:
        result = await translator.translate(input_, dest="en")
        return result.text


def name_to_human_readable(name: str):
    name = name.strip()

    if len(name) == 0:
        return name

    if name.isascii():
        return name

    transliterated = "".join([item["passport"] for item in kks.convert(name)])

    if transliterated.isascii():
        return transliterated

    return asyncio.run(google_translate(name))


print(f"\n{L_PURPLE}Moving pixiv images{NC}")

for author_dir in PIXIV_IMAGES_SOURCE_DIR.iterdir():
    parts = author_dir.name.split("_")  # <author_name>_id<id>

    author_name = "_".join(parts[:-1])  # pylint: disable=invalid-name
    pixiv_id = int(parts[-1].replace("id", ""))

    author_name_readable = name_to_human_readable(author_name)

    print(f"\n╭─{BLUE}Moving images for {author_name_readable}{NC}")

    parsed_user_data = user_data_from_pixiv(author_name, author_name_readable, pixiv_id)
    merged_userdata = find_or_create_author_info(parsed_user_data, False)

    target_author_dir = Path(TARGET_DIRECTORY_PATH, get_folder_name_for_author(merged_userdata))
    existing_images_in_target = list(target_author_dir.iterdir())

    moved_images = 0

    for image_path in author_dir.iterdir():
        print("│")
        print(f"├╼ Processing {image_path}")

        image_title = ""  # pylint: disable=invalid-name

        if "+" in image_path.stem:  # New format: <id>+<title>+<part>
            split = image_path.stem.split("+")
            if len(split) != 3:
                err_exit(f"Wrong number of parts for {image_path.stem}, expected 3 (<id>+<title>+<part>)")

            image_id, image_title, image_part = split

            image_part_int = int(image_part)
            image_id_int = int(image_id)
        else:  # Old format: <id>_p<part>
            split = image_path.stem.split("_")

            if len(split) != 2:
                err_exit(f"Wrong number of parts for {image_path.stem}, expected 2 (<id>_p<part>)")

            image_id, image_part = split

            image_part_int = int(image_part.strip("p"))
            image_id_int = int(image_id)

        image_title_readable = name_to_human_readable(image_title)
        image_slug = (
            re.compile(" *").sub(
                "-", " ".join([ch if ch.isalpha() else " " for ch in image_title_readable.lower().strip()])
            )
            if len(image_title_readable) > 0
            else ""
        )

        image_info = image_info_from_pixiv(image_title, image_slug, image_id_int, image_part_int)

        existing_images = [
            existing_image
            for existing_image in existing_images_in_target
            if image_info["image_id"] in existing_image.name
        ]

        if len(existing_images) > 1:
            err_exit(f"Several images found in target ({target_author_dir}) for id {image_info['image_id']}")

        if len(existing_images) > 0:
            print(
                f"├╼ {L_YELLOW}Target image (id: {image_info['image_id']} | source path: {image_path}) already exists, replacing with our version{NC}"
            )
            existing_images[0].unlink()

        processed_image_path = post_process_image(image_path, image_info, merged_userdata, False)

        shutil.move(
            processed_image_path.absolute().as_posix(),
            Path(target_author_dir, get_file_name_for_image(image_info, "jpg")).absolute().as_posix(),
        )
        moved_images += 1

    print(f"╰{L_GREEN} Moved {moved_images} images from {author_dir}{NC}")
    author_dir.rmdir()

print(f"\n{L_GREEN}============ Pixiv DONE!{NC}")

print(f"\n╭─{L_PURPLE}Setting creation date tags{NC}")

dirs_to_check_nested = [list(dir_.rglob("*")) for dir_ in DATETIME_UPDATE_DIRS]
dirs_to_check = [dir__ for dirlist in dirs_to_check_nested for dir__ in dirlist if dir__.is_dir()]


directory_update_time_cache = json.loads(
    MTIME_CACHE_FILE.read_text(encoding="utf-8") if MTIME_CACHE_FILE.exists() else "{}"
)

for file_or_dir in dirs_to_check:
    if file_or_dir.is_dir():
        path_str = file_or_dir.resolve().absolute().as_posix()
        mtime = file_or_dir.stat().st_mtime

        last_recorded_modification_dt = directory_update_time_cache.get(path_str, "")
        if last_recorded_modification_dt == mtime:
            print(f"├╼ {GRAY}Skipping {file_or_dir} (unchanged: {datetime.datetime.fromtimestamp(mtime)}) {NC}")
            continue

        directory_update_time_cache[path_str] = mtime

        print(f"├╼ {CYAN}Processing {file_or_dir}{NC}")
        # Try FileCreateDate
        r = subprocess.call(
            [
                "exiftool",
                "-if",
                "not $DateTimeOriginal",
                "-MWG:DateTimeOriginal<FileCreateDate"  # https://exiftool.org/TagNames/MWG.html
                "-overwrite_original",
                file_or_dir.absolute().as_posix(),
            ],
            stderr=subprocess.STDOUT,
        )
        if r == 1:
            err_exit("")
        # Try FileModifyDate
        r = subprocess.call(
            [
                "exiftool",
                "-if",
                "not $DateTimeOriginal",
                "-MWG:DateTimeOriginal<FileModifyDate",
                "-overwrite_original",
                file_or_dir.absolute().as_posix(),
            ],
            stderr=subprocess.STDOUT,
        )
        if r == 1:
            err_exit("")

MTIME_CACHE_FILE.write_text(json.dumps(directory_update_time_cache), encoding="utf-8")

print(f"╰─{L_GREEN}OK{NC}")

print(f"\n{L_PURPLE}Converting images to jpg if necessary{NC}")

for file_or_dir in TARGET_DIRECTORY_PATH.rglob("*"):
    if file_or_dir.is_file() and file_or_dir.name != AUTHOR_INFO_FILENAME:
        convert_to_jpg_if_needed(file_or_dir)

print(f"\n{L_GREEN}============ Conversion DONE!{NC}")


print(f"\n╭─{L_PURPLE}Generating OPML feed{NC}")

latest_exported_opml_path: Path | None = None
latest_exported_opml_date: datetime.datetime = datetime.datetime(year=1, month=1, day=1)

for exported_opml_path in FEEDER_EXPORTS_PATH.iterdir():
    if exported_opml_path.name == ARTSTATION_OPML_EXPORT_FILENAME:
        continue

    export_date = datetime.datetime.strptime(exported_opml_path.stem.replace("feeder-export-", ""), "%Y-%m-%d-%f")
    if export_date > latest_exported_opml_date:
        latest_exported_opml_date = export_date
        latest_exported_opml_path = exported_opml_path

if latest_exported_opml_path is None:
    err_exit("Couldn't find latest feeder export path")


def get_artstation_rss_url(a_info: AuthorInfo):
    return f"https://{a_info['artstation_username']}.artstation.com/rss"


print(f"├╼ {GREEN}Using {latest_exported_opml_path} as opml source {NC}")

loaded_opml = ET.parse(latest_exported_opml_path)

existing_artstation_section = [
    section for section in loaded_opml.getroot().findall("./body/outline") if section.get("text") == "Artstation"
][0]

existing_author_rss_feeds: set[str | None] = {elem.get("xmlUrl") for elem in existing_artstation_section.iter()}
authors_to_export_filtered = [
    author_info
    for author_info in AUTHOR_INFOS
    if len(author_info["artstation_username"]) > 0
    and get_artstation_rss_url(author_info) not in existing_author_rss_feeds
]

if len(authors_to_export_filtered) == 0:
    print(f"╰─{L_GREEN}Nothing to export{NC}")

print(f"├╼ {CYAN}Exporting {len(authors_to_export_filtered)} authors {NC}")

exported_opml_contents = f"""
<?xml version="1.0" encoding="UTF-8"?>
<opml version="1.1" xmlns:feeder="https://nononsenseapps.com/feeder">
  <head>
    <title>
      Feeder
    </title>
  </head>
  <body>
    <outline title="Artstation" text="Artstation">
    {"\n".join(f'    <outline feeder:notify="false" feeder:fullTextByDefault="false" feeder:openArticlesWith="" feeder:alternateId="false" title="{author_info["artstation_username"]} on artstation" text="{author_info["artstation_username"]} on artstation" type="rss" xmlUrl="{get_artstation_rss_url(author_info)}"/>' for author_info in authors_to_export_filtered)}
    </outline>
  </body>
</opml>
""".strip()

Path(FEEDER_EXPORTS_PATH, ARTSTATION_OPML_EXPORT_FILENAME).write_text(exported_opml_contents, encoding="utf-8")
print(f"╰─{L_GREEN}OK{NC}")
