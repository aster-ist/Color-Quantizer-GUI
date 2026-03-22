"""Module entry point for ``python -m color_quantizer_gui``."""

try:
    from .app import main
except ImportError:
    # PyInstaller may execute this file as a top-level script.
    from color_quantizer_gui.app import main


if __name__ == "__main__":
    main()
