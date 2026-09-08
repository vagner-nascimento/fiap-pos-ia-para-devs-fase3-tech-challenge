# ADR-006 — Fine-tuning executado no Google Colab (fora da aplicação)

**Status:** Aceito  
**Data:** 2026-08-18  
**Contexto:** Projeto FIAP POS IA Fase 3 — Restrições de hardware para execução do fine-tuning  
**Decisores:** Equipe do projeto  

---

## Contexto

Foi revertida a decisão de manter uma execução local de fine-tuning na aplicação. **O fine-tuning não será implementado localmente**, pois as máquinas dos desenvolvedores não possuem GPU dedicada suficiente para treinar o modelo Qwen2.5-1.5B com os datasets médicos em tempo razoável.

Alternativas avaliadas para contornar esta restrição de hardware:

1. Executar o fine-tuning na própria aplicação em CPU (inviável — estimativa de 20h+);
2. Alugar instâncias de GPU em cloud (custo elevado para um projeto acadêmico);
3. Usar o **Google Colab** com GPU gratuita (T4/A100 via Colab Pro ou ZeroGPU).

## Decisão

O fine-tuning e a avaliação do modelo foram realizados **externamente à aplicação**, utilizando **Jupyter Notebooks no Google Colab**, mantidos e documentados em `backend/src/notebooks/`:

| Notebook | Finalidade |
|---|---|
| `FIAP_PosTech_IA4Devs_Fase3_TechChallenge_Modelo_v1.ipynb` | Fine-tuning inicial (v1.0 — 188 steps de aquecimento) |
| `FIAP_PosTech_IA4Devs_Fase3_TechChallenge_Modelo_v2.ipynb` | Treinamento contínuo com checkpoints LoRA (início da linhagem v2.0) |
| `FIAP_PosTech_IA4Devs_Fase3_TechChallenge_Modelo_v3.ipynb` e `v4.ipynb` | Refinamento contínuo de checkpoints e consolidação da linhagem canônica v2.0 |
| `FIAP_PosTech_IA4Devs_Fase3_TechChallenge_RuntimeModelo_01.ipynb` | Servidor FastAPI + ngrok para inferência remota interativa |
| `FIAP_PosTech_IA4Devs_Fase3_TechChallenge_TestesValidacoes.ipynb` | Validação clínica qualitativa e testes pontuais de sanidade |
| `FIAP_PosTech_IA4Devs_Fase3_TechChallenge_AvaliacaoModelos.ipynb` | Pipeline de avaliação quantitativa formal (ROUGE-1/2/L, BLEU-1/2/3/4, latência) com dataset golden test |
| `..._AvaliacaoModelos_Config[A|B|C].ipynb` | Execuções completas com outputs e gráficos para calibração de decodificação |

O modelo treinado é publicado como **repositório público no HuggingFace Hub** ([`fiap-hospital-helper/hospital-helper-qwen2.5-1.5b`](https://huggingface.co/fiap-hospital-helper/hospital-helper-qwen2.5-1.5b)), com a tag `v2.0` como versão oficial de produção.

## Justificativa

| Critério | Colab (gratuito) | Colab Pro | AWS/GCP GPU | Local (CPU) |
|---|---|---|---|---|
| Custo | $0 | ~$10/mês | $2–5/hora | $0 |
| GPU disponível | T4 (15GB) | A100 (40GB) | Qualquer | ❌ |
| Tempo de treino | ~1–2h | ~30min | ~30min | 20h+ |
| Facilidade de setup | Alta | Alta | Média | Alta |
| Adequado para projeto acadêmico | ✅ | ✅ | ❌ (custo) | ❌ (tempo) |

## Consequências

**Positivas:**
- Fine-tuning realizado sem custo de infraestrutura;
- Notebooks versionados no repositório permitem reproduzibilidade;
- Separação clara entre o ambiente de treinamento (Colab) e o ambiente de produção (Docker).

**Negativas:**
- O fine-tuning não é automatizado ou integrado ao CI/CD do projeto;
- Requer acesso manual ao Colab para reexecutar o treinamento;
- Sessões do Colab gratuito têm limite de tempo (desconecta após ~12h inativas).

**Neutras:**
- Não haverá endpoint ou tela para iniciar e monitorar fine-tuning localmente. O treinamento será realizado somente no Google Colab, através dos notebooks versionados no repositório.

## Referências

- [Google Colab](https://colab.research.google.com/)
- [HuggingFace Hub — Publicação de modelos](https://huggingface.co/docs/hub/models-uploading)
- Notebooks: [`backend/src/notebooks/`](../../../backend/src/notebooks/)
