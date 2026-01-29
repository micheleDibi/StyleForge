"""
Rilevatore di testo generato da AI usando il metodo Binoculars.

Il metodo Binoculars confronta la perplessità di un testo calcolata da due modelli:
- Observer: modello base (non istruito)
- Performer: modello istruito (fine-tuned per seguire istruzioni)

Un testo generato da AI tende ad avere un rapporto di perplessità più basso
rispetto a un testo scritto da un umano.

Riferimento: https://arxiv.org/abs/2401.12070
"""

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer
from typing import Literal


class BinocularsDetector:
    """
    Rilevatore di testo AI usando il metodo Binoculars.

    Confronta le perplessità di due modelli per determinare se un testo
    è stato generato da un'AI o scritto da un umano.
    """

    # Modelli disponibili per il rilevamento
    # I modelli sono ordinati per dimensione (dal più piccolo al più grande)
    AVAILABLE_MODELS = {
        # === MODELLI PICCOLI (< 4GB) - Consigliati per Mac ===
        "gpt2": {
            "observer": "openai-community/gpt2",
            "performer": "openai-community/gpt2-medium",
            "size": "~500MB + ~1.5GB",
            "recommended_for": "Mac con poca RAM, test veloci"
        },
        "gpt2-medium": {
            "observer": "openai-community/gpt2-medium",
            "performer": "openai-community/gpt2-large",
            "size": "~1.5GB + ~3GB",
            "recommended_for": "Mac con 16GB+ RAM"
        },
        "phi-2": {
            "observer": "microsoft/phi-2",
            "performer": "microsoft/phi-2",  # Stesso modello, risultati meno accurati
            "size": "~5.5GB",
            "recommended_for": "Mac con 16GB+ RAM, buona qualità"
        },
        "qwen2-1.5b": {
            "observer": "Qwen/Qwen2-1.5B",
            "performer": "Qwen/Qwen2-1.5B-Instruct",
            "size": "~3GB x2",
            "recommended_for": "Mac con 16GB+ RAM, ottimo rapporto qualità/dimensione"
        },
        # === MODELLI MEDI (4-10GB) ===
        "qwen2-7b": {
            "observer": "Qwen/Qwen2-7B",
            "performer": "Qwen/Qwen2-7B-Instruct",
            "size": "~14GB x2",
            "recommended_for": "Mac con 32GB+ RAM o GPU NVIDIA"
        },
        # === MODELLI GRANDI (>10GB) - Richiedono GPU o molta RAM ===
        "falcon-7b": {
            "observer": "tiiuae/falcon-7b",
            "performer": "tiiuae/falcon-7b-instruct",
            "size": "~14GB x2",
            "recommended_for": "GPU NVIDIA con 24GB+ VRAM"
        },
        "llama2-7b": {
            "observer": "meta-llama/Llama-2-7b-hf",
            "performer": "meta-llama/Llama-2-7b-chat-hf",
            "size": "~14GB x2",
            "recommended_for": "GPU NVIDIA con 24GB+ VRAM (richiede accesso HF)"
        },
        "mistral-7b": {
            "observer": "mistralai/Mistral-7B-v0.1",
            "performer": "mistralai/Mistral-7B-Instruct-v0.1",
            "size": "~14GB x2",
            "recommended_for": "GPU NVIDIA con 24GB+ VRAM"
        }
    }

    def __init__(
        self,
        model_name: Literal[
            "gpt2", "gpt2-medium", "phi-2", "qwen2-1.5b", "qwen2-7b",
            "falcon-7b", "llama2-7b", "mistral-7b"
        ] = "qwen2-1.5b",
        threshold: float = 0.9,
        device: str | None = None,
        load_in_8bit: bool = False,
        load_in_4bit: bool = False
    ):
        """
        Inizializza il rilevatore Binoculars.

        Args:
            model_name: Nome del modello da usare. Opzioni:
                - "gpt2": Più leggero (~2GB totali), veloce ma meno accurato
                - "gpt2-medium": Leggero (~4.5GB totali), buon compromesso
                - "phi-2": Medio (~5.5GB), buona qualità
                - "qwen2-1.5b": Consigliato per Mac (~6GB totali), ottimo rapporto qualità/dimensione
                - "qwen2-7b": Grande (~28GB), richiede molta RAM
                - "falcon-7b": Grande (~28GB), richiede GPU NVIDIA
                - "llama2-7b": Grande (~28GB), richiede accesso HF + GPU
                - "mistral-7b": Grande (~28GB), richiede GPU NVIDIA
            threshold: Soglia per la classificazione. Score < threshold = AI generato.
            device: Device su cui caricare i modelli ('cuda', 'mps', 'cpu').
                   Se None, viene rilevato automaticamente.
            load_in_8bit: Carica i modelli in 8-bit (solo CUDA).
            load_in_4bit: Carica i modelli in 4-bit (solo CUDA).

        Note:
            - La quantizzazione 8-bit/4-bit richiede CUDA (GPU NVIDIA).
            - Su Mac (MPS) i modelli vengono caricati in float16.
            - Su CPU i modelli vengono caricati in float32.
            - Per Mac consigliato: "gpt2", "gpt2-medium" o "qwen2-1.5b"
        """
        self.threshold = threshold
        self.device = self._detect_device(device)

        if model_name not in self.AVAILABLE_MODELS:
            raise ValueError(
                f"Modello '{model_name}' non disponibile. "
                f"Scegli tra: {list(self.AVAILABLE_MODELS.keys())}"
            )

        model_config = self.AVAILABLE_MODELS[model_name]

        # Configurazione per quantizzazione
        # NOTA: bitsandbytes (8bit/4bit) funziona SOLO con CUDA
        load_kwargs = {}
        use_device_map = False

        if self.device == "cuda":
            # Su CUDA possiamo usare la quantizzazione
            if load_in_4bit:
                load_kwargs["load_in_4bit"] = True
                load_kwargs["bnb_4bit_compute_dtype"] = torch.float16
                use_device_map = True
            elif load_in_8bit:
                load_kwargs["load_in_8bit"] = True
                use_device_map = True
            else:
                load_kwargs["torch_dtype"] = torch.float16
                use_device_map = True
        elif self.device == "mps":
            # Su Mac Apple Silicon (MPS) non possiamo usare bitsandbytes
            # Usiamo float16 per risparmiare memoria
            if load_in_8bit or load_in_4bit:
                print("ATTENZIONE: La quantizzazione 8-bit/4-bit non è supportata su Mac (MPS).")
                print("           I modelli verranno caricati in float16.")
            load_kwargs["torch_dtype"] = torch.float16
            # MPS non supporta device_map="auto", carichiamo su CPU poi spostiamo
            use_device_map = False
        else:
            # CPU
            load_kwargs["torch_dtype"] = torch.float32
            use_device_map = False

        print(f"Caricamento modelli su {self.device}...")

        # Carica tokenizer
        self.tokenizer = AutoTokenizer.from_pretrained(
            model_config["observer"],
            trust_remote_code=True
        )
        if self.tokenizer.pad_token is None:
            self.tokenizer.pad_token = self.tokenizer.eos_token

        # Carica observer model
        print(f"  Caricamento observer: {model_config['observer']}")
        if use_device_map:
            self.observer_model = AutoModelForCausalLM.from_pretrained(
                model_config["observer"],
                device_map="auto",
                trust_remote_code=True,
                **load_kwargs
            )
        else:
            self.observer_model = AutoModelForCausalLM.from_pretrained(
                model_config["observer"],
                trust_remote_code=True,
                **load_kwargs
            )
            self.observer_model = self.observer_model.to(self.device)
        self.observer_model.eval()

        # Carica performer model
        print(f"  Caricamento performer: {model_config['performer']}")
        if use_device_map:
            self.performer_model = AutoModelForCausalLM.from_pretrained(
                model_config["performer"],
                device_map="auto",
                trust_remote_code=True,
                **load_kwargs
            )
        else:
            self.performer_model = AutoModelForCausalLM.from_pretrained(
                model_config["performer"],
                trust_remote_code=True,
                **load_kwargs
            )
            self.performer_model = self.performer_model.to(self.device)
        self.performer_model.eval()

        print("Modelli caricati con successo!")

    def _detect_device(self, device: str | None) -> str:
        """Rileva automaticamente il device migliore disponibile."""
        if device is not None:
            return device

        if torch.cuda.is_available():
            return "cuda"
        elif torch.backends.mps.is_available():
            return "mps"
        else:
            return "cpu"

    def _compute_perplexity(self, model: AutoModelForCausalLM, text: str) -> float:
        """
        Calcola la perplessità di un testo usando un modello.

        Args:
            model: Il modello da usare per il calcolo.
            text: Il testo da analizzare.

        Returns:
            Il valore di perplessità.
        """
        inputs = self.tokenizer(
            text,
            return_tensors="pt",
            truncation=True,
            max_length=2048,
            padding=True
        )

        # Sposta gli input sul device corretto
        inputs = {k: v.to(model.device) for k, v in inputs.items()}

        with torch.no_grad():
            outputs = model(**inputs, labels=inputs["input_ids"])
            loss = outputs.loss

        perplexity = torch.exp(loss).item()
        return perplexity

    def detect(self, text: str) -> dict:
        """
        Rileva se un testo è stato generato da AI.

        Args:
            text: Il testo da analizzare.

        Returns:
            Dizionario con:
                - score: Rapporto di perplessità (observer/performer)
                - is_ai_generated: True se probabilmente generato da AI
                - confidence: Livello di confidenza della predizione (0-1)
                - perplexity_observer: Perplessità del modello observer
                - perplexity_performer: Perplessità del modello performer
                - verdict: Stringa descrittiva del risultato
        """
        if not text or not text.strip():
            raise ValueError("Il testo da analizzare non può essere vuoto")

        # Calcola perplessità con entrambi i modelli
        ppl_observer = self._compute_perplexity(self.observer_model, text)
        ppl_performer = self._compute_perplexity(self.performer_model, text)

        # Evita divisione per zero
        if ppl_performer == 0:
            ppl_performer = 1e-10

        # Calcola lo score Binoculars
        score = ppl_observer / ppl_performer

        # Determina se è AI-generated
        is_ai_generated = score < self.threshold

        # Calcola la confidenza basata sulla distanza dalla soglia
        # Più lontano dalla soglia = più confidenza
        distance_from_threshold = abs(score - self.threshold)
        confidence = min(1.0, distance_from_threshold / self.threshold)

        # Genera un verdetto descrittivo
        if is_ai_generated:
            if confidence > 0.7:
                verdict = "Molto probabilmente generato da AI"
            elif confidence > 0.4:
                verdict = "Probabilmente generato da AI"
            else:
                verdict = "Possibilmente generato da AI"
        else:
            if confidence > 0.7:
                verdict = "Molto probabilmente scritto da un umano"
            elif confidence > 0.4:
                verdict = "Probabilmente scritto da un umano"
            else:
                verdict = "Possibilmente scritto da un umano"

        return {
            "score": round(score, 4),
            "is_ai_generated": is_ai_generated,
            "confidence": round(confidence, 4),
            "perplexity_observer": round(ppl_observer, 4),
            "perplexity_performer": round(ppl_performer, 4),
            "threshold": self.threshold,
            "verdict": verdict
        }

    def detect_batch(self, texts: list[str]) -> list[dict]:
        """
        Rileva se una lista di testi è stata generata da AI.

        Args:
            texts: Lista di testi da analizzare.

        Returns:
            Lista di risultati, uno per ogni testo.
        """
        return [self.detect(text) for text in texts]

    def set_threshold(self, threshold: float) -> None:
        """
        Imposta una nuova soglia per la classificazione.

        Args:
            threshold: Nuova soglia (score < threshold = AI generato).
        """
        if threshold <= 0:
            raise ValueError("La soglia deve essere positiva")
        self.threshold = threshold


def format_detection_result(result: dict) -> str:
    """
    Formatta il risultato del rilevamento in modo leggibile.

    Args:
        result: Dizionario restituito da detect().

    Returns:
        Stringa formattata con il risultato.
    """
    output = f"""
╔══════════════════════════════════════════════════════════════╗
║                    RISULTATO RILEVAMENTO                     ║
╠══════════════════════════════════════════════════════════════╣
║  Verdetto: {result['verdict']:<48} ║
╠══════════════════════════════════════════════════════════════╣
║  Score Binoculars: {result['score']:<40} ║
║  Soglia:           {result['threshold']:<40} ║
║  Confidenza:       {result['confidence'] * 100:.1f}%{' ' * 36}║
╠══════════════════════════════════════════════════════════════╣
║  Perplessità Observer:  {result['perplexity_observer']:<35} ║
║  Perplessità Performer: {result['perplexity_performer']:<35} ║
╚══════════════════════════════════════════════════════════════╝
"""
    return output


# ============================================================================
# ESEMPIO DI UTILIZZO
# ============================================================================
if __name__ == "__main__":
    # Inizializza il detector
    # Per Mac usa: "gpt2", "gpt2-medium" o "qwen2-1.5b"
    # Per GPU NVIDIA puoi usare modelli più grandi come "falcon-7b"
    detector = BinocularsDetector(
        model_name="qwen2-1.5b",  # Consigliato per Mac
        threshold=0.9
    )

    # Testo di esempio da analizzare
    testo_esempio = """
    L'intelligenza emotiva rappresenta una capacità fondamentale per navigare
    le complessità delle relazioni umane. Non si tratta semplicemente di
    riconoscere le emozioni, ma di saperle gestire in modo costruttivo,
    trasformando anche le esperienze negative in opportunità di crescita.
    """

    # Esegui il rilevamento
    risultato = detector.detect(testo_esempio)

    # Mostra il risultato formattato
    print(format_detection_result(risultato))
