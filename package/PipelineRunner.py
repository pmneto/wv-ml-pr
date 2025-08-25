import os
import json
from pathlib import Path
from typing import Any, Iterable
import re



class PipelineRunner:

    ROOT = Path(__file__).resolve().parent
    LOGS_DIR = ROOT / "logs"
    LOGS_DIR.mkdir(exist_ok=True, parents=True)

    def __init__(
        self,
        ocr_client: Any,
        text_corrector: Any,
        exporter: Any,
        base_dir: str = "images",
        output_dir: str = "output",
        order_by: str = "name",   # "name" | "mtime" | "ctime"
    ):
        self.ocr = ocr_client
        self.corrector = text_corrector
        self.exporter = exporter
        self.base_dir = Path(base_dir)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # corrige: caminho de arquivo de log (não a pasta)
        self.failed_log_path = self.LOGS_DIR / "falhas_ocr.txt"

        # como ordenar as imagens dentro de cada pasta
        self.order_by = order_by

    # --- helpers de ordenação ---
    @staticmethod
    def _natural_key(s: str) -> list:
        # "10" depois de "2"? natural sort resolve.
        return [int(t) if t.isdigit() else t.lower() for t in re.findall(r"\d+|\D+", s)]

    def _iter_images_sorted(self, folder: Path) -> list[Path]:
        exts = {".jpg", ".jpeg", ".png", ".pdf"}
        files = [p for p in folder.iterdir() if p.is_file() and p.suffix.lower() in exts]
        # ignora temporários, caso existam
        files = [p for p in files if not p.name.startswith("__tmp__")]

        if self.order_by == "name":
            return sorted(files, key=lambda p: self._natural_key(p.name))
        elif self.order_by == "mtime":
            return sorted(files, key=lambda p: p.stat().st_mtime)
        else:  # "ctime" (cuidado no Linux/WSL)
            st = files[0].stat() if files else None
            return sorted(files, key=lambda p: p.stat().st_ctime)

    def run(self, force_ocr: bool = False):
        for folder in self.base_dir.iterdir():
            if not folder.is_dir():
                continue

            print(f"Processando pasta: {folder.name}")
            all_text = []

            # >>> agora ordena por name|mtime|ctime conforme self.order_by
            image_files = self._iter_images_sorted(folder)

            for image in image_files:
                try:
                    json_path = image.with_suffix(".json")
                    if json_path.exists() and not force_ocr:
                        print(f"JSON já existe para {image.name}, pulando OCR...")
                        annotated_text = self._extract_words_with_confidence(json_path)
                        corrected = self.corrector.correct_text(annotated_text)
                    else:
                        print(f"🖼️  Extraindo via OCR: {image.name}")
                        raw_text = self.ocr.extract_text(str(image), save_json=True)
                        corrected = self.corrector.correct_text(raw_text)

                    all_text.append(corrected)

                except Exception as e:
                    self._log_failure(folder.name, image.name, str(e))
                    print(f"Falha ao processar {image.name}: {e}")

            if all_text:
                final_text = "\n\n".join(all_text)
                output_name = f"{folder.name}.docx"
                path = self.exporter.save_text_to_docx(final_text, output_name)
                print(f"Documento salvo em: {path}")
            else:
                print("No all text captured.")

    def _extract_words_with_confidence(self, json_path: Path) -> str:
        with open(json_path, "r", encoding="utf-8") as f:
            json_dict = json.load(f)

        words = []
        pages = json_dict.get("pages") or json_dict.get("analyzeResult", {}).get("pages", [])
        for page in pages:
            for word in page.get("words", []):
                content = word.get("content", "").strip()
                confidence = word.get("confidence", 0.0)
                if content:
                    if confidence >= 0.85:
                        words.append(content)
                    else:
                        words.append(f"[{content} | conf={confidence:.2f}]")
        return " ".join(words)

    def _log_failure(self, folder_name: str, file_name: str, error: str):
        self.LOGS_DIR.mkdir(parents=True, exist_ok=True)
        with open(self.failed_log_path, "a", encoding="utf-8") as f:
            f.write(f"[{folder_name}] {file_name} - ERRO: {error}\n")
