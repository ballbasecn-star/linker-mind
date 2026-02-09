"""
Book Processor Module - Handle EPUB and PDF books

This module processes book files to extract:
- Title, author, metadata
- Table of contents
- Chapter content
- Cover image
"""
import os
import re
from pathlib import Path
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from datetime import datetime

from url_detector import URLInfo, URLType
from content_processor import ContentProcessor, ProcessedContent


@dataclass
class BookMetadata:
    """Metadata extracted from a book"""
    title: str
    author: str = ""
    isbn: str = ""
    publisher: str = ""
    publish_date: str = ""
    language: str = ""
    subject: str = ""
    description: str = ""

    # Book structure
    total_pages: int = 0
    chapter_count: int = 0
    table_of_contents: List[Dict[str, Any]] = None

    def __post_init__(self):
        if self.table_of_contents is None:
            self.table_of_contents = []


@dataclass
class Chapter:
    """A chapter from a book"""
    title: str
    content: str
    index: int
    page_start: int = 0
    page_end: int = 0


class BookProcessor(ContentProcessor):
    """
    Processor for book files (EPUB, PDF)

    Supports:
    - EPUB files (.epub)
    - PDF files (.pdf)
    - Local file paths
    """

    def __init__(self):
        super().__init__()
        self.epub_available = self._check_epub_support()
        self.pdf_available = self._check_pdf_support()

    def can_process(self, url_info: URLInfo) -> bool:
        """Check if this is a book file"""
        # Check file extension
        if url_info.url_type == URLType.FILE:
            path = url_info.url.lower()
            return path.endswith(('.epub', '.pdf'))

        # Check for book URLs
        url_lower = url_info.url.lower()
        book_indicators = [
            'epub', 'ebook', 'e-book',
            'isbn', 'book', 'novel',
            'drive.google.com/file',  # Often used for books
            'archive.org/details'     # Internet Archive books
        ]

        return any(indicator in url_lower for indicator in book_indicators)

    def extract(self, url_info: URLInfo) -> ProcessedContent:
        """Extract content from a book file"""
        self._start_timer()
        result = self._create_base_content(url_info)

        # Determine file type
        file_path = url_info.url
        if file_path.startswith(('http://', 'https://')):
            # URL - would need to download first
            result.processing_info.update({
                "processing_time": self._end_timer(),
                "success": False,
                "errors": ["URL download not yet supported for books"]
            })
            return result

        # Local file
        path = Path(file_path)
        if not path.exists():
            result.processing_info.update({
                "processing_time": self._end_timer(),
                "success": False,
                "errors": [f"File not found: {file_path}"]
            })
            return result

        try:
            if path.suffix.lower() == '.epub':
                return self._extract_epub(path, url_info)
            elif path.suffix.lower() == '.pdf':
                return self._extract_pdf(path, url_info)
            else:
                result.processing_info.update({
                    "processing_time": self._end_timer(),
                    "success": False,
                    "errors": [f"Unsupported file type: {path.suffix}"]
                })
        except Exception as e:
            result.processing_info.update({
                "processing_time": self._end_timer(),
                "success": False,
                "errors": [str(e)]
            })

        return result

    def _extract_epub(self, path: Path, url_info: URLInfo) -> ProcessedContent:
        """Extract content from EPUB file"""
        result = self._create_base_content(url_info)

        if not self.epub_available:
            result.processing_info.update({
                "processing_time": self._end_timer(),
                "success": False,
                "errors": ["EPUB support not available. Install ebooklib: pip install EbookLib"]
            })
            return result

        try:
            import ebooklib
            from ebooklib import epub

            # Read EPUB
            book = epub.read_epub(str(path))

            # Extract metadata
            metadata = self._extract_epub_metadata(book)

            # Extract content
            chapters = []
            all_content = []

            for item in book.get_items():
                if item.get_type() == ebooklib.ITEM_DOCUMENT:
                    # Parse HTML content
                    from bs4 import BeautifulSoup
                    soup = BeautifulSoup(item.get_content(), 'html.parser')

                    # Extract text
                    text = soup.get_text(separator=' ', strip=True)
                    if len(text) > 100:  # Skip very short items
                        all_content.append(text)

                        # Try to get chapter title
                        title_tag = soup.find(['h1', 'h2', 'title'])
                        title = title_tag.get_text(strip=True) if title_tag else f"Chapter {len(chapters) + 1}"

                        chapters.append(Chapter(
                            title=title,
                            content=text[:5000],  # Limit chapter length
                            index=len(chapters)
                        ))

            # Build result
            result.content = {
                "title": metadata.title,
                "author": metadata.author,
                "url": str(path),
                "main_content": "\n\n".join(all_content[:20]),  # First 20 sections
                "summary": f"Book by {metadata.author}" if metadata.author else "EPUB book",
                "metadata": {
                    "isbn": metadata.isbn,
                    "publisher": metadata.publisher,
                    "publish_date": metadata.publish_date,
                    "language": metadata.language,
                    "total_chapters": len(chapters)
                }
            }

            # Store chapters separately
            result.processing_info.update({
                "processing_time": self._end_timer(),
                "success": True,
                "chapters_count": len(chapters),
                "file_size": path.stat().st_size
            })

            # Store chapter data for later access
            result.media = {
                "chapters": [
                    {"title": c.title, "index": c.index, "preview": c.content[:500]}
                    for c in chapters[:10]
                ]
            }

        except Exception as e:
            result.processing_info.update({
                "processing_time": self._end_timer(),
                "success": False,
                "errors": [f"EPUB extraction failed: {str(e)}"]
            })

        return result

    def _extract_pdf(self, path: Path, url_info: URLInfo) -> ProcessedContent:
        """Extract content from PDF file"""
        result = self._create_base_content(url_info)

        if not self.pdf_available:
            result.processing_info.update({
                "processing_time": self._end_timer(),
                "success": False,
                "errors": ["PDF support not available. Install PyPDF2: pip install PyPDF2"]
            })
            return result

        try:
            import PyPDF2

            # Read PDF
            with open(path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)

                # Extract metadata
                pdf_info = pdf_reader.metadata
                metadata = BookMetadata(
                    title=pdf_info.get('/Title', path.stem),
                    author=pdf_info.get('/Author', ''),
                    total_pages=len(pdf_reader.pages)
                )

                # Extract text from pages (limit to first 50 pages)
                all_text = []
                page_texts = []

                for i, page in enumerate(pdf_reader.pages[:50]):
                    try:
                        text = page.extract_text()
                        if text and len(text.strip()) > 50:
                            all_text.append(text)
                            page_texts.append({
                                "page": i + 1,
                                "content": text[:1000]  # Preview per page
                            })
                    except Exception as e:
                        continue

                # Combine text
                combined_text = "\n\n".join(all_text)
                # Clean up text
                combined_text = re.sub(r'\s+', ' ', combined_text)

                result.content = {
                    "title": metadata.title,
                    "author": metadata.author,
                    "url": str(path),
                    "main_content": combined_text[:10000],  # Limit total content
                    "summary": self._generate_summary_from_text(combined_text[:2000]),
                    "metadata": {
                        "total_pages": metadata.total_pages,
                        "pages_extracted": len(all_text)
                    }
                }

                result.processing_info.update({
                    "processing_time": self._end_timer(),
                    "success": True,
                    "total_pages": metadata.total_pages,
                    "pages_extracted": len(all_text),
                    "file_size": path.stat().st_size
                })

                result.media = {
                    "pages": page_texts[:10]  # First 10 pages
                }

        except Exception as e:
            result.processing_info.update({
                "processing_time": self._end_timer(),
                "success": False,
                "errors": [f"PDF extraction failed: {str(e)}"]
            })

        return result

    def _extract_epub_metadata(self, book) -> BookMetadata:
        """Extract metadata from EPUB"""
        metadata = BookMetadata(title="Untitled")

        # Get metadata from epub
        epub_metadata = book.get_metadata('DC', [])

        for item in epub_metadata:
            name = item[0]
            value = item[1]

            if name == 'title':
                metadata.title = value
            elif name == 'creator':
                metadata.author = value
            elif name == 'publisher':
                metadata.publisher = value
            elif name == 'date':
                metadata.publish_date = value
            elif name == 'language':
                metadata.language = value
            elif name == 'subject':
                metadata.subject = value
            elif name == 'description':
                metadata.description = value
            elif name == 'identifier':
                if value.startswith('isbn:'):
                    metadata.isbn = value[5:]
                else:
                    metadata.isbn = value

        # Get table of contents
        toc = book.get_toc_list()
        metadata.table_of_contents = [
            {"title": item.get_title(), "href": item.get_href()}
            for item in toc[:50]  # Limit to 50 items
        ]
        metadata.chapter_count = len(toc)

        return metadata

    def _generate_summary_from_text(self, text: str) -> str:
        """Generate a simple summary from text"""
        # Take first paragraph and some key sentences
        sentences = re.split(r'[.!?]+', text)
        sentences = [s.strip() for s in sentences if len(s.strip()) > 20]

        if not sentences:
            return "Document content"

        # First sentence as summary
        return sentences[0][:500] if sentences else "Document content"

    def _check_epub_support(self) -> bool:
        """Check if EPUB support is available"""
        try:
            import ebooklib
            return True
        except ImportError:
            return False

    def _check_pdf_support(self) -> bool:
        """Check if PDF support is available"""
        try:
            import PyPDF2
            return True
        except ImportError:
            return False

    @staticmethod
    def get_installation_instructions() -> str:
        """Return installation instructions for dependencies"""
        return """
To enable book processing, install the following:

For EPUB support:
    pip install EbookLib beautifulsoup4

For PDF support:
    pip install PyPDF2

Or install all:
    pip install EbookLib beautifulsoup4 PyPDF2
        """


if __name__ == "__main__":
    # Test the book processor
    print("Book Processor Module")
    print("=" * 50)

    processor = BookProcessor()

    print(f"\nEPUB support: {processor.epub_available}")
    print(f"PDF support: {processor.pdf_available}")

    if not processor.epub_available or not processor.pdf_available:
        print("\n" + processor.get_installation_instructions())

    print("\n✓ Book processor module loaded!")
