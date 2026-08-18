# ADR-009 — Detecção automática GPU/CPU no backend

**Status:** Aceito  
**Data:** 2026-08-18  
**Contexto:** Projeto FIAP POS IA Fase 3 — Execução em ambientes heterogêneos de hardware  
**Decisores:** Equipe do projeto  

---

## Contexto

O backend precisa executar duas categorias de operações intensivas de computação:

1. **Tradução dos datasets** (Step 3 do pré-processamento) — inferência de modelo de tradução;
2. **Fine-tuning do LLM** — treinamento com PyTorch/SFTTrainer.

Ambas as operações se beneficiam enormemente de GPU Nvidia (speedup de 10x–100x vs CPU), mas o ambiente de execução pode variar:

- Máquina de desenvolvimento local (geralmente sem GPU dedicada);
- Container Docker com `runtime: nvidia` (GPU disponível);
- Google Colab (GPU gratuita via sessão);
- Servidor de produção (com ou sem GPU).

Forçar a dependência de GPU tornaria a aplicação inutilizável em ambientes sem GPU, enquanto ignorar a GPU disponível desperdiçaria recursos.

## Decisão

O backend implementa **detecção automática de dispositivo** usando PyTorch, sem necessidade de configuração manual:

```python
def _resolve_device() -> torch.device:
    return torch.device("cuda" if torch.cuda.is_available() else "cpu")
```

Essa lógica é aplicada:

1. **No fine-tuning** (`services/fine_tunning.py`): determina o device e adapta as estratégias de carregamento do modelo (QLoRA em GPU, fp32 em CPU);
2. **Na tradução** (`services/preprocess/step_three_translation.py`): o modelo de tradução é movido para o device disponível.

### Estratégia de precisão numérica por device

```python
if device.type == "cuda":
    if torch.cuda.is_bf16_supported():
        dtype = torch.bfloat16  # Ampere+ (A100, RTX 30xx+)
    else:
        dtype = torch.float16   # GPUs mais antigas (T4, V100)
else:
    dtype = torch.float32       # CPU (sem risco de underflow)
```

### Comportamento no Docker Compose

O `app-docker-compose.yaml` inclui configuração `runtime: nvidia`, mas o container ainda inicia normalmente sem GPU — a detecção automática fará fallback para CPU. O comportamento esperado é descrito no README:

> "Quando houver uma GPU Nvidia compatível e o runtime/driver estiverem instalados, o backend usa GPU automaticamente; caso contrário, ele faz fallback para CPU, o que deixa a tradução dos datasets bem mais lenta."

## Justificativa

A detecção automática é preferível a configuração manual pois:

- Elimina um ponto de falha de configuração (usuário não precisa editar variáveis de ambiente);
- O código se adapta automaticamente ao hardware disponível;
- PyTorch já provê a primitiva `cuda.is_available()` para este fim;
- Segue o princípio de **menor surpresa** para o desenvolvedor.

## Alternativas consideradas

| Alternativa | Razão para não escolher |
|---|---|
| Variável de ambiente `DEVICE=cuda/cpu` | Configuração manual propensa a erros; não detecta se a GPU está realmente disponível |
| Forçar GPU (falhar se não encontrar) | Quebra em ambientes sem GPU; inacessível para desenvolvimento local |
| Forçar CPU sempre | Desperdiça GPU disponível; treino muito lento |
| Suporte apenas a CUDA (sem CPU) | Exclui usuários sem GPU |

## Consequências

**Positivas:**
- A aplicação funciona em qualquer ambiente sem configuração adicional;
- Em ambientes com GPU, o desempenho é otimizado automaticamente;
- A precisão numérica é ajustada conforme a geração da GPU (bf16 vs fp16).

**Negativas:**
- Em CPU, a tradução e o fine-tuning são ordens de magnitude mais lentos;
- O comportamento diferente entre GPU e CPU pode gerar resultados de treino ligeiramente distintos (bf16 vs fp32 têm precisões diferentes);
- `torch.cuda.is_available()` retorna `False` mesmo se a GPU existe mas o driver não está instalado corretamente.

**Neutras:**
- O device detectado é registrado no documento de fine-tuning no MongoDB (`device` field), permitindo rastreabilidade do ambiente de execução de cada run.
