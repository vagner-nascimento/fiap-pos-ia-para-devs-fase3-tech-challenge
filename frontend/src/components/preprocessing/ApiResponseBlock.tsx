import type { PreprocessDocument } from "../../types/preprocess";

interface Props {
  document: PreprocessDocument;
}

export function ApiResponseBlock({ document }: Props) {
  return (
    <div className="response-block">
      <h3>Resposta da API</h3>
      <pre>{JSON.stringify(document, null, 2)}</pre>
    </div>
  );
}
