# save_requests.py

import gzip
from io import BytesIO
import os
import uuid
import sys

# Base storage path
STORAGE_PATH = "storage"
CAPTURES_PATH = os.path.join(STORAGE_PATH, "captures")

# Ensure the captures path exists
if not os.path.exists(CAPTURES_PATH):
    os.makedirs(CAPTURES_PATH)

unique_id = sys.argv[-1]

captured_file_path = os.path.join(CAPTURES_PATH, f"captured_requests_{unique_id}.txt")
error_file_path = os.path.join(CAPTURES_PATH, f"errors_{unique_id}.txt")

# Ensure a clean start (overwrite if exists)
with open(captured_file_path, "w") as _: pass
with open(error_file_path, "w") as _: pass

def response(flow):
    try:
        if 'api/v5/vendors' in flow.request.url:

            with open(captured_file_path, "a", encoding='utf-8') as f:
                f.write("\n#####\n")
                f.write("URL: " + flow.request.url + "\n")
                headers_to_log = [
                    #"Content-Type",
                    #"Content-Length",
                    #"X-Frame-Options",
                    #"X-Content-Type-Options",
                    #"X-XSS-Protection",
                    #"Access-Control-Allow-Origin"
                ]

                for header in headers_to_log:
                    value = flow.response.headers.get(header, "N/A")
                    f.write(f"{header}: {value}\n")

                content_encoding = flow.response.headers.get("Content-Encoding", "")
                
                if "gzip" in content_encoding:
                    buffer = BytesIO(flow.response.content)
                    try:
                        with gzip.GzipFile(fileobj=buffer, mode="rb") as decompressed:
                            body = decompressed.read().decode('utf-8', 'ignore')
                            f.write("Response Body:\n" + body + "\n\n")
                    except:
                        f.write("Response Body:\n" + flow.response.text + "\n\n")
                else:
                    f.write("Response Body:\n" + flow.response.text + "\n\n")

    except Exception as e:
        with open(error_file_path, "a") as error_file:
            error_file.write(f"Error processing request to {flow.request.url}: {str(e)}\n")