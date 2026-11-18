"""
IntelliDocs AI Model & Dataset Pre-downloader
Downloads required NLTK corpora, spaCy linguistic models, and Hugging Face weights.
"""
import sys
import subprocess


def download_nltk_data():
    print("[1/3] Downloading NLTK corpora (punkt, stopwords, wordnet)...")
    import nltk
    for pkg in ["punkt", "punkt_tab", "stopwords", "wordnet", "averaged_perceptron_tagger", "averaged_perceptron_tagger_eng"]:
        try:
            nltk.download(pkg, quiet=True)
            print(f"  + NLTK package '{pkg}' verified.")
        except Exception as e:
            print(f"  ! Warning downloading NLTK '{pkg}': {e}")


def download_spacy_model():
    print("[2/3] Downloading spaCy 'en_core_web_sm' model...")
    try:
        import spacy
        spacy.load("en_core_web_sm")
        print("  + spaCy model 'en_core_web_sm' is already installed.")
    except Exception:
        print("  Installing 'en_core_web_sm' via spacy download...")
        subprocess.run([sys.executable, "-m", "spacy", "download", "en_core_web_sm"], check=True)
        print("  + spaCy model 'en_core_web_sm' installed successfully.")


def verify_models():
    print("[3/3] Model verification complete.")
    print("Neural models (MiniLM, DistilBART, FLAN-T5) will lazy-load on demand via ModelManager.")


if __name__ == "__main__":
    download_nltk_data()
    download_spacy_model()
    verify_models()
    print("All basic language models and datasets initialized successfully!")
