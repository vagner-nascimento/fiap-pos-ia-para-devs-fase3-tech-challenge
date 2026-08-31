---
license: apache-2.0
base_model: Qwen/Qwen2.5-1.5B-Instruct
tags:
  - lora
  - fine-tuned
  - healthcare
  - qwen2.5
language:
  - pt
pipeline_tag: text-generation
---

# Hospital Helper — Qwen2.5-1.5B (Fine-tuned)

Modelo de linguagem ajustado para apoio hospitalar (perguntas e respostas e protocolos clínicos), desenvolvido como trabalho de pós-graduação (FIAP).

## Sobre o modelo

- **Modelo base:** [`Qwen/Qwen2.5-1.5B-Instruct`](https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct)
- **Técnica de fine-tuning:** LoRA (Low-Rank Adaptation), com merge posterior dos pesos no modelo base
- **Framework de treino:** `transformers` + `trl` (`SFTTrainer`) + `peft`, executado em ambiente Google Colab
- **Demo:** disponível em um [Hugging Face Space](https://huggingface.co/spaces) (link no repositório da org)

## Dados de treinamento

- **QAs**: pares de pergunta e resposta no domínio hospitalar
- **Protocolos**: exemplos derivados de protocolos clínicos/institucionais

Ambos os conjuntos foram convertidos em exemplos de texto no formato de chat template do Qwen2.5-Instruct antes do treinamento.

## Configuração do fine-tuning (LoRA)

| Parâmetro             | Valor                                                         |
| --------------------- | ------------------------------------------------------------- |
| r (rank)              | 16                                                            |
| lora_alpha            | 16                                                            |
| lora_dropout          | 0.05                                                          |
| bias                  | none                                                          |
| target_modules        | q_proj, k_proj, v_proj, o_proj, gate_proj, up_proj, down_proj |
| task_type             | CAUSAL_LM                                                     |
| Quantização no treino | 4-bit (NF4, double quant)                                     |

## Hiperparâmetros de treinamento

| Parâmetro                   | Valor                                        |
| --------------------------- | -------------------------------------------- |
| Épocas                      | 1.0                                          |
| Batch size (por device)     | 1                                            |
| Gradient accumulation steps | 4                                            |
| Learning rate               | 2e-4                                         |
| Warmup ratio                | 0.03                                         |
| Otimizador                  | adamw_torch                                  |
| Gradient checkpointing      | Ativado                                      |
| Precisão                    | bf16 (ou fp16, conforme suporte de hardware) |
| Estratégia de salvamento    | Por época (save_total_limit=1)               |

## Histórico de versões

Cada retreinamento gera um novo commit no repositório (o Hub versiona tudo via git), marcado com uma tag correspondente. Para carregar uma versão específica:

```python
from transformers import AutoModelForCausalLM, AutoTokenizer

MODEL_NAME = "fiap-hospital-helper/hospital-helper-qwen2.5-1.5b"

model = AutoModelForCausalLM.from_pretrained(MODEL_NAME, revision="v1.0")
tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME, revision="v1.0")
```

| Versão (tag) | Data       | Principais mudanças                                                     |
| ------------ | ---------- | ----------------------------------------------------------------------- |
| `v1.0`       | 10/08/2026 | Primeira versão treinada e publicada                                    |
| `v2.0`       | 23/08/2026 | Treino adicional realizado somente com q&a, protocolos foram para o RAG |

> Atualize esta tabela a cada novo upload, junto com a criação da tag correspondente (ver script abaixo).

### Como criar uma tag após um novo upload

```python
from huggingface_hub import HfApi
api = HfApi()

ORG_NAME = "fiap-hospital-helper"
MODEL_REPO = f"{ORG_NAME}/hospital-helper-qwen2.5-1.5b"

api.create_repo(
    repo_id=MODEL_REPO,
    repo_type="model",
    private=False,
    exist_ok=True
)

api.upload_folder(folder_path=MERGED_DIR, repo_id=MODEL_REPO, repo_type="model")

# Marca esta versão com uma tag, para referência futura
api.create_tag(repo_id=MODEL_REPO, repo_type="model", tag="v2.0", revision="main")

print(f"Modelo disponível em: https://huggingface.co/{MODEL_REPO} (tag v2.0)")
```

## Limitações

- Modelo de pequeno porte (1.5B de parâmetros): pode apresentar respostas menos robustas que modelos maiores em casos fora do domínio de treino.
- Fine-tuning realizado com volume de dados limitado, típico de um projeto acadêmico — não deve ser usado para decisões clínicas reais.
- Este é um projeto experimental/educacional, sem validação clínica ou regulatória.

## Contexto

Projeto desenvolvido como trabalho de pós-graduação, com o objetivo de aplicar técnicas de fine-tuning (LoRA) em um modelo de linguagem de pequeno porte para um domínio específico (apoio hospitalar).
