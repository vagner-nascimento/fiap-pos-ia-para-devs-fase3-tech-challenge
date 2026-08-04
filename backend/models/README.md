# Models

Este diretorio e reservado para armazenar os artefatos gerados pelo processo de fine-tuning.

Estrutura esperada:

- `hospital_helper/` para o modelo treinado
- `hospital_helper_tokenizer/` para o tokenizer salvo
- `hospital_helper/training_summary.json` com o resumo da execucao

Quando o treinamento produzir um novo artefato, ele deve ser salvo aqui para ficar disponivel nas proximas execucoes. Se um modelo ja existir neste local, ele pode ser reutilizado diretamente, evitando recriacao e novo treinamento desnecessario.
