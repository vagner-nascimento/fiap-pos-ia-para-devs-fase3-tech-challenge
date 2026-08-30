# ADR-012 — Arquitetura Híbrida de Inferência para a LLM (HF Spaces ZeroGPU e FastAPI ngrok)

**Status:** Aceito  
**Data:** 2026-08-29  
**Contexto:** Projeto FIAP POS IA Fase 3 — Agente Médico e Serviço de Inferência da LLM Fine-Tunada  
**Decisores:** Equipe do projeto  

---

## Contexto

O modelo fine-tunado (**`fiap-hospital-helper/hospital-helper-qwen2.5-1.5b`**) necessita de infraestrutura com GPU para executar inferência de forma eficiente. No entanto, o ciclo de desenvolvimento apresenta necessidades distintas entre ambientes:

1. **Ambiente de Desenvolvimento e Testes Rápidos (Dev/Colab):**
   - Os desenvolvedores executam sessões interativas de treino ou testes no Google Colab, expondo um servidor FastAPI via túnel ngrok temporário (`POST /generate`).
2. **Ambiente de Produção e Demonstração Oficial (Prod/Hugging Face):**
   - O modelo é servido como aplicação oficial no **Hugging Face Spaces ZeroGPU** com Gradio (`hospital-helper`), consumindo recursos de GPU sob demanda de forma estável e serverless através da API Gradio (`api_name="/generate"`).

Era necessário evitar duplicidade de código no agente e garantir que o mesmo serviço pudesse alternar entre os ambientes sem retrabalho.

## Decisão

Adotamos uma **arquitetura de cliente LLM híbrida e unificada** no módulo [`agent/src/services/llm_client.py`](file:///home/luizbaroni/Projetos/fiap/fiap-pos-ia-para-devs-fase3-tech-challenge/agent/src/services/llm_client.py), com capacidade de auto-detecção de provedor:

- **`GradioSpaceLLMClient` (Produção):** Conecta-se diretamente ao Hugging Face Space utilizando o `gradio-client` para acionar a rota `/generate` com alocação ZeroGPU (`@spaces.GPU`), suportando autenticação via token Hugging Face (`HF_TOKEN`) e fallback HTTP nativo.
- **`FastApiLLMClient` (Desenvolvimento):** Realiza chamadas REST padrão (`POST /generate`), enviando os parâmetros `pergunta`, `contexto` e `max_new_tokens`, incluindo o cabeçalho `ngrok-skip-browser-warning: true` para contornar telas intermediárias do ngrok free.
- **Auto-detecção na Factory (`build_llm_client`):** Inspeciona a URL configurada em `LLM_ENDPOINT_URL` (ou a variável `LLM_PROVIDER`) e instancia o cliente correto automaticamente.

## Justificativa

| Critério | Cliente Único Fixo (HF Hub) | Endpoints Separados por Código | **Cliente Híbrido com Auto-Detecção** |
|---|---|---|---|
| Flexibilidade de Ambiente | ❌ Bloqueia testes com ngrok local | ❌ Código duplicado e branches separadas | ✅ Chaveamento transparente via `.env` |
| Suporte a ZeroGPU (Gradio) | ❌ Incompatível com rotas Gradio | ⚠️ Requer código customizado | ✅ Suporte nativo via `gradio-client` |
| Desacoplamento do Agente | ❌ Agente preso a um fornecedor | ❌ Acoplamento rígido | ✅ Agente consome interface única `generate()` |
| Tolerância a Falhas | ⚠️ Erros de rede bloqueiam o nó | ⚠️ Manutenção complexa | ✅ Fallbacks HTTP diretos implementados |

## Consequências

### Positivas
- **Portabilidade:** Para alternar entre o servidor temporário no Colab (ngrok) e o Space oficial no Hugging Face, basta alterar uma única linha no `.env` (`LLM_ENDPOINT_URL`).
- **Resiliência:** O cliente trata automaticamente peculiaridades de rede do ngrok e da API Gradio.
- **Zero Overhead:** O agente expõe uma assinatura uniforme `generate(pergunta, contexto, prompt)` independente do backend de inferência ativo.

### Negativas
- Adiciona a dependência do `gradio-client` ao projeto do agente.
- Necessidade de manter compatibilidade com os dois schemas de payload caso a API do Colab seja alterada.

---

← [Voltar para o Índice de ADRs](README.md)
