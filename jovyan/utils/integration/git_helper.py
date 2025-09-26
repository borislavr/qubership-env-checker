import sys
import os
import subprocess
import shutil
from urllib.parse import urlsplit, urlunsplit, quote

def authenticate_repo_url(repo_url: str) -> str:
    """
    Authenticate repository URL using environment variables if available.
    
    Args:
        repo_url (str): The original repository URL.
        
    Returns:
        str: Authenticated URL if GIT_USERNAME/GIT_TOKEN are available, otherwise original URL.
    """
    username = os.environ.get("GIT_USERNAME")
    token = os.environ.get("GIT_TOKEN")
    if username and token:
        return get_auth_string(token=token, username=username, repo_url=repo_url)
    return repo_url

def fetch_from_repo(repo_url: str, target_path: str, sparse_path: str, branch: str = "main", subfolder: str = "") -> bool:
    """
    Sparse-checkout a repository path into target_path.
    If GIT_USERNAME/GIT_TOKEN are present in the environment, the function
    will authenticate by embedding credentials into the repo URL (HTTPS only).
    
    Args:
        repo_url (str): The URL of the Git repository.
        target_path (str): Local directory where files will be fetched.
        sparse_path (str): Path to fetch from the repository.
        branch (str): Branch to fetch from. Defaults to "main".
        subfolder (str): Subfolder to move files to. Defaults to "".
        
    Returns:
        bool: True if successful.
        
    Raises:
        FileExistsError: If target_path already exists.
        subprocess.CalledProcessError: If git commands fail.
    """
    # Authenticate URL if credentials are available
    repo_url = authenticate_repo_url(repo_url)

    if os.path.exists(target_path):
        raise FileExistsError(f"Target path {target_path} already exists.")

    # init empty repo and enable sparse checkout
    os.makedirs(target_path, exist_ok=True)
    subprocess.run(["git", "init"], cwd=target_path, check=True)
    subprocess.run(["git", "remote", "add", "origin", repo_url], cwd=target_path, check=True)
    subprocess.run(["git", "config", "core.sparseCheckout", "true"], cwd=target_path, check=True)

    sparse_file = os.path.join(target_path, ".git", "info", "sparse-checkout")
    with open(sparse_file, "w", encoding="utf-8") as f:
        f.write(sparse_path + "\n")

    subprocess.run(["git", "pull", "origin", branch], cwd=target_path, check=True)

    src_path = os.path.join(target_path, *sparse_path.split("/"))
    if subfolder:
        dst_dir = os.path.join(target_path, subfolder)
        os.makedirs(dst_dir, exist_ok=True)
        # If src_path is a directory, move its contents to dst_dir
        if os.path.isdir(src_path):
            for item in os.listdir(src_path):
                shutil.move(os.path.join(src_path, item), dst_dir)
            shutil.rmtree(src_path)
        else:
            shutil.move(src_path, dst_dir)
        # Remove all parent directories created by git (e.g., jovyan/tests)
        top_level = os.path.join(target_path, sparse_path.split("/")[0])
        if os.path.exists(top_level):
            shutil.rmtree(top_level)
    else:
        # If src_path is a directory, move its contents to target_path
        if os.path.isdir(src_path):
            for item in os.listdir(src_path):
                shutil.move(os.path.join(src_path, item), target_path)
            shutil.rmtree(src_path)
        else:
            shutil.move(src_path, target_path)
        # Remove all parent directories created by git (e.g., jovyan/tests)
        top_level = os.path.join(target_path, sparse_path.split("/")[0])
        if os.path.exists(top_level):
            shutil.rmtree(top_level)
    return True

def get_auth_string(token: str, username: str, repo_url: str) -> str:
    """
    Authenticate with a Git repository using a token and a username.

    Args:
        token (str): The token to use for authentication.
        username (str): The username to use for authentication.
        repo_url (str): The URL of the Git repository.

    Returns:
        str: The authenticated URL of the Git repository. If creds are missing,
        returns the original URL unchanged.

    Notes:
        - Works for HTTPS(S) URLs by embedding credentials in netloc.
        - SSH URLs are returned unchanged.
    """
    if not token or not username:
        return repo_url

    parts = urlsplit(repo_url)
    # don't try to inject into SSH/other schemes
    if parts.scheme not in ("http", "https"):
        return repo_url

    # netloc may already contain creds; replace them
    host = parts.hostname or ""
    port = f":{parts.port}" if parts.port else ""
    auth = f"{quote(username)}:{quote(token)}@" if username and token else ""
    new_netloc = f"{auth}{host}{port}"
    return urlunsplit((parts.scheme, new_netloc, parts.path, parts.query, parts.fragment))

if __name__ == "__main__":
    if len(sys.argv) < 4:
        print("Usage: python3 git_helper.py <repo_url> <target_path> <sparse_path> [branch] [subfolder]")
        sys.exit(1)
    repo_url = sys.argv[1]
    target_path = sys.argv[2]
    sparse_path = sys.argv[3]
    branch = sys.argv[4] if len(sys.argv) > 4 else "main"
    subfolder = sys.argv[5] if len(sys.argv) > 5 else ""
    fetch_from_repo(repo_url, target_path, sparse_path, branch, subfolder)
