"""
Harness di misura Compilatio per la riduzione del punteggio "Rilevamento AI"
delle tesi StyleForge.

Dato un testo (o una generazione fresca), applica le varianti anti-AI e misura
il punteggio AI/similarità via l'integrazione Compilatio esistente
(compilatio_service.scan_text). Permette confronti before/after e A/B di modello.

Eseguire dalla cartella backend/:

    # validazione offline-ish (nessuna scansione Compilatio):
    python -m tools.compilatio_harness --text-file campione.txt --variants raw,algo --dry-run

    # baseline reale di una tesi già a 34%:
    python -m tools.compilatio_harness --text-file tesi.txt --variants raw

    # ablation completa su un excerpt:
    python -m tools.compilatio_harness --text-file tesi.txt \
        --variants raw,rewrite,algo,rewrite+algo --max-chars 6000

    # A/B di modello generando un campione nuovo:
    python -m tools.compilatio_harness --generate --topic "Educazione affettiva nella scuola primaria" \
        --providers openai,claude --variants raw,rewrite+algo --words 1200

NOTE:
- scan_text NON deduce crediti applicativi (la deduzione è nella route): l'harness
  consuma solo quota Compilatio. Scrive comunque una riga CompilatioScan (admin).
- La variante 'rewrite' richiede ANTHROPIC_API_KEY; '--generate' con provider
  openai richiede OPENAI_API_KEY; la scansione richiede le credenziali COMPILATIO_*.
- Il dedup via hash evita di riscansionare un testo identico.
"""

import argparse
import json
import re
import sys
import uuid
from typing import List, Optional

CITE_RE = re.compile(r'\[\d+\]')
NOTE_RE = re.compile(r'\{\{nota:')


# ---------------------------------------------------------------------------
# Trasformazioni (varianti)
# ---------------------------------------------------------------------------
def transform(text: str, variant: str) -> str:
    """Applica una variante: raw | rewrite | algo | rewrite+algo."""
    if variant == 'raw':
        return text
    out = text
    if 'rewrite' in variant:
        from ai_client import academic_deai_rewrite
        out = academic_deai_rewrite(out)
    if 'algo' in variant:
        from anti_ai_processor import humanize_text_post_processing
        out = humanize_text_post_processing(out, profile='academic')
    return out


# ---------------------------------------------------------------------------
# Estrazione punteggi (difensiva: i nomi dei campi possono variare)
# ---------------------------------------------------------------------------
def _extract_scores(d: dict) -> dict:
    def g(*keys):
        for k in keys:
            if isinstance(d, dict) and d.get(k) is not None:
                return d[k]
        return None
    return {
        'ai': g('ai_generated_percent', 'ai_score', 'ai_generated', 'ai_percent'),
        'sim': g('similarity_percent', 'similarity_score', 'similarity', 'global_score_percent'),
    }


def _stats(text: str) -> dict:
    return {
        'words': len(text.split()),
        'cites': len(CITE_RE.findall(text)),
        'notes': len(NOTE_RE.findall(text)),
    }


# ---------------------------------------------------------------------------
# Scansione singola
# ---------------------------------------------------------------------------
def _ensure_job(db, job_id: str, user_id: str):
    """Crea una riga jobs per soddisfare la FK compilatio_scans.job_id -> jobs.job_id."""
    import uuid as _uuid
    from db_models import Job
    if db.query(Job).filter(Job.job_id == job_id).first():
        return
    db.add(Job(
        job_id=job_id,
        user_id=_uuid.UUID(user_id) if isinstance(user_id, str) else user_id,
        job_type='compilatio_scan',
        name='harness compilatio',
    ))
    db.commit()


def scan_once(text: str, label: str, user_id: Optional[str], dry_run: bool,
              show_raw: bool = False, retries: int = 4) -> dict:
    import time
    st = _stats(text)
    row = {'label': label, 'ai': None, 'sim': None, 'cached': False, **st}
    if dry_run:
        return row

    import requests
    from compilatio_service import get_compilatio_service, CompilatioService

    # Errori di rete transitori su cui ritentare l'intera scansione (il servizio
    # non ritenta i drop di connessione durante il polling lungo).
    retryable = [requests.exceptions.RequestException]
    try:
        from compilatio_service import CompilatioError
        retryable.append(CompilatioError)
    except Exception:
        pass
    try:
        from sqlalchemy.exc import OperationalError as _SAOpErr
        retryable.append(_SAOpErr)  # blip DNS/connettività verso il DB
    except Exception:
        pass
    retryable = tuple(retryable)

    from database import SessionLocal
    db = SessionLocal()
    try:
        text_hash = CompilatioService.compute_text_hash(text)
        existing = CompilatioService.check_existing_scan(text_hash, user_id, db)
        if existing:
            sc = _extract_scores(existing)
            row.update(ai=sc['ai'], sim=sc['sim'], cached=True)
            return row

        svc = get_compilatio_service()
        last_err = None
        for attempt in range(1, retries + 1):
            job_id = f"harness_{uuid.uuid4().hex[:12]}"
            _ensure_job(db, job_id, user_id)
            print(f"  [scan] '{label}' ({st['words']} parole) tentativo {attempt}/{retries} → Compilatio… (minuti)", flush=True)
            try:
                result = svc.scan_text(text, user_id, job_id, source_type='manual')
                data = json.loads(result) if isinstance(result, str) else (result or {})
                if show_raw:
                    print("  [raw result]", json.dumps(data, ensure_ascii=False)[:1000])
                sc = _extract_scores(data)
                row.update(ai=sc['ai'], sim=sc['sim'])
                return row
            except retryable as e:
                last_err = e
                try:
                    db.rollback()  # resetta la sessione dopo un blip DB
                except Exception:
                    pass
                print(f"  [scan] errore di rete ({type(e).__name__}); nuovo tentativo tra 15s…", flush=True)
                time.sleep(15)
            except Exception as e:
                print(f"  [scan] errore non ritentabile: {type(e).__name__}: {e}", flush=True)
                row['error'] = f"{type(e).__name__}: {e}"
                return row
        row['error'] = f"rete: {last_err}"
        print(f"  [scan] esauriti i tentativi: {last_err}", flush=True)
        return row
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Caricamento campioni
# ---------------------------------------------------------------------------
def load_text_file(path: str, max_chars: int) -> str:
    with open(path, 'r', encoding='utf-8') as f:
        text = f.read()
    return text[:max_chars] if max_chars and len(text) > max_chars else text


def load_thesis(thesis_id: str, max_chars: int) -> str:
    from database import SessionLocal
    from db_models import Thesis
    db = SessionLocal()
    try:
        thesis = db.query(Thesis).get(thesis_id)
        if not thesis or not thesis.generated_content:
            raise SystemExit(f"Tesi {thesis_id} non trovata o senza contenuto generato")
        text = thesis.generated_content
        return text[:max_chars] if max_chars and len(text) > max_chars else text
    finally:
        db.close()


def generate_sample(provider: str, topic: str, words: int) -> str:
    """Genera una sezione di esempio col provider indicato (per A/B di modello)."""
    from ai_client import get_ai_client
    client = get_ai_client(provider)
    thesis_data = {
        'title': topic,
        'words_per_section': words,
        'writing_style_name': 'Accademico',
        'content_depth_name': 'Avanzato',
        'target_audience_name': 'Docenti e ricercatori',
        'knowledge_level_name': 'Avanzato',
        'industry_name': 'Educazione',
        'citation_style': 'footnotes',
    }
    chapter = {'chapter_index': 1, 'chapter_title': topic}
    section = {
        'index': 1,
        'title': f'{topic}: quadro teorico',
        'key_points': [
            'Definizione e cornice concettuale',
            'Riferimenti normativi e di ricerca',
            'Implicazioni didattiche',
        ],
    }
    return client.generate_section_content(thesis_data=thesis_data, chapter=chapter, section=section)


# ---------------------------------------------------------------------------
# Resolve admin user
# ---------------------------------------------------------------------------
def resolve_user_id(cli_user_id: Optional[str]) -> str:
    if cli_user_id:
        return cli_user_id
    from database import SessionLocal
    from db_models import User
    from credits import is_admin_user
    db = SessionLocal()
    try:
        for u in db.query(User).all():
            try:
                if is_admin_user(u):
                    return str(u.id)
            except Exception:
                continue
        u = db.query(User).first()
        if u:
            return str(u.id)
    finally:
        db.close()
    raise SystemExit("Nessun utente nel DB: passa --user-id <uuid>")


# ---------------------------------------------------------------------------
# Stampa tabella
# ---------------------------------------------------------------------------
def print_table(rows: List[dict]):
    headers = ['sample', 'variant', 'words', 'cites', 'notes', 'ai%', 'sim%', 'cached']
    widths = {h: len(h) for h in headers}
    def fmt(v):
        if v is None:
            return '-'
        if isinstance(v, float):
            return f"{v:.1f}"
        return str(v)
    table = []
    for r in rows:
        cells = {
            'sample': r.get('sample', ''),
            'variant': r.get('variant', r.get('label', '')),
            'words': fmt(r.get('words')),
            'cites': fmt(r.get('cites')),
            'notes': fmt(r.get('notes')),
            'ai%': fmt(r.get('ai')),
            'sim%': fmt(r.get('sim')),
            'cached': 'sì' if r.get('cached') else '',
        }
        for h in headers:
            widths[h] = max(widths[h], len(cells[h]))
        table.append(cells)
    line = '  '.join(h.ljust(widths[h]) for h in headers)
    print(line)
    print('  '.join('-' * widths[h] for h in headers))
    for cells in table:
        print('  '.join(cells[h].ljust(widths[h]) for h in headers))

    # Delta AI vs raw, per sample
    by_sample = {}
    for r in rows:
        by_sample.setdefault(r.get('sample', ''), {})[r.get('variant', r.get('label', ''))] = r.get('ai')
    print()
    for sample, variants in by_sample.items():
        base = variants.get('raw')
        if base is None:
            continue
        for v, ai in variants.items():
            if v == 'raw' or ai is None:
                continue
            print(f"Δ AI  [{sample}] {v}: {ai:.1f}% (raw {base:.1f}%, {ai - base:+.1f})")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main(argv=None):
    p = argparse.ArgumentParser(description="Harness di misura Compilatio anti-AI")
    src = p.add_mutually_exclusive_group(required=True)
    src.add_argument('--text-file', help="File di testo da misurare")
    src.add_argument('--thesis-id', help="UUID di una tesi (usa generated_content)")
    src.add_argument('--generate', action='store_true', help="Genera un campione nuovo (A/B modello)")
    p.add_argument('--topic', default="Educazione affettiva nella scuola primaria",
                   help="Argomento per --generate")
    p.add_argument('--providers', default="openai,claude",
                   help="Provider per --generate, separati da virgola (openai,claude)")
    p.add_argument('--words', type=int, default=1200, help="Parole target per --generate")
    p.add_argument('--variants', default="raw,rewrite,algo,rewrite+algo",
                   help="Varianti da misurare, separate da virgola")
    p.add_argument('--user-id', help="UUID utente per la scansione (default: primo admin)")
    p.add_argument('--max-chars', type=int, default=0, help="Tronca il campione a N caratteri (0=intero)")
    p.add_argument('--dry-run', action='store_true', help="Applica le trasformazioni senza scansionare")
    p.add_argument('--show-raw', action='store_true', help="Stampa il JSON grezzo della prima scansione")
    args = p.parse_args(argv)

    variants = [v.strip() for v in args.variants.split(',') if v.strip()]

    # Raccogli i campioni: {nome_sample: testo_raw}
    samples = {}
    if args.text_file:
        samples[args.text_file.split('/')[-1]] = load_text_file(args.text_file, args.max_chars)
    elif args.thesis_id:
        samples[f"thesis:{args.thesis_id[:8]}"] = load_thesis(args.thesis_id, args.max_chars)
    else:  # --generate
        providers = [x.strip() for x in args.providers.split(',') if x.strip()]
        for prov in providers:
            print(f"[generate] provider={prov} topic='{args.topic}' (~{args.words} parole)…", flush=True)
            text = generate_sample(prov, args.topic, args.words)
            if args.max_chars and len(text) > args.max_chars:
                text = text[:args.max_chars]
            samples[f"gen:{prov}"] = text

    user_id = None
    if not args.dry_run:
        user_id = resolve_user_id(args.user_id)
        print(f"[scan] user_id={user_id}")

    rows = []
    first_scan = True
    for sample_name, raw_text in samples.items():
        for variant in variants:
            transformed = transform(raw_text, variant)
            r = scan_once(transformed, f"{sample_name}/{variant}", user_id,
                          args.dry_run, show_raw=(args.show_raw and first_scan and not args.dry_run))
            first_scan = False
            r['sample'] = sample_name
            r['variant'] = variant
            rows.append(r)

    print()
    print_table(rows)
    return 0


if __name__ == '__main__':
    sys.exit(main())
