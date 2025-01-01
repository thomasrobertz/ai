from flask import Flask, request, Response, jsonify
from flask_cors import CORS
import chromadb
from chromadb.config import Settings, DEFAULT_TENANT, DEFAULT_DATABASE
from openai import OpenAI
import os
from dotenv import load_dotenv
import logging
import re
import json

load_dotenv()
system_prompt = ""
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

# Store last context and query globally
last_context = None
last_query = None

def normalize_text(text):
    return re.findall(r'\b[\w.-]+\b', text.lower())

def highlight_context(context, query_words):
    def replacer(match):
        word = match.group()
        return f"<span style='background-color: #ffefbf'>{word}</span>" if word.lower() in query_words else word
    return re.sub(r'\b[\w.-]+\b', replacer, context)

def dummy_response(context, user_query):
    """Generate an empty streaming response."""
    try:
        #logging.info("Generating empty streaming response")
        def empty_stream():
            yield "data: \n\n"
        return empty_stream()
    except Exception as e:
        logging.error(f"Error generating response: {e}")
        def error_stream():
            yield f"data: Error: {str(e)}\n\n"
        return error_stream()

def generate_response(context, user_query):
    """Generate streaming response using OpenAI's API."""
    try:
        completion = client.chat.completions.create(
            model="gpt-4",
            max_tokens=1000,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Context: {context}\n\nQuery: {user_query}"}
            ],
            stream=True
        )
        has_streamed_data = False

        for chunk in completion:
            for choice in chunk.choices:
                if choice.delta.content:
                    content = choice.delta.content
                    yield f"data: {json.dumps({'content': content})}\n\n"
                    has_streamed_data = True

        if not has_streamed_data:
            logging.warning("No data streamed from OpenAI.")
            yield f"data: {json.dumps({'error': 'No data received from OpenAI.'})}\n\n"
        
        yield "data: [DONE]\n\n"

    except Exception as e:
        logging.error(f"Error during OpenAI completion: {e}", exc_info=True)
        yield f"data: {json.dumps({'error': str(e)})}\n\n"

@app.route('/context', methods=['POST'])
def get_context():
    """Get RAG context for a query."""
    try:
        global last_context, last_query
        
        # Validate query input
        user_query = request.json.get("query", "").strip()
        if not user_query:
            logging.warning("No query provided in request")
            return jsonify({"error": "Query is required"}), 400

        # Apply code filter if applicable
        code_filter = None
        code_match = re.search(code_pattern, user_query, re.IGNORECASE)
        if code_match:
            code_filter = {"code": {"$eq": code_match.group(1)}}

        # Query the collection
        try:
            context_results = collection.query(
                query_texts=[user_query],
                n_results=10,
                where=code_filter
            )
        except Exception as query_error:
            logging.error(f"Error querying collection: {query_error}")
            return jsonify({"error": "Error querying collection"}), 500

        # Store context and query for later use
        last_context = " ".join([" ".join(doc) if isinstance(doc, list) else doc for doc in context_results.get("documents", [])])
        last_query = user_query

        # Return highlighted context
        user_query_split = normalize_text(user_query)
        highlighted_context = highlight_context(last_context, set(user_query_split))
        
        return jsonify({"context": highlighted_context})

    except Exception as e:
        logging.error(f"Error in get_context: {e}", exc_info=True)
        return jsonify({"error": "Internal server error"}), 500

@app.route('/query', methods=['POST'])
def query_collection():
    """Handle OpenAI streaming response."""
    try:
        global last_context, last_query
        
        # Validate query input
        user_query = request.json.get("query", "").strip()
        if not user_query or not last_context or user_query != last_query:
            logging.warning("Invalid query state")
            return jsonify({"error": "Please get context first"}), 400

        # Stream response
        return Response(generate_response(last_context, user_query), content_type="text/event-stream")

    except Exception as e:
        logging.error(f"Error in query_collection: {e}", exc_info=True)
        return jsonify({"error": "Internal server error"}), 500

@app.errorhandler(500)
def handle_internal_server_error(e):
    app.logger.error(f"Internal Server Error: {e}")
    response = {
        "error": "Internal server error",
        "message": "An unexpected error occurred. Please contact support if the issue persists.",
        "details": str(e)  # Include the exception details (optional, avoid in production)
    }
    return jsonify(response), 500

def read_system_prompt(file_path="input/system_prompt.txt"):
    try:
        with open(file_path, "r", encoding="utf-8") as file:
            return file.read()
    except FileNotFoundError:
        raise FileNotFoundError(f"The file '{file_path}' was not found.")
    except IOError as e:
        raise IOError(f"An error occurred while reading the file '{file_path}': {e}")

if __name__ == '__main__':
    system_prompt = read_system_prompt()
    app.run(debug=True)
