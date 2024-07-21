import os

def generate_directory_tree(directory, exceptions):
    tree = []
    for root, dirs, files in os.walk(directory):
        relative_root = os.path.relpath(root, directory)
        # Check if the current root is in the exceptions list or is a .git directory
        if any(os.path.commonpath([relative_root, exception]) == exception for exception in exceptions) or '.git' in relative_root:
            continue
        level = root.replace(directory, '').count(os.sep)
        indent = ' ' * 4 * (level)
        tree.append(f"{indent}{os.path.basename(root)}/")
        subindent = ' ' * 4 * (level + 1)
        for file in files:
            file_relative_path = os.path.join(relative_root, file)
            # Check if the file is in the exceptions list or is a git-related file
            if not any(os.path.commonpath([file_relative_path, exception]) == exception for exception in exceptions) and '.git' not in file_relative_path:
                if any(file.endswith(ext) for ext in ['.py', '.env']):
                    tree.append(f"{subindent}{file}")
    return tree

def generate_summary(directory, exceptions, include_extensions):
    summary = []
    for root, dirs, files in os.walk(directory):
        relative_root = os.path.relpath(root, directory)
        # Check if the current root is in the exceptions list or is a .git directory
        if any(os.path.commonpath([relative_root, exception]) == exception for exception in exceptions) or '.git' in relative_root:
            continue
        for file in files:
            file_relative_path = os.path.join(relative_root, file)
            # Check if the file is in the exceptions list, has an allowed extension, or is a git-related file
            if not any(os.path.commonpath([file_relative_path, exception]) == exception for exception in exceptions) and '.git' not in file_relative_path:
                if any(file.endswith(ext) for ext in include_extensions):
                    file_path = os.path.join(root, file)
                    summary.append(file_path)
    return summary

def read_and_prepend_file(file_path):
    with open(file_path, 'r', encoding='utf-8', errors='ignore') as file:
        content = file.read()
    return f"{file_path}\n{content}"

if __name__ == "__main__":
    exceptions = [
        os.path.normpath('extensions/gulp'),
        os.path.normpath('assets/instance/database.db'),
        os.path.normpath('assets/migrations')
    ]  # Add more directories to this list if needed
    include_extensions = [
        '.py'
    ]  # Only include .py files for content
    with open('project_summary.txt', 'w', encoding='utf-8') as f:
        # Write directory tree
        directory_tree = generate_directory_tree('.', exceptions)
        for line in directory_tree:
            f.write(line + '\n')

        f.write('\n\n')  # Separate the directory tree from the file contents

        # Write file contents
        summary = generate_summary('.', exceptions, include_extensions)
        for file_path in summary:
            file_content = read_and_prepend_file(file_path)
            f.write(file_content + '\n\n')
