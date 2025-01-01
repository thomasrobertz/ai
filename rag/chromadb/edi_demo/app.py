from flask import Flask, request, Response, jsonify
from flask_cors import CORS
import chromadb
from chromadb.config import Settings, DEFAULT_TENANT, DEFAULT_DATABASE
from openai import OpenAI
import os
from dotenv import load_dotenv
import logging
import re

load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

chroma_client = chromadb.PersistentClient(
    path="chroma",
    settings=Settings(),
    tenant=DEFAULT_TENANT,
    database=DEFAULT_DATABASE
)

collection = chroma_client.get_or_create_collection("eded")

app = Flask(__name__)
CORS(app)

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
code_pattern = r"code\s+(\d{4})"

system_prompt = """You are a helpful assistant specialized in answering questions about EDI document specifications.
The request will contain a Context: and a Query: section.
"""

def dummy_response(context, user_query):
    """Generate an empty streaming response."""
    try:
        logging.info("Generating empty streaming response")
        def empty_stream():
            yield "data: \n\n"
        return empty_stream()
    except Exception as e:
        logging.error(f"Error generating response: {e}")
        def error_stream():
            yield f"data: Error: {str(e)}\n\n"
        return error_stream()

def generate_response(context, user_query):
    """Generate streaming response using OpenAI's API, with RAG data included."""
    try:
        logging.info("Starting OpenAI completion request")

        if context:
            logging.info(f"Streaming RAG context: {context}")
            yield f"data: {json.dumps({'rag_context': context})}\n\n"

        completion = client.chat.completions.create(
            model="gpt-4",
            max_tokens=150,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Context: {context}\n\nQuery: {user_query}"}
            ],
            stream=True
        )
        has_streamed_data = False

        for chunk in completion:
            logging.info(f"Received chunk: {chunk}")

            for choice in chunk.choices:
                if choice.delta.content:
                    content = choice.delta.content
                    logging.info(f"Streaming chunk content: {content}")
                    yield f"data: {json.dumps({'openai_response': content})}\n\n"
                    has_streamed_data = True

        if not has_streamed_data:
            logging.warning("No data streamed from OpenAI.")
            yield "data: {json.dumps({'error': 'No data received from OpenAI.'})}\n\n"
        logging.info("Completed streaming all chunks")

        yield "data: [DONE]\n\n"

    except Exception as e:
        logging.error(f"Error during OpenAI completion: {e}", exc_info=True)
        yield f"data: {json.dumps({'error': str(e)})}\n\n"

@app.route('/query', methods=['POST'])
def query_collection():
    """Handle user query and stream response."""
    try:
        logging.info("Received query request")
        user_query = request.json.get("query", "")
        if not user_query:
            logging.warning("No query provided in request")
            return jsonify({"error": "Query is required"}), 400

        logging.info(f"Query: {user_query}")

        code_filter = None
        code_match = re.search(code_pattern, user_query, re.IGNORECASE)

        if code_match:
            code_filter = {"code": {"$eq": code_match.group(1)}}

        context_results = collection.query(
            query_texts=[user_query],
            n_results=2,
            where=code_filter
        )
        context = " ".join([" ".join(doc) if isinstance(doc, list) else doc for doc in context_results["documents"]])
        logging.info(f"Retrieved context: {context}")

        return Response(generate_response(context, user_query), content_type="text/event-stream")
        #return Response(dummy_response(context, user_query), mimetype='text/event-stream')

    except Exception as e:
        logging.error(f"Error in query_collection: {e}", exc_info=True)
        return jsonify({"error": "Internal server error"}), 500

@app.errorhandler(500)
def handle_internal_server_error(e):
    # Log the error details
    app.logger.error(f"Internal Server Error: {e}")
    
    # Enrich the response
    response = {
        "error": "Internal server error",
        "message": "An unexpected error occurred. Please contact support if the issue persists.",
        "details": str(e)  # Include the exception details (optional, avoid in production)
    }
    return jsonify(response), 500

if __name__ == '__main__':
    app.run(debug=True)
