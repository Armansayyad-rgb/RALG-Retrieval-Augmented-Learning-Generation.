"""Tiny dependency-light Python client for the local RALG API."""
from __future__ import annotations
import json
from urllib.request import Request, urlopen

class RALGClient:
    def __init__(self, base_url="http://127.0.0.1:8000", timeout=30):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
    def _post(self, path, payload):
        req = Request(self.base_url + path, data=json.dumps(payload).encode(), headers={"Content-Type":"application/json"})
        with urlopen(req, timeout=self.timeout) as response:
            return json.loads(response.read().decode())

    def _request(self, method, path, payload=None):
        data = None if payload is None else json.dumps(payload).encode()
        headers = {} if payload is None else {"Content-Type": "application/json"}
        req = Request(self.base_url + path, data=data, headers=headers, method=method)
        with urlopen(req, timeout=self.timeout) as response:
            return json.loads(response.read().decode())

    def health(self):
        return self._request("GET", "/health")

    def ready(self):
        return self._request("GET", "/ready")

    def stats(self):
        return self._request("GET", "/stats")

    def documents(self):
        return self._request("GET", "/documents")
    def query(self, question, top_k=5, include_sources=True):
        return self._post("/query", {"question": question, "top_k": top_k, "include_sources": include_sources})
    def ingest(self, text, document_name=None):
        payload = {"text": text}
        if document_name: payload["document_name"] = document_name
        return self._post("/ingest", payload)

    def delete(self, document_id):
        return self._request("DELETE", "/documents/" + str(document_id))
