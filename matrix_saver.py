"""Entry point of the Windows .scr (build.ps1 freezes this file with PyInstaller) and of
`python matrix_saver.py` from a checkout. The code is in digital_rain/windows/matrix_saver.py."""

from digital_rain.windows.matrix_saver import main

if __name__ == "__main__":
    main()
