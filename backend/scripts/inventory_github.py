import json
import sys
import os

# Ensure the repository backend folder is on sys.path so `app` imports resolve
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.github_service import GitHubService


def main():
    gh = GitHubService()
    repo = gh._get_repo()
    base = gh._base_branch

    def walk(path):
        try:
            items = repo.get_contents(path, ref=base)
        except Exception as e:
            print(json.dumps({"error": str(e)}))
            return []
        out = []
        for it in items:
            out.append({"path": it.path, "type": it.type})
            if it.type == 'dir':
                out.extend(walk(it.path))
        return out

    items = walk("")
    locals_files = [i for i in items if i['path'].endswith('locals.tf')]
    glue_files = [i for i in items if i['path'].endswith('glue.tf')]
    terraform_like_dirs = sorted(set(p.split('/')[0] for p in items if '/' in p))
    root_dirs = [i['path'] for i in items if '/' not in i['path']]

    print(json.dumps({
        'root_dirs': root_dirs,
        'terraform_like_dirs': terraform_like_dirs,
        'locals_files': locals_files,
        'glue_files': glue_files,
    }, indent=2))

    # Use git tree API (recursive) for a full listing
    try:
        tree = repo.get_git_tree(base, recursive=True).tree
        all_paths = [t.path for t in tree]
        locals_files = [p for p in all_paths if p.endswith('locals.tf')]
        glue_files = [p for p in all_paths if p.endswith('glue.tf')]
        terraform_like_dirs = sorted(set(p.split('/')[0] for p in all_paths if '/' in p))
        print('\nRECURSIVE TREE SUMMARY:\n')
        print(json.dumps({
            'total_paths': len(all_paths),
            'terraform_like_dirs_sample': terraform_like_dirs[:200],
            'locals_files': locals_files,
            'glue_files': glue_files,
        }, indent=2))
    except Exception as e:
        print('Could not fetch recursive git tree:', e)


if __name__ == '__main__':
    main()
