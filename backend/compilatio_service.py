"""
Servizio Compilatio per AI Detection e analisi plagio.

Integrazione completa con le API Compilatio per:
- Upload documenti (con conversione testo -> PDF)
- Analisi plagio e AI detection
- Download report PDF
- Caching risultati tramite hash del testo (dedup)
"""

import os
import json
import time
import hashlib
import logging
import tempfile
from datetime import datetime
from typing import Optional, Callable

import requests
import fitz  # PyMuPDF

import config
from database import SessionLocal
from db_models import CompilatioScan

logger = logging.getLogger(__name__)


class CompilatioError(Exception):
    """Errore generico del servizio Compilatio."""
    pass


class CompilatioAuthError(CompilatioError):
    """Errore di autenticazione Compilatio."""
    pass


class CompilatioTimeoutError(CompilatioError):
    """Timeout durante elaborazione/analisi Compilatio."""
    pass


class CompilatioService:
    """
    Client API Compilatio per analisi plagio e AI detection.

    Gestisce autenticazione, upload, analisi e download report.
    Supporta caching token e dedup tramite hash del testo.
    """

    def __init__(self):
        self.base_url = config.COMPILATIO_BASE_URL
        self.username = config.COMPILATIO_USERNAME
        self.password = config.COMPILATIO_PASSWORD
        self.recipe = config.COMPILATIO_RECIPE
        self.report_lang = config.COMPILATIO_REPORT_LANG
        self.poll_interval = config.COMPILATIO_POLL_INTERVAL
        self.max_retries = config.COMPILATIO_MAX_RETRIES
        self.reports_dir = config.COMPILATIO_REPORTS_DIR

        # Sessione HTTP persistente
        self._session = None
        self._token = None
        self._folder_id = None

    def _get_session(self) -> requests.Session:
        """Restituisce una sessione HTTP configurata."""
        if self._session is None:
            self._session = requests.Session()
            self._session.headers.update({
                "Accept": "application/json",
                "User-Agent": "StyleForge/1.0"
            })
        return self._session

    def _login(self) -> str:
        """
        Effettua il login su Compilatio e restituisce il token.
        Il token viene cachato per riutilizzo.
        """
        if self._token:
            return self._token

        session = self._get_session()
        url = f"{self.base_url}/api/private/authentication/login/credentials"
        payload = {
            "username": self.username,
            "password": self.password,
            "version": 5
        }

        try:
            resp = session.post(url, json=payload, timeout=30)
            resp.raise_for_status()
            data = resp.json()

            self._token = data["data"]["token"]
            session.headers.update({"x-auth-token": self._token})
            logger.info("Login Compilatio riuscito")
            return self._token
        except requests.exceptions.RequestException as e:
            logger.error(f"Login Compilatio fallito: {e}")
            raise CompilatioAuthError(f"Login fallito: {e}")

    def _get_folder_id(self) -> str:
        """Recupera l'ID della cartella principale (cachato)."""
        if self._folder_id:
            return self._folder_id

        session = self._get_session()
        url = f"{self.base_url}/api/private/folders"
        params = {
            "filter": "not_lms",
            "filterParams[search]": ""
        }

        try:
            resp = session.get(url, params=params, timeout=30)
            resp.raise_for_status()
            folders = resp.json()["data"]["folders"]

            for folder in folders:
                if folder.get("main"):
                    self._folder_id = folder["id"]
                    logger.info(f"Cartella principale trovata: {self._folder_id[:12]}...")
                    return self._folder_id

            raise CompilatioError("Nessuna cartella principale trovata su Compilatio")
        except requests.exceptions.RequestException as e:
            raise CompilatioError(f"Errore recupero cartelle: {e}")

    def _text_to_pdf(self, text: str, filename: str = "document.pdf") -> str:
        """
        Converte testo in un file PDF usando PyMuPDF (fitz).

        Args:
            text: Testo da convertire
            filename: Nome del file PDF

        Returns:
            Path del file PDF creato
        """
        pdf_path = os.path.join(tempfile.gettempdir(), f"compilatio_{hashlib.md5(text[:100].encode()).hexdigest()}.pdf")

        try:
            doc = fitz.open()

            # Configurazione pagina A4
            page_width = 595  # A4 width in points
            page_height = 842  # A4 height in points
            margin = 50
            usable_width = page_width - 2 * margin
            usable_height = page_height - 2 * margin

            fontname = "helv"
            fontsize = 11
            line_height = fontsize * 1.5

            # Dividi il testo in righe wrappate
            lines = []
            for paragraph in text.split('\n'):
                if not paragraph.strip():
                    lines.append('')
                    continue

                # Word-wrap manuale
                words = paragraph.split()
                current_line = ''
                for word in words:
                    test_line = f"{current_line} {word}".strip() if current_line else word
                    text_width = fitz.get_text_length(test_line, fontname=fontname, fontsize=fontsize)
                    if text_width <= usable_width:
                        current_line = test_line
                    else:
                        if current_line:
                            lines.append(current_line)
                        current_line = word
                if current_line:
                    lines.append(current_line)

            # Scrivi le righe sulle pagine
            page = doc.new_page(width=page_width, height=page_height)
            y = margin

            for line in lines:
                if y + line_height > page_height - margin:
                    page = doc.new_page(width=page_width, height=page_height)
                    y = margin

                if line:  # Non scrivere righe vuote (solo spazio)
                    page.insert_text(
                        fitz.Point(margin, y),
                        line,
                        fontname=fontname,
                        fontsize=fontsize,
                        color=(0, 0, 0)
                    )
                y += line_height

            doc.save(pdf_path)
            doc.close()

            logger.info(f"PDF creato: {pdf_path} ({os.path.getsize(pdf_path) / 1024:.1f} KB)")
            return pdf_path

        except Exception as e:
            logger.error(f"Errore creazione PDF: {e}")
            raise CompilatioError(f"Errore conversione testo in PDF: {e}")

    def _force_relogin(self):
        """Forza un nuovo login invalidando il token corrente."""
        self._token = None
        session = self._get_session()
        # Rimuovi header token vecchio
        session.headers.pop("x-auth-token", None)
        return self._login()

    def _upload_document(self, pdf_path: str, folder_id: str) -> str:
        """
        Carica un documento PDF su Compilatio.
        Gestisce token scaduti (errore 498) con retry automatico.

        Returns:
            Document ID su Compilatio
        """
        session = self._get_session()
        url = f"{self.base_url}/api/private/document/create"
        filename = os.path.basename(pdf_path)

        max_attempts = 2  # 1 tentativo + 1 retry con re-login
        for attempt in range(1, max_attempts + 1):
            try:
                with open(pdf_path, "rb") as f:
                    files = {"file": (filename, f, "application/pdf")}
                    data = {"folder_id": folder_id}
                    resp = session.post(url, data=data, files=files, timeout=60)

                resp.raise_for_status()
                doc_id = resp.json()["data"]["document"]["id"]
                logger.info(f"Documento caricato su Compilatio: {doc_id[:12]}...")
                return doc_id
            except requests.exceptions.HTTPError as e:
                status_code = e.response.status_code if e.response is not None else 0
                # 498 = token scaduto/invalido, 401 = non autorizzato
                if status_code in (498, 401) and attempt < max_attempts:
                    logger.warning(f"Token scaduto (HTTP {status_code}) durante upload, ri-autenticazione...")
                    self._force_relogin()
                    continue
                raise CompilatioError(f"Errore upload documento: {e}")
            except requests.exceptions.RequestException as e:
                raise CompilatioError(f"Errore upload documento: {e}")

    def _fetch_documents(self, folder_id: str) -> list:
        """Recupera la lista documenti di una cartella."""
        session = self._get_session()
        url = f"{self.base_url}/api/private/documents"
        filter_obj = json.dumps({
            "folder_id": folder_id,
            "archived": False,
            "binned": False
        })
        params = {
            "filter": filter_obj,
            "page": 1,
            "limit": 50,
            "sort[uploadDate]": -1
        }

        resp = session.get(url, params=params, timeout=30)
        resp.raise_for_status()
        return resp.json()["data"]["documents"]

    def _find_document(self, documents: list, doc_id: str) -> Optional[dict]:
        """Trova un documento per ID nella lista."""
        for doc in documents:
            if doc["id"] == doc_id:
                return doc
        return None

    def _wait_for_processing(
        self,
        folder_id: str,
        doc_id: str,
        progress_callback: Optional[Callable] = None
    ) -> dict:
        """
        Attende che il documento venga elaborato (estrazione testo).

        Args:
            folder_id: ID cartella
            doc_id: ID documento
            progress_callback: Callback per aggiornare progresso (0-30%)
        """
        for attempt in range(1, self.max_retries + 1):
            documents = self._fetch_documents(folder_id)
            doc = self._find_document(documents, doc_id)

            if doc is None:
                logger.debug(f"Elaborazione: documento non ancora visibile (tentativo {attempt})")
                time.sleep(self.poll_interval)
                continue

            tags = doc.get("tags", [])
            words = doc.get("words_count", 0)

            if "empty" not in tags and words > 0:
                logger.info(f"Documento elaborato: {words} parole")
                if progress_callback:
                    progress_callback(30)
                return doc

            if progress_callback:
                progress = min(25, int(attempt / self.max_retries * 25))
                progress_callback(progress)

            time.sleep(self.poll_interval)

        raise CompilatioTimeoutError("Timeout: documento non elaborato in tempo")

    def _start_analysis(self, doc_id: str) -> str:
        """
        Avvia l'analisi di plagio e AI detection.
        Gestisce token scaduti con retry automatico.

        Returns:
            Analysis ID
        """
        session = self._get_session()
        url = f"{self.base_url}/api/private/analysis/create"
        payload = {
            "recipe_name": self.recipe,
            "doc_id": doc_id,
            "params": None
        }

        max_attempts = 2
        for attempt in range(1, max_attempts + 1):
            try:
                resp = session.post(url, json=payload, timeout=30)
                resp.raise_for_status()
                analysis_id = resp.json()["data"]["analysis"]["id"]
                logger.info(f"Analisi avviata: {analysis_id[:12]}...")
                return analysis_id
            except requests.exceptions.HTTPError as e:
                status_code = e.response.status_code if e.response is not None else 0
                if status_code in (498, 401) and attempt < max_attempts:
                    logger.warning(f"Token scaduto (HTTP {status_code}) durante avvio analisi, ri-autenticazione...")
                    self._force_relogin()
                    continue
                raise CompilatioError(f"Errore avvio analisi: {e}")
            except requests.exceptions.RequestException as e:
                raise CompilatioError(f"Errore avvio analisi: {e}")

    def _wait_for_analysis(
        self,
        folder_id: str,
        doc_id: str,
        progress_callback: Optional[Callable] = None
    ) -> dict:
        """
        Attende il completamento dell'analisi.

        Args:
            folder_id: ID cartella
            doc_id: ID documento
            progress_callback: Callback per aggiornare progresso (30-85%)
        """
        last_state = None
        analysis_poll_interval = max(self.poll_interval, 7)  # Analisi piu' lenta

        for attempt in range(1, self.max_retries + 1):
            documents = self._fetch_documents(folder_id)
            doc = self._find_document(documents, doc_id)

            if doc is None:
                time.sleep(analysis_poll_interval)
                continue

            analyses = doc.get("analyses", {})
            analysis = analyses.get(self.recipe)

            if analysis is None:
                time.sleep(analysis_poll_interval)
                continue

            state = analysis.get("state", "unknown")

            if state != last_state:
                logger.info(f"Stato analisi: {state}")
                last_state = state

            if state == "finished":
                logger.info("Analisi completata!")
                if progress_callback:
                    progress_callback(85)
                return doc

            if state in ("error", "canceled"):
                raise CompilatioError(f"Analisi fallita con stato: {state}")

            if progress_callback:
                progress = 30 + min(50, int(attempt / self.max_retries * 50))
                progress_callback(progress)

            time.sleep(analysis_poll_interval)

        raise CompilatioTimeoutError("Timeout: analisi non completata in tempo")

    def _get_results(self, document: dict) -> dict:
        """Estrae i risultati dell'analisi dal documento."""
        scores = document.get("scores", {}) or {}
        analyses = document.get("analyses", {})
        analysis = analyses.get(self.recipe, {})
        light_reports = document.get("light_reports", {}) or {}
        light_report = light_reports.get(self.recipe, {})

        pois = light_report.get("pois", [])

        return {
            "analysis_id": analysis.get("id"),
            "global_score_percent": scores.get("global_score_percent", 0),
            "similarity_percent": scores.get("similarity_percent", 0),
            "exact_percent": scores.get("exact_percent", 0),
            "ai_generated_percent": scores.get("ai_generated_percent", 0),
            "same_meaning_percent": scores.get("same_meaning_percent", 0),
            "translation_percent": scores.get("translation_percent", 0),
            "quotation_percent": scores.get("quotation_percent", 0),
            "suspicious_fingerprint_percent": scores.get("suspicious_fingerprint_percent", 0),
            "points_of_interest": len(pois),
            "pois": pois,
        }

    def _download_report(self, analysis_id: str, output_path: str) -> str:
        """
        Scarica il report PDF dettagliato.

        Args:
            analysis_id: ID dell'analisi
            output_path: Path dove salvare il PDF

        Returns:
            Path del file salvato
        """
        session = self._get_session()
        url = f"{self.base_url}/api/private/report/anasim/{analysis_id}/pdf/{self.report_lang}/detailed"

        try:
            resp = session.get(url, stream=True, timeout=120)
            resp.raise_for_status()

            os.makedirs(os.path.dirname(output_path), exist_ok=True)

            with open(output_path, "wb") as f:
                for chunk in resp.iter_content(chunk_size=8192):
                    f.write(chunk)

            report_size = os.path.getsize(output_path)
            logger.info(f"Report scaricato: {output_path} ({report_size / 1024:.1f} KB)")
            return output_path
        except requests.exceptions.RequestException as e:
            logger.error(f"Errore download report: {e}")
            raise CompilatioError(f"Errore download report: {e}")

    @staticmethod
    def compute_text_hash(text: str) -> str:
        """Calcola SHA-256 del testo per dedup."""
        # Normalizza: rimuovi spazi multipli, trim
        normalized = ' '.join(text.split())
        return hashlib.sha256(normalized.encode('utf-8')).hexdigest()

    @staticmethod
    def check_existing_scan(text_hash: str, user_id: str, db=None) -> Optional[dict]:
        """
        Controlla se esiste gia' una scansione per questo testo.

        Args:
            text_hash: Hash SHA-256 del testo
            user_id: ID utente
            db: Sessione database (opzionale, ne crea una se non fornita)

        Returns:
            dict con risultato se trovato, None altrimenti
        """
        close_db = False
        if db is None:
            db = SessionLocal()
            close_db = True

        try:
            scan = db.query(CompilatioScan).filter(
                CompilatioScan.document_text_hash == text_hash,
                CompilatioScan.completed_at.isnot(None)
            ).order_by(CompilatioScan.created_at.desc()).first()

            if scan:
                return scan.to_dict()
            return None
        finally:
            if close_db:
                db.close()

    def scan_text(
        self,
        text: str,
        user_id: str,
        job_id: str,
        source_type: Optional[str] = None,
        source_job_id: Optional[str] = None,
        progress_callback: Optional[Callable] = None
    ) -> str:
        """
        Esegue una scansione completa Compilatio su un testo.

        Questo metodo e' pensato per essere chiamato come task di un job:
        1. Converte testo in PDF
        2. Login su Compilatio
        3. Upload documento
        4. Avvia e attende analisi
        5. Raccoglie risultati
        6. Scarica report PDF
        7. Salva tutto nel database

        Args:
            text: Testo da analizzare
            user_id: ID utente
            job_id: ID del job associato
            source_type: Tipo sorgente (generate, humanize, thesis, manual)
            source_job_id: Job ID del contenuto originale
            progress_callback: Callback per aggiornare progresso (0-100)

        Returns:
            JSON string con i risultati (salvato in Job.result)
        """
        db = SessionLocal()

        try:
            text_hash = self.compute_text_hash(text)
            word_count = len(text.split())

            if progress_callback:
                progress_callback(5)

            # 1. Converti testo in PDF
            logger.info(f"[Compilatio] Conversione testo in PDF ({word_count} parole)...")
            pdf_path = self._text_to_pdf(text, f"scan_{job_id}.pdf")

            if progress_callback:
                progress_callback(10)

            # 2. Login
            logger.info("[Compilatio] Login...")
            self._login()

            if progress_callback:
                progress_callback(15)

            # 3. Recupera cartella principale
            folder_id = self._get_folder_id()

            # 4. Upload documento
            logger.info("[Compilatio] Upload documento...")
            doc_id = self._upload_document(pdf_path, folder_id)

            if progress_callback:
                progress_callback(20)

            # 5. Attendi elaborazione
            logger.info("[Compilatio] Attesa elaborazione...")
            doc = self._wait_for_processing(folder_id, doc_id, progress_callback)
            compilatio_word_count = doc.get("words_count", word_count)

            # 6. Avvia analisi
            logger.info("[Compilatio] Avvio analisi...")
            analysis_id = self._start_analysis(doc_id)

            if progress_callback:
                progress_callback(35)

            # 7. Attendi analisi
            logger.info("[Compilatio] Attesa completamento analisi...")
            doc = self._wait_for_analysis(folder_id, doc_id, progress_callback)

            # 8. Estrai risultati
            results = self._get_results(doc)
            logger.info(
                f"[Compilatio] Risultati: AI={results['ai_generated_percent']:.1f}%, "
                f"Similarita={results['similarity_percent']:.1f}%, "
                f"Globale={results['global_score_percent']:.1f}%"
            )

            if progress_callback:
                progress_callback(90)

            # 9. Download report PDF
            report_filename = f"report_{job_id}.pdf"
            report_path = os.path.join(str(self.reports_dir), report_filename)
            try:
                self._download_report(results["analysis_id"], report_path)
            except CompilatioError as e:
                logger.warning(f"Download report fallito (non critico): {e}")
                report_path = None

            if progress_callback:
                progress_callback(95)

            # 10. Salva nel database
            scan = CompilatioScan(
                job_id=job_id,
                user_id=user_id,
                compilatio_doc_id=doc_id,
                compilatio_analysis_id=results.get("analysis_id"),
                compilatio_folder_id=folder_id,
                document_filename=f"scan_{job_id}.pdf",
                document_text_hash=text_hash,
                word_count=compilatio_word_count,
                global_score_percent=results["global_score_percent"],
                similarity_percent=results["similarity_percent"],
                exact_percent=results["exact_percent"],
                ai_generated_percent=results["ai_generated_percent"],
                same_meaning_percent=results["same_meaning_percent"],
                translation_percent=results["translation_percent"],
                quotation_percent=results["quotation_percent"],
                suspicious_fingerprint_percent=results["suspicious_fingerprint_percent"],
                points_of_interest=results["points_of_interest"],
                report_pdf_path=report_path,
                scan_details=results,
                source_type=source_type,
                source_job_id=source_job_id,
                completed_at=datetime.utcnow()
            )
            db.add(scan)
            db.commit()
            db.refresh(scan)

            logger.info(f"[Compilatio] Scansione salvata: {scan.id}")

            # Pulisci PDF temporaneo
            try:
                os.remove(pdf_path)
            except OSError:
                pass

            if progress_callback:
                progress_callback(100)

            # Ritorna JSON con risultati (salvato in Job.result)
            return json.dumps(scan.to_dict(), default=str)

        except Exception as e:
            logger.error(f"[Compilatio] Errore scansione: {e}")
            # Pulisci PDF temporaneo in caso di errore
            try:
                if 'pdf_path' in locals():
                    os.remove(pdf_path)
            except OSError:
                pass
            raise
        finally:
            db.close()


# Singleton del servizio
_compilatio_service: Optional[CompilatioService] = None


def get_compilatio_service() -> CompilatioService:
    """Restituisce l'istanza singleton del servizio Compilatio."""
    global _compilatio_service
    if _compilatio_service is None:
        _compilatio_service = CompilatioService()
    return _compilatio_service
