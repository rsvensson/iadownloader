import os
import requests
import threading
import time
from datetime import datetime
from queue import Queue
from tqdm import tqdm


# Graciously stolen and adapted from Anurag Uniyal @ https://stackoverflow.com/a/18883984

class DownloadThread(threading.Thread):
    def __init__(self, queue: Queue, output_dir: str):
        super(DownloadThread, self).__init__()
        self.queue = queue
        self.output_dir = output_dir
        self.daemon = True

    def run(self):
        while True:
            url = self.queue.get()
            try:
                self.download_url(url)
            except Exception as e:
                print(f"Error: {e}")
            self.queue.task_done()

    def _get_mtime_from_str(self, last_mod: str):
        try:
            mod_date = datetime.strptime(last_mod, "%a, %d %b %Y %H:%M:%S %Z").timetuple()
            return int(time.mktime(mod_date))
        except TypeError:
            return int(time.mktime(datetime.now().timetuple()))

    def download_url(self, url: str):
        filename = requests.utils.unquote(url.split("/")[-1])
        compressed = False
        if url.find("/compress/") != -1:
            # User requested the compressed archive
            filename += ".zip"
            compressed = True
        dlpath = os.path.join(self.output_dir, filename)

        # Handle resuming a download
        resume_pos = 0
        if os.path.exists(dlpath):
            with requests.get(url, stream=True, allow_redirects=True) as r:
                local_size = os.path.getsize(dlpath)
                remote_size = int(r.headers.get("content-length", 0))
                if not compressed:
                    # The compressed archive's mtime is created at the time of download
                    local_time = int(os.path.getmtime(dlpath))
                    remote_time = self._get_mtime_from_str(r.headers.get("last-modified"))
                    if local_time == remote_time and local_size > 0:
                        print(f"{filename} already downloaded. Skipping.\n")
                        return
                else:
                    if local_size == remote_size and local_size > 0:
                        print(f"{filename} already downloaded. Skipping.\n")
                        return
                resume_pos = local_size

        if resume_pos > 0:
            print(f"Resuming download at {resume_pos} bytes.")
        with requests.get(url, stream=True, allow_redirects=True,
                          headers={"Range": f"bytes={resume_pos}-"}) as r:
            r.raise_for_status()
            total_size = int(r.headers.get("content-length", 0))
            block_size = 8192
            progress_bar = tqdm(total=total_size, unit='iB', unit_scale=True)
            progress_bar.set_description(filename)  # Prefix filename to output
            mod_time = self._get_mtime_from_str(r.headers.get("last-modified"))
            mode = "wb" if resume_pos == 0 else "ab"
            with open(dlpath, mode) as fd:
                for block in r.iter_content(block_size):
                    progress_bar.update(len(block))
                    fd.write(block)
            progress_bar.close()
        # Set last modified time
        os.utime(dlpath, (mod_time, mod_time))
