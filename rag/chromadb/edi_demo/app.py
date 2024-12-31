from flask import Flask, request, Response, jsonify
from flask_cors import CORS
import chromadb
from chromadb.config import Settings, DEFAULT_TENANT, DEFAULT_DATABASE
import openai
from dotenv import load_dotenv

load_dotenv()
openai_api_key = os.getenv("OPENAI_API_KEY")

chroma_client = chromadb.PersistentClient(
    path="chroma",
    settings=Settings(),
    tenant=DEFAULT_TENANT,
    database=DEFAULT_DATABASE
)

collection = chroma_client.get_or_create_collection("eded")

#results = collection.query(
#    query_texts=["Query about Document identifier"],
#    n_results=2
#)
#print(results)

app = Flask(__name__)
CORS(app)

@app.route('/query', methods=['POST'])
def query_collection():
    user_query = request.json.get("query", "")
    results = collection.query(
        query_texts=[user_query],
        n_results=2
    )
    return jsonify(results)

if __name__ == '__main__':
    app.run(debug=True)