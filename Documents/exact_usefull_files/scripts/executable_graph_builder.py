#!/usr/bin/python

import os
import mutagen
from dataclasses import dataclass
from enum import Enum
import re

from colorama import Fore
from colorama import Style

def walk_dir(dir_path: str):
    for root, _, files in os.walk(dir_path):
        for filename in files:
            process_file(os.path.join(root, filename));

illegal_chars = re.compile(r'[^\w\s-]');
def escape_name(name):
    return illegal_chars.sub("_", name);

def mkdir(path):
    if not os.path.exists(path):
        os.mkdir(path);
                    
def writeItem(name: str, item: str, file):
    if item != None:
        file.write(f"- {name}: [[{escape_name(item)}]]\n");
  
def writeSet(name: str, sett: set, file):
    file.write(f"- {name}:\n");
    for item in sett:
        file.write(f"    - [[{escape_name(item)}]]\n");

def getFile(subdir: str, name: str):
    _file = open(f"./{subdir}/{escape_name(name)}.md", "wt");
    _file.write(f"# {name}\n");
    return _file;

@dataclass
class SongItem:
    """Class for storing metadata of a single music title"""
    path: str
    title: str
    song_id: str
    genre: str
    year: str
    album: str
    artists: set
    
    def writeToFile(self, subdir):
        music_file = getFile(subdir, self.song_id);
        writeItem("genre", self.genre, music_file);
        writeItem("year", self.year, music_file);
        writeItem("album", self.album, music_file);
        writeSet("artists", self.artists, music_file);
        music_file.close();


@dataclass
class GenreItem:
    """Class for storing metadata of a single genre"""
    genre: str
    song_ids: set
    years: set
    albums: set
    artists: set

    def writeToFile(self, subdir):
        genre_file = getFile(subdir, self.genre);
        writeSet("songs", self.song_ids, genre_file);
        writeSet("albums", self.albums, genre_file);
        writeSet("artists", self.artists, genre_file);
        writeSet("years", self.years, genre_file);
        genre_file.close();
        

@dataclass
class ArtistItem:
    """Class for storing metadata of a single artist"""
    artist: str
    genres: set
    song_ids: set
    years: set
    albums: set
    
    def writeToFile(self, subdir):
        artist_file = getFile(subdir, self.artist);
        writeSet("songs", self.song_ids, artist_file);
        writeSet("albums", self.albums, artist_file);
        writeSet("years", self.years, artist_file);
        writeSet("genres", self.genres, artist_file);
        artist_file.close();

@dataclass
class YearItem:
    """Class for storing metadata of a single year"""
    year: str
    artists: set
    genres: set
    song_ids: set
    albums: set
    
    def writeToFile(self, subdir):
        year_file = getFile(subdir, self.year);
        writeSet("songs", self.song_ids, year_file);
        writeSet("albums", self.albums, year_file);
        writeSet("artists", self.artists, year_file);
        writeSet("genres", self.genres, year_file);
        year_file.close();

@dataclass
class AlbumItem:
    """Class for storing metadata of a single year"""
    album: str
    years: set
    artists: set
    genres: set
    song_ids: set
    
    def writeToFile(self, subdir):
        album_file = getFile(subdir, self.album);
        writeSet("songs", self.song_ids, album_file);
        writeSet("years", self.years, album_file);
        writeSet("artists", self.artists, album_file);
        writeSet("genres", self.genres, album_file);
        album_file.close();


unknown_prefix = "Unknown";

class TagExclusionStrategy(Enum):
    WARN_INCLUDE_IF_EMPTY = "wi"
    INCLUDE = "ji"
    WARN_EXCLUDE_IF_EMPTY = "we"
    EXCLUDE_IF_EMPTY = "wee"
    EXCLUDE = "je"
    
class Tag(Enum):
    ARTIST = "artist"
    TITLE = "title"
    ALBUM = "album"
    GENRE = "genre"
    YEAR = "year"
    
    def isIncluded(self, file_path: str, strategy_map, is_tag_empty):        
        strategy = strategy_map.get(self);
        
        exclude = (strategy == TagExclusionStrategy.EXCLUDE or 
                   (is_tag_empty and strategy == (TagExclusionStrategy.WARN_EXCLUDE_IF_EMPTY or 
                                                  strategy == TagExclusionStrategy.EXCLUDE_IF_EMPTY)));
        
        
        if is_tag_empty and (strategy == TagExclusionStrategy.WARN_EXCLUDE_IF_EMPTY or strategy == TagExclusionStrategy.WARN_INCLUDE_IF_EMPTY):
            print(f"{Style.BRIGHT}{Fore.MAGENTA}{unknown_prefix} {self.value}: {file_path} {Style.RESET_ALL}, {'excluding' if exclude else 'including anyway'}");
            
        return not exclude;
    
tag_map = {
    # TPE1 = track artist, TPE2 = various artists
    Tag.ARTIST: ["artist", "©ART", "aART", "TPE1", "TPE2"],
    Tag.TITLE: ["title", "©nam", "TIT2"],
    Tag.ALBUM: ["album", "©alb", "TALB"],
    Tag.GENRE: ["genre", "©gen", "TCON"],
    Tag.YEAR: ["date", "©day", "TDRC"],
}

tag_exclusion_strategy = {
    Tag.ARTIST: TagExclusionStrategy.WARN_EXCLUDE_IF_EMPTY,
    Tag.TITLE: TagExclusionStrategy.WARN_EXCLUDE_IF_EMPTY,
    Tag.ALBUM: TagExclusionStrategy.WARN_EXCLUDE_IF_EMPTY,
    Tag.GENRE: TagExclusionStrategy.WARN_EXCLUDE_IF_EMPTY,
    Tag.YEAR: TagExclusionStrategy.EXCLUDE,
}

include_single_albums = False;
include_extra_artists = False;

def get_tag(metadata, tag: Tag, file_path: str):
    
    tag_str = f"{unknown_prefix} {tag.value}"
    tag_empty = True;
    
    if metadata != None:
        for key in tag_map.get(tag):
            try:
                if key in metadata:
                    tag_str = str(metadata[key][0]).strip();
                    tag_empty = False;
                    break;
            except:
                print(f"{Style.BRIGHT}{Fore.RED}Err getting {key} from {metadata}{Style.RESET_ALL}");
            
    return tag_str, tag.isIncluded(file_path, tag_exclusion_strategy, tag_empty);

song_id_to_metadata = {}
genre_to_metadata = {}
artist_to_metadata = {}
year_to_metadata = {}
album_to_metadata = {}

remix_feat_regex = re.compile(r"feat\. |ft\. |Ft | remix| edit| cover", re.IGNORECASE)
artists_regex = re.compile(r" & |, | x ");

index: int = 0;
def process_file(file_path: str):
    global index;

    metadata = mutagen.File(file_path);
    if metadata != None:
        #print(f"{Fore.LIGHTGREEN_EX} {index} {file_path}");
        index = index + 1;
    else:
        print(f"{Fore.RED}Error at: {file_path}");
        return;

    artist, include_artist = get_tag(metadata, Tag.ARTIST, file_path);
    title, include_title = get_tag(metadata, Tag.TITLE, file_path);
    album, include_album = get_tag(metadata, Tag.ALBUM, file_path);
    genre, include_genre = get_tag(metadata, Tag.GENRE, file_path);
    year, include_year = get_tag(metadata, Tag.YEAR, file_path);

    album = artist + " - " + album;

    if include_single_albums and album.lower().endswith("single"):
        print(f"{Style.BRIGHT}{Fore.LIGHTBLUE_EX}Skipping single: {file_path} ||| {album}{Style.RESET_ALL}");
        include_album = False;

    if include_extra_artists and include_artist:
        title_parts = re.split(r" \(|\)", title);
        title = title_parts[0];
        if len(title_parts) > 1:
            extra_title = title_parts[1];
            if remix_feat_regex.search(extra_title):
                extra_artist = remix_feat_regex.sub("", extra_title).strip();
                artist = artist + ", " + extra_artist;
            else:
                print(f"{Fore.YELLOW}Don't know how to interpret: '{extra_title}'{Style.RESET_ALL} ({file_path})");
                title = f"{title} {extra_title}";

    artists = set(artists_regex.split(artist));
    song_id = f"{', '.join(artists)} - {title}";

    if song_id in song_id_to_metadata:
        print(f"{Style.BRIGHT}{Fore.BLUE}DUPLICATE: {file_path} ||| {song_id_to_metadata[song_id].path} ({song_id}){Style.RESET_ALL}");

    if include_title:
        song_item = song_id_to_metadata.setdefault(song_id, SongItem(path=file_path, 
                                                                    song_id=song_id,
                                                                    title=title if include_title else None, 
                                                                    genre=genre if include_genre else None, 
                                                                    year=year if include_year else None, 
                                                                    album=album if include_album else None, 
                                                                    artists=artists if include_artist else set()));
    if include_genre:
        genre_item = genre_to_metadata.setdefault(genre, GenreItem(genre=genre, 
                                                                albums=set(), 
                                                                artists=set(), 
                                                                song_ids=set(),
                                                                years=set()));
    
    if include_year:
        year_item = year_to_metadata.setdefault(year, YearItem(year=year, 
                                                            albums=set(),
                                                            artists=set(),
                                                            genres=set(),
                                                            song_ids=set()));
    
    if include_album:
        album_item = album_to_metadata.setdefault(album, AlbumItem(album=album, 
                                                                artists=set(),
                                                                genres=set(),
                                                                song_ids=set(),
                                                                years=set()));
    
    if include_album:
        album_item.song_ids.add(song_id);
        
        if include_genre:
            genre_item.albums.add(album);
            
        if include_year:
            year_item.albums.add(album);
    
    if include_genre:
        genre_item.song_ids.add(song_id);
        
        if include_year:
            year_item.genres.add(genre);
            
        if include_album:
            album_item.genres.add(genre);
    
    if include_year:
        year_item.song_ids.add(song_id);
        
        if include_genre:
            genre_item.years.add(year);
            
        if include_album:
            album_item.years.add(year);
    
    if include_artist:
        for unique_artist in artists:
            artist_item = artist_to_metadata.setdefault(unique_artist, ArtistItem(artist=unique_artist, 
                                                                        genres=set(), 
                                                                        albums=set(),
                                                                        song_ids=set(),
                                                                        years=set()));
            
            if include_title:
                song_item.artists.add(unique_artist);
                artist_item.song_ids.add(song_id);
        
            if include_genre:
                genre_item.artists.add(unique_artist);
                artist_item.genres.add(genre);
                
            if include_album:
                album_item.artists.add(unique_artist);
                artist_item.albums.add(album);
            
            if include_year:
                year_item.artists.add(unique_artist);
                artist_item.years.add(year);
    
walk_dir("/mnt/personal_misc/_Danila/_Music/!~}music{~!");

mkdir("songs");
mkdir("genres");
mkdir("artists");
mkdir("years");
mkdir("albums");

for song_id in song_id_to_metadata:
    song_id_to_metadata[song_id].writeToFile("songs");
    
for genre in genre_to_metadata:
    genre_to_metadata[genre].writeToFile("genres");
    
for artist in artist_to_metadata:
    artist_to_metadata[artist].writeToFile("artists");
    
for year in year_to_metadata:
    year_to_metadata[year].writeToFile("years");
    
for album in album_to_metadata:
    album_to_metadata[album].writeToFile("albums");
