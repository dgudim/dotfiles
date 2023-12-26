from dataclasses import dataclass
import json
from typing import Any
import re
import os


illegal_chars = re.compile(r"[^\w\s-]")


def escape_name(name):
    name = (name[:30] + '..') if len(name) > 30 else name
    return illegal_chars.sub("_", name)


def mkdir(path):
    if not os.path.exists(path):
        os.mkdir(path)


def write_item(name: str, item: str, file):
    if item != None:
        file.write(f"- {name}: [[{escape_name(item)}]]\n")


def write_list(name: str, listt: list, file):
    file.write(f"- {name}:\n")
    for item in listt:
        file.write(f"    - [[{escape_name(item)}]]\n")


def get_file(name: str):
    _file = open(f"./{escape_name(name)}.md", "wt")
    _file.write(f"# {name}\n")
    return _file


@dataclass
class Bookmark:
    tags: list[str]
    title: str
    url: str

    def write_to_file(self):
        file_ = get_file(self.title)
        write_item("url", self.url, file_)
        write_item("title", self.title, file_)
        write_list("tags", self.tags, file_)
        file_.close()


def parse_level(data: Any, bookmarks_l: list[Bookmark]):
    for key, value in data.items():
        if key == "children":
            for child in value:
                is_bookmark = child["type"] == "text/x-moz-place"
                if is_bookmark:
                    bookmarks_l.append(
                        Bookmark(
                            title=child["title"],
                            url=child["uri"],
                            tags=child["tags"].split(
                                ",") if "tags" in child else [],
                        )
                    )
                else:
                    parse_level(child, bookmarks_l)


with open("bookmarks.json") as json_file:
    json_data = json.load(json_file)
    bookmarks: list[Bookmark] = []
    parse_level(json_data, bookmarks)
    for bookmark in bookmarks:
        bookmark.write_to_file()
