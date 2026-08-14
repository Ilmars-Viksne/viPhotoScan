import contextlib
import shutil
import subprocess
import tempfile
from pathlib import Path

from photoscan.domain.exceptions import PluginError


class OcrResult:
    """Encapsulates plain text and processing diagnostics of OCR."""
    def __init__(self, text: str, confidence: float | None = None) -> None:
        self.text = text
        self.confidence = confidence

class OcrEngine:
    """Abstract interface for pluggable local OCR engines."""
    def is_available(self) -> bool:
        raise NotImplementedError

    def get_version(self) -> str:
        raise NotImplementedError

    def list_languages(self) -> list[str]:
        raise NotImplementedError

    def extract_text(
        self,
        image_path: Path,
        language: str = "eng",
        timeout: float = 30.0
    ) -> OcrResult:
        raise NotImplementedError

class TesseractOcrEngine(OcrEngine):
    """
    Subprocess-based Tesseract OCR Adapter.
    Communicates directly with the system 'tesseract' binary.
    """
    def __init__(self, executable_path: str | None = None) -> None:
        self.executable = executable_path or shutil.which("tesseract")

    def is_available(self) -> bool:
        return self.executable is not None

    def _run_cmd(self, args: list[str], timeout: float = 10.0) -> str:
        if not self.is_available():
            raise PluginError("Tesseract executable not found. Please install Tesseract on your system.")

        cmd = [self.executable] + args
        try:
            res = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                check=True
            )
            return res.stdout.strip()
        except subprocess.TimeoutExpired as e:
            raise PluginError(f"Tesseract operation timed out: {e}") from e
        except subprocess.CalledProcessError as e:
            raise PluginError(f"Tesseract failed (code {e.returncode}): {e.stderr}") from e
        except Exception as e:
            raise PluginError(f"Subprocess invocation error: {e}") from e

    def get_version(self) -> str:
        return self._run_cmd(["--version"])

    def list_languages(self) -> list[str]:
        output = self._run_cmd(["--list-langs"])
        # First line is usually "List of available languages (X):"
        lines = output.splitlines()
        langs = []
        for line in lines[1:]:
            line = line.strip()
            if line:
                langs.append(line)
        return langs

    def extract_text(
        self,
        image_path: Path,
        language: str = "eng",
        timeout: float = 30.0
    ) -> OcrResult:
        """
        Directly runs tesseract on the target image and reads the plain text.
        Uses a secure subprocess interface with arguments validation.
        """
        if not image_path.exists():
            raise PluginError(f"Image for OCR does not exist: {image_path}")

        # Basic input language validation to prevent argument injections
        safe_lang = "".join(c for c in language if c.isalnum() or c in ["-", "+"])

        temp_out = None
        try:
            # Tesseract outputs to a file; we use a temporary file path
            with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as tmp:
                temp_out = Path(tmp.name)

            # Tesseract appends '.txt' automatically if suffix is omitted,
            # but we can specify the base name of our temp file
            base_out = temp_out.with_suffix("")

            # Formulate arguments
            args = [
                str(image_path),
                str(base_out),
                "-l", safe_lang
            ]

            self._run_cmd(args, timeout=timeout)

            # Read extracted text
            actual_txt_file = temp_out.with_suffix(".txt")
            if actual_txt_file.exists():
                text = actual_txt_file.read_text(encoding="utf-8").strip()
                return OcrResult(text=text, confidence=None)
            else:
                return OcrResult(text="", confidence=0.0)

        except Exception as e:
            if isinstance(e, PluginError):
                raise
            raise PluginError(f"OCR execution failed: {e}") from e
        finally:
            # Cleanup temp files
            if temp_out:
                with contextlib.suppress(Exception):
                    temp_out.unlink()
                with contextlib.suppress(Exception):
                    temp_out.with_suffix(".txt").unlink()
                with contextlib.suppress(Exception):
                    temp_out.with_suffix("").unlink()
class MockOcrEngine(OcrEngine):
    """Fallback mock OCR engine for testing."""
    def is_available(self) -> bool:
        return True

    def get_version(self) -> str:
        return "tesseract 5.3.0"

    def list_languages(self) -> list[str]:
        return ["eng", "fra", "deu"]

    def extract_text(
        self,
        image_path: Path,
        language: str = "eng",
        timeout: float = 30.0
    ) -> OcrResult:
        return OcrResult(text="Mock OCR Extracted Text Content", confidence=1.0)
