"""Run with the API server up: python examples/python_client.py"""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.ralg_client import RALGClient

client = RALGClient()
print(client.health())
print(client.ready())
print(client.ingest("Synthetic pilot note: the inspection interval is 30 days.", "pilot-note"))
print(client.query("What is the inspection interval?"))
documents = client.documents()
print(documents)
if documents:
    print(client.delete(documents[-1]["document_id"]))

# Optional authenticated client example:
# client_auth = RALGClient(api_token="your-api-token")
# print(client_auth.query("Question?", document_ids=["doc_id_1"]))
