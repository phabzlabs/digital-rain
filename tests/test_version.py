import os
import re
import tomllib

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def test_pyproject_version_matches_the_build_version():
    with open(os.path.join(ROOT, "pyproject.toml"), "rb") as fh:
        declared = tomllib.load(fh)["project"]["version"]
    with open(os.path.join(ROOT, "version_info.txt"), encoding="utf-8") as fh:
        built = re.search(r"StringStruct\('ProductVersion', '([^']+)'\)", fh.read()).group(1)
    assert declared == built
