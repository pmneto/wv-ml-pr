import os
import json
from openai import OpenAI
from typing import Optional, Dict, Any
from dotenv import load_dotenv

class OpenAITextCorrector:
    def __init__(self, api_key: Optional[str] = None, model: str = "gpt-3.5-turbo"):
        load_dotenv()
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.model = model
        self.client = OpenAI(api_key=self.api_key)
        self.system_prompt = (
            "Você é um assistente que corrige textos com erros comuns de OCR. "
            "Mantenha a estrutura, pontuação e estilo do texto original tanto quanto possível. "
            "Por favor, em caso de desestruturação do texto, organize os parágrafos de forma necessária. "
            "Não invente informações e não altere o sentido do conteúdo. "
            "Você tem liberdade para inferir e realizar a troca de palavras que não têm sentido na língua portuguesa, "
            "mas cuidado: o autor usa linguagem tradicional, com palavras rebuscadas e mais antigas. "
            "O campo 'confidence' representa a confiança da ferramenta OCR sobre cada palavra. "
            "Dê atenção especial às palavras com confidence abaixo de 0.75, em caso dessa informação ser disponibilizada."
            "Palavras em caixa alta sem contexto devem ser adequadas a formatação correta."
            "Elimine detalhes como paginação e caractéres não essenciais para interpretação de texto."
            "Revise e corrija o texto, por favor"
            
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
