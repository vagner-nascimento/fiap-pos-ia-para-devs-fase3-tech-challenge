# ADR-002 — Uso de LoRA/PEFT para fine-tuning eficiente

**Status:** Aceito  
**Data:** 2026-08-18  
**Contexto:** Projeto FIAP POS IA Fase 3 — Fine-tuning do modelo Qwen2.5-1.5B-Instruct  
**Decisores:** Equipe do projeto  

---

## Contexto

Realizar um fine-tuning completo (full fine-tuning) de um LLM exige atualizar todos os bilhões de parâmetros do modelo, o que demanda:

- Dezenas de GBs de memória VRAM (impraticável em GPUs consumer-grade);
- Horas a dias de treinamento mesmo em hardware dedicado;
- Risco de catastrofic forgetting (perda do conhecimento geral do modelo base).

O projeto precisa de uma técnica de fine-tuning que seja viável em GPUs com 15-40GB de VRAM (Google Colab T4/A100), sem comprometer a qualidade do modelo resultante.

## Decisão

Utilizamos **LoRA (Low-Rank Adaptation)** via biblioteca **PEFT (Parameter-Efficient Fine-Tuning)** da HuggingFace para realizar o fine-tuning do modelo.

### Configuração adotada

```python
LoraConfig(
    r=16,               # rank das matrizes de adaptação
    lora_alpha=16,      # escala do LoRA
    lora_dropout=0.05,  # regularização
    bias="none",
    task_type=TaskType.CAUSAL_LM,
    target_modules=[
        "q_proj", "k_proj", "v_proj", "o_proj",   # atenção
        "gate_proj", "up_proj", "down_proj",        # FFN
    ]
)
```

## Justificativa

| Critério | Full Fine-tuning | LoRA |
|---|---|---|
| Parâmetros treináveis | ~100% (1.5B) | ~0.5–2% (~10–30M) |
| VRAM necessária | >40GB | ~6–15GB |
| Tempo de treino | Muito alto | Reduzido (3–10x) |
| Qualidade | Alta | Comparável para SFT de domínio |
| Catastrophic forgetting | Alto risco | Baixo risco |

## Alternativas consideradas

| Alternativa | Razão para não escolher |
|---|---|
| Full fine-tuning | Inviável com hardware disponível (T4/A100 Colab) |
| Prompt engineering / few-shot | Não persiste aprendizado; limitado ao contexto da janela |
| Adapter layers (Houlsby) | Mais lento na inferência que LoRA; menos suporte na comunidade |
| IA3 | Menos expressivo que LoRA para domínios específicos |

## Consequências

**Positivas:**
- Fine-tuning viável em GPU T4 (15GB) e A100 (40GB) do Google Colab;
- Apenas os pesos LoRA (~dezenas de MB) precisam ser salvos e compartilhados;
- Fácil merge com o modelo base para inferência via `peft.merge_adapter()`;
- Preserva o conhecimento geral do Qwen2.5.

**Negativas:**
- Introduz hiperparâmetros adicionais (`r`, `lora_alpha`) que precisam ser ajustados;
- A qualidade pode ser inferior ao full fine-tuning em tarefas muito específicas.

**Neutras:**
- Os módulos alvo (`q_proj`, `k_proj`, etc.) foram escolhidos seguindo boas práticas documentadas para a família Qwen2.

## Referências

- [LoRA: Low-Rank Adaptation of Large Language Models (Hu et al., 2021)](https://arxiv.org/abs/2106.09685)
- [PEFT Library — HuggingFace](https://github.com/huggingface/peft)
