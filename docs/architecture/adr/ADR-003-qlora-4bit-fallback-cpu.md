# ADR-003 — QLoRA (quantização 4-bit) com fallback para CPU

**Status:** Aceito  
**Data:** 2026-08-18  
**Contexto:** Projeto FIAP POS IA Fase 3 — Execução do fine-tuning em ambientes com diferentes capacidades de hardware  
**Decisores:** Equipe do projeto  

---

## Contexto

O fine-tuning de um modelo de 1.5B parâmetros com LoRA ainda pode exigir mais VRAM do que o disponível em determinadas GPUs, especialmente ao usar precisão de 16-bit (fp16/bf16). Para maximizar a compatibilidade com diferentes ambientes de execução (local, Colab T4, Colab A100), é necessário suportar:

1. Quantização 4-bit (QLoRA) quando GPU com suporte está disponível;
2. Fallback automático para CPU quando nenhuma GPU compatível é detectada.

Adicionalmente, o modelo deve usar a precisão de ponto flutuante mais adequada para cada hardware (bf16 em Ampere+, fp16 em GPUs mais antigas, fp32 em CPU).

## Decisão

O backend implementa **detecção automática de hardware** com as seguintes estratégias:

### Lógica de resolução de dispositivo

```python
def _resolve_device() -> torch.device:
    return torch.device("cuda" if torch.cuda.is_available() else "cpu")
```

### Lógica de carregamento do modelo

| Condição | Estratégia |
|---|---|
| GPU + `use_4bit=True` | QLoRA com `BitsAndBytesConfig` (nf4, double quant) |
| GPU + `use_4bit=False` | Carregamento em bf16 ou fp16 conforme suporte |
| CPU | Carregamento em fp32 |

### Configuração QLoRA

```python
BitsAndBytesConfig(
    load_in_4bit=True,
    bnb_4bit_use_double_quant=True,
    bnb_4bit_quant_type="nf4",
    bnb_4bit_compute_dtype=torch.bfloat16  # ou float16
)
```

## Justificativa

| Estratégia | VRAM necessária (modelo 1.5B) | Compatibilidade |
|---|---|---|
| fp32 (CPU) | N/A (RAM ~6GB) | Universal |
| fp16/bf16 (GPU) | ~3–4GB | GPUs modernas |
| QLoRA 4-bit (GPU) | ~2–3GB | GPUs com CUDA + bitsandbytes |

A quantização NF4 (Normal Float 4) com double quantization oferece o melhor equilíbrio entre compressão e qualidade em modelos de linguagem.

## Alternativas consideradas

| Alternativa | Razão para não escolher |
|---|---|
| Apenas fp16/bf16 | Pode não caber em GPUs com menos de 8GB |
| Apenas QLoRA | Requer GPU com CUDA; não funciona em CPU |
| GPTQ quantization | Requer pré-quantização offline do modelo; mais complexo |
| Erro em ausência de GPU | Prejudicaria testes e desenvolvimento local sem GPU |

## Consequências

**Positivas:**
- O sistema executa em qualquer ambiente sem configuração manual;
- QLoRA reduz o uso de VRAM em ~50-60% vs fp16;
- O parâmetro `use_4bit` pode ser controlado via API para flexibilidade.

**Negativas:**
- Execução em CPU é drasticamente mais lenta (horas vs minutos em GPU);
- QLoRA introduz pequena perda de qualidade vs bf16 puro;
- A biblioteca `bitsandbytes` tem suporte limitado em ambientes não-Linux.

**Neutras:**
- O arquivo `docker-compose.yaml` já inclui configurações `runtime: nvidia` e `NVIDIA_VISIBLE_DEVICES: all` para viabilizar o uso de GPU dentro do container.

## Referências

- [QLoRA: Efficient Finetuning of Quantized LLMs (Dettmers et al., 2023)](https://arxiv.org/abs/2305.14314)
- [bitsandbytes library](https://github.com/TimDettmers/bitsandbytes)
