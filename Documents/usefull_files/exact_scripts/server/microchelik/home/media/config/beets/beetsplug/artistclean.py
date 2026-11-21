"""Clean up artist names: regex replacements from the config, then strip
diacritics from Latin letters (é → e, ø → o). Other scripts are left alone.
Runs on import (so the library has the clean values too) and before every
tag write (covers modify, mbsync, write). `beet artistclean [query]` applies
it to items already in the library, matched or not."""
import re
import unicodedata

from beets import ui
from beets.plugins import BeetsPlugin

# Latin letters that don't decompose into letter + mark
EXTRA = str.maketrans({"ø": "o", "Ø": "O", "ł": "l", "Ł": "L", "đ": "d", "Đ": "D", "ð": "d", "Ð": "D",
                       "æ": "ae", "Æ": "Ae", "œ": "oe", "Œ": "Oe", "ß": "ss", "þ": "th", "Þ": "Th"})


def strip_latin_diacritics(s):
    out = []
    for ch in unicodedata.normalize("NFD", s):
        if unicodedata.combining(ch) and out and unicodedata.name(out[-1], "").startswith("LATIN"):
            continue  # a mark on a Latin letter
        out.append(ch)
    return unicodedata.normalize("NFC", "".join(out)).translate(EXTRA)


class ArtistClean(BeetsPlugin):
    def __init__(self):
        super().__init__()
        self.config.add({
            "fields": ["artist", "artists", "artist_sort", "artists_sort",
                       "artist_credit", "artists_credit",
                       "albumartist", "albumartists", "albumartist_sort",
                       "albumartists_sort", "albumartist_credit", "albumartists_credit"],
            "replace": {},
        })
        self.fields = self.config["fields"].as_str_seq()
        self.rules = [(re.compile(p), str(r)) for p, r in self.config["replace"].get(dict).items()]
        self.register_listener("import_task_apply", self.on_import)
        self.register_listener("write", self.on_write)

    def clean(self, value):
        if isinstance(value, list):
            return [self.clean(v) for v in value]
        if not isinstance(value, str):
            return value
        for pattern, repl in self.rules:
            value = pattern.sub(repl, value)
        return strip_latin_diacritics(value)

    def cleaned(self, data):
        """Fields of `data` whose clean value differs."""
        return {f: c for f in self.fields
                if f in data and (c := self.clean(data[f])) != data[f]}

    def on_import(self, session, task):
        for item in task.imported_items():
            item.update(self.cleaned(item))

    def on_write(self, item, path, tags):
        changes = self.cleaned(tags)
        if changes:
            tags.update(changes)
            item.update(changes)  # keep the library in step with the file
            if item.id and item._db:
                item.store()

    def commands(self):
        cmd = ui.Subcommand("artistclean", help="clean artist names in the library and files")
        cmd.parser.add_option("-p", "--pretend", action="store_true", help="only show changes")

        def run(lib, opts, args):
            for item in lib.items(args):
                changes = self.cleaned(item)
                if not changes:
                    continue
                for f, v in changes.items():
                    ui.print_(f"{item.path.decode(errors='replace')}: {f}: {item[f]!r} -> {v!r}")
                if not opts.pretend:
                    item.update(changes)
                    item.try_sync(write=True, move=False)

        cmd.func = run
        return [cmd]
