import os
import requests

class OneDriveUploader:
    def __init__(self, data: dict, remote_path: list):
        self.tenant_id = data.get("tenant_id")
        self.client_id = data.get("client_id")
        self.client_secret = data.get("client_secret")
        self.user_id = data.get("user_id")

        self.access_token = self.get_access_token()

        self.remote_path = remote_path

    def get_access_token(self):
        # 获取访问令牌
        token_url = f"https://login.microsoftonline.com/{self.tenant_id}/oauth2/v2.0/token"

        token_data = {
            "grant_type": "client_credentials",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "scope": "https://graph.microsoft.com/.default"
        }

        token_response = requests.post(token_url, data = token_data)
        token_json = token_response.json()

        return token_json.get("access_token")

    def create_upload_session(self, remote_path: str):
        # 创建上传会话
        url = f"https://graph.microsoft.com/v1.0/users/{self.user_id}/drive/root:/{remote_path}:/createUploadSession"

        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json"
        }

        body = {
            "item": {
                "@microsoft.graph.conflictBehavior": "replace"
            }
        }

        resp = requests.post(url, headers = headers, json = body)

        if resp.status_code == 200:
            return resp.json()["uploadUrl"]
        else:
            print("创建上传会话失败：", resp.text)
            return None
    
    def upload_file_in_chunks(self, upload_url: str, file_path: str, chunk_size: int = 3276800):
        # 分块上传文件
        file_size = os.path.getsize(file_path)

        with open(file_path, "rb") as f:
            start = 0

            while start < file_size:
                end = min(start + chunk_size, file_size) - 1
                f.seek(start)
                chunk_data = f.read(end - start + 1)
                
                headers = {
                    "Content-Length": str(end - start + 1),
                    "Content-Range": f"bytes {start}-{end}/{file_size}"
                }

                resp = requests.put(upload_url, headers = headers, data = chunk_data)

                if resp.status_code in [200, 201]:
                    return resp.json()
                
                elif resp.status_code in [202]:
                    start = end + 1
                else:
                    print(f"上传失败：{file_path}, {resp.text}")
                    return None
                
        return None
    
    def create_share_link(self, item_id: str, link_type = "view"):
        # 创建共享链接
        url = f"https://graph.microsoft.com/v1.0/users/{self.user_id}/drive/items/{item_id}/createLink"
        
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json"
        }
        body = {"type": link_type, "scope": "anonymous"}
        resp = requests.post(url, headers = headers, json = body)

        try:
            resp_json = resp.json()

        except Exception:
            print("创建共享链接失败：无法解析响应")
            return None
        
        if resp.status_code in [200, 201] and "link" in resp_json:
            return resp_json["link"]["webUrl"]
    
        else:
            print(f"创建共享链接失败: {resp_json}")
            return None

    def upload_file(self, file_path: str):
        # 上传文件到指定路径
        remote_name = os.path.basename(file_path)

        remote_url_path = self.remote_path.copy()
        remote_url_path.append(remote_name)

        upload_url = self.create_upload_session("/".join(remote_url_path))

        result = self.upload_file_in_chunks(upload_url, file_path)

        return result

    def share_folder(self, remote_path: list):
        # 分享 remote_path 指定的文件夹
        folder_path = "/".join(remote_path)

        # 获取该文件夹的 item id
        url = f"https://graph.microsoft.com/v1.0/users/{self.user_id}/drive/root:/{folder_path}"
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json"
        }
        resp = requests.get(url, headers = headers)

        if resp.status_code in [200, 201]:
            resp_json = resp.json()
            item_id = resp_json.get("id")

            if item_id:
                return self.create_share_link(item_id, link_type = "view")
            
        print(f"获取文件夹ID失败: {resp.text}")
        return None

if __name__ == "__main__":
    version = os.getenv("VERSION")

    files_to_upload = [
        f"Bili23_Downloader-{version}-windows-x64.zip",
        f"Bili23_Downloader-{version}-windows-x64-setup.exe",
        f"Bili23_Downloader-{version}-linux-amd64.deb",
    ]

    # 设置上传的远程路径
    remote_path = os.getenv("REMOTE_PATH").split("/")

    # 读取仓库设置的 SECRET 环境变量
    user_data = {
        "tenant_id": os.getenv("TENANT_ID"),
        "client_id": os.getenv("CLIENT_ID"),
        "client_secret": os.getenv("CLIENT_SECRET"),
        "user_id": os.getenv("USER_ID")
    }

    uploader = OneDriveUploader(user_data, remote_path)

    for file_path in files_to_upload:
        print(f"上传中： {file_path}")
        result = uploader.upload_file(file_path)
        if result:
            print(f"上传成功: {file_path}")
        else:
            print(f"上传失败: {file_path}")

    # 上传完所有文件后，统一分享 remote_path 文件夹
    folder_share_url = uploader.share_folder(remote_path)
    if folder_share_url:
        print(f"文件夹共享链接: {folder_share_url}")
    else:
        print("文件夹共享失败")