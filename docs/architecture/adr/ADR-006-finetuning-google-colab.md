# ADR-006 — Fine-tuning executado no Google Colab (fora da aplicação)

**Status:** Aceito  
**Data:** 2026-08-18  
**Contexto:** Projeto FIAP POS IA Fase 3 — Restrições de hardware para execução do fine-tuning  
**Decisores:** Equipe do projeto  

---

## Contexto

Embora o backend da aplicação implemente um endpoint `/fine-tunning` capaz de executar o treinamento localmente (quando há GPU disponível), na prática **as máquinas locais dos desenvolvedores do projeto não possuem GPU dedicada** suficiente para treinar o modelo Qwen2.5-1.5B com os datasets médicos em tempo razoável.

Alternativas avaliadas para contornar esta restrição de hardware:

1. Executar o fine-tuning na própria aplicação em CPU (inviável — estimativa de 20h+);
2. Alugar instâncias de GPU em cloud (custo elevado para um projeto acadêmico);
3. Usar o **Google Colab** com GPU gratuita (T4/A100 via Colab Pro ou ZeroGPU).

## Decisão

O fine-tuning do modelo foi realizado **externamente à aplicação**, utilizando **Jupyter Notebooks no Google Colab**, mantidos no repositório em `backend/src/notebooks/`:

| Notebook | Finalidade |
|---|---|
| `FIAP_PosTech_IA4Devs_Fase3_TechChallenge_FineTunning.ipynb` | Pipeline completa de fine-tuning (carrega dados, configura LoRA, treina, salva no HuggingFace) |
| `FIAP_PosTech_IA4Devs_Fase3_TechChallenge_RuntimeModelo_01.ipynb` | Testa o modelo fine-tunado carregado do HuggingFace |
| `FIAP_PosTech_IA4Devs_Fase3_TechChallenge_TestesValidacoes.ipynb` | Validações e métricas do modelo treinado |

O modelo treinado é publicado como **repositório privado no HuggingFace Hub** (`fiap-hospital-helper/hospital-helper-qwen2.5-1.5b`).

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
- O endpoint `/fine-tunning` da aplicação permanece funcional para ambientes com GPU disponível, servindo como alternativa para produção ou ambientes corporativos.

## Referências

- [Google Colab](https://colab.research.google.com/)
- [HuggingFace Hub — Publicação de modelos](https://huggingface.co/docs/hub/models-uploading)
- Notebooks: [`backend/src/notebooks/`](../../../backend/src/notebooks/)
