# 스모크 테스트: _log_response_details 동작 확인
# 이 스크립트는 실제 모듈 의존 없이 패치한 로직을 복제하여
# 3가지 케이스(500 비-JSON, 200 JSON, exception-with-response)를 검증합니다.

import json

class DummyLogger:
    def __init__(self):
        pass
    def debug(self, *args, **kwargs):
        print("DEBUG:", *args)
    def warning(self, *args, **kwargs):
        print("WARNING:", *args)
    def info(self, *args, **kwargs):
        print("INFO:", *args)
    def error(self, *args, **kwargs):
        print("ERROR:", *args)

class RespMock:
    def __init__(self, status_code, headers, text):
        self.status_code = status_code
        self.headers = headers
        self.text = text

class ObjWithResponse:
    def __init__(self, response):
        self.response = response

# 복제한 함수 (필요한 부분만)
def _log_response_details(self, obj, context: str = "response"):
    try:
        if obj is None:
            self.logger.debug(f"{context}: no response object")
            return

        # requests.Response 또는 response 속성이 있는 예외
        resp = None
        if hasattr(obj, "response"):
            resp = getattr(obj, "response")
        elif hasattr(obj, "getResponse"):
            try:
                resp = obj.getResponse()
            except Exception:
                resp = None
        elif hasattr(obj, "headers") and hasattr(obj, "text"):
            resp = obj

        if resp is not None:
            try:
                headers = dict(resp.headers) if hasattr(resp, "headers") else {}
            except Exception:
                headers = {}
            try:
                text = resp.text if hasattr(resp, "text") else str(resp)
            except Exception:
                text = str(resp)

            # 상태 코드 추출을 시도
            status_code = None
            try:
                status_code = getattr(resp, "status_code", None) or getattr(resp, "status", None)
            except Exception:
                status_code = None

            # JSON 파싱 시도
            parsed_json = None
            is_json = False
            try:
                if text is not None and isinstance(text, str) and text.strip():
                    parsed_json = json.loads(text)
                    is_json = True
            except Exception:
                parsed_json = None
                is_json = False

            payload = {
                "context": context,
                "type": "http",
                "http_status": status_code,
                "http_headers": headers,
                "http_body_truncated": (text[:5000] if text is not None else None),
                "http_body_is_json": is_json,
            }
            if is_json:
                payload["http_json"] = parsed_json

            try:
                self.logger.debug(f"{context} - HTTP headers: {headers}")
            except Exception:
                pass

            try:
                if status_code is not None and int(status_code) >= 500:
                    self.logger.warning(f"{context} - HTTP {status_code} body (truncated 5k): {text[:5000]}")
                else:
                    self.logger.debug(f"{context} - HTTP body (truncated 1k): {text[:1000]}")
            except Exception:
                pass

            try:
                self.logger.debug("structured_response", extra={"json_payload": payload})
            except Exception:
                try:
                    self.logger.debug(f"{context} - structured_response_payload: {str(payload)[:2000]}")
                except Exception:
                    pass

            if not is_json and status_code is not None and int(status_code) >= 500:
                try:
                    self.logger.warning(f"{context} - 비JSON 500 응답(원문 일부): {text[:2000]}")
                except Exception:
                    pass

            return

        # fallback
        try:
            self.logger.debug(f"{context} - {str(obj)[:1000]}")
        except Exception as ex:
            self.logger.debug(f"{context} - 상세 응답 로깅 실패: {ex}")
    except Exception as ex:
        self.logger.debug(f"{context} - 상세 응답 로깅 실패(최종): {ex}")


if __name__ == '__main__':
    logger = DummyLogger()
    self = type('S', (), {'logger': logger})()

    print('\n--- CASE 1: HTTP 500 HTML 비-JSON ---')
    resp1 = RespMock(500, {'Content-Type': 'text/html'}, '<html><body>Server Error</body></html>')
    _log_response_details(self, resp1, context='case1')

    print('\n--- CASE 2: HTTP 200 JSON ---')
    resp2 = RespMock(200, {'Content-Type': 'application/json'}, '{"ok": true, "data": [1,2,3]}')
    _log_response_details(self, resp2, context='case2')

    print('\n--- CASE 3: Exception with response (500) ---')
    resp3 = RespMock(500, {'Content-Type': 'text/plain'}, 'Internal Server Error: EGW00201')
    ex_obj = ObjWithResponse(resp3)
    _log_response_details(self, ex_obj, context='case3')
