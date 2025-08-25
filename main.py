from package.AzureOCRfile import AzureOCRClient
from package.FileLoader import FileLoader
from package.OpenAITextCorrector import OpenAITextCorrector
from package.DocxExporter import DocxExporter
from package.PipelineRunner import PipelineRunner

import streamlit as st
import os
from dotenv import load_dotenv

load_dotenv()


AZURE_DOC_INTEL_ENDPOINT = (
    os.getenv("AZURE_DOC_INTEL_ENDPOINT") 
    or st.secrets.get("AZURE_DOC_INTEL_ENDPOINT")
)
AZURE_DOC_INTEL_KEY = (
    os.getenv("AZURE_DOC_INTEL_KEY") 
    or st.secrets.get("AZURE_DOC_INTEL_KEY")
)


ocr = AzureOCRClient()
corrector = OpenAITextCorrector()
exporter = DocxExporter("output")

runner = PipelineRunner(ocr, corrector, exporter,base_dir='./images/')
runner.run()
