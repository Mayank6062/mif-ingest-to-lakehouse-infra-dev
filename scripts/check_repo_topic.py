from app.config import get_settings
from github import Github, GithubException

settings = get_settings()
owner = settings.github_repo_owner
repo_name = settings.github_repo_name
branch = settings.github_base_branch

def check_topic(source_system, schema_grain):
    topic_file = f"confluent_minerva_dev/topics_{source_system}.tf"
    print("source_system:", source_system)
    print("schema_grain:", schema_grain)
    print("repo_owner:", owner)
    print("repo_name:", repo_name)
    print("branch_name:", branch)
    print("resolved_path:", topic_file)
    try:
        gh = Github(settings.github_token.get_secret_value())
        repo = gh.get_repo(f"{owner}/{repo_name}")
        try:
            contents = repo.get_contents(topic_file, ref=branch)
            print("repository_file_found: True")
            print("file_size:", getattr(contents, 'size', None))
        except GithubException as e:
            print("repository_file_found: False")
            print("github_exception:", e)
    except Exception as e:
        print("github_client_error:", e)

if __name__ == '__main__':
    # Values for the test: dev.saptcc.multi-1.raw => saptcc, multi-1
    check_topic('saptcc', 'multi-1')
