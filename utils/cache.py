import os
from PIL import Image
import io
import json



class Cache:
    def __init__(self):
        self._db = {}

    def get(self, key):
        return self._db.get(key)

    def get_from_list(self, key, val):
        if val in self._db[key]:
            return val

    def rem(self, key):
        del self._db[key]

    def set(self, key, val):
        self._db[key] = val

    def append(self, key, val):
        if not self._db.get(key):
            self._db[key] = []
        self._db[key].append(val)

class JsonCache:
    def __init__(self):
        self.db = {}
        self.setup()

    def setup(self):
        for file in os.listdir("json"):
            name = file.split(".")[0]
            path = os.path.join("json", file)
            with open(path, 'r', encoding='utf8') as f:
                self.db[name] = json.load(f)


class FontCache:
    def __init__(self, path):
        self._db = {}
        self.path = path
        self.setup()

    # Adds the paths to the cache
    def setup(self):
        for file in os.listdir(self.path):
            ext = file.split(".")
            path = os.path.join(self.path, file)
            self._db[ext[0]] = path

    def get_font(self, key):
        return self._db.get(key)



class ImageCache:
    def __init__(self, path):
        self._db = {}
        self.path = path
        self.setup()

    def setup(self):

        # Start of path. Highest in hierarchy
        self.load(self.path, self._db)

    def load(self, path, cache):
        for file in os.listdir(path):

            # Divides the filename and filepath, unless it's a directory
            extended = file.split(".")

            # It is a directory
            if len(extended) == 1:
                cache[file] = {}
                self.load(os.path.join(path, file), cache[file])

            # It is a file
            else:
                filename = extended[0]

                # Store the image binary inside the cache
                cache[filename] = self.file_to_binary(os.path.join(path, file))

    # First gets the binary, then creates an image and returns it
    def get_image(self, *args):
        binary = self.get_image_binary(args)
        if not binary:
            return binary
        buf = io.BytesIO(binary)
        img = Image.open(buf)
        return img

    def get_image_binary(self, args):
        ptr = self._db
        # Goes through the tuple with arguments to fetch the binary
        for arg in args:
            try:
                ptr = ptr[arg]
            except KeyError:
                print("Image does not exist. Returning None")
                return None
        # returns the binary
        return ptr

    def file_to_binary(self, path):
        img = Image.open(path)
        extension = path.split(".")[1]
        buf = io.BytesIO()
        if extension == "gif":
            img.save(buf, 'gif', save_all=True, duration=1000, loop=0)
        else:
            img.save(buf, 'png')
        buf.seek(0)
        binary = buf.getvalue()
        buf.close()
        return binary

