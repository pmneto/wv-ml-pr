import os
from pathlib import Path
from docx import Document
from typing import Optional

class DocxExporter:
    def __init__(self, output_dir: str = "output"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def save_text_to_docx(self, text: str, filename: Optional[str] = "documento_corrigido.docx") -> Path:
        doc = Document()
        for line in text.strip().splitlines():
            doc.add_paragraph(line)

        output_path = self.output_dir / filename
        doc.save(output_path)
        return output_path