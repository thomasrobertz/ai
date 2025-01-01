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
import nltk
from nltk.corpus import stopwords
from nltk.tokenize import word_tokenize

load_dotenv()
system_prompt = ""
german_stopwords = set()
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

def dummy_response(context, user_query):
    """Generate an empty streaming response for debugging purposes."""
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
            #logging.info(f"Received chunk: {chunk}")

            for choice in chunk.choices:
                if choice.delta.content:
                    content = choice.delta.content
                    #logging.info(f"Streaming chunk content: {content}")
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
        
        # Validate query input
        user_query = request.json.get("query", "").strip()
        if not user_query:
            logging.warning("No query provided in request")
            return jsonify({"error": "Query is required"}), 400
        logging.info(f"Query: {user_query}")

        # Apply code filter if applicable
        code_filter = None
        code_match = re.search(code_pattern, user_query, re.IGNORECASE)
        if code_match:
            code_filter = {"code": {"$eq": code_match.group(1)}}

        # Query the collection
        try:
            context_results = collection.query(
                query_texts=[user_query],
                n_results=2,
                where=code_filter
            )
        except Exception as query_error:
            logging.error(f"Error querying collection: {query_error}")
            return jsonify({"error": "Error querying collection"}), 500

        # Retrieve context
        context = " ".join(
            [" ".join(doc) if isinstance(doc, list) else doc for doc in context_results.get("documents", [])]
        )
        logging.info(f"Retrieved context: {context}")
    
        # Filter German stopwords for matching keywords in retrieved context
        #tokens = word_tokenize(user_query, language='german')
        #filtered_query = [word for word in tokens if word.lower() not in german_stopwords]
        #logging.info(f"Filtered Query: {' '.join(filtered_query)}")
        
        # Highlight matched keywords in context
        #highlighted_context = ""
        #for token in filtered_query:
        #    highlighted_token = f"<span style='background-color: yellow;'>{token}</span>"
        #    highlighted_context += highlighted_token + " "

        # Stream response
        return Response(generate_response(context, user_query), content_type="text/event-stream")

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

def read_system_prompt(file_path="input/system_prompt.txt"):
    try:
        with open(file_path, "r", encoding="utf-8") as file:
            return file.read()
    except FileNotFoundError:
        raise FileNotFoundError(f"The file '{file_path}' was not found.")
    except IOError as e:
        raise IOError(f"An error occurred while reading the file '{file_path}': {e}")

def download_nltk_data():
    try:
        nltk.data.find('corpora/stopwords')
    except LookupError:
        print("Downloading stopwords...")
        nltk.download('stopwords')

    try:
        nltk.data.find('tokenizers/punkt')
    except LookupError:
        print("Downloading punkt tokenizer...")
        nltk.download('punkt')

    try:
        nltk.data.find('tokenizers/punkt_tab')
    except LookupError:
        print("Downloading punkt_tab tokenizer...")
        nltk.download('punkt_tab')

if __name__ == '__main__':
    system_prompt = read_system_prompt()
    #download_nltk_data()
    #german_stopwords = set(stopwords.words('german'))
    app.run(debug=True)
