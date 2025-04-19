import os
import base64
from azure.core.credentials import AzureKeyCredential
from azure.ai.documentintelligence import DocumentIntelligenceClient
from pathlib import Path

import json


class AzureOCRClient:
    def __init__(self, endpoint: str = None, key: str = None):
        self.endpoint = endpoint or os.getenv("AZURE_DOC_INTEL_ENDPOINT")
        self.key = key or os.getenv("AZURE_DOC_INTEL_KEY")
        self.client = DocumentIntelligenceClient(
            endpoint=self.endpoint,
            credential=AzureKeyCredential(self.key)
        )

   
    def extract_text(self, file_path: str, save_json: bool = True) -> str:
    
     with open(file_path, "rb") as f:
        base64_data = base64.b64encode(f.read()).decode("utf-8")

        poller = self.client.begin_analyze_document(
            model_id="prebuilt-read",
            analyze_request={"base64Source": base64_data}
        )

        result = poller.result()
        result_dict = result.as_dict()

        if save_json:
            output_path = Path(file_path).with_suffix(".json")
            with open(output_path, "w", encoding="utf-8") as out_file:
                json.dump(result_dict, out_file, ensure_ascii=False, indent=2)

        return "\n".join([line.content for page in result.pages for line in page.lines])


    def extract_raw_json(self, file_path: str) -> dict:

        with open(file_path, "rb") as f:
            base64_data = base64.b64encode(f.read()).decode("utf-8")

        poller = self.client.begin_analyze_document(
            model_id="prebuilt-read",
            analyze_request={"base64Source": base64_data}
        )

        result = poller.result()
   
   
        return result.as_dict()


   