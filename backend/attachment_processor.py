"""
Processore per gli allegati delle tesi.

Questo modulo gestisce l'estrazione del testo da vari formati di file
(PDF, DOCX, TXT) per utilizzarli come contesto nella generazione AI.
"""

import os
import fitz  # PyMuPDF
from pathlib import Path
from typing import Optional, List
from datetime import datetime
import mimetypes

# Importazione condizionale per python-docx
try:
    from docx import Document as DocxDocument
    DOCX_AVAILABLE = True
except ImportError:
    DOCX_AVAILABLE = False
    print("Warning: python-docx non installato. Supporto DOCX disabilitato.")

import config

# Formati supportati
ALLOWED_EXTENSIONS = {'.pdf', '.docx', '.txt'}
MAX_FILE_SIZE = config.THESIS_MAX_UPLOAD_SIZE  # 50MB default
MAX_CONTEXT_CHARS = config.THESIS_MAX_CONTEXT_CHARS  # 50000 caratteri default


def validate_file(filename: str, file_size: int) -> tuple[bool, str]:
    """
    Valida un file prima del processamento.

    Args:
        filename: Nome del file
        file_size: Dimensione in bytes

    Returns:
        Tupla (is_valid, error_message)
    """
    # Controlla estensione
    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        return False, f"Formato non supportato: {ext}. Formati validi: {', '.join(ALLOWED_EXTENSIONS)}"

    # Controlla dimensione
    if file_size > MAX_FILE_SIZE:
        max_mb = MAX_FILE_SIZE / (1024 * 1024)
        return False, f"File troppo grande. Dimensione massima: {max_mb:.0f}MB"

    return True, ""


def get_mime_type(filename: str) -> str:
    """Determina il MIME type di un file."""
    mime_type, _ = mimetypes.guess_type(filename)
    return mime_type or "application/octet-stream"


def extract_text_from_pdf(file_path: Path, max_pages: int = 100) -> str:
    """
    Estrae il testo da un file PDF.

    Args:
        file_path: Percorso del file PDF
        max_pages: Numero massimo di pagine da leggere

    Returns:
        Testo estratto dal PDF
    """
    try:
        doc = fitz.open(file_path)
        text_parts = []

        pages_to_read = min(max_pages, len(doc))

        for i in range(pages_to_read):
            page = doc[i]
            text = page.get_text()
            if text.strip():
                text_parts.append(text)

        doc.close()

        return "\n\n".join(text_parts)

    except Exception as e:
        raise RuntimeError(f"Errore nell'estrazione del testo dal PDF: {str(e)}")


def extract_text_from_docx(file_path: Path) -> str:
    """
    Estrae il testo da un file DOCX.

    Args:
        file_path: Percorso del file DOCX

    Returns:
        Testo estratto dal documento
    """
    if not DOCX_AVAILABLE:
        raise RuntimeError(
            "python-docx non installato. Installa con: pip install python-docx"
        )

    try:
        doc = DocxDocument(file_path)
        paragraphs = [para.text for para in doc.paragraphs if para.text.strip()]
        return "\n\n".join(paragraphs)

    except Exception as e:
        raise RuntimeError(f"Errore nell'estrazione del testo dal DOCX: {str(e)}")


def extract_text_from_txt(file_path: Path) -> str:
    """
    Legge il contenuto di un file di testo.

    Args:
        file_path: Percorso del file TXT

    Returns:
        Contenuto del file
    """
    try:
        # Prova diversi encoding
        for encoding in ['utf-8', 'latin-1', 'cp1252']:
            try:
                return file_path.read_text(encoding=encoding)
            except UnicodeDecodeError:
                continue

        raise RuntimeError("Impossibile decodificare il file con gli encoding supportati")

    except Exception as e:
        raise RuntimeError(f"Errore nella lettura del file TXT: {str(e)}")


def extract_text(file_path: Path) -> str:
    """
    Estrae il testo da un file in base al suo formato.

    Args:
        file_path: Percorso del file

    Returns:
        Testo estratto

    Raises:
        ValueError: Se il formato non è supportato
        RuntimeError: Se l'estrazione fallisce
    """
    extension = file_path.suffix.lower()

    if extension == '.pdf':
        return extract_text_from_pdf(file_path)
    elif extension == '.docx':
        return extract_text_from_docx(file_path)
    elif extension == '.txt':
        return extract_text_from_txt(file_path)
    else:
        raise ValueError(f"Formato non supportato: {extension}")


def process_attachment(
    file_path: Path,
    original_filename: str
) -> dict:
    """
    Processa un allegato e ne estrae il testo.

    Args:
        file_path: Percorso del file salvato
        original_filename: Nome originale del file

    Returns:
        Dizionario con i metadati dell'allegato e il testo estratto
    """
    file_size = file_path.stat().st_size

    # Valida
    is_valid, error = validate_file(original_filename, file_size)
    if not is_valid:
        raise ValueError(error)

    # Estrai testo
    extracted_text = extract_text(file_path)

    return {
        "filename": file_path.name,
        "original_filename": original_filename,
        "file_path": str(file_path),
        "file_size": file_size,
        "mime_type": get_mime_type(original_filename),
        "extracted_text": extracted_text,
        "created_at": datetime.utcnow()
    }


def build_attachments_context(
    attachments: List[dict],
    max_chars: int = MAX_CONTEXT_CHARS
) -> str:
    """
    Costruisce il contesto dagli allegati per i prompt AI.

    Combina il testo estratto da tutti gli allegati in un unico
    contesto, rispettando il limite di caratteri.

    Args:
        attachments: Lista di allegati con 'original_filename' e 'extracted_text'
        max_chars: Numero massimo di caratteri totali

    Returns:
        Stringa con il contesto formattato
    """
    if not attachments:
        return ""

    context_parts = []
    total_chars = 0
    chars_per_attachment = max_chars // len(attachments)

    for att in attachments:
        if not att.get('extracted_text'):
            continue

        text = att['extracted_text']
        filename = att.get('original_filename', 'Allegato')

        # Limita il testo di ogni allegato
        if len(text) > chars_per_attachment:
            text = text[:chars_per_attachment] + "\n[...testo troncato...]"

        context_part = f"""
--- ALLEGATO: {filename} ---
{text}
--- FINE ALLEGATO: {filename} ---
"""
        context_parts.append(context_part)
        total_chars += len(context_part)

        if total_chars >= max_chars:
            break

    return "\n".join(context_parts)


def save_uploaded_file(
    file_content: bytes,
    original_filename: str,
    thesis_id: str
) -> Path:
    """
    Salva un file uploadato nella directory appropriata.

    Args:
        file_content: Contenuto binario del file
        original_filename: Nome originale del file
        thesis_id: ID della tesi

    Returns:
        Path del file salvato
    """
    # Crea directory per la tesi
    thesis_dir = config.THESIS_UPLOADS_DIR / thesis_id
    thesis_dir.mkdir(parents=True, exist_ok=True)

    # Genera nome file unico
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_filename = "".join(c for c in original_filename if c.isalnum() or c in '._-')
    filename = f"{timestamp}_{safe_filename}"

    file_path = thesis_dir / filename

    # Salva il file
    with open(file_path, 'wb') as f:
        f.write(file_content)

    return file_path


def delete_attachment_file(file_path: str) -> bool:
    """
    Elimina un file allegato.

    Args:
        file_path: Percorso del file da eliminare

    Returns:
        True se eliminato con successo
    """
    try:
        path = Path(file_path)
        if path.exists():
            path.unlink()
            return True
        return False
    except Exception as e:
        print(f"Errore nell'eliminazione del file: {e}")
        return False


def cleanup_thesis_attachments(thesis_id: str) -> bool:
    """
    Elimina tutti gli allegati di una tesi.

    Args:
        thesis_id: ID della tesi

    Returns:
        True se eliminati con successo
    """
    try:
        thesis_dir = config.THESIS_UPLOADS_DIR / thesis_id
        if thesis_dir.exists():
            import shutil
            shutil.rmtree(thesis_dir)
            return True
        return False
    except Exception as e:
        print(f"Errore nella pulizia degli allegati: {e}")
        return False


# ============================================================================
# TEST
# ============================================================================
if __name__ == "__main__":
    # Test base
    print("Testing Attachment Processor...")
    print(f"Allowed extensions: {ALLOWED_EXTENSIONS}")
    print(f"Max file size: {MAX_FILE_SIZE / (1024*1024):.0f}MB")
    print(f"Max context chars: {MAX_CONTEXT_CHARS}")

    # Test validazione
    is_valid, error = validate_file("test.pdf", 1024)
    print(f"Validation test.pdf: {is_valid}, {error}")

    is_valid, error = validate_file("test.exe", 1024)
    print(f"Validation test.exe: {is_valid}, {error}")
