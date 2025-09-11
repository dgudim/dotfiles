# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileCopyrightText: 2013-2022 Campbell Barton
# SPDX-FileCopyrightText: 2024 Mikhail Rachinskiy

_data = []


def update(*args):
    _data[:] = args


def info():
    return tuple(_data)


def clear():
    _data.clear()
