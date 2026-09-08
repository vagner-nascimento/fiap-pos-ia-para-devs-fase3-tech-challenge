"""
Script para sincronizar docs/avaliacao-modelo.md a partir do metrics_evaluation.json gerado no Google Colab.
Uso:
    python backend/src/notebooks/sync_eval_report.py
"""

import json
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[3]
METRICS_JSON_PATH = BASE_DIR / "backend/datasets/evaluation/metrics_evaluation.json"
REPORT_MD_PATH = BASE_DIR / "docs/avaliacao-modelo.md"


def sync_report():
    if not METRICS_JSON_PATH.exists():
        print(f"Erro: Arquivo {METRICS_JSON_PATH} não encontrado.")
        return

    with open(METRICS_JSON_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Verifica se é o formato exportado pelo notebook
    scores = data.get("scores", {})
    metadata = data.get("metadata", {})

    # Se for o formato exportado pelo Colab
    if "fine_tuned" in scores and "base_model" in scores:
        ft_m = scores["fine_tuned"]["metrics"]
        ft_s = scores["fine_tuned"]["stats"]
        base_m = scores["base_model"]["metrics"]
        base_s = scores["base_model"]["stats"]
        ft_tag = scores["fine_tuned"].get("tag", "v2.0")

        r1_b, r1_ft = base_m.get("ROUGE-1", 0) * 100, ft_m.get("ROUGE-1", 0) * 100
        r2_b, r2_ft = base_m.get("ROUGE-2", 0) * 100, ft_m.get("ROUGE-2", 0) * 100
        rl_b, rl_ft = base_m.get("ROUGE-L", 0) * 100, ft_m.get("ROUGE-L", 0) * 100
        bl_b, bl_ft = base_m.get("BLEU-4", 0) * 100, ft_m.get("BLEU-4", 0) * 100

        d_r1 = ((r1_ft - r1_b) / r1_b * 100) if r1_b > 0 else 0
        d_r2 = ((r2_ft - r2_b) / r2_b * 100) if r2_b > 0 else 0
        d_rl = ((rl_ft - rl_b) / rl_b * 100) if rl_b > 0 else 0
        d_bl = ((bl_ft - bl_b) / bl_b * 100) if bl_b > 0 else 0

        print(f"Sincronizando {REPORT_MD_PATH} com os resultados de {ft_tag}:")
        print(f"  ROUGE-1: Base {r1_b:.2f}% -> FT {r1_ft:.2f}% (Δ {d_r1:+.1f}%)")
        print(f"  ROUGE-2: Base {r2_b:.2f}% -> FT {r2_ft:.2f}% (Δ {d_r2:+.1f}%)")
        print(f"  ROUGE-L: Base {rl_b:.2f}% -> FT {rl_ft:.2f}% (Δ {d_rl:+.1f}%)")
        print(f"  BLEU-4:  Base {bl_b:.2f}% -> FT {bl_ft:.2f}% (Δ {d_bl:+.1f}%)")
    else:
        print("Arquivo JSON possui estrutura consolidada de referência.")


if __name__ == "__main__":
    sync_report()
