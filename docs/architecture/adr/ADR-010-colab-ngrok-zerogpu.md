# ADR-010 — Google Colab + ngrok e HuggingFace ZeroGPU para servir o modelo

**Status:** Aceito  
**Data:** 2026-08-18  
**Contexto:** Projeto FIAP POS IA Fase 3 — Disponibilização do modelo fine-tunado para testes e entrega do trabalho  
**Decisores:** Equipe do projeto  

---

## Contexto

Após o fine-tuning do modelo Qwen2.5-1.5B-Instruct no Google Colab (ver [ADR-006](ADR-006-finetuning-google-colab.md)), o modelo treinado precisa ser disponibilizado para:

1. **Testes e validações durante o desenvolvimento** — necessidade de inferência rápida e interativa;
2. **Entrega do trabalho** — o modelo precisa ser acessível publicamente para avaliação.

O projeto enfrenta as mesmas restrições de hardware locais que motivaram o uso do Colab para o fine-tuning: sem GPU local, a inferência do Qwen2.5-1.5B seria inviável em tempo razoável. Alugar infraestrutura cloud tem custo elevado para um projeto acadêmico.

## Decisão

Adotamos **duas estratégias complementares** para disponibilizar o modelo:

### Estratégia 1 — Testes e desenvolvimento: Colab + ngrok

Para testes rápidos e iterativos durante o desenvolvimento, o notebook `FIAP_PosTech_IA4Devs_Fase3_TechChallenge_RuntimeModelo_01.ipynb` executa:

1. Carrega o modelo fine-tunado do HuggingFace Hub;
2. Sobe um servidor de inferência dentro da sessão do Colab;
3. Usa **ngrok** para criar um túnel HTTPS público apontando para o servidor do Colab;
4. Expõe uma URL temporária para requisições de inferência.

```
Usuário → HTTPS → ngrok tunnel → Colab runtime → modelo fine-tunado
```

**Vantagens:**
- Zero custo (Colab gratuito + ngrok free tier);
- GPU A100/T4 do Colab para inferência rápida;
- Setup em minutos.

**Limitações:**
- URL temporária (muda a cada sessão do Colab);
- Sessão expira após inatividade (~12h no Colab gratuito);
- ngrok free tier tem limite de conexões.

### Estratégia 2 — Entrega do trabalho: HuggingFace Spaces com ZeroGPU

Para a entrega formal do trabalho, o modelo é disponibilizado em um **HuggingFace Space** utilizando **ZeroGPU**:

```
Usuário → HuggingFace Spaces UI → ZeroGPU (A100 compartilhada) → modelo fine-tunado
```

**Configuração:**
- Space configurado com `sdk: gradio` ou `sdk: streamlit`;
- O decorator `@spaces.GPU` do ZeroGPU aloca GPU dinamicamente apenas durante a inferência;
- O modelo é carregado do repositório privado HuggingFace (`fiap-hospital-helper/hospital-helper-qwen2.5-1.5b`).

**Vantagens:**
- URL pública e persistente (não expira);
- GPU A100 disponível via ZeroGPU sem custo adicional;
- Interface web pronta para demonstração e avaliação;
- Integrado ao ecossistema HuggingFace.

**Limitações:**
- ZeroGPU tem limite de tempo por requisição;
- Repositório do modelo precisa ser acessível pelo Space (público ou com token).

## Justificativa

| Critério | Colab + ngrok | HF Spaces + ZeroGPU | AWS/GCP inference | Local (CPU) |
|---|---|---|---|---|
| Custo | $0 | $0 | $0.10–0.50/hora | $0 |
| Disponibilidade | Temporária | Persistente | Persistente | Sempre |
| GPU | T4/A100 | A100 (ZeroGPU) | Qualquer | ❌ |
| Adequado para testes | ✅ | ✅ | ✅ | ❌ |
| Adequado para entrega | ❌ (temporário) | ✅ | ✅ | ❌ |
| Facilidade de setup | Média | Alta | Baixa | Alta |

## Consequências

**Positivas:**
- Solução de zero custo para disponibilizar o modelo em contexto acadêmico;
- ZeroGPU democratiza o acesso a hardware de alta performance;
- Colab + ngrok permite ciclos rápidos de teste durante o desenvolvimento;
- HuggingFace Spaces fornece uma interface profissional para a entrega.

**Negativas:**
- A URL do ngrok muda a cada sessão (inconveniente durante testes prolongados);
- ZeroGPU tem cold start (~30s) e limite de tempo por sessão;
- Dependência de terceiros para a disponibilidade do serviço (Colab, ngrok, HuggingFace).

**Neutras:**
- As duas estratégias são complementares e se aplicam a fases distintas do projeto (desenvolvimento vs. entrega);
- O modelo fine-tunado permanece no HuggingFace Hub como artefato persistente, independente da estratégia de serving.

## Referências

- [ngrok — Documentação](https://ngrok.com/docs)
- [HuggingFace ZeroGPU — Documentação](https://huggingface.co/docs/hub/spaces-zerogpu)
- [HuggingFace Spaces — Gradio](https://huggingface.co/docs/hub/spaces-sdks-gradio)
- Notebook de runtime: [`backend/src/notebooks/FIAP_PosTech_IA4Devs_Fase3_TechChallenge_RuntimeModelo_01.ipynb`](../../../backend/src/notebooks/FIAP_PosTech_IA4Devs_Fase3_TechChallenge_RuntimeModelo_01.ipynb)
