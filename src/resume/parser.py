import pdfplumber
from src.prompts import RESUME_PARSER_SYSTEM, RESUME_PARSER_USER
from src.llm.base import LLMClient


def extract_text_from_pdf(pdf_path: str) -> str:
    """Extract raw text from a PDF using pdfplumber."""
    pages = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                pages.append(text.strip())
    if not pages:
        raise ValueError(f"Could not extract any text from PDF: {pdf_path}")
    return "\n\n".join(pages)


def parse_resume_with_llm(raw_text: str, llm_client: LLMClient) -> dict:
    """Send raw resume text to LLM and return structured JSON dict."""
    user_msg = RESUME_PARSER_USER.format(raw_resume_text=raw_text)
    return llm_client.complete_json(RESUME_PARSER_SYSTEM, user_msg)
