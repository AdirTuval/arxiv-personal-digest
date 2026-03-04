from unittest.mock import MagicMock, patch

import httpx
import pytest

from pdf_extract import (
    download_pdf,
    extract_text_from_pdf,
    fetch_paper_full_text,
    fetch_paper_full_texts,
)


class TestDownloadPdf:
    @patch("pdf_extract.httpx.get")
    def test_download_pdf_returns_bytes(self, mock_get):
        mock_response = MagicMock()
        mock_response.content = b"%PDF-1.4 fake pdf content"
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        result = download_pdf("2401.12345")

        assert result == b"%PDF-1.4 fake pdf content"
        mock_get.assert_called_once_with(
            "https://arxiv.org/pdf/2401.12345.pdf",
            timeout=60,
            follow_redirects=True,
        )

    @patch("pdf_extract.httpx.get")
    def test_download_pdf_raises_on_http_error(self, mock_get):
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "404", request=MagicMock(), response=MagicMock()
        )
        mock_get.return_value = mock_response

        with pytest.raises(httpx.HTTPStatusError):
            download_pdf("2401.99999")

    @patch("pdf_extract.httpx.get")
    def test_download_pdf_custom_timeout(self, mock_get):
        mock_response = MagicMock()
        mock_response.content = b"pdf"
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        download_pdf("2401.12345", timeout=30)

        mock_get.assert_called_once_with(
            "https://arxiv.org/pdf/2401.12345.pdf",
            timeout=30,
            follow_redirects=True,
        )


class TestExtractTextFromPdf:
    @patch("pdf_extract.pymupdf.open")
    def test_extract_text_from_pdf(self, mock_open):
        mock_page1 = MagicMock()
        mock_page1.get_text.return_value = "Page 1 text"
        mock_page2 = MagicMock()
        mock_page2.get_text.return_value = "Page 2 text"
        mock_doc = MagicMock()
        mock_doc.__iter__ = MagicMock(return_value=iter([mock_page1, mock_page2]))
        mock_open.return_value = mock_doc

        result = extract_text_from_pdf(b"fake pdf bytes")

        assert result == "Page 1 text\nPage 2 text"
        mock_open.assert_called_once_with(stream=b"fake pdf bytes", filetype="pdf")
        mock_doc.close.assert_called_once()


class TestFetchPaperFullText:
    @patch("pdf_extract.extract_text_from_pdf")
    @patch("pdf_extract.download_pdf")
    def test_fetch_paper_full_text_success(self, mock_download, mock_extract):
        mock_download.return_value = b"pdf bytes"
        mock_extract.return_value = "Extracted paper text"

        result = fetch_paper_full_text("2401.12345")

        assert result == "Extracted paper text"
        mock_download.assert_called_once_with("2401.12345")
        mock_extract.assert_called_once_with(b"pdf bytes")

    @patch("pdf_extract.download_pdf")
    def test_fetch_paper_full_text_download_failure(self, mock_download):
        mock_download.side_effect = httpx.ConnectError("Connection failed")

        result = fetch_paper_full_text("2401.12345")

        assert result == ""

    @patch("pdf_extract.extract_text_from_pdf")
    @patch("pdf_extract.download_pdf")
    def test_fetch_paper_full_text_extract_failure(self, mock_download, mock_extract):
        mock_download.return_value = b"corrupted pdf"
        mock_extract.side_effect = RuntimeError("Parse error")

        result = fetch_paper_full_text("2401.12345")

        assert result == ""


class TestFetchPaperFullTexts:
    @patch("pdf_extract.fetch_paper_full_text")
    def test_fetch_paper_full_texts_batch(self, mock_fetch):
        mock_fetch.side_effect = ["Text for paper 1", "", "Text for paper 3"]

        result = fetch_paper_full_texts(["2401.12345", "2401.12346", "2401.12347"])

        assert result == {
            "2401.12345": "Text for paper 1",
            "2401.12346": "",
            "2401.12347": "Text for paper 3",
        }
        assert mock_fetch.call_count == 3

    @patch("pdf_extract.fetch_paper_full_text")
    def test_fetch_paper_full_texts_empty(self, mock_fetch):
        result = fetch_paper_full_texts([])

        assert result == {}
        mock_fetch.assert_not_called()
