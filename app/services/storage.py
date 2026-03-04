import os
import shutil
import json


class StorageService:
    def __init__(self, app=None):
        self.mode = "local"
        if app:
            self.init_app(app)

    def init_app(self, app):
        self.mode = os.getenv("STORAGE_TYPE", "local")
        self.base_path = os.path.join(os.getcwd(), 'data')
        
        # Supabase Config
        self.supabase_url = os.getenv("SUPABASE_URL")
        self.supabase_key = os.getenv("SUPABASE_KEY")
        self.bucket = "gate_papers"
        
        if self.mode == "supabase":
            if not (self.supabase_url and self.supabase_key):
                 print("[Storage Error] STORAGE_TYPE=supabase but credentials missing!")
                 # Raise error to prevent silent failure in production
                 raise ValueError("Missing SUPABASE_URL or SUPABASE_KEY env vars")
            
            from supabase import create_client
            self.client = create_client(self.supabase_url, self.supabase_key)
            print("[Storage] Initialized Supabase Storage")
        else:
            self.mode = "local"
            # Ensure local dirs
            os.makedirs(os.path.join(self.base_path, 'live'), exist_ok=True)
            os.makedirs(os.path.join(self.base_path, 'staging'), exist_ok=True)
            print("[Storage] Initialized Local Storage")

    def _get_local_path(self, path):
        # path e.g. "live/2025/CS/answer_key.pdf"
        return os.path.join(self.base_path, path)

    def save(self, path, data_bytes, content_type="application/pdf"):
        if self.mode == "local":
            full_path = self._get_local_path(path)
            os.makedirs(os.path.dirname(full_path), exist_ok=True)
            with open(full_path, "wb") as f:
                f.write(data_bytes)
            return full_path
        else:
            # Supabase Upload
            try:
                self.client.storage.from_(self.bucket).upload(
                    path=path,
                    file=data_bytes,
                    file_options={"content-type": content_type, "upsert": "true"}
                )
                return self.client.storage.from_(self.bucket).get_public_url(path)
            except Exception as e:
                print(f"[Storage Error] Save failed: {e}")
                raise e

    def read(self, path):
        """Returns bytes"""
        if self.mode == "local":
            full_path = self._get_local_path(path)
            if not os.path.exists(full_path):
                return None
            with open(full_path, "rb") as f:
                return f.read()
        else:
            try:
                res = self.client.storage.from_(self.bucket).download(path)
                return res
            except Exception as e:
                print(f"[Storage Error] Read failed: {e}")
                return None
    
    def exists(self, path):
        if self.mode == "local":
            return os.path.exists(self._get_local_path(path))
        else:
            # List files in dir and check match
            # path: live/2025/CS/schema.json
            directory = os.path.dirname(path)
            filename = os.path.basename(path)
            try:
                files = self.client.storage.from_(self.bucket).list(directory)
                for f in files:
                    if f['name'] == filename:
                        return True
                return False
            except:
                return False

    def list(self, directory):
        """Returns list of item names (folders/files)"""
        if self.mode == "local":
            full_dir = self._get_local_path(directory)
            if not os.path.exists(full_dir):
                return []
            return os.listdir(full_dir)
        else:
            try:
                # storage list returns dicts
                res = self.client.storage.from_(self.bucket).list(directory)
                return [x['name'] for x in res]
            except Exception as e:
                print(f"[Storage Error] List failed for {directory}: {e}")
                return []
    
    def move(self, src, dst):
        """Moves file or directory"""
        if self.mode == "local":
            full_src = self._get_local_path(src)
            full_dst = self._get_local_path(dst)
            if os.path.exists(full_dst):
                shutil.rmtree(full_dst)
            os.makedirs(os.path.dirname(full_dst), exist_ok=True)
            shutil.move(full_src, full_dst)
        else:
            # Supabase Move (Recursive for directories)
            try:
                items = self.list(src)
                
                if not items:
                    # Maybe it's a single file? Try direct move
                    self.client.storage.from_(self.bucket).move(src, dst)
                    return
                
                # It's a directory, move children
                for item in items:
                    old_path = f"{src}/{item}"
                    new_path = f"{dst}/{item}"
                    try:
                        self.client.storage.from_(self.bucket).move(old_path, new_path)
                    except Exception as ex:
                        print(f"[Storage Error] Failed to move {old_path}: {ex}")

            except Exception as e:
                print(f"[Storage Error] Move failed: {e}")

    def delete(self, path):
        if self.mode == "local":
            full_path = self._get_local_path(path)
            if os.path.isdir(full_path):
                shutil.rmtree(full_path)
            elif os.path.exists(full_path):
                os.remove(full_path)
        else:
            # Supabase Delete (Recursive)
            try:
                # 1. Try list (for folder)
                items = self.list(path)
                if items:
                    # Delete all files in folder
                    files_to_remove = [f"{path}/{x}" for x in items]
                    self.client.storage.from_(self.bucket).remove(files_to_remove)
                else:
                    # 2. Try single file
                    self.client.storage.from_(self.bucket).remove([path])
            except Exception as e:
                print(f"[Storage Error] Delete failed: {e}")

    def save_json(self, path, data):
        json_bytes = json.dumps(data, indent=4).encode('utf-8')
        return self.save(path, json_bytes, "application/json")

    def read_json(self, path):
        data_bytes = self.read(path)
        if data_bytes:
            return json.loads(data_bytes)
        return None
