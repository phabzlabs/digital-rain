"""The name Windows shows for the .scr in the screensaver picker.

The picker reads string resource 1 of the .scr and falls back to the file name
(MatrixRain), so build.ps1 embeds this name as string 1 with PyInstaller's
--resource FILE,6,1,0 (RT_STRING, block 1, language neutral).

Usage: python tools/build/scr_name.py write FILE   write the string table block
       python tools/build/scr_name.py check SCR    exit 1 unless SCR's string 1 is the name
"""

import struct
import sys

NAME = "Digital Rain"


def block(strings):
    """One RT_STRING block: 16 entries, each a UTF-16 length then the characters.
    String id n lives in block n // 16 + 1 at index n % 16."""
    out = b""
    for i in range(16):
        s = strings.get(i, "")
        out += struct.pack("<H", len(s)) + s.encode("utf-16-le")
    return out


def loaded_name(path):
    import ctypes
    from ctypes import wintypes

    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    u32 = ctypes.WinDLL("user32", use_last_error=True)
    k32.LoadLibraryExW.restype = wintypes.HMODULE
    k32.LoadLibraryExW.argtypes = [wintypes.LPCWSTR, wintypes.HANDLE, wintypes.DWORD]
    k32.FreeLibrary.argtypes = [wintypes.HMODULE]
    u32.LoadStringW.argtypes = [wintypes.HMODULE, wintypes.UINT, wintypes.LPWSTR, ctypes.c_int]
    mod = k32.LoadLibraryExW(path, None, 0x2)  # LOAD_LIBRARY_AS_DATAFILE
    if not mod:
        raise OSError(f"cannot load {path}")
    try:
        buf = ctypes.create_unicode_buffer(256)
        n = u32.LoadStringW(mod, 1, buf, 256)
        return buf.value[:n]
    finally:
        k32.FreeLibrary(mod)


def main(argv):
    if len(argv) != 3 or argv[1] not in ("write", "check"):
        print(__doc__)
        return 2
    if argv[1] == "write":
        with open(argv[2], "wb") as fh:
            fh.write(block({1: NAME}))
        return 0
    got = loaded_name(argv[2])
    print(f"string 1 of {argv[2]}: {got!r}")
    return 0 if got == NAME else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
