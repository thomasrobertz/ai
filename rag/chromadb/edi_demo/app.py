from flask import Flask, request, Response, jsonify
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import chromadb
from chromadb.config import Settings, DEFAULT_TENANT, DEFAULT_DATABASE
from openai import OpenAI
import os
import html
from dotenv import load_dotenv
import logging
import re
import json
import nltk
from nltk.corpus import stopwords
from nltk.tokenize import word_tokenize
from sklearn.metrics.pairwise import cosine_similarity
import pandas as pd
import numpy as np

load_dotenv()
system_prompt = ""
english_stopwords = set()
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
limiter = Limiter(key_func=get_remote_address)
limiter.init_app(app)

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
code_pattern = r"code\s+(\d{4})"

# Store last context and query globally
last_context = None
last_query = None

def validate_input(user_input):
    if len(user_input) > 1000: 
        raise ValueError("Input too long.")
    if not all(ord(c) < 128 for c in user_input):
        raise ValueError("Invalid characters detected.")
    return html.escape(user_input)

def normalize_text(text):
    return re.findall(r'\b[\w.-]+\b', text.lower())

def highlight_context(context, query_words):
    def replacer(match):
        word = match.group()
        return f"<span style='background-color: #ffefbf'>{word}</span>" if word.lower() in query_words else word
    return re.sub(r'\b[\w.-]+\b', replacer, context)

def get_embedding(text, engine="text-embedding-ada-002"):
    """Fetch the embedding for a given text."""
    response = client.embeddings.create(
        input=text,
        model=engine
    )
    return response.data[0].embedding

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
@limiter.limit("15 per minute") 
def get_context():
    """Get RAG context data for a query with Top-K Aggregate Similarity."""
    try:
        global last_context, last_query

        user_query = request.json.get("query", "").strip()
        if not user_query:
            logging.warning("No query provided in request")
            return jsonify({"error": "Query is required"}), 400

        user_query = validate_input(user_query)

        # Apply code filter if query contains a code pattern
        code_filter = None
        code_match = re.search(code_pattern, user_query, re.IGNORECASE)
        if code_match:
            code_filter = {"code": {"$eq": code_match.group(1)}}

        try:
            context_results = collection.query(
                query_texts=[user_query],
                n_results=10,
                where=code_filter
            )
        except Exception as query_error:
            logging.error(f"Error querying collection: {query_error}")
            return jsonify({"error": "Error querying collection"}), 500

        # Retrieve and flatten grouped documents
        retrieved_contexts = [
            context for group in context_results.get("documents", []) for context in group
        ]
        if not retrieved_contexts:
            logging.warning("No documents retrieved from the collection")
            return jsonify({"similarities": [], "top_k_similarity": None})

        # Set the global context for chat functionality
        last_context = " ".join(retrieved_contexts)
        last_query = user_query

        # Generate embeddings
        query_embedding = get_embedding(user_query)
        context_embeddings = [get_embedding(context) for context in retrieved_contexts]

        # Compute similarities
        similarities = cosine_similarity([query_embedding], context_embeddings)[0]

        # Highlight query words for each context
        tokens = word_tokenize(user_query, language='english')
        filtered_query = [word for word in tokens if word.lower() not in english_stopwords]
        query_words = normalize_text(' '.join(filtered_query))

        similarity_results = [
            {
                "context": highlight_context(retrieved_contexts[i], set(query_words)),
                "similarity": float(similarities[i])
            }
            for i in range(len(retrieved_contexts))
        ]

        # Compute Top-K aggregate similarity
        top_k = 3
        if len(retrieved_contexts) <= 5:
            top_k = 2
        if len(retrieved_contexts) <= 3:
            top_k = 1
        top_indices = np.argsort(similarities)[-top_k:]  # Indices of top-K similar entries
        top_embeddings = [context_embeddings[i] for i in top_indices]
        top_mean_embedding = np.mean(top_embeddings, axis=0)
        top_k_similarity = float(cosine_similarity([query_embedding], [top_mean_embedding])[0][0])

        #logging.info(f"Retrieved Contexts: {retrieved_contexts}")
        #logging.info(f"Context Embeddings Count: {len(context_embeddings)}")
        #logging.info(f"Similarities: {similarities}")

        return jsonify({
            "similarities": similarity_results,
            "top_k_similarity": top_k_similarity
        })

    except Exception as e:
        logging.error(f"Error in get_context: {e}", exc_info=True)
        return jsonify({"error": "Internal server error"}), 500





@app.route('/query', methods=['POST'])
@limiter.limit("15 per minute") 
def query_collection():
    """Handle OpenAI streaming response."""
    try:
        global last_context, last_query
        
        user_query = request.json.get("query", "").strip()
        if not user_query or not last_context or user_query != last_query:
            logging.warning("Invalid query state")
            return jsonify({"error": "Please get context first"}), 400

        user_query = validate_input(user_query)

        response = Response(
            generate_response(last_context, user_query),
            content_type="text/event-stream",
            headers={
                'Cache-Control': 'no-cache',
                'X-Accel-Buffering': 'no',  # Disable Nginx buffering
                'Connection': 'keep-alive'
            }
        )
        return response

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

def download_nltk_data():
    required_packages = ['stopwords', 'punkt', 'punkt_tab']
    for package in required_packages:
        try:
            nltk.data.find(f'corpora/{package}' if package == 'stopwords' else f'tokenizers/{package}')
        except LookupError:
            print(f"Downloading {package}...")
            nltk.download(package)

if __name__ == '__main__':
    system_prompt = read_system_prompt()
    download_nltk_data()
    english_stopwords = set(stopwords.words('english'))
    app.run(debug=True)
