"""Testes do formatador de resposta e remoção defensiva de loops de repetição."""
import pytest
from services.nodes.response_formatter import _clean_llm_artifacts, _remove_repetition_loops, response_formatter_node


def test_remove_repeticao_consecutiva_mesma_sentenca():
    texto = "A maioria dos pacientes com TB pulmonar está sob tratamento. " * 25
    resultado = _remove_repetition_loops(texto)
    assert resultado == "A maioria dos pacientes com TB pulmonar está sob tratamento."


def test_remove_ciclo_repeticao_duas_sentencas():
    texto = "Febre alta observada. Tosse persistente relatada. Febre alta observada. Tosse persistente relatada. Febre alta observada. Tosse persistente relatada."
    resultado = _remove_repetition_loops(texto)
    assert resultado == "Febre alta observada. Tosse persistente relatada."


def test_remove_repeticao_intra_sentenca():
    texto = "Os sintomas incluem dor de cabeça forte dor de cabeça forte dor de cabeça forte e febre."
    resultado = _clean_llm_artifacts(texto)
    assert resultado == "Os sintomas incluem dor de cabeça forte e febre."


def test_preserva_texto_normal_sem_repeticao():
    texto = "O paciente apresenta febre e tosse. Recomenda-se repouso e hidratação oral."
    resultado = _clean_llm_artifacts(texto)
    assert resultado == texto


def test_response_formatter_node_aplica_disclaimer_e_limpa_loop():
    repetitivo = "A maioria dos pacientes com TB pulmonar está sob tratamento. " * 15
    state = {
        "llm_response_raw": repetitivo,
        "sources_cited": ["FHEMIG (Protocolos Clínicos)"],
    }
    novo_state = response_formatter_node(state)

    assert "A maioria dos pacientes com TB pulmonar está sob tratamento." in novo_state["final_response"]
    # Verifica que não contém 15 repetições
    assert novo_state["final_response"].count("A maioria dos pacientes com TB pulmonar está sob tratamento.") == 1
    assert "AVISO IMPORTANTE" in novo_state["final_response"]
    assert "FHEMIG (Protocolos Clínicos)" in novo_state["final_response"]
    assert novo_state["has_disclaimer"] is True
    assert novo_state["requires_human_validation"] is True


def test_remove_quase_duplicata_com_prefixo_comum_e_dangling():
    texto = (
        "A maioria dos pacientes com TB pulmonar está sob tratamento. "
        "A maioria dos pacientes com TB pulmonar está submetida a tratamento. "
        "A maioria dos pacientes com TB pulmonar está em tratamento. "
        "A maioria dos pacientes com TB pulmonar está em"
    )
    resultado = _remove_repetition_loops(texto)
    assert resultado == "A maioria dos pacientes com TB pulmonar está sob tratamento."


def test_remove_bloco_com_variacao_morfologica():
    """Testa exatamente o caso real onde a repetição de 3 frases varia de plural para singular."""
    bloco1 = (
        "A maioria dos indivíduos com TB apresentará sintomas iniciais durante o curso da doença. "
        "Outros sintomas incluem perda de peso, diminuição da atividade física, falta de ar, fraqueza, irritabilidade, mudanças no humor, sonolência excessiva, constipação e diarréia. "
        "Algumas pessoas afetadas pelo câncer têm sintomas relacionados à doença, enquanto outras não."
    )
    bloco2 = (
        "A maioria dos indivíduos com TB apresentará sintomas iniciais durante o curso da doença. "
        "Outros sintomas incluem perda de peso, diminuição da atividade física, falta de ar, fraqueza, irritabilidade, mudança no humor, sonolência excessiva, constipação e diarréia. "
        "Algumas pessoas afetadas pelo câncer têm sintomas relacionados à doença, enquanto outras não."
    )
    texto = f"{bloco1} {bloco2}"
    resultado = _remove_repetition_loops(texto)
    assert resultado == bloco1


def test_remove_repeticao_lista_ponto_e_virgula():
    texto = (
        "A síndrome é caracterizada por erupções cutâneas esporádicas; "
        "inchaço; edemas; erupções cutâneas secundárias; erupções cutânicas crônicas; "
        "erupções cutânea secundário; erupções cutâneas secundários; erupções cutâneas secundarias; "
        "erupções cutâneas secundaria; erupções cutâneas secundária."
    )
    resultado = _remove_repetition_loops(texto)
    assert resultado.count("erupções cutâneas secund") <= 1
    assert "inchaço" in resultado
    assert "edemas" in resultado


def test_response_formatter_inclui_links_de_url_quando_disponiveis():
    state = {
        "llm_response_raw": "A tuberculose requer tratamento prolongado com antibióticos específicos.",
        "sources_cited": ["FHEMIG (Protocolos Clínicos)"],
        "rag_documents": [
            {
                "dataset": "clinical_protocols",
                "metadatas": {
                    "name": "PC-15---Manejo-hospitalar-da-Tuberculose-(2019).pdf",
                    "source_label": "FHEMIG",
                    "url": "https://www.fhemig.mg.gov.br/files/1394/PC-15.pdf",
                },
            }
        ],
    }
    novo_state = response_formatter_node(state)
    assert "[FHEMIG: PC-15 — Manejo hospitalar da Tuberculose (2019)](https://www.fhemig.mg.gov.br/files/1394/PC-15.pdf)" in novo_state["final_response"]



