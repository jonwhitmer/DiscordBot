import os

def scan_file_for_null_bytes(file_path):
    with open(file_path, 'rb') as file:
        content = file.read()
        if b'\x00' in content:
            return True
    return False

def scan_directory_for_null_bytes(directory):
    null_byte_files = []
    for root, dirs, files in os.walk(directory):
        for file in files:
            file_path = os.path.join(root, file)
            if scan_file_for_null_bytes(file_path):
                null_byte_files.append(file_path)
    return null_byte_files

if __name__ == "__main__":
    directory_to_scan = '.'  # Current directory
    null_byte_files = scan_directory_for_null_bytes(directory_to_scan)
    
    if null_byte_files:
        print("Files containing null bytes:")
        for file in null_byte_files:
            print(file)
    else:
        print("No files containing null bytes found.")
