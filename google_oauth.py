import sys
import webbrowser
import requests
from urllib.parse import urlparse, parse_qs
from http.server import HTTPServer, BaseHTTPRequestHandler
from threading import Thread

# 실제 발급받은 값
CLIENT_ID = "44798885024-pf7otl5hsn6a0am4cagg1dlcssr5b6ng.apps.googleusercontent.com"
CLIENT_SECRET = "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"
REDIRECT_URI = "http://localhost"  # 반드시 Google Cloud Console의 값과 일치!
SCOPE = "openid email profile"

class OAuthHandler(BaseHTTPRequestHandler):
    code = None
    def do_GET(self):
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)
        if "code" in params:
            OAuthHandler.code = params["code"][0]
            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            self.wfile.write("<h1>인증이 완료되었습니다. 창을 닫으세요.</h1>".encode("utf-8"))
        else:
            self.send_response(400)
            self.end_headers()

def start_server():
    httpd = HTTPServer(("localhost", 80), OAuthHandler)  # 포트 80 사용
    httpd.handle_request()  # 한 번만 처리

def get_auth_code():
    auth_url = (
        "https://accounts.google.com/o/oauth2/v2/auth?"
        f"client_id={CLIENT_ID}&"
        f"redirect_uri={REDIRECT_URI}&"
        f"response_type=code&"
        f"scope={SCOPE}&"
        "access_type=offline"
    )
    Thread(target=start_server, daemon=True).start()
    webbrowser.open(auth_url)
    print("브라우저에서 인증 후, 이 창으로 돌아오세요...")

    while OAuthHandler.code is None:
        pass
    return OAuthHandler.code

def get_tokens(code):
    token_url = "https://oauth2.googleapis.com/token"
    data = {
        "code": code,
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "redirect_uri": REDIRECT_URI,
        "grant_type": "authorization_code"
    }
    response = requests.post(token_url, data=data)
    return response.json()

def get_userinfo(access_token):
    userinfo_url = "https://www.googleapis.com/oauth2/v2/userinfo"
    headers = {"Authorization": f"Bearer {access_token}"}
    response = requests.get(userinfo_url, headers=headers)
    return response.json()

if __name__ == "__main__":
    code = get_auth_code()
    print("인증 코드:", code)
    tokens = get_tokens(code)
    print("토큰:", tokens)
    userinfo = get_userinfo(tokens["access_token"])
    print("사용자 정보:", userinfo) 