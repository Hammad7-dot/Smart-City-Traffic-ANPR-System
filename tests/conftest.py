import os

# Must run before any test imports torch/easyocr transitively (see CLAUDE.md:
# "Set KMP_DUPLICATE_LIB_OK=TRUE ... before running anything that imports torch").
# pipeline/run_pipeline.py sets this itself, but test modules that import
# pipeline.ocr directly (bypassing run_pipeline) need it set here instead.
os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")
