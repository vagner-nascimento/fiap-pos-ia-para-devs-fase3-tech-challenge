# Grounding de laudos médicos e histórico de exames

## Visão geral

O processo de grounding de laudos médicos integra o prontuário do paciente, os registros de exames e a base de conhecimento do agente para responder perguntas clínicas de forma ancorada em evidências reais.

A arquitetura combina três fontes de informação:

- o prontuário estruturado do paciente;
- os laudos médicos associados ao paciente;
- a base RAG de protocolos e conhecimento clínico institucional.

A principal exigência do processo é manter o contexto clínico útil para a resposta sem expor dados pessoais sensíveis. Por isso, a consulta do paciente e a recuperação dos laudos usam um fluxo estritamente filtrado, com campos clínicos relevantes e remoção de PII antes de o texto entrar no prompt da LLM.

## Recuperação do contexto do paciente

Quando a consulta é feita em contexto de paciente, o agente ativa a jornada 2 do pipeline. Nesse estágio, o retriever do paciente consulta:

- `GET /medical-record?patient_name=...`
- `GET /medical-reports?patient_name=...`

O objetivo é compor um contexto clínico sem identificar o paciente diretamente no prompt. Para isso, o sistema preserva apenas campos relevantes como:

- diagnósticos e avaliação clínica;
- orientação terapêutica e plano;
- alergias e contraindicações;
- sinais vitais e objetivo da consulta;
- tipo de exame, descrição técnica, impressão diagnóstica, CID-10 e conduta terapêutica dos laudos.

Esse conjunto é transformado em texto claro para o modelo, em vez de ser enviado como dicionários brutos ou estruturas aninhadas.

## Vinculação entre registro bruto e laudo anonimizado

A base de laudos preparada para RAG e busca vetorial é anonimizada por design. Isso é importante para proteger dados pessoais, mas impõe uma regra arquitetural clara: a correlação de paciente e laudo precisa acontecer em duas etapas.

1. o sistema identifica o paciente no conjunto de dados brutos;
2. a partir do registro correto, recupera o identificador do laudo (`id_laudo`);
3. esse identificador é usado para localizar o documento equivalente na base anonimizada;
4. somente o conteúdo clínico relevante é devolvido ao agente.

Esse mecanismo garante que a busca por laudo continue ligada ao paciente correto, mesmo quando o nome foi removido do dataset de indexação RAG.

## RAG e enriquecimento da pergunta

Depois de montar o contexto do paciente, o agente combina esse material com a pergunta clínica do usuário e executa a busca RAG. O objetivo é enriquecer a recuperação com o quadro real do paciente, buscando protocolos ou diretrizes que tenham maior aderência ao caso atual.

A busca leva em conta:

- diagnóstico ou avaliação atual;
- contexto de laudos e exames prévios;
- objetivo clínico da pergunta;
- histórico de conduta e observações relevantes.

Esse enriquecimento reduz o risco de respostas genéricas e melhora a qualidade do contexto que entra na LLM.

## Guardrail de groundedness para exames e resultados

Para perguntas que envolvem exames, resultados ou histórico de laudos, o fluxo exige evidência documental antes de responder. O modelo não deve inferir exames ausentes nem inventar resultados sem suporte no contexto disponível.

Nesse ponto, o sistema aplica um guardrail explícito:

- se houver laudo ou contexto clínico confiável, a resposta pode detalhar o exame, a impressão diagnóstica e a conduta registrada;
- se não houver documento que sustente a afirmativa, a resposta é bloqueada ou substituída por uma mensagem segura, evitando alucinação.

Essa regra é essencial para casos como:

- último exame do paciente;
- tipo de exame realizado;
- resultado de exames anteriores;
- conduta recomendada a partir de laudos e observações registradas.

## Formação do prompt final

O contexto final entregue à LLM é composto por:

- pergunta do usuário;
- histórico da conversa, quando relevante;
- dados clínicos do paciente anonimizados;
- laudos médicos consolidados do paciente;
- trechos relevantes da base RAG.

O prompt é estruturado de forma explícita para que a LLM use as informações clínicas do paciente como contexto e mantenha a resposta em português, com disclaimer e validação humana obrigatória.

## Benefícios do processo

Esse modelo de grounding oferece vantagens importantes:

- preserva privacidade e conformidade com regras de dados sensíveis;
- mantém a resposta clínica conectada a dados reais do paciente;
- reduz alucinações em consultas sobre exames e resultados;
- melhora a capacidade do agente de responder com contexto clínico relevante e rastreável;
- aumenta a confiabilidade do assistente para uso em cenários de apoio à decisão médica.
