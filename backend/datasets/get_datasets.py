import json
import os
import re
import subprocess
from pathlib import Path
from typing import Optional, Dict, List, Tuple
from urllib.parse import quote, unquote, urlparse, urlunparse

import requests
from bs4 import BeautifulSoup

SOURCE_NAME = "Fundação Hospitalar do Estado de Minas Gerais"
FHEMIG_PROTOCOLS_URL = "https://www.fhemig.mg.gov.br/index.php/acesso-rapido/protocolos-clinicos"

PCDT_SOURCE_NAME = "Ministério da Saúde - Protocolos Clínicos e Diretrizes Terapêuticas (PCDT)"
LAUDOS_SOURCE_NAME = "Dataset sintético de laudos médicos (pt-BR)"


def clone_qa_repositories() -> Dict[str, str]:
    # Caminho base para salvar os repositórios (backend/datasets/files/qas)
    script_dir = os.path.dirname(os.path.abspath(__file__))
    target_dir = os.path.join(script_dir, "files", "qas")

    # Criar a pasta datasets/files/qas se não existir
    os.makedirs(target_dir, exist_ok=True)

    repositories = {
        "pubmedqa": "https://github.com/pubmedqa/pubmedqa.git",
        "MedQuAD": "https://github.com/abachaa/MedQuAD.git",
    }

    repo_paths: Dict[str, str] = {}
    for repo_name, repo_url in repositories.items():
        repo_path = os.path.join(target_dir, repo_name)
        if os.path.exists(repo_path):
            print(f"O repositório {repo_name} já existe em {repo_path}. Pulando...")
        else:
            print(f"Clonando {repo_name} de {repo_url}...")
            try:
                subprocess.run(["git", "clone", repo_url, repo_path], check=True)
                print(f"{repo_name} clonado com sucesso!")
            except subprocess.CalledProcessError as e:
                print(f"Erro ao clonar {repo_name}: {e}")

        repo_paths[repo_name] = repo_path

    return repo_paths


def extract_clinical_protocol_links(html: str) -> List[Dict[str, str]]:
    if not html:
        return []

    protocols = []
    seen_urls = set()

    if BeautifulSoup is not None:
        soup = BeautifulSoup(html, "html.parser")
        for link in soup.find_all("a", href=True):
            href = link.get("href", "")
            parsed_url = urlparse(href)
            if not parsed_url.path.lower().endswith(".pdf"):
                continue

            clean_url = href.split("?", 1)[0]
            if clean_url in seen_urls:
                continue

            seen_urls.add(clean_url)
            protocols.append(
                {
                    "name": unquote(Path(parsed_url.path).name) or "documento.pdf",
                    "url": clean_url,
                    "source": SOURCE_NAME,
                }
            )

        if protocols:
            return protocols

    patterns = [
        r'href=["\']([^"\']+\.pdf(?:\?[^"\']*)?)["\']',
        r'https?://[^"\'\s<>]+\.pdf(?:\?[^"\'\s<>]*)?',
        r'(?<![\w/.-])(?:/|https?://)[^"\'\s<>]+\.pdf(?:\?[^"\'\s<>]*)?',
    ]

    for pattern in patterns:
        for match in re.finditer(pattern, html, re.IGNORECASE):
            candidate = match.group(0)
            if candidate.startswith("href="):
                candidate = candidate[len("href=") :]
                if candidate[0] in {'"', "'"} and candidate[-1] == candidate[0]:
                    candidate = candidate[1:-1]
            if candidate.startswith("/"):
                candidate = f"https://www.fhemig.mg.gov.br{candidate}"

            clean_url = candidate.split("?", 1)[0]
            if clean_url in seen_urls:
                continue

            seen_urls.add(clean_url)
            protocols.append(
                {
                    "name": unquote(Path(urlparse(clean_url).path).name) or "documento.pdf",
                    "url": clean_url,
                    "source": SOURCE_NAME,
                }
            )

    return protocols


def download_clinical_protocol_files(protocols: List[Dict[str, str]], target_dir: Optional[Path] = None) -> List[str]:
    script_dir = Path(__file__).resolve().parent
    download_dir = Path(target_dir) if target_dir is not None else script_dir / "files" / "fhemig" / "data"
    download_dir.mkdir(parents=True, exist_ok=True)

    downloaded_files: List[str] = []
    for protocol in protocols:
        url = protocol.get("url", "")
        if not url:
            continue

        file_name = protocol.get("name") or Path(urlparse(url).path).name or "documento.pdf"
        safe_name = re.sub(r"[^\w.-]+", "_", file_name, flags=re.UNICODE).strip("._-") or "documento.pdf"
        safe_name = safe_name.replace("__", "_").strip("._-")
        if not safe_name.lower().endswith(".pdf"):
            safe_name = f"{safe_name}.pdf"

        output_path = download_dir / safe_name
        if not output_path.exists():
            try:
                # Codifica caracteres não-ASCII no path da URL (ex: ç, ã, ô)
                parsed = urlparse(url)
                encoded_url = urlunparse(parsed._replace(path=quote(parsed.path, safe="/")))

                if requests is not None:
                    response = requests.get(encoded_url, timeout=60)
                    response.raise_for_status()
                    content = response.content
                else:
                    import urllib.request

                    with urllib.request.urlopen(encoded_url, timeout=60) as response:
                        content = response.read()

                output_path.write_bytes(content)
            except Exception as exc:
                print(f"Falha ao baixar {url}: {exc}")
                continue

        downloaded_files.append(str(output_path))

    return downloaded_files


def download_fhemig_clinical_protocols(
    url: str = FHEMIG_PROTOCOLS_URL,
) -> Tuple[Path, Path]:
    script_dir = Path(__file__).resolve().parent
    output_dir = script_dir / "files" / "clinical_protocols"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / "clinical_protocols.json"
    download_dir = output_dir / "data"

    if requests is not None:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        html = response.text
    else:
        import urllib.request

        with urllib.request.urlopen(url, timeout=30) as response:
            html = response.read().decode("utf-8", errors="ignore")

    protocols = extract_clinical_protocol_links(html)
    if not protocols:
        raise ValueError(f"Nenhum link de PDF encontrado em {url}")

    with output_file.open("w", encoding="utf-8") as handle:
        json.dump(protocols, handle, indent=2, ensure_ascii=False)

    downloaded_files = download_clinical_protocol_files(protocols, download_dir)
    print(f"{len(protocols)} protocolos clínicos salvos em {output_file}")
    print(f"{len(downloaded_files)} arquivos PDF salvos em {download_dir}")
    return output_file, download_dir


def prepare_pcdt_protocols() -> Tuple[Path, Path]:
    """
    Prepare the local PCDT (Protocolos Clínicos e Diretrizes Terapêuticas) dataset.

    The source PDFs are shipped **as a single ZIP** (`pcdt.zip`, tracked via
    Git LFS) at ``backend/datasets/files/pcdt/``. On the first run this
    function extracts the ZIP into ``backend/datasets/files/pcdt/data/`` and
    then builds a catalog JSON describing each PDF (mirroring the FHEMIG
    structure).

    Returns ``(catalog_json_path, pdfs_dir)``.
    """
    script_dir = Path(__file__).resolve().parent
    base_dir = script_dir / "files" / "pcdt"
    pdfs_dir = base_dir / "data"
    zip_path = base_dir / "pcdt.zip"
    catalog_path = base_dir / "pcdt_protocols.json"

    pdfs_dir.mkdir(parents=True, exist_ok=True)

    # Extract the shipped ZIP on first run (or whenever data/ has no PDFs).
    # Path traversal (CWE-22) is mitigated by rejecting any absolute member
    # name or ".." segment before extraction.
    existing_pdfs = list(pdfs_dir.glob("*.pdf"))
    if not existing_pdfs and zip_path.exists():
        import zipfile

        print(f"Extraindo PCDTs a partir de {zip_path}...")
        with zipfile.ZipFile(zip_path, "r") as archive:
            for member in archive.infolist():
                member_name = member.filename
                if not member_name.lower().endswith(".pdf"):
                    continue
                # Skip macOS metadata artifacts and dotfiles.
                base_name = Path(member_name).name
                if base_name.startswith("._") or "__MACOSX" in member_name:
                    continue
                # Reject any path traversal attempts.
                if member_name.startswith("/") or ".." in Path(member_name).parts:
                    print(f"Aviso: entrada de ZIP ignorada por seguranca: {member_name}")
                    continue

                target_path = pdfs_dir / base_name
                if target_path.exists():
                    continue
                with archive.open(member) as source, target_path.open("wb") as sink:
                    sink.write(source.read())

        existing_pdfs = list(pdfs_dir.glob("*.pdf"))
        print(f"{len(existing_pdfs)} PDFs extraidos em {pdfs_dir}")

    if not pdfs_dir.exists() or not existing_pdfs:
        raise FileNotFoundError(
            f"Nenhum PDF do PCDT encontrado em {pdfs_dir} e nenhum ZIP disponivel em {zip_path}. "
            "Faca git-lfs pull ou baixe o ZIP manualmente."
        )

    protocols: List[Dict[str, str]] = []
    for pdf_path in sorted(pdfs_dir.glob("*.pdf")):
        protocols.append(
            {
                "name": pdf_path.name,
                # Local file — no remote URL. Keep field for schema compatibility.
                "url": "",
                "source": PCDT_SOURCE_NAME,
            }
        )

    if not protocols:
        raise ValueError(f"Nenhum PDF encontrado em {pdfs_dir}")

    with catalog_path.open("w", encoding="utf-8") as handle:
        json.dump(protocols, handle, indent=2, ensure_ascii=False)

    print(f"{len(protocols)} PCDTs catalogados em {catalog_path}")
    return catalog_path, pdfs_dir


def prepare_laudos_medicos_dataset() -> Path:
    """
    Return the path to the local synthetic medical reports dataset (pt-BR).

    The JSON file is shipped with the repository under
    ``backend/datasets/files/laudos_medicos/dataset_laudos_medicos.json``.
    """
    script_dir = Path(__file__).resolve().parent
    dataset_path = script_dir / "files" / "laudos_medicos" / "dataset_laudos_medicos.json"

    if not dataset_path.exists():
        raise FileNotFoundError(
            f"Dataset de laudos médicos não encontrado em {dataset_path}."
        )

    print(f"Dataset de laudos médicos disponível em {dataset_path}")
    return dataset_path


if __name__ == "__main__":
    print(clone_qa_repositories())
    print(download_fhemig_clinical_protocols())
    print(prepare_pcdt_protocols())
    print(prepare_laudos_medicos_dataset())
