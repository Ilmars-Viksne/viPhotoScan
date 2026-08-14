import contextlib
import hashlib
import json
import os
import tempfile
import zipfile
from pathlib import Path

from photoscan.domain.exceptions import ConfigurationError, ExportFailureError
from photoscan.domain.project import ProjectModel


def calculate_sha256(file_path: Path) -> str:
    """Computes SHA256 checksum of a file."""
    sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            sha256.update(chunk)
    return sha256.hexdigest()

class ProjectStore:
    """
    Handles serialization and deserialization of .photoscan JSON projects
    and self-contained .photoscanpkg zip packages.
    """

    def save_project(self, project: ProjectModel, file_path: Path | str) -> None:
        """
        Saves a project model to a JSON file atomically.
        """
        path = Path(file_path)
        # Validate parent directory exists
        if not path.parent.exists():
            path.parent.mkdir(parents=True, exist_ok=True)

        temp_file = None
        try:
            # Create a temporary file in the same directory
            with tempfile.NamedTemporaryFile(
                dir=path.parent,
                suffix=".tmp.photoscan",
                delete=False,
                mode="w",
                encoding="utf-8"
            ) as tmp:
                temp_file = Path(tmp.name)
                # Dump Pydantic json representation
                json.dump(project.model_dump(), tmp, indent=2)

            os.replace(temp_file, path)
        except Exception as e:
            if temp_file and temp_file.exists():
                with contextlib.suppress(Exception):
                    temp_file.unlink()
            raise ExportFailureError(f"Failed to save project file: {e}") from e

    def load_project(self, file_path: Path | str) -> ProjectModel:
        """
        Loads a project model from a JSON file.
        """
        path = Path(file_path)
        if not path.exists():
            raise ConfigurationError(f"Project file does not exist: {path}")

        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            return ProjectModel.model_validate(data)
        except Exception as e:
            raise ConfigurationError(f"Failed to load or validate project file: {e}") from e

    def save_package(self, project: ProjectModel, package_path: Path | str) -> None:
        """
        Packages the project metadata and all references of original source images
        into a single self-contained compressed .photoscanpkg ZIP archive.
        """
        dest_path = Path(package_path)
        if not dest_path.parent.exists():
            dest_path.parent.mkdir(parents=True, exist_ok=True)

        temp_zip = None
        try:
            with tempfile.NamedTemporaryFile(
                dir=dest_path.parent,
                suffix=".tmp.photoscanpkg",
                delete=False
            ) as tmp:
                temp_zip = Path(tmp.name)

            # Update project references so that sources point to the internal folder
            packaged_project = project.model_copy(deep=True)

            with zipfile.ZipFile(temp_zip, "w", zipfile.ZIP_DEFLATED) as zf:
                # Add source images
                for page in packaged_project.pages:
                    src_file = Path(page.source_path)
                    if not src_file.exists():
                        raise ConfigurationError(f"Source file not found for packaging: {src_file}")

                    # Use secure unique naming inside zip
                    internal_name = f"sources/{page.id}{src_file.suffix}"
                    zf.write(src_file, internal_name)

                    # Update paths and checksums
                    page.source_path = internal_name
                    page.checksum = calculate_sha256(src_file)

                # Write manifest JSON inside zip
                manifest_data = json.dumps(packaged_project.model_dump(), indent=2)
                zf.writestr("manifest.json", manifest_data)

            os.replace(temp_zip, dest_path)
        except Exception as e:
            if temp_zip and temp_zip.exists():
                with contextlib.suppress(Exception):
                    temp_zip.unlink()
            raise ExportFailureError(f"Failed to save portable package: {e}") from e

    def extract_package(self, package_path: Path | str, extract_dir: Path | str) -> ProjectModel:
        """
        Extracts a .photoscanpkg archive into the extraction directory safely.
        Applies Zip-Slip path traversal protection and validation of compressed sizes.
        """
        pkg_path = Path(package_path)
        out_dir = Path(extract_dir).resolve()

        if not pkg_path.exists():
            raise ConfigurationError(f"Package file does not exist: {pkg_path}")

        if not out_dir.exists():
            out_dir.mkdir(parents=True, exist_ok=True)

        try:
            with zipfile.ZipFile(pkg_path, "r") as zf:
                # 1. Zip Slip / Path Traversal Protection
                for member in zf.infolist():
                    target_path = Path(out_dir, member.filename).resolve()
                    # Check if target path starts with extraction directory path
                    if not str(target_path).startswith(str(out_dir)):
                        raise SecurityError(f"Malicious zip entry detected (path traversal): {member.filename}")

                    # Safeguard against decompression bomb: maximum member size 100MB
                    if member.file_size > 100_000_000:
                        raise SecurityError(f"Decompression limit exceeded: {member.filename}")

                # 2. Extract contents
                zf.extractall(out_dir)

            # Load the manifest
            manifest_file = out_dir / "manifest.json"
            if not manifest_file.exists():
                raise ConfigurationError("Package manifest.json is missing.")

            with open(manifest_file, encoding="utf-8") as f:
                data = json.load(f)

            project = ProjectModel.model_validate(data)

            # Update paths in the project relative to the extraction directory
            for page in project.pages:
                relative_src = Path(page.source_path)
                full_src = (out_dir / relative_src).resolve()
                page.source_path = str(full_src)

            return project
        except Exception as e:
            raise ConfigurationError(f"Failed to load or validate portable package: {e}") from e

class SecurityError(Exception):
    """Raised for security-related validation failures."""
    pass
