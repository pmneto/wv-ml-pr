import os
import json
from openai import OpenAI
from typing import Optional, Dict, Any
from dotenv import load_dotenv
import streamlit as st

class OpenAITextCorrector:
    def __init__(self, api_key: Optional[str] = None, model: str = "gpt-4o-mini"):
        load_dotenv()
        self.api_key = api_key or os.getenv("OPENAI_API_KEY") or st.secrets.get("OPENAI_API_KEY")
        self.model = model
        self.client = OpenAI(api_key=self.api_key)
        self.system_prompt = (
            "You are an assistant specialized in correcting texts with common OCR (Optical Character Recognition) errors. "
            "Your mission is to make the content readable and grammatically correct, without changing the original meaning. "
            "You may receive the text in two forms:\n"
            "1. Plain text, without confidence markers — in this case, just correct spelling, punctuation, and structure, "
            "while preserving the author's style.\n"
            "2. Text with markers in the format [word | conf=value], where 'conf' indicates the OCR's confidence score "
            "for that word. Pay special attention to words with confidence below 0.75, as they are more likely to be wrong. "
            "Replace or correct them according to context.\n\n"
            "In both cases:\n"
            "- Respect the original style, which tends to be traditional, formal, and may include elaborate or archaic words.\n"
            "- Reorganize sentences and paragraphs when necessary to maintain cohesion and textual flow.\n"
            "- Remove useless symbols, page numbers, and disconnected words that hinder readability.\n"
            "- Never invent information or alter the meaning of the content."
        )



    def set_prompt(self, prompt: str):
        self.system_prompt = prompt

    def correct_text(self, raw_text: str) -> str:
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": f"Corrija o seguinte texto OCR:\n{raw_text}"}
            ],
            temperature=0.4,
        )
        return response.choices[0].message.content.strip()

    def correct_text_from_json(self, json_dict: dict) -> str:
        """
        Corrige o texto extraído do OCR a partir do JSON bruto.
        """
        try:
            raw_text = json_dict.get("analyzeResult", {}).get("content", "")
            
            if not raw_text.strip():
                raise ValueError("Texto OCR está vazio ou não foi encontrado no JSON.")

            # (Opcional) Debug para visualizar o que está sendo enviado
            print("[DEBUG] Texto enviado ao LLM:", raw_text[:300])

            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": f"Corrija o seguinte texto OCR:\n{raw_text}"}
                ],
                temperature=0.4,
            )

            return response.choices[0].message.content.strip()
        
        except Exception as e:
            print(f"[ERRO] Falha ao corrigir JSON: {e}")
            return f"[ERRO] Falha ao corrigir texto OCR: {e}"
