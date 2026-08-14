# PhotoScan

PhotoScan is a Python-based document scanning application designed to convert photographs of paper documents into clean, scanner-style digital documents. Utilizing classical computer vision techniques, PhotoScan automatically identifies document boundaries, corrects perspective distortions, and normalizes uneven illumination.

## Project Status

The project is currently in **early development / alpha stage**. While core document processing, geometry rectification, and project serialization are fully implemented and validated with automated tests, some components, such as the desktop user interface and third-party OCR integration, are in experimental or optional stages.

### Capability Matrix

| Capability | Status | Notes |
| :--- | :--- | :--- |
| **Document detection** | **Supported** | Automatic edge and contour detection with manual corner override. |
| **Perspective correction** | **Supported** | High-quality rectification using Lanczos4 interpolation. |
| **Local projects** | **Supported** | Saving and loading nondestructive configurations via `.photoscan` files. |
| **Portable projects** | **Supported** | Self-contained, traversal-protected archiving in `.photoscanpkg` files. |
| **Tesseract OCR** | **Optional** | Plain-text OCR requires local, system-installed Tesseract binary. |
| **Searchable PDF** | **Planned** | Embedded OCR text layers inside exported PDFs are not currently supported. |
| **PDF/A** | **Planned** | PDF/A archival format compliance is not implemented or validated. |
| **Packaged applications** | **Platform-dependent** | PyInstaller build configs exist; binaries must be compiled per target OS. |

## Key Features

* **Document Boundary Detection:** Automated extraction of convex quadrilaterals based on edge-contrast analysis across multiple scales.
* **Manual Corner Refinement:** Interactive four-point geometry selection to correct imperfect automated edge detection.
* **Perspective Correction:** Warp-perspective mapping to rectify camera angle skew and restore correct document aspect ratios.
* **Illumination and Shadow Correction:** Non-local background estimation in LAB color space to equalize brightness and remove harsh shadows.
* **Specialized Scan Modes:** Adaptive binarization (Sauvola thresholding) and local contrast optimization for document, grayscale, color, and receipt modes.
* **Nondestructive Project Management:** Work progress is kept safe via lightweight serialization format or packed archives.
* **Transactional Export:** Safe page-by-page or multipage saves to PNG, JPEG, TIFF, or PDF, ensuring incomplete writes never corrupt files.

## Screenshots or Demonstration

An interactive GUI workspace is available to help preview and fine-tune detected document corners:

```
+--------------------------------------------------------------+
| PhotoScan - Document Scanner                                 |
+------------------------------+-------------------------------+
|  Document Pages              |  [O] [O] [O] (Corner Markers) |
|  +------------------------+  |                               |
|  | Page 1 (Source.jpg)    |  |       Document                |
|  +------------------------+  |       Preview                 |
|  | Page 2 (Source.png)    |  |         Area                  |
|  +------------------------+  |                               |
|                              |  [O]                       [O]|
+------------------------------+-------------------------------+
| Scan Mode: [Color Document]  | Advanced: Brightness, Contrast|
+------------------------------+-------------------------------+
```

## Table of Contents

* [Part I: User Guide](#part-i-user-guide)
  * [1. What the Application Does](#1-what-the-application-does)
  * [2. Main User Workflow](#2-main-user-workflow)
  * [3. System Requirements](#3-system-requirements)
  * [4. Installation](#4-installation)
    * [Installing from Python Packages](#installing-from-python-packages)
    * [Running from Source](#running-from-source)
    * [Optional Components](#optional-components)
  * [5. Starting the Application](#5-starting-the-application)
  * [6. Using the Desktop Application](#6-using-the-desktop-application)
  * [7. Scan and Enhancement Modes](#7-scan-and-enhancement-modes)
  * [8. Preparing Good Source Photographs](#8-preparing-good-source-photographs)
  * [9. Working with Multiple Pages](#9-working-with-multiple-pages)
  * [10. Saving and Reopening Projects](#10-saving-and-reopening-projects)
  * [11. Exporting Results](#11-exporting-results)
  * [12. Command-Line Usage](#12-command-line-usage)
  * [13. Optional OCR](#13-optional-ocr)
  * [14. Privacy and Offline Operation](#14-privacy-and-offline-operation)
  * [15. Troubleshooting](#15-troubleshooting)
  * [16. Getting Help and Reporting Problems](#16-getting-help-and-reporting-problems)
* [Part II: Developer Guide](#part-ii-developer-guide)
  * [1. Development Status and Scope](#1-development-status-and-scope)
  * [2. Architecture Overview](#2-architecture-overview)
  * [3. Repository Structure](#3-repository-structure)
  * [4. Technology Stack](#4-technology-stack)
  * [5. Development Prerequisites](#5-development-prerequisites)
  * [6. Setting Up the Development Environment](#6-setting-up-the-development-environment)
  * [7. Running the Project During Development](#7-running-the-project-during-development)
  * [8. Processing Pipeline](#8-processing-pipeline)
  * [9. Document Detection and Geometry](#9-document-detection-and-geometry)
  * [10. Image Enhancement](#10-image-enhancement)
  * [11. Configuration Model](#11-configuration-model)
  * [12. Public Python API](#12-public-python-api)
  * [13. Extending the Application](#13-extending-the-application)
  * [14. GUI Architecture and Headless Testing](#14-gui-architecture-and-headless-testing)
  * [15. CLI Architecture](#15-cli-architecture)
  * [16. Project Persistence](#16-project-persistence)
  * [17. Testing](#17-testing)
  * [18. Code Quality](#18-code-quality)
  * [19. Building Packages](#19-building-packages)
  * [20. CI/CD](#20-cicd)
  * [21. Logging and Diagnostics](#21-logging-and-diagnostics)
  * [22. Security and Privacy for Developers](#22-security-and-privacy-for-developers)
  * [23. Performance and Benchmarking](#23-performance-and-benchmarking)
  * [24. Contribution Workflow](#24-contribution-workflow)
  * [25. Release Process](#25-release-process)
  * [26. Known Limitations and Roadmap](#26-known-limitations-and-roadmap)
* [Shared Final Sections](#shared-final-sections)
  * [License](#license)
  * [Acknowledgements](#acknowledgements)
  * [Support and Security](#support-and-security)

---

# Part I: User Guide

## 1. What the Application Does

PhotoScan is designed to solve the common problems associated with capturing documents using mobile cameras instead of flatbed scanners. Handheld photographs of paper sheets typically suffer from:
* Keystoning and perspective tilt from shooting at off-angles.
* Uneven illumination, shadow occlusions, or localized bright glare.
* Low contrast between background fibers and ink strokes.

By passing source images through PhotoScan, the application isolates the document region, flattens the geometry into an orthographic view, corrects shadows, and outputs high-contrast, digital-quality scans.

> [!IMPORTANT]
> PhotoScan relies on classical computer vision. It cannot reconstruct data lost due to extreme camera motion blur, heavy light reflections (glare), or severe underexposure that clips ink and paper intensities to the same value.

## 2. Main User Workflow

1. **Import:** Add one or more source photographs (JPG, PNG, TIFF, BMP, or WebP) containing a document sheet.
2. **Review Detection:** The application automatically attempts to trace the boundary of the page.
3. **Refine Geometry:** Adjust the corner positions manually if the auto-detection was affected by high-contrast backgrounds or low lighting.
4. **Select Mode:** Choose an enhancement mode (e.g., Color Document, Grayscale, or adaptive Black and White) depending on page contents.
5. **Preview & Adjust:** Use sliders to fine-tune shadow removal, contrast levels, and sharpening.
6. **Save/Export:** Commit your scan nondestructive settings to a project file or generate final output files.

## 3. System Requirements

* **Operating System:** Platform-independent (fully supported on Linux, Windows, and macOS).
* **Python Runtime:** Version 3.12 or newer.
* **Display (GUI only):** 1100x750 minimum screen resolution for desktop interface.
* **External Executables:** System-installed Tesseract OCR binary (optional, only required if plain-text OCR is needed).

## 4. Installation

### Installing from Python Packages

You can install PhotoScan and its command-line tool directly via pip.

```bash
pip install .
```

To install with graphical user interface support, use the `gui` extra:

```bash
pip install ".[gui]"
```

### Running from Source

If you want to run the application directly from a source checkout, it is highly recommended to use **uv** to manage isolated environments and resolve packages predictably.

1. Install uv on your system if you have not already:
   ```bash
   curl -LsSf https://astral.sh/uv/install.sh | sh
   ```
2. Navigate to the repository root directory:
   ```bash
   cd photoscan
   ```
3. Run the CLI tool immediately without manual activation:
   ```bash
   uv run photoscan --help
   ```

### Optional Components

You can append extra package qualifiers depending on your workflow:

```bash
# GUI interface support (PySide6)
pip install ".[gui]"

# Subprocess OCR dependencies (pytesseract interface)
pip install ".[ocr]"

# Developer dependencies (testing, linting, code quality)
pip install ".[dev,test]"
```

## 5. Starting the Application

The package exposes the command-line entry point `photoscan` when installed.

### Command Line Interface

Check that the installation succeeded by calling:

```bash
photoscan --help
```

### Desktop GUI Window

To launch the PySide6 graphical window, you can run a short custom runner script, as the package focuses primarily on providing CLI commands. Create a file named `run_gui.py` containing:

```python
import sys
from PySide6.QtWidgets import QApplication
from photoscan.gui.main_window import PhotoScanWindow

def main():
    app = QApplication(sys.argv)
    window = PhotoScanWindow()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
```

Execute the script inside your environment:

```bash
uv run python run_gui.py
```

## 6. Using the Desktop Application

The graphical workspace is divided into three functional columns:

1. **Left (Document Pages List):** Displays loaded page cards and thumbnails. Use the "Import Images" button or press `Ctrl+I` to populate this sidebar.
2. **Center (Interactive Editor View):** Shows the selected document page. Colored round handles are placed at the page corners. You can click and drag these handles to align them precisely with physical page borders. Buttons at the bottom let you reset back to the auto-detected boundary or fall back to full-image corners.
3. **Right (Enhancement Controls):** Selects active rendering presets and maps custom value offsets for:
   * **Brightness:** Shifts image intensity level globally.
   * **Contrast:** Scales contrast distribution.
   * **Sharpening:** Applies high-pass edge enhancements.
   * **Saturation:** Increases or dampens chromaticity.
   * **Shadow Removal:** Adjusts non-local luminance correction strength.

## 7. Scan and Enhancement Modes

The application processes cropped pages using specialized algorithms:

* **Auto Mode:** Evaluates color saturation levels. Automatically routes the image to *Grayscale* if chroma variance is small, otherwise defaults to *Color*.
* **Color Document:** Corrects uneven lighting and boosts text contrast while preserving color elements (signatures, stamps, annotations).
* **Grayscale:** Converts the image to luminance and applies Contrast Limited Adaptive Histogram Equalization (CLAHE) for deep, readable text.
* **Black and White:** Applies Sauvola adaptive local binarization. This mode is ideal for pure text sheets, but may lose fine illustration details.
* **Original Enhanced:** Bypasses aggressive filters, running only basic brightness/contrast adjustments and mild illumination correction.
* **Receipt:** A high-contrast adaptive thresholding preset with small window sizes designed to keep faint thermal-paper receipt ink crisp.
* **Photo on Page:** Applies conservative, low-strength shadow removal to prevent clipping of complex photographic gradients or illustrations.

## 8. Preparing Good Source Photographs

To minimize manual geometry edits and guarantee pristine outputs, observe these capture practices:
* **Background Contrast:** Place the paper on a dark or highly contrasting surface. White documents on light desks make automatic detection difficult.
* **Capture Angles:** Hold the lens parallel to the paper plane when possible to limit extreme perspective stretching.
* **Full Coverage:** Ensure all four corners of the page are completely visible within the camera viewport.
* **In-Focus Text:** Stand steady and maintain focus. Lens blur cannot be corrected algorithmically.
* **Even Lighting:** Shoot in diffuse light. Avoid hard directional bulbs that cast long, dark hand shadows across the sheet.

## 9. Working with Multiple Pages

The application fully supports multi-page operations:
* Import several images at once using `Ctrl+I` or via CLI input arguments.
* Re-order or rotate pages individually. Use `Ctrl+L` or `Ctrl+R` in the GUI to rotate selected pages.
* Export a multi-page collection into a single document (such as a multi-page TIFF or standard PDF file).

## 10. Saving and Reopening Projects

PhotoScan offers two nondestructive file formats to store your work:

### Lightweight JSON Projects (`.photoscan`)
Stores page order, page labels, manual corner coordinate sets, and enhancement offsets in a human-readable JSON schema.

> [!WARNING]
> Normal `.photoscan` project files reference source files by their path instead of embedding them. Moving or deleting the source photographs will cause missing-image warnings.

### Portable Project Packages (`.photoscanpkg`)
Compresses the project metadata along with original source images inside a self-contained ZIP archive. This format is perfect for moving complete workspaces between different systems safely.

## 11. Exporting Results

Processed pages are written transactionally to any of the following output formats:
* **PNG:** Lossless compression, best for high-contrast binarized text.
* **JPEG:** Lossy compression, best for colored pages or photographic plates.
* **TIFF:** Supports lossless LZW multi-page compression.
* **PDF:** Combines all processed pages into a single digital document.

> [!IMPORTANT]
> Exported PDFs are generated as raster-image documents. Searchable text layer generation is not currently supported.

## 12. Command-Line Usage

The CLI interface allows fast headless batch processing of files and directories.

### Basic Syntax

```bash
photoscan <inputs...> --output <destination> [options]
```

### Options Reference

* `inputs`: Paths to input image files or directories containing images.
* `-o`, `--output`: Target path for output. If processing multiple inputs, this must point to a directory or a `.pdf` file.
* `-m`, `--mode`: Enhancement preset (`auto`, `color`, `grayscale`, `black_white`, `original_enhanced`, `receipt`, `photo`). Default is `auto`.
* `--dpi`: Set physical target DPI resolution in metadata (default: 300).
* `-q`, `--quality`: Set compression quality for JPEG exports (1-100, default: 90).
* `-c`, `--corners`: Pass manual crop corners: `'x1,y1;x2,y2;x3,y3;x4,y4'` using normalized float values (0.0 to 1.0).
* `--paper-size`: Adjust dimensions to match a standard format (e.g. `A4`, `Letter`, `Legal`).
* `--no-overwrite`: Aborts rather than replacing pre-existing files.
* `--dry-run`: Performs crop calculations and generates quality reports without saving output files.
* `--json`: Outputs machine-readable status logs and metrics to the console.
* `-v`, `--verbose`: Prints detailed diagnostic debug traces.
* `--quiet`: Suppresses normal console outputs.

### CLI Examples

* **Single Page Color Crop to PNG:**
  ```bash
  photoscan input_page.jpg --output scan_result.png --mode color
  ```

* **Batch Process a Directory of Receipts:**
  ```bash
  photoscan billing_docs/ --output output_scans/ --mode receipt --no-overwrite
  ```

* **Merge Multiple Source Images into a Single 150 DPI PDF:**
  ```bash
  photoscan page1.jpg page2.jpg --output complete_document.pdf --dpi 150
  ```

* **Perform Dry-Run with JSON Output:**
  ```bash
  photoscan bad_shot.png --output test.png --dry-run --json
  ```

## 13. Optional OCR

PhotoScan defines a pluggable plain-text OCR engine interface. When the optional Tesseract adapter is configured, you can extract plain text from processed documents.

* **Availability Check:** The application searches for a system `tesseract` binary using environment paths.
* **Usage Limit:** Plain-text OCR operates as an API interface only. It is not currently integrated into standard CLI or GUI export workflows.
* **Searchable PDF Support:** Standard PDF exports generate image-only documents. OCR-based text layers are not embedded.

## 14. Privacy and Offline Operation

* **100% Offline Processing:** All mathematical calculations, document detection, and binarization filters run strictly on your local CPU.
* **No Telemetry:** The application does not collect usage metrics, crash dumps, or upload documents to remote servers.
* **Temporary Files:** Transactional exports create temporary files inside your system's temporary directory or the target directory. They are fully deleted upon success or failure.

## 15. Troubleshooting

### The Application Does Not Start
* Ensure you are running Python >= 3.12.
* If using the GUI, verify that PySide6 is installed in your current virtual environment:
  ```bash
  pip show PySide6
  ```

### Page Boundary Detection Fails
* The automatic detector requires visible contrast. Try recapturing the document over a dark surface.
* If background clutter is unavoidable, use the GUI corner handles to drag and snap the crop borders manually.

### Text Stroking Disappears in Black and White Mode
* Sauvola thresholding can clip very faint strokes. Switch to **Color Document** or **Grayscale** mode, or adjust the sliders to decrease contrast.

### OCR is Unavailable
* Verify that Tesseract is installed and registered in your system path:
  ```bash
  tesseract --version
  ```

## 16. Getting Help and Reporting Problems

Use the issue tracker associated with this repository to report reproducible bugs or request features. When submitting a report, include:
1. Application version (`photoscan` version is `0.1.0`).
2. Operating system details and Python version.
3. Steps to reproduce and any logged terminal outputs.
4. Input image dimensions (e.g., megapixels) and format.

Do not upload confidential or sensitive documents to public issue trackers.

---

# Part II: Developer Guide

## 1. Development Status and Scope

PhotoScan is built around a clean, decoupled design where the core image-processing pipeline is separated from user interface frameworks. Developers can safely integrate the document scanner library into CLI applications, background daemon workers, or custom GUI applications.

## 2. Architecture Overview

```
+-----------------------------------------------------------+
|                        GUI / CLI                          |
|             (PySide6 widgets / Argparse entry)            |
+---------------------------------------------+-------------+
                                              |
                                              v
+-----------------------------------------------------------+
|                     Application Service                   |
|                    (DocumentScanner API)                  |
+-----------------------------------------------------------+
                                              |
                                              v
+--------------------+-------------------+------------------+
| Processing Core    | Models            | Infrastructure   |
| (cv2, numpy, PIL)  | (Pydantic schemas)| (ZipStore)       |
+--------------------+-------------------+------------------+
```

* **Domain Layer (`domain/`):** Contains validated configurations, scan modes, and structured models (e.g., `ScanSettings`, `OrderedCorners`, `QualityReport`).
* **Processing Layer (`processing/`):** Coordinates stage operations: decoding, boundary extraction, geometry warping, enhancement filters, and quality checks.
* **Application Layer (`application/`):** Exposes `DocumentScanner` which bundles stages into an end-to-end interface.
* **Infrastructure Layer (`infrastructure/`):** Implements safe storage serialization (`ProjectStore`).
* **Presentation Layer (`gui/`, `cli/`):** Adapts services to interactive screens and shell commands.

## 3. Repository Structure

```
src/
  photoscan/
    application/     # High-level entry point (DocumentScanner)
    cli/             # CLI runner and arguments parsing
    domain/          # Core models, exceptions, project definitions
    export/          # Safe document exporting (DocumentExporter)
    gui/             # PySide6 components (main window, corner editor)
    infrastructure/  # Project serialization and package extraction
    processing/      # Core mathematical processing stages
tests/
  unit/              # Unit tests for CLI, core processing, and GUI
packaging/           # PyInstaller spec and build script definitions
```

## 4. Technology Stack

* **Core Language:** Python 3.12+
* **Image Processing:** OpenCV (`opencv-python-headless`), NumPy, Pillow.
* **Data Validation:** Pydantic (v2.0+)
* **GUI Engine:** PySide6 (v6.5+)
* **Testing:** pytest, pytest-qt, pytest-cov.
* **Formatting & Linting:** Ruff, mypy.
* **Build System:** Hatchling, uv, PyInstaller.

## 5. Development Prerequisites

* Python >= 3.12.
* **uv** environment manager (recommended).
* C compiler and native development tools if wheel compilation is needed.

## 6. Setting Up the Development Environment

1. Clone the repository:
   ```bash
   git clone <repository-url>
   cd photoscan
   ```
2. Initialize and sync the complete development workspace using uv:
   ```bash
   uv sync --all-extras
   ```

Alternatively, if you are using standard pip, create a virtual environment and install dependencies manually:

```bash
python -m venv .venv
source .venv/bin/activate  # Or Windows: .venv\Scripts\activate
pip install --upgrade pip
pip install -e ".[gui,ocr,dev,test,packaging]"
```

## 7. Running the Project During Development

To run the command-line interface from source:

```bash
uv run photoscan --help
```

To run a development image through the scanner and output JSON metrics:

```bash
uv run photoscan input_test.jpg -o output_test.jpg --json
```

## 8. Processing Pipeline

The `DocumentScanner` executes processing steps in a rigid, deterministic order:

1. **Input Decoding (`decoding.py`):** Loads source images safely via Pillow, normalizes dimensions, and outputs a standard RGB NumPy array.
2. **Boundary Detection (`detection.py`):** Runs bilateral filtering, calculates edge maps across several channels, fits candidate contours, and refines corners with subpixel precision.
3. **Geometry Correction (`geometry.py`):** Validates geometry against intersecting segments, calculates correct pixel aspect ratios, and performs projective warp transformations.
4. **Image Enhancement (`enhancement.py`):** Runs luminance equalizations, filters sensor noise, sharpens edges, and renders pixels matching the requested mode.
5. **Quality Assessment (`quality.py`):** Benchmarks output characteristics and raises warning notices if defects exist.
6. **Output Encoding (`export/`):** Packs arrays safely into target files.

## 9. Document Detection and Geometry

Automatic extraction evaluates contour geometries:
* **Analysis Scaling:** Images are downscaled to 800px max bounds to accelerate canny, bilateral, and thresholding steps.
* **Convexity & Area Constraints:** Candidate regions must be convex 4-sided quadrilaterals covering at least 10% but no more than 99% of total image pixels.
* **Refinement:** The selected candidate's coordinates are mapped back to full-resolution coordinates and optimized using OpenCV's `cornerSubPix` solver.
* **Geometry Warnings:** If angles diverge too far from 90 degrees or self-intersect, `InvalidGeometryError` is raised.

## 10. Image Enhancement

The processing core features high-quality restoration:
* **Luminance Normalization:** Conversions to LAB color space isolate luminance (L channel). A non-local morphological closing closing-by-reconstruction background model is calculated and divided out to correct heavy shading gradients.
* **Sauvola Adaptive Thresholding:**
  $$\text{Threshold} = m \cdot \left(1 + k \cdot \left(\frac{s}{R} - 1\right)\right)$$
  Where $m$ is local mean, $s$ is local standard deviation, and $R=128$.
* **Unsharp Masking:** Sharp high-pass residuals are extracted using Gaussian blur diffs and blended back to optimize text legibility.

## 11. Configuration Model

Configurations are implemented as strict Pydantic schemas.

### Schema Example (`ScanSettings`)

```json
{
  "mode": "auto",
  "brightness": 0.0,
  "contrast": 1.0,
  "white_level": 255.0,
  "black_level": 0.0,
  "shadow_removal_strength": 0.5,
  "background_cleanup_strength": 0.5,
  "denoising_strength": 0.0,
  "sharpening_amount": 0.0,
  "saturation": 1.0,
  "adaptive_threshold_window_size": 25,
  "threshold_bias": 10.0,
  "border_removal": true,
  "output_dpi": 300,
  "paper_size": "A4",
  "padding": 0.0
}
```

Precedence order during scans: Runtime arguments override project settings, which override default schema values.

## 12. Public Python API

Developers can import and execute the high-level scanner class directly.

### Usage Example

```python
from pathlib import Path
from photoscan.application.api import DocumentScanner
from photoscan.domain.models import ScanSettings, ScanMode

# Initialize scanner service
scanner = DocumentScanner()

# Define customized settings
settings = ScanSettings(
    mode=ScanMode.COLOR,
    sharpening_amount=1.2,
    shadow_removal_strength=0.8
)

# Process photograph
result = scanner.scan("path/to/doc.jpg", settings=settings)

# Extract diagnostic metrics
print(f"Confidence score: {result.quality_report.detection_confidence}")
print(f"Blur estimate: {result.quality_report.blur_estimate}")

# Save output document
result.save("output_scan.png", format_name="PNG", dpi=300)
```

## 13. Extending the Application

The package design allows simple modular extensions:
* **New Scan Presets:** Add options inside `ScanMode` enum and define mapping algorithms inside `DocumentEnhancer.enhance()`.
* **Alternative OCR Adapter:** Subclass the `OcrEngine` base abstract class (`processing/ocr.py`) and implement `extract_text`.

## 14. GUI Architecture and Headless Testing

The desktop view utilizes PySide6 widgets coordinated by `PhotoScanWindow`. Slow scanning routines run inside background `QThread` workers (`gui/worker.py`) to prevent freezing the interface.

To support automated GUI unit tests without physical monitors or virtual screens, pytest is configured to run headlessly.

### Headless Verification Command

```bash
QT_QPA_PLATFORM=offscreen uv run pytest tests/unit/test_gui.py
```

* `QT_QPA_PLATFORM=offscreen` forces Qt to route paint events to a virtual framebuffer.
* Dialog boxes, file selection screens, and file writes are mocked during testing.
* Passing offscreen test suites ensures widget bindings and signals function, but does not substitute for native OS UI manual checks.

## 15. CLI Architecture

* **Parsing Core:** Utilizes standard Python `argparse`.
* **Configuration Sync:** Translates arguments directly into validated Pydantic models.
* **Exit Codes:**
  * `0`: Success.
  * `1`: Scan/pipeline execution failure.
  * `2`: Argument/validation schema parse error.
  * `3`: Source file reading or decoding error.
  * `4`: Non-convex or collinear crop geometry error.

## 16. Project Persistence

* **Project Schemas:** Managed using Pydantic, ensuring version safety.
* **Traversal Protections:** To prevent Zip-Slip vulnerabilities when extracting self-contained packages (`.photoscanpkg`), the extracting algorithm checks target output paths against the base directory. It also enforces a strict 100MB member limit to reject compression bomb files.

## 17. Testing

The suite is run via pytest and is configured in `pyproject.toml`.

### Running All Tests

```bash
QT_QPA_PLATFORM=offscreen uv run pytest
```

### Coverage Reports

```bash
QT_QPA_PLATFORM=offscreen uv run pytest --cov=photoscan
```

* Test fixtures are stored inside the `tests/` directory.
* Tolerance bands on image matrix assertions account for subtle floating-point deviations in multi-platform OpenCV implementations.

## 18. Code Quality

The repository enforces formatting and typing standards.

### Running Ruff (Linter and Formatter)

```bash
uv run ruff check .
```

### Running Static Type Checking (mypy)

```bash
uv run mypy src/
```

## 19. Building Packages

The repository bundles PyInstaller build configurations under `packaging/`.

### Compile Binary Executables

```bash
python packaging/build_all.py
```

* Compilation compiles `src/photoscan/cli/main.py` into a console utility.
* Executables are built into `dist/`.
* For native stability, binaries should be compiled and tested directly on target platforms (Windows, macOS, Linux).

## 20. CI/CD

The workflow is configured via GitHub Actions under `.github/workflows/ci.yml`:
* **Matrix Testing:** Runs the test suite across Ubuntu, Windows, and macOS on Python 3.12.
* **Packaging Verification:** Triggers `packaging/build_all.py` across all environments to ensure binary packaging steps complete without errors.

## 21. Logging and Diagnostics

PhotoScan outputs clean diagnostic traces. When processing with `--verbose` or executing via Python with debug configurations enabled, logs track stage timing, matrix sizes, and detected coordinate limits. Personal metadata, paths, or document data are kept secure and redacted from basic outputs.

## 22. Security and Privacy for Developers

Key development safety features:
* **Subprocess Security:** Tesseract executions validate target paths and languages, sanitizing strings to prevent shell-escapes.
* **Zip Slip Protection:** Restricts `.photoscanpkg` files from writing to arbitrary system paths.
* **Memory Protections:** Maximum resolution bounds prevent memory exhaustion crashes.

## 23. Performance and Benchmarking

No fabrication of performance figures is introduced. The pipeline's execution times depend heavily on:
* Resolution: Cropping and detection scale on 800px preview scales.
* Filter selections: Sauvola thresholding requires local mean sliding calculations; larger window settings scale processing times.

## 24. Contribution Workflow

1. Search open issues or create one to discuss planned code changes.
2. Fork the repository and open a focused development branch.
3. Keep changes tight, atomic, and clear of unrelated code edits.
4. Verify changes with tests and run Ruff and mypy.
5. Submit your PR linking to the original issue.

## 25. Release Process

1. Increment standard version tags inside `src/photoscan/__init__.py` and `pyproject.toml`.
2. Generate changelog summaries.
3. Commit and push standard tags.
4. CI/CD builds binaries, calculates SHA256 checksums, and uploads target artifacts.

## 26. Known Limitations and Roadmap

* **Boundary Failures:** High noise, curved textures, or weak margins require manual editing.
* **Single-Threaded Filters:** Processing huge image sets in CLI relies on simple loops; parallel batch scans are planned.
* **Text Embedding:** Direct PDF text injection (making PDFs searchable) remains as a future milestone.
* **Metadata Conflict:** There is a known declaration mismatch between `pyproject.toml` and the root `LICENSE` file. See the [License](#license) section for more details.

---

# Shared Final Sections

## License

The repository's root `LICENSE` file contains the full Apache License 2.0 text. However, the Python package metadata in `pyproject.toml` identifies the license as MIT. These two declarations are inconsistent and require official maintainer resolution. Consult the `LICENSE` file before using, distributing, or modifying the project.

## Acknowledgements

* **OpenCV & NumPy:** High-performance multidimensional matrix math libraries.
* **Pillow:** Robust file loading and safe PIL metadata extraction.
* **Sauvola & Pietikainen:** Developers of the adaptive document binarization thresholding technique.

## Support and Security

* **Bugs & Features:** Submit detailed bug writeups on the repository issue tracker.
* **Security Advisories:** Do not post security issues publicly. For confidential disclosures, please contact the maintainers privately or follow the standard reporting channels.
