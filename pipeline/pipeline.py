import infrastructure.nlp as nlp 
import infrastructure.ocr as ocr 
import multiprocessing
import os 

def pipeline(dir: str) -> list[tuple]: 
    
    cores = multiprocessing.cpu_count()
    worker = multiprocessing.Pool(cores/2)
    
    dir = os.listdir(dir)
    preprocessed_files = worker.map(ocr.preprocess, dir)
    extracted_content = worker.map(ocr.ocr_document, preprocessed_files)
        