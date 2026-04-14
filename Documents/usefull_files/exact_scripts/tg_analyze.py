#!/usr/bin/venv python3

from collections import defaultdict
import datetime
from enum import StrEnum
import json

import re

from attr import dataclass
import matplotlib.pyplot as plt
import numpy as np

msgs = json.load(open("./result.json", "r", encoding="utf-8"))["messages"]


@dataclass
class Message:
    text: str
    date: datetime.datetime
    user: str


class MessageType(StrEnum):
    MIXED = "mixed"
    BEL = "bel"
    RUS = "rus"
    ENG = "eng"
    SYMBOLIC = "symbolic"


START_DATE = datetime.datetime(year=2025, month=1, day=1)

matched_words_per_user: dict[str, dict[str, list[Message]]] = {}
word_match_lists = [
    ["<call_saul_0000>"],
    ["🌚"],
    [" extra"],
    [" alright"],
    ["xd", "xdd", "xddd", "xdddd"],
    [" huh"],
    [" lol"],
    [" good"],
    [" nice"],
    [")"],
    [":)"],
    [" damn", " daaamn", " daamn", " daymn"],
    [" horny"],
    [" i'm sorry", " i am sorry"],
    [" uh huh"],
    [" great"],
    [" uhh", " uhhh", " uhhhh", " uhhhhh"],
]

per_day_messages: dict[datetime.date, list[Message]] = defaultdict(list)
per_day_message_lang_percentages: dict[datetime.date, dict[MessageType, float]] = {}


def has_cyrillic(text__: str):
    return bool(re.search("[а-яА-Я]", text__))


def has_latin(text__: str):
    return bool(re.search("[a-zA-Z]", text__))


def classify_message(msg__: str, usr: str):
    if has_cyrillic(msg__):
        if has_latin(msg__):
            return MessageType.MIXED
        if usr == "Аня":
            return MessageType.BEL
        return MessageType.RUS

    if has_latin(msg__):
        return MessageType.ENG

    return MessageType.SYMBOLIC


total_call_duration = 0

for msg in msgs:
    dt = datetime.datetime.fromtimestamp(int(msg["date_unixtime"]))

    if dt < START_DATE:
        continue

    if msg["type"] == "service":
        text = "<call_saul_0000>"
        username = msg["actor"]
        total_call_duration += msg.get("duration_seconds", 0)
    else:
        username = msg["from"]
        text = msg["text"]

    if isinstance(text, list):
        text_ = ""  # pylint: disable=invalid-name
        for item in text:
            if isinstance(item, str):
                text_ += f" {item}"
                continue
            if item["type"] == "link":
                # Skip links
                continue
            text_ += f" {item['text']}"
        text = text_  # pylint: disable=invalid-name

    message = Message(text, dt, username)

    per_day_messages[dt.date()].append(message)

    for match_list in word_match_lists:
        for word in match_list:
            if word in f" {text.lower()} " or text.lower() == word:
                user_stats = matched_words_per_user.get(username, {})
                word_group_stats = user_stats.get(match_list[0], [])
                word_group_stats.append(message)
                user_stats[match_list[0]] = word_group_stats
                matched_words_per_user[username] = user_stats
                break

print(f"Total call duration: {total_call_duration}")

for date, msgs in per_day_messages.items():
    per_type_counts: dict[MessageType, int] = defaultdict(int)

    for msg in msgs:
        per_type_counts[classify_message(msg.text, msg.user)] += 1

    total_messages = len(msgs)
    per_day_message_lang_percentages[date] = {}

    for type__, count in per_type_counts.items():
        per_day_message_lang_percentages[date][type__] = count / total_messages * 100

date_axis_data = list(per_day_message_lang_percentages.keys())
fig, ax = plt.subplots()

for m_type in [
    MessageType.MIXED,
    MessageType.ENG,
    MessageType.BEL,
    MessageType.RUS,
    MessageType.SYMBOLIC,
]:
    x_axis_data = [
        point_data.get(m_type, 0)
        for point_data in per_day_message_lang_percentages.values()
    ]
    line = ax.plot(np.array(date_axis_data), x_axis_data)
    line[0].set_label(m_type)


ax.set(xlabel="date", ylabel="%", title="message types")
ax.grid()
ax.legend()
plt.show()

graphs: dict[str, list[tuple[str, list[datetime.date], list[int]]]] = defaultdict(list)
users = matched_words_per_user.keys()

for user, word_groups in matched_words_per_user.items():
    for word_group_key, messages in word_groups.items():
        xy: dict[datetime.date, int] = defaultdict(int)
        for message in messages:
            xy[message.date.date()] += 1
        graphs[word_group_key].append((user, list(xy.keys()), list(xy.values())))

for graph_name, graph_datasets in graphs.items():
    fig, ax = plt.subplots()

    totals_str = " | ".join(
        f"{dataset[0]}: {sum(dataset[2])}" for dataset in graph_datasets
    )

    # union_dates = set(date_ for dataset in graph_datasets for date_ in dataset[0])

    # for dataset in graph_datasets:
    #     for u_date in union_dates:
    #         if u_date not in dataset[0]:
    #             dataset[0].append(u_date)
    #             dataset[1].append(0)

    for dataset, index in zip(graph_datasets, range(len(graph_datasets))):
        bar = ax.bar(
            np.array(dataset[1]), np.array(dataset[2]) * (-1 if index % 2 else 1)
        )
        bar.set_label(dataset[0])

    ax.set(xlabel="date", ylabel="count", title=f"{graph_name} ({totals_str})")
    ax.grid()
    ax.legend()
    plt.show()
