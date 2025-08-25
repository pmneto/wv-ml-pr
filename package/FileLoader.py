import os
from pathlib import Path
from typing import List, Literal

class FileLoader:
    def __init__(self, directory: str = "images", allowed_extensions: List[str] = None):
        self.directory = Path(directory)
        self.allowed_extensions = [ext.lower() for ext in (allowed_extensions or [".jpg", ".jpeg", ".png", ".pdf"])]

        if not self.directory.exists():
            raise FileNotFoundError(f"Diretório '{self.directory}' não encontrado.")

    def list_files(self) -> List[Path]:
        return [
            f for f in self.directory.iterdir()
            if f.is_file() and f.suffix.lower() in self.allowed_extensions
        ]

    def list_files_sorted_by_metadata(self, sort_by: Literal["mtime", "size", "name"] = "mtime", reverse: bool = False) -> List[Path]:
        files = self.list_files()

        if sort_by == "mtime":
            return sorted(files, key=lambda f: f.stat().st_mtime, reverse=reverse)
        elif sort_by == "size":
            return sorted(files, key=lambda f: f.stat().st_size, reverse=reverse)
        elif sort_by == "name":
            return sorted(files, key=lambda f: f.name, reverse=reverse)
        else:
            raise ValueError("Opção inválida. Use 'mtime', 'size' ou 'name'.")