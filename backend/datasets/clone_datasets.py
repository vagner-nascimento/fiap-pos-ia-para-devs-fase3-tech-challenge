import os
import subprocess

def clone_repositories():
    # Caminho base para salvar os repositórios (backend/datasets/files)
    script_dir = os.path.dirname(os.path.abspath(__file__))
    target_dir = os.path.join(script_dir, "files")
    
    # Criar a pasta datasets/files se não existir
    os.makedirs(target_dir, exist_ok=True)
    
    repositories = {
        "pubmedqa": "https://github.com/pubmedqa/pubmedqa.git",
        "MedQuAD": "https://github.com/abachaa/MedQuAD.git"
    }
    
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

if __name__ == "__main__":
    clone_repositories()
