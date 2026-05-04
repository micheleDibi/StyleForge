"""
Client SOAP per SolutionPA / PagoPA (Modello 1, Checkout online).

Espone le operazioni del DataProvider:
  * pdpCaricaPagamentoInAttesa  -> crea posizione, restituisce IUV
  * pdpAttivaRPT                 -> attiva pagamento, restituisce checkout URL + CCP
  * pdpModificaPosizioneDebitoria -> annulla / modifica posizione
  * pdpEsitRT                    -> recupero ricevute telematiche (riconciliazione)

In input/output a tutte le operazioni e' una stringa Base64 di un XML
"opaco" rispetto al WSDL (`param`); il WSDL accetta solo `xs:string`. Per
questo motivo costruiamo / parseiamo il XML a mano, lasciando a zeep solo
il trasporto SOAP e l'autenticazione HTTP Basic.

NOTA: la firma esatta dei campi e' tratta dalle Specifiche Client Web
Services DataProvider V.10.4 (sezioni 3.x) di SolutionPA. Riferimenti
puntuali sono nei commenti.
"""

from __future__ import annotations

import base64
import logging
import re
from datetime import datetime
from io import BytesIO
from typing import Any, Dict, List, Optional, Tuple
from xml.etree import ElementTree as ET

from requests import Session
from requests.auth import HTTPBasicAuth

import config


logger = logging.getLogger(__name__)


# ============================================================================
# COSTANTI E NAMESPACE
# ============================================================================

# Namespace del XML interno a `param` (DataProvider V.10.4, sez. 3.x)
PARAM_NS = "http://generatedsource.dp.webservice.intermediariopa.infogroup.it/"

# Stato HTTP timeout
DEFAULT_TIMEOUT = 30


class PagoPAError(Exception):
    """Errore generico del client PagoPA."""


class PagoPAValidationError(PagoPAError):
    """Errore di validazione lato client (CF errato, importo invalido, ecc.)."""


class PagoPARemoteError(PagoPAError):
    """Errore restituito da SolutionPA (esitoOperazione=KO)."""

    def __init__(self, code: str, message: str = ""):
        super().__init__(f"{code}: {message}" if message else code)
        self.code = code
        self.message = message


# ============================================================================
# VALIDAZIONE INPUT
# ============================================================================

# Codice fiscale italiano: 16 alfanumerici (no checksum severo per ora)
_CF_REGEX = re.compile(r"^[A-Z0-9]{16}$")
# Partita IVA italiana: 11 cifre
_PI_REGEX = re.compile(r"^[0-9]{11}$")


def is_valid_codice_fiscale(cf: str) -> bool:
    """Verifica formale del codice fiscale (16 char alfanumerici)."""
    if not cf:
        return False
    return bool(_CF_REGEX.match(cf.upper().strip()))


def is_valid_partita_iva(pi: str) -> bool:
    """Verifica formale della partita IVA (11 cifre)."""
    if not pi:
        return False
    return bool(_PI_REGEX.match(pi.strip()))


def normalize_codice_fiscale(cf: str) -> str:
    """Normalizza il CF a maiuscolo + trim."""
    return (cf or "").upper().strip()


# ============================================================================
# COSTRUZIONE XML del campo `param`
# ============================================================================

def _format_importo(amount_cents: int) -> str:
    """Formatta un importo in centesimi come decimale a 2 cifre (es. 4500 -> '45.00')."""
    return f"{amount_cents / 100.0:.2f}"


def _xml_escape(s: str) -> str:
    """XML-escape robusta su un valore di testo."""
    if s is None:
        return ""
    return (
        str(s)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&apos;")
    )


def build_param_carica(
    *,
    modalita: str,
    iuv: Optional[str],
    id_tenant: Optional[str],
    payer_codice_fiscale: str,
    payer_anagrafica: str,
    payer_email: Optional[str],
    payer_is_giuridico: bool,
    importo_totale_cents: int,
    causale: str,
    cod_tributo: str,
) -> str:
    """
    Costruisce il XML del campo `param` per pdpCaricaPagamentoInAttesa.
    Restituisce la stringa Base64 pronta per l'invio.

    Riferimento: DataProvider V.10.4 sez. 3.x (pdpCaricaPagamentoInAttesa).
    """
    if modalita not in ("INS", "MOD", "INV", "ASP"):
        raise PagoPAValidationError(f"modalita invalida: {modalita}")
    if importo_totale_cents <= 0:
        raise PagoPAValidationError("importo_totale_cents deve essere > 0")

    importo = _format_importo(importo_totale_cents)
    iuv_xml = _xml_escape(iuv) if iuv else ""
    id_tenant_xml = _xml_escape(id_tenant) if id_tenant else ""
    tipo_id = "G" if payer_is_giuridico else "F"

    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        f'<pdpCaricaPagamentoInAttesa xmlns="{PARAM_NS}">'
        '<datiPagamentoInAttesa>'
        f'<modalita>{modalita}</modalita>'
        f'<identificativoUnivocoVersamento>{iuv_xml}</identificativoUnivocoVersamento>'
        f'<id_tenant>{id_tenant_xml}</id_tenant>'
        '<soggetoPagatore>'
        f'<tipoIdentificativoUnivocoPagatore>{tipo_id}</tipoIdentificativoUnivocoPagatore>'
        f'<codiceIdentificativoUnivocoPagatore>{_xml_escape(payer_codice_fiscale)}</codiceIdentificativoUnivocoPagatore>'
        f'<anagraficaPagatore>{_xml_escape(payer_anagrafica)}</anagraficaPagatore>'
        + (f'<emailPagatore>{_xml_escape(payer_email)}</emailPagatore>' if payer_email else '')
        + '</soggetoPagatore>'
        f'<importoTotaleDaVersare>{importo}</importoTotaleDaVersare>'
        '<datiSingoloVersamento>'
        f'<identificativoServizio>{_xml_escape(cod_tributo)}</identificativoServizio>'
        f'<importoSingoloVersamento>{importo}</importoSingoloVersamento>'
        f'<causaleVersamento>{_xml_escape(causale[:140])}</causaleVersamento>'
        '</datiSingoloVersamento>'
        '</datiPagamentoInAttesa>'
        '</pdpCaricaPagamentoInAttesa>'
    )
    return base64.b64encode(xml.encode("utf-8")).decode("ascii")


def build_param_attiva_rpt(*, iuv: str, callback_url: str) -> str:
    """
    Costruisce il XML del campo `param` per pdpAttivaRPT.
    Restituisce la stringa Base64.
    """
    if not iuv:
        raise PagoPAValidationError("iuv obbligatorio per pdpAttivaRPT")
    if not callback_url:
        raise PagoPAValidationError("callback_url obbligatorio per pdpAttivaRPT")

    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        f'<pdpAttivaRpt xmlns="{PARAM_NS}">'
        '<datiPagamentoInAttesa>'
        f'<identificativoUnivocoVersamento>{_xml_escape(iuv)}</identificativoUnivocoVersamento>'
        '</datiPagamentoInAttesa>'
        f'<callbackURL>{_xml_escape(callback_url)}</callbackURL>'
        '</pdpAttivaRpt>'
    )
    return base64.b64encode(xml.encode("utf-8")).decode("ascii")


def build_param_modifica_invalida(*, iuv: str) -> str:
    """
    Costruisce il XML del campo `param` per pdpModificaPosizioneDebitoria
    in modalita' INV (annullamento posizione non pagata).
    """
    if not iuv:
        raise PagoPAValidationError("iuv obbligatorio per pdpModificaPosizioneDebitoria")
    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        f'<pdpModificaPosizioneDebitoria xmlns="{PARAM_NS}">'
        f'<identificativoUnivocoVersamento>{_xml_escape(iuv)}</identificativoUnivocoVersamento>'
        '<parametriDaModificare>'
        '<modalita>INV</modalita>'
        '</parametriDaModificare>'
        '</pdpModificaPosizioneDebitoria>'
    )
    return base64.b64encode(xml.encode("utf-8")).decode("ascii")


# ============================================================================
# PARSING della risposta SOAP
# ============================================================================

def _strip_ns(tag: str) -> str:
    """Rimuove il namespace XML da un tag (es. '{ns}foo' -> 'foo')."""
    if "}" in tag:
        return tag.split("}", 1)[1]
    return tag


def _find_text(elem: ET.Element, *names: str) -> Optional[str]:
    """Trova ricorsivamente il primo elemento con uno dei nomi indicati e ne restituisce il testo."""
    target = set(names)
    for el in elem.iter():
        if _strip_ns(el.tag) in target:
            return (el.text or "").strip()
    return None


def parse_response_xml(b64_payload: str) -> Dict[str, Any]:
    """
    Decodifica la risposta `param` (Base64 -> XML) e ne estrae i campi noti.

    Ritorna sempre un dict con almeno:
      - esito_operazione: 'OK' | 'KO' | None
      - codice_errore:    str | None
      - identificativo_univoco_versamento: IUV restituito (o None)
      - redirect_url:     URL Checkout (solo per pdpAttivaRPT)
      - codice_contesto_pagamento: CCP (solo per pdpAttivaRPT)
      - raw_xml:          stringa XML decodificata (utile per audit/log)
    """
    if not b64_payload:
        return {"esito_operazione": None, "raw_xml": ""}
    try:
        xml_bytes = base64.b64decode(b64_payload)
    except Exception as e:
        raise PagoPAError(f"Risposta param non e' Base64 valida: {e}")

    raw_xml = xml_bytes.decode("utf-8", errors="replace")
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError as e:
        raise PagoPAError(f"Risposta XML non parseabile: {e}\n{raw_xml[:400]}")

    return {
        "esito_operazione": _find_text(root, "esitoOperazione"),
        "codice_errore": _find_text(root, "codiceErrore"),
        "descrizione_errore": _find_text(root, "descrizioneErrore"),
        "identificativo_univoco_versamento": _find_text(root, "identificativoUnivocoVersamento"),
        "redirect_url": _find_text(root, "redirectURL"),
        "codice_contesto_pagamento": _find_text(root, "codiceContestoPagamento"),
        "raw_xml": raw_xml,
    }


# ============================================================================
# CLIENT SOAP (zeep)
# ============================================================================

_zeep_client_cache = None


def _get_zeep_client():
    """
    Restituisce un client zeep (cached) configurato con HTTP Basic Auth.
    Solleva PagoPAError se la configurazione manca.
    """
    global _zeep_client_cache
    if _zeep_client_cache is not None:
        return _zeep_client_cache

    try:
        from zeep import Client as ZeepClient
        from zeep.transports import Transport
    except ImportError as e:
        raise PagoPAError(
            "Libreria 'zeep' non installata. Esegui: pip install zeep>=4.2.0"
        ) from e

    if not config.PAGOPA_WSDL_URL:
        raise PagoPAError("PAGOPA_WSDL_URL non configurato")
    if not config.PAGOPA_USERNAME or not config.PAGOPA_PASSWORD:
        raise PagoPAError("Credenziali PAGOPA_USERNAME / PAGOPA_PASSWORD mancanti")

    session = Session()
    session.auth = HTTPBasicAuth(config.PAGOPA_USERNAME, config.PAGOPA_PASSWORD)
    transport = Transport(session=session, timeout=config.PAGOPA_SOAP_TIMEOUT)

    logger.info("[PagoPA] Inizializzazione client SOAP (WSDL=%s)", config.PAGOPA_WSDL_URL)
    _zeep_client_cache = ZeepClient(wsdl=config.PAGOPA_WSDL_URL, transport=transport)
    return _zeep_client_cache


def reset_client_cache():
    """Forza il reload del WSDL alla prossima chiamata (utile dopo cambio config)."""
    global _zeep_client_cache
    _zeep_client_cache = None


def _call_soap_with_param(operation_name: str, param_b64: str) -> Dict[str, Any]:
    """
    Invoca un'operazione del DataProvider passando dominio, BU e param Base64.
    Wrappa il parsing della risposta e solleva PagoPARemoteError se KO.
    """
    if not config.PAGOPA_DOMINIO or not config.PAGOPA_UB:
        raise PagoPAError("PAGOPA_DOMINIO o PAGOPA_UB non configurati")

    client = _get_zeep_client()
    op = getattr(client.service, operation_name, None)
    if op is None:
        raise PagoPAError(
            f"Operazione SOAP '{operation_name}' non esposta dal WSDL. "
            "Verifica la URL del WSDL configurato."
        )

    logger.info("[PagoPA] -> %s (dominio=%s, ub=%s)",
                operation_name, config.PAGOPA_DOMINIO, config.PAGOPA_UB)

    try:
        raw_response = op(
            identificativoDominio=config.PAGOPA_DOMINIO,
            identificativoBU=config.PAGOPA_UB,
            param=param_b64,
        )
    except Exception as e:
        logger.exception("[PagoPA] Errore chiamando %s", operation_name)
        raise PagoPAError(f"Errore SOAP {operation_name}: {e}") from e

    # zeep restituisce un oggetto; il campo 'param' contiene la risposta Base64
    response_b64 = None
    if hasattr(raw_response, "param"):
        response_b64 = raw_response.param
    elif isinstance(raw_response, dict):
        response_b64 = raw_response.get("param")
    elif isinstance(raw_response, str):
        response_b64 = raw_response

    parsed = parse_response_xml(response_b64 or "")
    logger.info("[PagoPA] <- %s esito=%s", operation_name, parsed.get("esito_operazione"))

    if parsed.get("esito_operazione") and parsed["esito_operazione"].upper() != "OK":
        raise PagoPARemoteError(
            code=parsed.get("codice_errore") or "UNKNOWN",
            message=parsed.get("descrizione_errore") or "",
        )

    return parsed


# ============================================================================
# OPERAZIONI DI ALTO LIVELLO (chiamate dai router)
# ============================================================================

def carica_pagamento_in_attesa(
    *,
    payer_codice_fiscale: str,
    payer_anagrafica: str,
    importo_totale_cents: int,
    causale: str,
    id_tenant: Optional[str] = None,
    payer_email: Optional[str] = None,
    payer_partita_iva: Optional[str] = None,
    payer_ragione_sociale: Optional[str] = None,
) -> str:
    """
    Crea una posizione debitoria su SolutionPA. Restituisce l'IUV generato.

    Validazioni client-side:
      - codice fiscale formato 16 alfanumerici (oppure P.IVA 11 cifre per soggetti giuridici)
      - importo > 0

    L'IUV viene generato da SolutionPA (modalita=INS, IUV vuoto in input).
    """
    cf = normalize_codice_fiscale(payer_codice_fiscale)
    is_giuridico = False
    if payer_partita_iva and is_valid_partita_iva(payer_partita_iva):
        # Per soggetti giuridici si invia la P.IVA come codiceIdentificativoUnivocoPagatore
        cf = payer_partita_iva.strip()
        is_giuridico = True
    elif not is_valid_codice_fiscale(cf):
        raise PagoPAValidationError(f"Codice fiscale non valido: {payer_codice_fiscale}")

    anagrafica = (payer_ragione_sociale.strip() if (is_giuridico and payer_ragione_sociale)
                  else payer_anagrafica.strip())
    if not anagrafica:
        raise PagoPAValidationError("anagrafica pagatore mancante")

    param_b64 = build_param_carica(
        modalita="INS",
        iuv=None,
        id_tenant=id_tenant,
        payer_codice_fiscale=cf,
        payer_anagrafica=anagrafica[:70],
        payer_email=payer_email,
        payer_is_giuridico=is_giuridico,
        importo_totale_cents=importo_totale_cents,
        causale=causale,
        cod_tributo=config.PAGOPA_COD_TRIBUTO,
    )

    parsed = _call_soap_with_param("pdpCaricaPagamentoInAttesa", param_b64)
    iuv = parsed.get("identificativo_univoco_versamento")
    if not iuv:
        raise PagoPAError("SolutionPA non ha restituito un IUV (response vuota)")
    return iuv


def attiva_rpt(*, iuv: str, return_url: str) -> Tuple[str, str]:
    """
    Attiva l'RPT per un IUV gia' caricato. Ritorna (checkout_url, codice_contesto_pagamento).
    `return_url` e' la URL del frontend dove pagoPA reindirizzera' l'utente al termine.
    """
    if not iuv:
        raise PagoPAValidationError("iuv obbligatorio")

    param_b64 = build_param_attiva_rpt(iuv=iuv, callback_url=return_url)
    parsed = _call_soap_with_param("pdpAttivaRPT", param_b64)
    redirect_url = parsed.get("redirect_url")
    ccp = parsed.get("codice_contesto_pagamento") or ""
    if not redirect_url:
        raise PagoPAError("SolutionPA non ha restituito redirectURL")
    return redirect_url, ccp


def annulla_posizione(*, iuv: str) -> Dict[str, Any]:
    """Annulla una posizione non pagata (modalita=INV)."""
    if not iuv:
        raise PagoPAValidationError("iuv obbligatorio")
    param_b64 = build_param_modifica_invalida(iuv=iuv)
    return _call_soap_with_param("pdpModificaPosizioneDebitoria", param_b64)


# ============================================================================
# RICONCILIAZIONE — parsing del file estrcc.xml
# ============================================================================

def parse_estrcc(xml_bytes: bytes) -> List[Dict[str, Any]]:
    """
    Parsea un file di riconciliazione `RiconciliazioneEstrcc.xml` (vedi XSD).

    Restituisce una lista di dict, uno per riga di riconciliazione, con i campi:
      data_contabile, data_valuta, identificativo_flusso, importo (decimale),
      iuv, singolo_importo_pagato, data_esito, stato_quadratura,
      anagrafica_pagatore, id_tenant, ub, causale_movimento, esito9,
      provvisorio_entrata, id_servizio (opt), iban_accredito (opt)
    """
    items: List[Dict[str, Any]] = []
    if not xml_bytes:
        return items

    try:
        root = ET.parse(BytesIO(xml_bytes)).getroot()
    except ET.ParseError as e:
        raise PagoPAError(f"estrcc XML non parseabile: {e}")

    def _txt(el: Optional[ET.Element]) -> Optional[str]:
        if el is None:
            return None
        return (el.text or "").strip()

    # Il root e' <RiconciliazioneEstrcc> con figli <datiEstrcc>+
    for dati in root.iter():
        if _strip_ns(dati.tag) != "datiEstrcc":
            continue
        children = {_strip_ns(c.tag): c for c in list(dati)}
        items.append({
            "data_contabile": _txt(children.get("dataContabileEstrcc")),
            "data_valuta": _txt(children.get("dataValuta")),
            "identificativo_flusso": _txt(children.get("identificativoFlusso")),
            "importo": _txt(children.get("importo")),
            "iuv": _txt(children.get("iuv")),
            "singolo_importo_pagato": _txt(children.get("singoloImportoPagato")),
            "data_esito": _txt(children.get("dataEsitoSingoloPagamento")),
            "stato_quadratura": _txt(children.get("statoQuadratura")),
            "anagrafica_pagatore": _txt(children.get("anagraficaPagatore")),
            "id_tenant": _txt(children.get("idTenant")),
            "ub": _txt(children.get("ub")),
            "causale_movimento": _txt(children.get("causaleMovimento")),
            "esito9": _txt(children.get("esito9")),
            "provvisorio_entrata": _txt(children.get("provvisorioEntrata")),
            "id_servizio": _txt(children.get("idServizio")),
            "iban_accredito": _txt(children.get("ibanAccredito")),
        })

    return items
