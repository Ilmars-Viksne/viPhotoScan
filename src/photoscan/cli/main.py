import argparse
import json
import sys
from pathlib import Path

from photoscan.application.api import DocumentScanner
from photoscan.domain.models import Corner, OrderedCorners, ScanMode, ScanSettings


def parse_corners_string(corners_str: str) -> OrderedCorners:
    """
    Parses a corners string formatted as: 'x1,y1;x2,y2;x3,y3;x4,y4'
    where each coordinate is normalized (0.0 to 1.0).
    """
    try:
        pairs = corners_str.strip().split(";")
        if len(pairs) != 4:
            raise ValueError("Must provide exactly 4 corners.")

        coords = []
        for pair in pairs:
            x_str, y_str = pair.split(",")
            coords.append((float(x_str), float(y_str)))

        return OrderedCorners(
            top_left=Corner(x=coords[0][0], y=coords[0][1]),
            top_right=Corner(x=coords[1][0], y=coords[1][1]),
            bottom_right=Corner(x=coords[2][0], y=coords[2][1]),
            bottom_left=Corner(x=coords[3][0], y=coords[3][1]),
        )
    except Exception as e:
        raise argparse.ArgumentTypeError(
            f"Invalid corners format. Expected 'x1,y1;x2,y2;x3,y3;x4,y4'. Error: {e}"
        ) from e

def process_single_file(
    scanner: DocumentScanner,
    input_path: Path,
    output_path: Path,
    settings: ScanSettings,
    manual_corners: OrderedCorners | None = None,
    dry_run: bool = False,
    overwrite: bool = True
) -> dict:
    """
    Processes a single image file and exports it. Returns a diagnostic dict.
    """
    if not overwrite and output_path.exists():
        return {
            "status": "skipped",
            "reason": f"Output file already exists: {output_path}",
            "file": str(input_path)
        }

    if dry_run:
        return {
            "status": "dry_run",
            "file": str(input_path),
            "destination": str(output_path)
        }

    try:
        result = scanner.scan(input_path, settings=settings, corners=manual_corners)

        # Save output
        fmt = output_path.suffix.lstrip(".").upper() or "PNG"
        result.save(
            destination=output_path,
            format_name=fmt,
            dpi=settings.output_dpi
        )

        return {
            "status": "success",
            "file": str(input_path),
            "destination": str(output_path),
            "metrics": result.quality_report.model_dump()
        }
    except Exception as e:
        return {
            "status": "failed",
            "file": str(input_path),
            "error": str(e)
        }

def find_images_recursively(dir_path: Path) -> list[Path]:
    """Finds all common image file paths under a directory recursively."""
    extensions = [".jpg", ".jpeg", ".png", ".tiff", ".tif", ".bmp", ".webp"]
    results = []
    for ext in extensions:
        # Match case-insensitive
        results.extend(dir_path.rglob(f"*{ext}"))
        results.extend(dir_path.rglob(f"*{ext.upper()}"))
    # Return unique, sorted paths
    return sorted(set(results))

def main(args_list: list[str] | None = None) -> int:
    """
    Main entry point for CLI.
    Exit codes:
        0: Success
        1: Processing Failure or General Uncaught Error
        2: Configuration / CLI Arguments Parsing Error
        3: Input File / Decode Failure
        4: Geometry / Crop Selection Failure
    """
    parser = argparse.ArgumentParser(
        prog="photoscan",
        description="PhotoScan: Transform photographs of documents into clean scanner-style digital scans."
    )
    parser.add_argument("inputs", nargs="+", help="Input image file(s) or directories.")
    parser.add_argument("--output", "-o", required=True, help="Output destination file or directory.")
    parser.add_argument("--mode", "-m", default="auto", choices=[m.value for m in ScanMode],
                        help="Scan processing mode (default: auto).")
    parser.add_argument("--dpi", type=int, default=300, help="Target DPI metadata (default: 300).")
    parser.add_argument("--quality", "-q", type=int, default=90, help="JPEG quality [1-100] (default: 90).")
    parser.add_argument("--corners", "-c", type=parse_corners_string, default=None,
                        help="Manual normalized corners coordinates: 'x1,y1;x2,y2;x3,y3;x4,y4'")
    parser.add_argument("--paper-size", help="Target standard paper dimensions (e.g. A4, Letter, Legal).")
    parser.add_argument("--no-overwrite", action="store_true", help="Prevent overwriting existing output files.")
    parser.add_argument("--dry-run", action="store_true", help="Perform checks and analysis but don't save output.")
    parser.add_argument("--json", action="store_true", help="Output machine-readable JSON status reports.")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose log diagnostics.")
    parser.add_argument("--quiet", action="store_true", help="Suppress console outputs.")

    try:
        args = parser.parse_args(args_list if args_list is not None else sys.argv[1:])
    except SystemExit as e:
        return 2 if e.code != 0 else 0

    # Initialize processing configuration settings
    try:
        settings = ScanSettings(
            mode=ScanMode(args.mode),
            output_dpi=args.dpi,
            paper_size=args.paper_size
        )
    except Exception as e:
        if not args.quiet:
            print(f"Configuration error: {e}", file=sys.stderr)
        return 2

    # Collect inputs
    input_paths: list[Path] = []
    for item in args.inputs:
        p = Path(item)
        if not p.exists():
            if not args.quiet:
                print(f"Input path does not exist: {p}", file=sys.stderr)
            return 3
        if p.is_dir():
            input_paths.extend(find_images_recursively(p))
        else:
            input_paths.append(p)

    if not input_paths:
        if not args.quiet:
            print("No valid input images found.", file=sys.stderr)
        return 3

    # Resolve output path
    dest = Path(args.output)
    is_multi = len(input_paths) > 1

    # Initialize scanning service
    scanner = DocumentScanner(default_settings=settings)
    results_diagnostics = []
    has_failed = False

    # Perform multipage export if output format is PDF and we have multiple images
    if is_multi and dest.suffix.lower() == ".pdf":
        if not args.quiet and not args.json:
            print(f"Processing {len(input_paths)} images into a single multipage PDF: {dest}")

        if args.dry_run:
            results_diagnostics.append({"status": "dry_run", "destination": str(dest)})
        else:
            try:
                scanned_images = []
                for p in input_paths:
                    scan_res = scanner.scan(p, settings=settings, corners=args.corners)
                    scanned_images.append(scan_res.enhanced_image)

                # Export multipage PDF
                from photoscan.export.exporter import DocumentExporter
                exporter = DocumentExporter()
                exporter.export_multipage(
                    scanned_images,
                    dest,
                    "pdf",
                    dpi=settings.output_dpi,
                    jpeg_quality=args.quality
                )
                results_diagnostics.append({
                    "status": "success",
                    "destination": str(dest),
                    "pages_count": len(scanned_images)
                })
            except Exception as e:
                results_diagnostics.append({"status": "failed", "error": str(e)})
                has_failed = True
    else:
        # Process files individually
        for idx, input_p in enumerate(input_paths):
            # Determine correct output file name
            if dest.is_dir() or is_multi or not dest.suffix:
                # Output is a directory or multiple inputs, so output should be saved in dest
                out_file = dest / f"scan_{input_p.name}"
                if dest.suffix: # if dest has extension but multiple files, replace suffix
                    out_file = dest.parent / f"scan_{idx}_{input_p.stem}{dest.suffix}"
            else:
                out_file = dest

            diag = process_single_file(
                scanner=scanner,
                input_path=input_p,
                output_path=out_file,
                settings=settings,
                manual_corners=args.corners,
                dry_run=args.dry_run,
                overwrite=not args.no_overwrite
            )
            results_diagnostics.append(diag)
            if diag.get("status") == "failed":
                has_failed = True

            if not args.quiet and not args.json:
                if diag["status"] == "success":
                    print(f"Successfully scanned: {input_p} -> {out_file}")
                elif diag["status"] == "skipped":
                    print(f"Skipped (already exists): {input_p}")
                elif diag["status"] == "failed":
                    print(f"Failed to scan {input_p}: {diag['error']}", file=sys.stderr)

    # Output JSON report if requested
    if args.json:
        print(json.dumps(results_diagnostics, indent=2))

    if has_failed:
        # Determine exit code based on the first error
        first_fail = next(d for d in results_diagnostics if d.get("status") == "failed")
        err_msg = first_fail.get("error", "")
        if "Decode" in err_msg or "decode" in err_msg:
            return 3
        if "Geometry" in err_msg or "geometry" in err_msg:
            return 4
        return 1

    return 0

if __name__ == "__main__":
    sys.exit(main())
