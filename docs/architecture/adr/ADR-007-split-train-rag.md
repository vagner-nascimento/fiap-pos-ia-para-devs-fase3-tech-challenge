# ADR-007 — Split train/RAG configurável via parâmetro rag_percent

**Status:** Aceito  
**Data:** 2026-08-18  
**Contexto:** Projeto FIAP POS IA Fase 3 — Preparação de dados para fine-tuning e Retrieval-Augmented Generation  
**Decisores:** Equipe do projeto  

---

## Contexto

O projeto utiliza os datasets médicos (PubMedQA, MedQuAD e protocolos FHEMIG) para duas finalidades distintas e complementares:

1. **Fine-tuning (treino supervisionado):** os dados são formatados em pares instrução/resposta e usados para adaptar o LLM ao domínio médico;
2. **RAG (Retrieval-Augmented Generation):** os dados são indexados em uma base de recuperação para enriquecer o contexto durante a inferência do modelo.

Como os datasets são compartilhados entre os dois usos, é necessário definiir a proporção de dados destinada a cada um. Essa proporção depende do objetivo do experimento e das necessidades de cada execução, o que torna desejável que seja **configurável em tempo de execução**.

## Decisão

Introduzimos o parâmetro **`rag_percent`** (float entre 0.0 e 1.0) na API de pré-processamento, que controla a fração dos dados reservada para o conjunto RAG. O restante `(1 - rag_percent)` é destinado ao conjunto de treino.

### Interface

```http
POST /preprocess
Content-Type: application/json

{
  "rag_percent": 0.5
}
```

### Comportamento

- `rag_percent = 0.5` → 50% treino / 50% RAG (padrão)
- `rag_percent = 0.2` → 80% treino / 20% RAG (mais dados para fine-tuning)
- `rag_percent = 0.0` → 100% treino / 0% RAG
- `rag_percent = 1.0` → 0% treino / 100% RAG

### Validação

```python
# Pydantic model
rag_percent: float = Field(default=0.5, ge=0.0, le=1.0)
```

### Arquivos gerados

| Conjunto | Dataset | Arquivo |
|---|---|---|
| Treino | QAs (traduzido) | `datasets/preprocessed/qas/train_pt_br.json` |
| RAG | QAs (traduzido) | `datasets/preprocessed/qas/rag_pt_br.json` |
| Treino | Protocolos clínicos | `datasets/preprocessed/clinical_protocols/train.json` |
| RAG | Protocolos clínicos | `datasets/preprocessed/clinical_protocols/rag.json` |

## Justificativa

A configurabilidade via API permite que diferentes experimentos sejam executados sem alterar o código:

- Pesquisadores podem ajustar o balanço treino/RAG conforme o experimento;
- O valor default de 50% é um ponto de partida razoável;
- A validação no nível do Pydantic garante integridade sem código extra.

## Alternativas consideradas

| Alternativa | Razão para não escolher |
|---|---|
| Split fixo (ex.: 80/20) | Sem flexibilidade para experimentos diferentes |
| Split configurado via arquivo .env | Menos conveniente; requer reinício da aplicação |
| Split definido em tempo de fine-tuning | Tardio demais; os arquivos de saída já precisam estar separados |

## Consequências

**Positivas:**
- Cada execução de pré-processamento produz arquivos com o split configurado;
- A configuração fica registrada no documento MongoDB (`rag_percent` field), permitindo rastreabilidade;
- Permite reproduzir exatamente as condições de um experimento passado.

**Negativas:**
- O usuário precisa entender o trade-off entre dados de treino e RAG para definir o parâmetro adequado;
- Um `rag_percent` muito alto reduz os dados de treino e pode prejudicar a qualidade do fine-tuning.

**Neutras:**
- O split é aplicado igualmente a QAs e clinical_protocols, sem possibilidade de configurar proporções distintas por tipo de dado na versão atual.
