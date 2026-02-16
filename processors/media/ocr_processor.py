"""
OCR Processor Module - Handle images with text

This module processes images to extract:
- Text content using OCR
- Image metadata
- Text layout and structure
"""
import os
import re
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime
from base64 import b64encode

from url_detector import URLInfo, URLType
from processors.content_processor import ContentProcessor, ProcessedContent


@dataclass
class OCRResult:
    """Result from OCR processing"""
    text: str
    confidence: float
    language: str = "unknown"
    blocks: List[Dict[str, Any]] = None
    lines: List[str] = None

    def __post_init__(self):
        if self.blocks is None:
            self.blocks = []
        if self.lines is None:
            self.lines = []


@dataclass
class ImageMetadata:
    """Metadata from image"""
    width: int
    height: int
    format: str
    size_bytes: int
    orientation: str = "horizontal"  # horizontal, vertical, square
    has_text: bool = False
    text_confidence: float = 0.0


class OCRProcessor(ContentProcessor):
    """
    Processor for images with text (OCR)

    Supports:
    - Image files (JPG, PNG, WebP, etc.)
    - Screenshots
    - Scanned documents
    - Handwriting recognition (with capable engine)
    """

    def __init__(self):
        super().__init__()
        self.pil_available = self._check_pil_support()
        self.ocr_engines = self._detect_ocr_engines()

    def can_process(self, url_info: URLInfo) -> bool:
        """Check if this is an image file"""
        # Check file extension
        if url_info.url_type == URLType.FILE:
            path = url_info.url.lower()
            image_extensions = (
                '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff',
                '.webp', '.svg', '.ico'
            )
            return path.endswith(image_extensions)

        # Check for image URLs
        url_lower = url_info.url.lower()

        # Image hosting platforms
        image_domains = [
            'imgur.com', 'i.redd.it', 'i.imgur.com',
            'pbs.twimg.com', 'twimg.com',
            'images.unsplash.com', 'cdn.pixabay.com',
            'screenshot.pics', 'prnt.sc'
        ]

        # Image file indicators
        image_indicators = [
            '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp'
        ]

        return any(domain in url_lower for domain in image_domains) or \
               any(indicator in url_lower for indicator in image_indicators)

    def extract(self, url_info: URLInfo) -> ProcessedContent:
        """Extract content from image using OCR"""
        self._start_timer()
        result = self._create_base_content(url_info)

        # Determine source type
        url = url_info.url

        # Local file
        if not url.startswith(('http://', 'https://')):
            return self._extract_local_image(url, url_info)

        # URL - would need to download first
        result.content = {
            "title": self._extract_title_from_url(url),
            "url": url,
            "main_content": "",
            "summary": "Image - Download for OCR processing",
            "metadata": {"type": "image", "requires_download": True}
        }

        result.processing_info.update({
            "processing_time": self._end_timer(),
            "success": True,
            "note": "Image URL detected. Download for full OCR processing."
        })

        return result

    def _extract_local_image(self, file_path: str, url_info: URLInfo) -> ProcessedContent:
        """Extract from local image file"""
        result = self._create_base_content(url_info)

        path = Path(file_path)
        if not path.exists():
            result.processing_info.update({
                "processing_time": self._end_timer(),
                "success": False,
                "errors": [f"File not found: {file_path}"]
            })
            return result

        try:
            # Get image metadata
            metadata = self._extract_image_metadata(path)

            # Perform OCR
            ocr_result = self._perform_ocr(path)

            # Build result
            result.content = {
                "title": path.stem,
                "url": str(path),
                "main_content": ocr_result.text,
                "summary": self._generate_image_summary(metadata, ocr_result),
                "metadata": {
                    "width": metadata.width,
                    "height": metadata.height,
                    "format": metadata.format,
                    "size_bytes": metadata.size_bytes,
                    "orientation": metadata.orientation,
                    "has_text": metadata.has_text,
                    "text_confidence": metadata.text_confidence,
                    "language": ocr_result.language,
                    "line_count": len(ocr_result.lines)
                }
            }

            # Add OCR blocks to media
            if ocr_result.blocks:
                result.media = {
                    "ocr_blocks": ocr_result.blocks[:20]  # First 20 blocks
                }

            result.processing_info.update({
                "processing_time": self._end_timer(),
                "success": True,
                "text_length": len(ocr_result.text),
                "ocr_engine": self.ocr_engines.get('primary', 'none')
            })

        except Exception as e:
            result.processing_info.update({
                "processing_time": self._end_timer(),
                "success": False,
                "errors": [f"Image processing failed: {str(e)}"]
            })

        return result

    def _extract_image_metadata(self, path: Path) -> ImageMetadata:
        """Extract metadata from image file"""
        metadata = ImageMetadata(
            width=0,
            height=0,
            format=path.suffix[1:].upper(),
            size_bytes=path.stat().st_size
        )

        if not self.pil_available:
            return metadata

        try:
            from PIL import Image

            with Image.open(path) as img:
                metadata.width, metadata.height = img.size
                metadata.format = img.format or metadata.format

                # Determine orientation
                if metadata.width > metadata.height * 1.2:
                    metadata.orientation = "horizontal"
                elif metadata.height > metadata.width * 1.2:
                    metadata.orientation = "vertical"
                else:
                    metadata.orientation = "square"

                # Get EXIF data
                if hasattr(img, '_getexif'):
                    exif = img._getexif()
                    if exif:
                        # Could extract more EXIF data here
                        pass

        except Exception as e:
            print(f"Warning: Could not extract image metadata: {e}")

        return metadata

    def _perform_ocr(self, path: Path) -> OCRResult:
        """Perform OCR on image"""
        result = OCRResult(
            text="",
            confidence=0.0,
            language="unknown"
        )

        if not self.pil_available:
            result.text = "PIL not available for image processing"
            return result

        # Try available OCR engines in order
        if 'tesseract' in self.ocr_engines.get('available', []):
            result = self._ocr_with_tesseract(path)
        elif 'easyocr' in self.ocr_engines.get('available', []):
            result = self._ocr_with_easyocr(path)
        elif 'pytesseract' in self.ocr_engines.get('available', []):
            result = self._ocr_with_pytesseract(path)
        else:
            # Fallback: basic image info
            result.text = f"[Image: {path.name} - {path.suffix[1:].upper()} format]"

        return result

    def _ocr_with_tesseract(self, path: Path) -> OCRResult:
        """OCR using pytesseract"""
        try:
            import pytesseract
            from PIL import Image

            img = Image.open(path)

            # Get text
            text = pytesseract.image_to_string(img)

            # Get detailed data
            data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT)

            # Build blocks
            blocks = []
            lines = []
            current_line = ""
            line_num = 0

            for i, text_val in enumerate(data['text']):
                if text_val.strip():
                    conf = int(data['conf'][i]) if data['conf'][i] != '-1' else 0

                    if data.get('line_num', [])[i] != line_num:
                        if current_line:
                            lines.append(current_line.strip())
                            line_num = data.get('line_num', [])[i]
                            current_line = ""

                    current_line += text_val + " "

                    blocks.append({
                        "text": text_val,
                        "confidence": conf / 100.0,
                        "bbox": {
                            "x": data.get('left', [0])[i],
                            "y": data.get('top', [0])[i],
                            "width": data.get('width', [0])[i],
                            "height": data.get('height', [0])[i]
                        }
                    })

            if current_line:
                lines.append(current_line.strip())

            return OCRResult(
                text=text,
                confidence=0.8,  # Tesseract doesn't give overall confidence
                language="unknown",
                blocks=blocks,
                lines=lines
            )

        except Exception as e:
            return OCRResult(
                text=f"OCR processing error: {str(e)}",
                confidence=0.0
            )

    def _ocr_with_easyocr(self, path: Path) -> OCRResult:
        """OCR using EasyOCR"""
        try:
            import easyocr

            reader = easyocr.Reader(['en', 'ch_sim'])  # English and Chinese
            results = reader.readtext(str(path))

            text_parts = []
            blocks = []

            for (bbox, text, conf) in results:
                text_parts.append(text)
                blocks.append({
                    "text": text,
                    "confidence": conf,
                    "bbox": {
                        "x1": bbox[0][0],
                        "y1": bbox[0][1],
                        "x2": bbox[2][0],
                        "y2": bbox[2][1]
                    }
                })

            return OCRResult(
                text="\n".join(text_parts),
                confidence=sum(b["confidence"] for b in blocks) / len(blocks) if blocks else 0,
                language="auto",
                blocks=blocks
            )

        except Exception as e:
            return OCRResult(
                text=f"EasyOCR error: {str(e)}",
                confidence=0.0
            )

    def _ocr_with_pytesseract(self, path: Path) -> OCRResult:
        """Simple OCR using pytesseract (no detailed data)"""
        try:
            import pytesseract
            from PIL import Image

            img = Image.open(path)
            text = pytesseract.image_to_string(img)

            return OCRResult(
                text=text,
                confidence=0.7,
                language="unknown"
            )

        except Exception as e:
            return OCRResult(
                text=f"OCR error: {str(e)}",
                confidence=0.0
            )

    def _generate_image_summary(self, metadata: ImageMetadata, ocr_result: OCRResult) -> str:
        """Generate summary from image metadata and OCR"""
        parts = []

        parts.append(f"{metadata.format} image")
        parts.append(f"{metadata.width}x{metadata.height}")
        parts.append(metadata.orientation)

        if ocr_result.text:
            word_count = len(ocr_result.text.split())
            parts.append(f"{word_count} words detected")

            # Get first line as preview
            if ocr_result.lines:
                preview = ocr_result.lines[0][:100]
                parts.append(f'"{preview}"')

        return " | ".join(parts)

    def _extract_title_from_url(self, url: str) -> str:
        """Extract title from URL"""
        parts = url.split('/')
        filename = parts[-1] if parts else ''

        title = filename.rsplit('.', 1)[0] if '.' in filename else filename
        title = title.replace('-', ' ').replace('_', ' ').title()
        title = re.sub(r'\s+', ' ', title).strip()

        return title or "Image"

    def _detect_ocr_engines(self) -> Dict[str, Any]:
        """Detect available OCR engines"""
        available = []

        try:
            import pytesseract
            available.append('pytesseract')
        except ImportError:
            pass

        try:
            import easyocr
            available.append('easyocr')
        except ImportError:
            pass

        # Check for tesseract binary
        tesseract_available = False
        try:
            import shutil
            tesseract_available = shutil.which('tesseract') is not None
        except:
            pass

        if tesseract_available:
            available.append('tesseract')

        return {
            'available': available,
            'primary': available[0] if available else None,
            'tesseract_binary': tesseract_available
        }

    def _check_pil_support(self) -> bool:
        """Check if PIL/Pillow is available"""
        try:
            from PIL import Image
            return True
        except ImportError:
            return False

    @staticmethod
    def get_installation_instructions() -> str:
        """Return installation instructions for dependencies"""
        return """
To enable image OCR processing, install the following:

Required:
    pip install Pillow

For OCR (choose one):
    pip install pytesseract  # Requires Tesseract OCR binary installed
    pip install easyocr

Tesseract binary installation:
    - macOS: brew install tesseract
    - Ubuntu: sudo apt install tesseract-ocr
    - Windows: Download from https://github.com/UB-Mannheim/tesseract/wiki

Or install all:
    pip install Pillow pytesseract easyocr
        """

    def extract_text_to_markdown(self, image_path: str) -> str:
        """
        Extract text and format as markdown

        Useful for creating notes from screenshots
        """
        result = self._perform_ocr(Path(image_path))

        if not result.text or result.text.strip() == "":
            return f"[Image with no text detected]"

        # Format as markdown
        lines = result.lines or result.text.split('\n')

        md_parts = []
        for line in lines:
            line = line.strip()
            if line:
                md_parts.append(line)

        return "\n".join(md_parts)


if __name__ == "__main__":
    # Test the OCR processor
    print("OCR Processor Module")
    print("=" * 50)

    processor = OCRProcessor()

    print(f"\nPIL support: {processor.pil_available}")
    print(f"Available OCR engines: {processor.ocr_engines['available']}")

    if not processor.pil_available:
        print("\n" + processor.get_installation_instructions())

    print("\n✓ OCR processor module loaded!")
