# Mobile Verification Toolkit (MVT)
# Copyright (c) 2021-2022 Claudio Guarnieri.
# Use of this software is governed by the MVT License 1.1 that can be found at
#   https://license.mvt.re/1.1/

import requests
from packaging import version

from .version import MVT_VERSION


def check_for_updates() -> str:
    res = requests.get("https://pypi.org/pypi/mvt/json")
    data = res.json()
    latest_version = data.get("info", {}).get("version", "")

    if version.parse(latest_version) > version.parse(MVT_VERSION):
        return latest_version

    return ""
