#!/usr/bin/env python3


import os
from pathlib import Path

base_path = Path("~/.config/PrusaSlicer").expanduser().absolute()
scripts_path = Path(base_path, "scripts")

scripts_path.mkdir(exist_ok=True)

wanted_scripts = [
    "https://github.com/TengerTechnologies/FeatureBasedGcodeSettings",
    "https://github.com/TengerTechnologies/Fuzzyficator",
    "https://github.com/TengerTechnologies/Smoothificator",
    "https://github.com/TengerTechnologies/Bricklayers",
    "https://github.com/TengerTechnologies/NonPlanarInfill"
]

script_folders = [url.split('/')[-1] for url in wanted_scripts]

updated_folders = []
for script_dir in scripts_path.iterdir():
    if script_dir.name not in script_folders:
        print(f"Skipping unknown folder: {script_dir.name}") 
        continue
    print(f"Updating {script_dir.name}")
    os.system(f"cd {script_dir.absolute().as_posix()} && git pull")
    updated_folders.append(script_dir.name)

for wanted_script, wanted_script_folder in zip(wanted_scripts, script_folders):
    if wanted_script_folder in updated_folders:
        print(f"{wanted_script_folder} Already present")
        continue
    print(f"Cloning {wanted_script_folder}")
    os.system(f"cd {scripts_path} && git clone {wanted_script}")


