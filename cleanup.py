import os

def clean_dir(path:str):
    for file in os.listdir(path):
        curr_path = os.path.join(path,file)
        if os.path.isfile(curr_path):
            if file.endswith(("aux","fdb_latexmk","fls","idx","ilg","ind","log","out","synctex.gz","synctex(busy)","toc")):
                print(f"Removing file: {curr_path}")
                os.remove(curr_path)
        elif os.path.isdir(curr_path):
            clean_dir(curr_path)

if __name__ == "__main__":
    curr_path = os.path.dirname(os.path.abspath(__file__))
    clean_dir(curr_path)
    