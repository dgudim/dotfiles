#!/usr/bin/python

import sys
import os
import requests

p_input = sys.argv[-1].strip()

split = p_input.split("/")
repo = split[0]
package = split[1]

try:
    if repo == "aur":
        arch_repo_api_url = f"https://aur.archlinux.org/rpc/v5/info?arg[]={package}"
        results = requests.get(arch_repo_api_url, timeout=3).json()["results"]
        if len(results) == 0:
            raise Exception(f"Package not found: {package}")
        upstream = str(results[0]["URL"])
    elif repo in ["extra", "multilib", "core"]:
        try:
            arch_repo_api_url = f"https://archlinux.org/packages/{repo}/x86_64/{package}/json"
            upstream = str(requests.get(arch_repo_api_url, timeout=3).json()["url"])
        except Exception:
            arch_repo_api_url = f"https://archlinux.org/packages/{repo}/any/{package}/json"
            upstream = str(requests.get(arch_repo_api_url, timeout=3).json()["url"])
    else:
        os.system(f'kdialog --detailederror "No handler for repo" "{repo}"')
        sys.exit(0)

    if upstream.find("github.com") != -1:
        github_repo_api_url = (
            upstream.replace("github.com", "api.github.com/repos") + "/releases"
        )
        changelog = str(
            requests.get(github_repo_api_url, timeout=3).json()[0]["body"]
        ).strip()
        os.system(f'kdialog --msgbox "{changelog}"')

    else:
        os.system(f'kdialog --error "No handler for upstream: {upstream}"')
except Exception as e:
    os.system(f'kdialog --detailederror "An error occurred" "{e}"')
