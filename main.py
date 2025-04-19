from package.AzureOCRfile import AzureOCRClient
from package.FileLoader import FileLoader
from package.OpenAITextCorrector import OpenAITextCorrector
from package.DocxExporter import DocxExporter
from package.PipelineRunner import PipelineRunner


import os
from dotenv import load_dotenv

load_dotenv()


AZURE_DOC_INTEL_ENDPOINT, AZURE_DOC_INTEL_KEY = os.environ['AZURE_DOC_INTEL_ENDPOINT'],os.environ['AZURE_DOC_INTEL_KEY']


ocr = AzureOCRClient()
corrector = OpenAITextCorrector()
exporter = DocxExporter("output")

runner = PipelineRunner(ocr, corrector, exporter,base_dir='wv-ml-pr/images/')
runner.run()
